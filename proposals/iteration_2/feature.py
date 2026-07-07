"""Iteration 2 signal: Post-Earnings-Announcement Drift (PEAD).

Economic rationale
------------------
When a company reports EPS that beats (or misses) the consensus estimate, its
price does NOT fully re-rate on the announcement day. Investors under-react to
the earnings news, so the stock keeps drifting in the direction of the surprise
for several weeks — the classic PEAD anomaly (Ball & Brown 1968; Bernard &
Thomas 1989). A 21-trading-day forward horizon sits squarely inside the
documented drift window. This is orthogonal to price momentum (iteration 1):
the catalyst is a discrete fundamental event, not trailing price.

Point-in-time discipline
-------------------------
- Earnings surprises are used ONLY from reports whose announcement date is
  STRICTLY BEFORE the panel row's date (merge_asof backward, exact matches
  disallowed). A report on trading day t is therefore not actionable until t+1,
  which is conservative regardless of whether the firm reported pre-open or
  post-close.
- The SUE denominator (rolling std of surprises) uses only PRIOR reports
  (shifted by one), never the current one.
- When the last report is stale (>63 calendar days, i.e. the drift has faded
  into the next quarter's silence) the signal decays to ~0 = "no fresh
  catalyst / neutral", the natural baseline.
"""
from __future__ import annotations

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "research-methodology", "scripts"))
from data import fetch_earnings  # noqa: E402


SIGNAL_NAME = "pead_earnings_surprise"
HYPOTHESIS = (
    "Investors under-react to earnings surprises, so a stock's price keeps "
    "drifting in the direction of its most recent EPS surprise for weeks after "
    "the report (post-earnings-announcement drift). A positive standardized "
    "surprise therefore predicts a higher chance of a positive 21-day return, "
    "with the effect decaying as the announcement recedes."
)

# One fiscal quarter ~ 63 trading days ~ 92 calendar days; past that the drift
# has faded and the next report has not yet arrived.
_STALE_CALENDAR_DAYS = 63
_DECAY_DAYS = 21.0  # e-folding time of the drift, matched to the forecast horizon


def _build_sue_table(tickers):
    """Return per-report standardized unexpected earnings, point-in-time.

    Columns: ticker, date (announcement), sue.
    SUE = surprise / (rolling std of the 8 PRIOR surprises for that ticker).
    """
    earnings = fetch_earnings(list(tickers))
    if earnings.empty:
        return pd.DataFrame(columns=["ticker", "date", "sue"])

    earnings = earnings.dropna(subset=["eps_surprise", "date"]).copy()
    earnings["date"] = pd.to_datetime(earnings["date"]).astype("datetime64[ns]")
    earnings = earnings.sort_values(["ticker", "date"]).reset_index(drop=True)

    surprise = earnings["eps_surprise"].astype(float)
    # Rolling std of PRIOR surprises only (shift(1) excludes the current report).
    prior = earnings.groupby("ticker")["eps_surprise"].transform(
        lambda s: s.shift(1).rolling(8, min_periods=4).std()
    )
    # Fallback scale for early reports: expanding std of prior surprises.
    prior_exp = earnings.groupby("ticker")["eps_surprise"].transform(
        lambda s: s.shift(1).expanding(min_periods=2).std()
    )
    scale = prior.fillna(prior_exp)
    scale = scale.replace(0.0, np.nan)

    earnings["sue"] = (surprise / scale)
    # Winsorize SUE to tame outliers from tiny-denominator quarters.
    earnings["sue"] = earnings["sue"].clip(-4.0, 4.0)
    earnings = earnings.dropna(subset=["sue"])
    return earnings[["ticker", "date", "sue"]].reset_index(drop=True)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")

    sue_tbl = _build_sue_table(panel["ticker"].unique())

    # merge_asof per ticker: attach the most recent report STRICTLY before each
    # panel date (allow_exact_matches=False => announcement day t not used until t+1).
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)
    if sue_tbl.empty:
        panel["pead_sue"] = 0.0
        panel["pead_sue_decayed"] = 0.0
        return panel, ["pead_sue", "pead_sue_decayed"]

    sue_tbl = sue_tbl.sort_values(["date", "ticker"]).reset_index(drop=True)

    merged = pd.merge_asof(
        panel,
        sue_tbl.rename(columns={"date": "earn_date"}),
        left_on="date",
        right_on="earn_date",
        by="ticker",
        direction="backward",
        allow_exact_matches=False,
    )

    days_since = (merged["date"] - merged["earn_date"]).dt.days

    # Raw SUE, valid only while the report is fresh; else neutral (0).
    fresh = days_since <= _STALE_CALENDAR_DAYS
    pead_sue = merged["sue"].where(fresh, other=0.0).fillna(0.0)

    # Exponentially decayed SUE: weight recent surprises more, fade to ~0.
    decay = np.exp(-days_since.astype(float) / _DECAY_DAYS)
    pead_sue_decayed = (merged["sue"].fillna(0.0) * decay).fillna(0.0)
    pead_sue_decayed = pead_sue_decayed.where(days_since.notna(), 0.0)

    merged["pead_sue"] = pead_sue.astype(float)
    merged["pead_sue_decayed"] = pead_sue_decayed.astype(float)

    merged = merged.drop(columns=["earn_date", "sue"])
    return merged, ["pead_sue", "pead_sue_decayed"]
