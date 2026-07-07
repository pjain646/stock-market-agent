"""Iteration 3 signal: the low-volatility anomaly, industry-relative.

Both prior signals (12-1 momentum, PEAD) were direction-CONTINUATION ideas that
empirically reversed in this 24-name large-cap universe and, critically, flipped sign
across sectors. A quick train-only screen showed that short-horizon REALIZED VOLATILITY
is the one feature whose relationship to the 21-day up/down label is *consistently
negative in all three sectors* (Financials, Pharma, Technology) -- i.e. calmer stocks
tend to rise, choppier stocks tend to disappoint. That sector-consistency is exactly the
property the earlier signals lacked, so this is a genuinely different (risk-based, not
direction-based) axis to bet on.
"""

import numpy as np
import pandas as pd

SIGNAL_NAME = "low_volatility"
HYPOTHESIS = (
    "Leverage-constrained and lottery-seeking investors bid up high-volatility stocks and "
    "shun calm ones, so low-realized-volatility names are relatively underpriced and tend to "
    "drift up while high-volatility names disappoint (the low-volatility anomaly). A stock "
    "with low recent realized volatility, ranked within its industry, should therefore have a "
    "higher probability of a positive 21-day return."
)


def add_feature(panel):
    """Compute industry-relative low-volatility features, point-in-time safe.

    Uses only trailing adjusted-close prices (no future information). For each ticker we
    compute realized daily-return volatility over 20- and 60-trading-day trailing windows,
    then express each cross-sectionally within its (date, industry) group so the signal is
    sector-neutral (Tech is structurally more volatile than Financials, etc.). The signed
    "lowvol" ranks are oriented so that HIGH = low volatility = the predicted-up side.
    """
    df = panel.sort_values(["ticker", "date"]).reset_index(drop=True).copy()

    # Daily simple returns per ticker (past prices only -> point-in-time safe).
    df["_ret"] = df.groupby("ticker")["adj_close"].transform(lambda s: s.pct_change())

    new_cols = []

    for w in (20, 60):
        rvol_col = f"rvol_{w}"
        # Trailing realized volatility; require most of the window to be present.
        df[rvol_col] = df.groupby("ticker")["_ret"].transform(
            lambda s, w=w: s.rolling(window=w, min_periods=max(10, w // 2)).std()
        )

        # Industry-relative percentile rank of volatility within each date.
        pct = df.groupby(["date", "industry"])[rvol_col].rank(pct=True)
        # Orient so HIGH = LOW volatility (the side the anomaly says should rise).
        lowvol_col = f"lowvol_{w}_ind"
        df[lowvol_col] = 1.0 - pct

        new_cols.extend([rvol_col, lowvol_col])

    df = df.drop(columns=["_ret"])
    return df, new_cols
