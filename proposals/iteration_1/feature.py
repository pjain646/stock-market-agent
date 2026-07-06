"""52-week-high drawdown reversion signal.

Iteration 0 showed raw 21d momentum has no edge (it mixes trend with
short-term reversal). Here we isolate the reversion component that IS
present in this quality mega-cap universe: distance below the trailing
52-week high.
"""

import pandas as pd

SIGNAL_NAME = "drawdown_from_52w_high"
HYPOTHESIS = (
    "In a universe of quality mega-caps with persistent upward drift, the trailing "
    "52-week high acts as an anchor of 'fair value'; temporary drawdowns from that "
    "high are treated as discounts and bought back, so the deeper the current "
    "drawdown, the higher the probability of a rebound over the next 21 days. "
    "This isolates the reversion component that raw momentum (iter 0) failed to "
    "capture; the effect is monotonic across train deciles (deepest vs shallowest "
    "drawdown decile up-rate ~0.648 vs ~0.584)."
)

# Trailing window ~ one year of trading days.
_WINDOW = 252
_MIN_PERIODS = 126  # need ~6 months of history before trusting the trailing high


def add_feature(panel):
    """Compute drawdown from the trailing 52-week high, point-in-time safe.

    Uses only past and current adj_close for each ticker (rolling window on a
    time-sorted per-ticker series), so no future information leaks in.
    """
    df = panel.copy()
    # Sort by time within ticker for the rolling window; keep the original index
    # so we can restore the caller's row order at the end.
    df = df.sort_values(["ticker", "date"])

    trailing_high = df.groupby("ticker")["adj_close"].transform(
        lambda s: s.rolling(_WINDOW, min_periods=_MIN_PERIODS).max()
    )

    # Drawdown depth: 0 at a fresh high, larger the further price sits below it.
    # Higher value = more bullish (deeper discount -> stronger expected rebound).
    df["drawdown_from_52w_high"] = 1.0 - (df["adj_close"] / trailing_high)

    # Restore the caller's original row order.
    df = df.reindex(panel.index)

    return df, ["drawdown_from_52w_high"]
