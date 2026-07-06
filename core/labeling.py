"""Labeling: turn raw prices into the thing the model learns to predict.

The label is the DIRECTION of the move over the next `forward_horizon_days`
trading days: 1 if the price is higher that many days later, else 0.

The last `forward_horizon_days` rows of each ticker have no future yet, so their
label is left as NaN. Those rows stay in the table (they're valid inputs for a
LIVE prediction today) but are excluded from training. This is the no-lookahead
rule enforced in code: a row can never be trained on an outcome that hasn't
happened.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_forward_direction_label(
    price_history: pd.DataFrame,
    forward_horizon_days: int = 21,
    price_column: str = "adj_close",
) -> pd.DataFrame:
    """Add a binary 'label' column = did the price rise over the next N days?

    Args:
        price_history: long-format prices [date, ticker, adj_close, ...].
        forward_horizon_days: how many trading days forward to measure direction.
        price_column: which column holds the (adjusted) price.

    Returns:
        The same rows with an added 'label' column (1.0 up, 0.0 down/flat,
        NaN for the final N rows of each ticker that have no future yet) and a
        'forward_return' column (the realized fractional move over the same
        horizon — the label's continuous sibling, kept ONLY for scoring, e.g.
        information-coefficient calculations; it must never be used as a
        feature, for the same reason the label can't be).
    """
    labeled_ticker_frames = []

    # Process one ticker at a time so the forward shift never bleeds across names.
    for _ticker, single_ticker_history in price_history.sort_values("date").groupby(
        "ticker", sort=False
    ):
        single_ticker_history = single_ticker_history.copy()

        current_price = single_ticker_history[price_column]
        # Price N trading days in the future (NaN for the last N rows).
        future_price = current_price.shift(-forward_horizon_days)

        # 1 if it went up, 0 if not — but only where a real future price exists.
        single_ticker_history["label"] = np.where(
            future_price.notna(),
            (future_price > current_price).astype(float),
            np.nan,  # no future yet -> unlabeled (kept for live prediction)
        )
        # The realized move itself (scoring-only; see docstring).
        single_ticker_history["forward_return"] = future_price / current_price - 1.0
        labeled_ticker_frames.append(single_ticker_history)

    return pd.concat(labeled_ticker_frames).reset_index(drop=True)
