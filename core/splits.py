"""Splitting data in time, and weighting recent data more heavily.

Two jobs:
  1. assign_time_split  -- carve the data into train / validation / locked
     holdout, strictly in time order (oldest -> newest). The holdout is the
     newest block and stays sealed until the very end of a run; that's what
     makes the final verdict honest.
  2. recency_weights    -- give more recent training samples more weight, because
     markets move and old relationships decay.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def assign_time_split(
    dataset: pd.DataFrame,
    split_fractions=(0.6, 0.2, 0.2),
    date_column: str = "date",
):
    """Tag each row as 'train', 'validation', or 'holdout' by date.

    The split is by calendar order, NOT random: the oldest `split_fractions[0]`
    of dates are train, the next chunk is validation, and the newest chunk is the
    locked holdout. Splitting by time (not randomly) prevents a row from being
    trained on its own near-future neighbors.

    Args:
        dataset: any frame with a date column.
        split_fractions: (train, validation, holdout) fractions, summing to ~1.
        date_column: name of the date column.

    Returns:
        (dataset_with_split_column, train_end_date, validation_end_date)
    """
    unique_dates_sorted = np.sort(dataset[date_column].unique())
    total_dates = len(unique_dates_sorted)

    # Index boundaries between the three time blocks.
    last_train_index = int(total_dates * split_fractions[0])
    last_validation_index = int(total_dates * (split_fractions[0] + split_fractions[1]))

    train_end_date = unique_dates_sorted[last_train_index - 1]
    validation_end_date = unique_dates_sorted[last_validation_index - 1]

    def which_split(row_date):
        if row_date <= train_end_date:
            return "train"
        if row_date <= validation_end_date:
            return "validation"
        return "holdout"

    dataset_with_split = dataset.copy()
    dataset_with_split["split"] = dataset_with_split[date_column].map(which_split)

    return dataset_with_split, pd.Timestamp(train_end_date), pd.Timestamp(validation_end_date)


def recency_weights(dates, half_life_days: float, reference_date=None) -> np.ndarray:
    """Exponential-decay sample weights: newer dates count more.

    A sample exactly `half_life_days` older than the reference gets half the
    weight of a sample at the reference date; twice that age gets a quarter, etc.

    Args:
        dates: the dates of the samples to weight.
        half_life_days: how many days it takes for a sample's weight to halve.
        reference_date: the "now" the ages are measured from (defaults to the
            newest date in `dates`).

    Returns:
        A numpy array of weights, one per input date.
    """
    dates_series = pd.to_datetime(pd.Series(list(dates)))
    reference = pd.to_datetime(reference_date) if reference_date is not None else dates_series.max()

    sample_age_in_days = (reference - dates_series).dt.days.clip(lower=0).to_numpy()
    decay_rate = np.log(2.0) / float(half_life_days)  # so weight halves every half-life

    return np.exp(-decay_rate * sample_age_in_days)
