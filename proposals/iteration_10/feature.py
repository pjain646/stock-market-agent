"""Iteration 10 — short-term reversal.

A genuinely non-fundamental, orthogonal axis to the eight quality/capital-discipline
and momentum/vol signals tried so far. Insider (Form 4) and analyst-grade data were
explored first but are infeasible here: the bundled Form 4 fetcher only returns the
last ~1yr of filings (2025-2026) and never overlaps the 2014-2024 panel, and FMP
grades are rate-limited on the free tier. Reversal is built from adjusted prices,
which are fully covered and split/dividend-adjusted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SIGNAL_NAME = "short_term_reversal"
HYPOTHESIS = (
    "Over ~1-month horizons stock prices that moved sharply recently tend to reverse, "
    "because much of a short-run move reflects temporary liquidity demand / overreaction "
    "that mean-reverts as liquidity providers are compensated; in this large-cap universe "
    "continuation signals have repeatedly inverted, so a stock whose recent 1-week/1-month "
    "return is weak — especially large relative to its own volatility — has a higher chance "
    "of a positive 21-day return."
)


def add_feature(panel):
    """Compute short-term reversal features, point-in-time safe.

    Every value uses only adjusted closes up to and including the row's own date:
    a past return over [t-k, t] and a trailing volatility over [t-21, t] are both
    fully known at t, while the label looks forward from t. No lookahead.
    """
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    g = panel.groupby("ticker")["adj_close"]

    # Trailing simple returns (known at date t). Negated so that HIGHER value =
    # more "oversold" = the reversal-implied bullish direction.
    past_1m = g.transform(lambda s: s / s.shift(21) - 1.0)
    past_1w = g.transform(lambda s: s / s.shift(5) - 1.0)
    panel["str_rev_1m"] = -past_1m
    panel["str_rev_1w"] = -past_1w

    # Volatility-normalized 1-month "stretch": how many ~monthly sigmas the recent
    # move is. A big move relative to the stock's own normal vol is the strongest
    # overreaction/reversal candidate. Uses trailing daily-return std (known at t).
    daily_ret = g.transform(lambda s: s.pct_change())
    daily_vol_21 = (
        panel.assign(_r=daily_ret)
        .groupby("ticker")["_r"]
        .transform(lambda s: s.rolling(21, min_periods=10).std())
    )
    monthly_vol = daily_vol_21 * np.sqrt(21.0)
    stretch = past_1m / monthly_vol.replace(0.0, np.nan)
    panel["str_rev_1m_volnorm"] = (-stretch).clip(-5.0, 5.0)

    # Cross-sectional, within-industry rank of the 1-month reversal on each date
    # (0..1, higher = most oversold in its sector). Neutralizes sector-wide moves
    # so the signal is relative, consistent with what worked in prior iterations.
    panel["str_rev_1m_ind_rank"] = (
        panel.groupby(["date", "industry"])["str_rev_1m"]
        .rank(pct=True)
    )

    new_cols = [
        "str_rev_1m",
        "str_rev_1w",
        "str_rev_1m_volnorm",
        "str_rev_1m_ind_rank",
    ]
    return panel, new_cols
