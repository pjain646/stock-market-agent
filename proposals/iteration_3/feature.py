"""Iteration 3 signal: fundamental earnings ACCELERATION (freshness-decayed).

Economic mechanism -- distinct from iteration 2's PEAD:
  PEAD measured the earnings *surprise* vs. the analyst consensus. This signal
  measures a firm's surprise vs. *its own recent trend*: the change in its
  year-over-year single-quarter net-income growth rate from one quarter to the
  next (i.e. earnings acceleration / the second derivative of fundamentals).

  Investors anchor on a company's established growth trajectory and are slow to
  update when that trajectory INFLECTS. The *level* of growth is largely priced
  in (a mega-cap that reliably grows ~15% is expected to), and indeed shows no
  edge on the training slice; what carries information is the *change* in the
  growth rate -- an acceleration says the business just entered a better regime
  than the market had extrapolated, and that re-rating diffuses over weeks. So a
  freshness-decayed earnings-acceleration term should be positively related to
  the next 21-day move.

  On the training slice this construction shows a positive rank correlation with
  direction (Spearman ~+0.02; top vs. bottom decile up-rate ~0.63 vs ~0.58 and
  positive-acceleration up-rate ~0.62 vs ~0.60 for deceleration), whereas the
  raw growth *level* was flat/negative -- consistent with the mechanism.

  Orthogonal to price momentum (iters 0-1, which failed) and to surprise-based
  PEAD (iter 2, which worked): a firm can grow strongly yet decelerate, or shrink
  less than before and thus accelerate. Built from SEC EDGAR filings (point-in-
  time by filed_date), avoiding rate-limited analyst endpoints.
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

from data import fetch_fundamentals  # noqa: E402

SIGNAL_NAME = "fund_earn_accel_yoy"
HYPOTHESIS = (
    "Investors anchor on a firm's established growth trajectory and update slowly "
    "when it inflects; the change in a firm's YoY single-quarter net-income "
    "growth rate (earnings acceleration) therefore signals a fundamental regime "
    "shift the market re-rates over weeks, so a freshness-decayed acceleration "
    "term should be positively related to the next 21-day return."
)

# PEAD-style freshness window: fundamental information is "fresh" for ~1 quarter.
_DECAY_DAYS = 90.0
# Clip growth to tame lumpy quarters (loss->profit swings, one-off charges).
_GROWTH_CLIP = 2.0


def _quarterly_ni(tickers):
    """First-disclosure single-quarter net income per (ticker, quarter).

    Returns DataFrame [ticker, period_end, filed_date, value] where value is the
    single-quarter (≈90-day) NetIncomeLoss and filed_date is the EARLIEST date
    that quarter's figure became public (point-in-time correct: a later 10-K that
    restates the same quarter cannot leak backward).
    """
    fund = fetch_fundamentals(list(tickers), concepts=["NetIncomeLoss"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "period_end", "filed_date", "value"])

    fund = fund.dropna(subset=["period_start", "period_end", "filed_date", "value"]).copy()
    dur = (fund["period_end"] - fund["period_start"]).dt.days
    q = fund[(dur >= 80) & (dur <= 100)].copy()  # single fiscal quarter only
    if q.empty:
        return pd.DataFrame(columns=["ticker", "period_end", "filed_date", "value"])

    # Earliest filing for each fiscal quarter = first public disclosure.
    q = q.sort_values(["ticker", "period_end", "filed_date"])
    first = q.groupby(["ticker", "period_end"], as_index=False).first()
    return first[["ticker", "period_end", "filed_date", "value"]]


def _accel_table(tickers):
    """Per-quarter earnings acceleration, stamped with its disclosure date.

    growth_t = (NI_t - NI_{t-1yr}) / (|NI_{t-1yr}| + eps), clipped; then
    accel_t = growth_t - growth_{t-1quarter} (change in the YoY growth rate),
    clipped. The as-of date is the CURRENT quarter's filed_date (every figure it
    depends on -- this quarter, a year ago, and the prior quarter -- is already
    public by then), so it is safe to use from filed_date onward.
    """
    q = _quarterly_ni(tickers)
    if q.empty:
        return pd.DataFrame(columns=["ticker", "filed_date", "accel"])

    rows = []
    eps = 1.0  # dollars; guards div-by-zero, negligible vs. mega-cap NI (billions)
    for tkr, grp in q.groupby("ticker"):
        grp = grp.sort_values("period_end").reset_index(drop=True)
        # Match each quarter to the one ~1 year earlier (±25 days tolerance).
        cur = grp[["period_end", "value", "filed_date"]].rename(
            columns={"value": "ni_now", "filed_date": "filed_now"}
        )
        prior = grp[["period_end", "value"]].rename(columns={"value": "ni_prior"}).copy()
        cur_key = cur.copy()
        cur_key["match_end"] = cur_key["period_end"] - pd.Timedelta(days=365)
        cur_key = cur_key.sort_values("match_end")
        prior = prior.sort_values("period_end")
        merged = pd.merge_asof(
            cur_key,
            prior,
            left_on="match_end",
            right_on="period_end",
            direction="nearest",
            tolerance=pd.Timedelta(days=25),
            suffixes=("", "_p"),
        )
        for _, r in merged.iterrows():
            if pd.isna(r["ni_prior"]):
                continue
            g = (r["ni_now"] - r["ni_prior"]) / (abs(r["ni_prior"]) + eps)
            g = float(np.clip(g, -_GROWTH_CLIP, _GROWTH_CLIP))
            rows.append({
                "ticker": tkr,
                "period_end": r["period_end"],
                "filed_date": r["filed_now"],
                "growth": g,
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["ticker", "filed_date", "accel"])
    # Acceleration = change in the YoY growth rate vs. the prior fiscal quarter.
    out = out.sort_values(["ticker", "period_end"]).reset_index(drop=True)
    out["accel"] = out.groupby("ticker")["growth"].diff()
    out = out.dropna(subset=["accel"])
    out["accel"] = out["accel"].clip(-_GROWTH_CLIP, _GROWTH_CLIP)
    return out.sort_values(["ticker", "filed_date"])[
        ["ticker", "filed_date", "accel"]
    ].reset_index(drop=True)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")

    accel_tbl = _accel_table(panel["ticker"].unique())
    if not accel_tbl.empty:
        accel_tbl["filed_date"] = accel_tbl["filed_date"].astype("datetime64[ns]")

    col = SIGNAL_NAME
    if accel_tbl.empty:
        panel[col] = 0.0
        return panel, [col]

    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    parts = []
    for tkr, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date")
        g = accel_tbl[accel_tbl["ticker"] == tkr]
        if g.empty:
            grp[col] = 0.0
            parts.append(grp)
            continue
        # Attach the most recent filing STRICTLY before each panel date (the value
        # is actionable at that day's open, never the same-day filing).
        merged = pd.merge_asof(
            grp[["date"]].reset_index(),
            g[["filed_date", "accel"]].rename(columns={"filed_date": "date"}),
            on="date",
            direction="backward",
            allow_exact_matches=False,
        ).set_index("index")
        days_since = (grp["date"].values - merged["date"].values) / np.timedelta64(1, "D")
        weight = np.clip(1.0 - days_since / _DECAY_DAYS, 0.0, 1.0)
        signal = merged["accel"].values * weight
        signal = np.where(np.isnan(signal), 0.0, signal)
        grp[col] = signal
        parts.append(grp)

    result = pd.concat(parts).sort_index()
    return result, [col]
