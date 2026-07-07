"""Iteration 1 signal: 12-1 month cross-sectional price momentum.

Economic rationale
------------------
Medium-term momentum (Jegadeesh & Titman 1993) is the most robustly documented
cross-sectional return predictor. Its mechanism is behavioral: information
diffuses gradually and investors underreact to it, so stocks that have
outperformed over the past ~year tend to keep outperforming over the following
month. We measure the cumulative return from t-252 to t-21 trading days — the
canonical "12 minus 1 month" window that DELIBERATELY skips the most recent
month, because the last ~21 days are dominated by the opposite (short-term
reversal / bid-ask bounce) effect and would dilute the momentum signal.

Point-in-time safety
--------------------
Every value uses only prices strictly in the past relative to the row's date:
the window ends 21 trading days BEFORE the current bar, so it cannot see the
current price or the forward return it is being scored against. The
cross-sectional rank on each date uses only same-date momentum values, all of
which are knowable that day.
"""
from __future__ import annotations

import pandas as pd

SIGNAL_NAME = "mom_12_1"
HYPOTHESIS = (
    "Stocks with high cumulative returns over the past year excluding the most "
    "recent month (12-1 momentum) tend to keep rising over the next 21 days, "
    "because information diffuses slowly and investors underreact — medium-term "
    "return continuation. Skipping the last month avoids short-term reversal."
)

# Trading-day windows
_LOOKBACK = 252   # ~12 months
_SKIP = 21        # ~1 month, skipped to avoid short-term reversal


def add_feature(panel):
    """Add 12-1 momentum features, point-in-time safe.

    Returns (panel_with_new_columns, list_of_new_feature_column_names).
    """
    df = panel.copy()
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    g = df.groupby("ticker", sort=False)["adj_close"]

    # Price 21 trading days ago (end of the momentum window) and 252 days ago
    # (start). Both are strictly past prices relative to the current bar.
    price_skip = g.shift(_SKIP)          # adj_close at t-21
    price_lookback = g.shift(_LOOKBACK)  # adj_close at t-252

    # Raw 12-1 momentum: return from t-252 to t-21.
    df["mom_12_1"] = price_skip / price_lookback - 1.0

    # Cross-sectional percentile rank of the raw signal within each date.
    # Uses only same-date values -> no lookahead. NaN where momentum is NaN
    # (insufficient history) so those rows are simply not ranked.
    df["mom_12_1_xs_rank"] = (
        df.groupby("date")["mom_12_1"].rank(pct=True)
    )

    new_cols = ["mom_12_1", "mom_12_1_xs_rank"]
    return df, new_cols
