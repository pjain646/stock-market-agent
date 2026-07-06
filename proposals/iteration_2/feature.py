"""Iteration 2 signal: post-earnings-announcement drift (PEAD).

Economic mechanism: investors systematically UNDER-react to earnings news.
After a positive earnings surprise, prices drift up (and after a negative
surprise, drift down) for several weeks as the information is slowly absorbed
— one of the most robust, longest-surviving anomalies (Ball & Brown 1968;
Bernard & Thomas 1989). We measure the surprise as a standardized unexpected
earnings (SUE) score — the latest EPS surprise scaled by the stock's own
trailing volatility of surprises — and let it decay over the ~1-quarter drift
window. Prior iterations tested only price paths (momentum, mean-reversion);
this uses fundamental surprise information, an orthogonal driver.
"""

import sys
import os

import numpy as np
import pandas as pd

_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "research-methodology", "scripts",
)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from data import fetch_earnings  # noqa: E402

SIGNAL_NAME = "pead_sue_decayed"
HYPOTHESIS = (
    "Markets under-react to earnings surprises, so a stock's most recent "
    "standardized unexpected earnings (SUE) keeps predicting direction for "
    "roughly a quarter after the announcement; a recency-decayed SUE should be "
    "positively related to the next 21-day return."
)

# Drift window: PEAD is concentrated in the ~60-90 calendar days post-announcement.
_DECAY_DAYS = 90.0


def _compute_sue_table(tickers):
    """Per-announcement standardized unexpected earnings, point-in-time safe.

    Returns DataFrame [ticker, ann_date, sue] where sue for an announcement is
    that announcement's eps_surprise divided by the trailing std of the stock's
    PRIOR eps_surprises (so only past data feeds the normalization).
    """
    earn = fetch_earnings(list(tickers))
    if earn.empty:
        return pd.DataFrame(columns=["ticker", "ann_date", "sue"])

    earn = earn.dropna(subset=["eps_surprise"]).copy()
    earn["date"] = pd.to_datetime(earn["date"])
    earn = earn.sort_values(["ticker", "date"]).reset_index(drop=True)

    rows = []
    for tkr, grp in earn.groupby("ticker"):
        grp = grp.sort_values("date")
        surp = grp["eps_surprise"].astype(float)
        # Trailing std of PRIOR surprises (shifted so current row excluded),
        # min 4 observations; expanding window for stability.
        trailing_std = surp.shift(1).expanding(min_periods=4).std()
        sue = surp / trailing_std.replace(0.0, np.nan)
        for d, s in zip(grp["date"].values, sue.values):
            if pd.notna(s):
                rows.append({"ticker": tkr, "ann_date": pd.Timestamp(d), "sue": float(s)})
    out = pd.DataFrame(rows)
    # Clip extreme SUE to limit single-print outlier influence.
    if not out.empty:
        out["sue"] = out["sue"].clip(-8.0, 8.0)
    return out


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    sue_tbl = _compute_sue_table(panel["ticker"].unique())

    col = SIGNAL_NAME
    if sue_tbl.empty:
        panel[col] = 0.0
        return panel, [col]

    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    sue_tbl = sue_tbl.sort_values(["ticker", "ann_date"]).reset_index(drop=True)

    parts = []
    for tkr, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date")
        anns = sue_tbl[sue_tbl["ticker"] == tkr]
        if anns.empty:
            grp[col] = 0.0
            parts.append(grp)
            continue
        # For each panel date, attach the most recent announcement STRICTLY before
        # that date (allow_exact_matches=False -> same-day announcement not used,
        # making the value actionable at that day's open).
        merged = pd.merge_asof(
            grp[["date"]].reset_index(),
            anns[["ann_date", "sue"]].rename(columns={"ann_date": "date"}),
            on="date",
            direction="backward",
            allow_exact_matches=False,
        ).set_index("index")
        days_since = (grp["date"].values - merged["date"].values) / np.timedelta64(1, "D")
        weight = np.clip(1.0 - days_since / _DECAY_DAYS, 0.0, 1.0)
        signal = merged["sue"].values * weight
        signal = np.where(np.isnan(signal), 0.0, signal)
        grp[col] = signal
        parts.append(grp)

    result = pd.concat(parts).sort_index()
    return result, [col]
