"""The honest judge — scores a feature out-of-sample and cannot be talked around.

This is the component the skill tells the researcher it may never overrule. It
trains a simple, interpretable model and grades it ONLY on data the model didn't
train on, always compared to the base rate (the hit rate of just guessing the
majority outcome), because a precision number means nothing on its own.

Two entry points:
  - walk_forward_eval: the everyday scorer. Walks forward through the validation
    period, retraining on everything strictly before each chunk. NEVER touches
    the holdout.
  - open_holdout_once: opens the LOCKED HOLDOUT exactly once, at the very end of
    a run. It refuses to run unless the caller explicitly acknowledges that.

Primary model: recency-weighted, class-balanced logistic regression (the spec's
primary). Random forest and XGBoost run as comparisons (Phase B) — the LR
number stays the tested_score; the comparisons exist to show whether an edge is
model-fragile (only one model sees it = suspicious) or robust across all three.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score

from .splits import recency_weights

MODEL_TYPES = ("logistic", "random_forest", "gradient_boosting")


def _train_model(feature_matrix, labels, sample_weights=None, model_type: str = "logistic"):
    """Fit one of the three fixed models (spec: the researcher can never change these).

    All three are class-balanced so none can win by just predicting the majority
    class, and all honor the recency sample weights.

    Note on the third model: the spec names XGBoost, but the pip xgboost wheel
    needs macOS's OpenMP runtime (brew install libomp), which this machine lacks.
    sklearn's HistGradientBoostingClassifier is the same model family
    (histogram-based gradient-boosted trees) with no native dependency, so it
    serves the spec's purpose — a boosted-trees robustness comparison. Swap to
    literal XGBoost later if libomp gets installed.
    """
    if model_type == "logistic":
        model = LogisticRegression(max_iter=1000, class_weight="balanced")
    elif model_type == "random_forest":
        # Shallow-ish, well-regularized: min_samples_leaf keeps it from memorizing
        # the (autocorrelated) panel; fixed seed keeps verdicts reproducible.
        model = RandomForestClassifier(
            n_estimators=200, min_samples_leaf=50, class_weight="balanced",
            n_jobs=-1, random_state=0,
        )
    elif model_type == "gradient_boosting":
        from sklearn.ensemble import HistGradientBoostingClassifier

        model = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, min_samples_leaf=50,
            class_weight="balanced", random_state=0,
        )
    else:
        raise ValueError(f"unknown model_type: {model_type!r} (expected one of {MODEL_TYPES})")

    model.fit(feature_matrix, labels, sample_weight=sample_weights)
    return model


def _purge_cutoff_date(all_trading_dates: np.ndarray, boundary_date, label_horizon_days: int):
    """The last training date whose forward-return label CANNOT overlap `boundary_date`.

    A row's label looks `label_horizon_days` trading days into the future, so a
    training row within that many trading days of the test boundary has a label
    computed from prices INSIDE the test period — a leak. Training must therefore
    stop `label_horizon_days` trading days before the boundary (a "purge gap").
    `all_trading_dates` (sorted, unique) serves as the trading calendar.
    """
    # Normalize: callers pass either np.datetime64 (fold starts) or pd.Timestamp
    # (holdout start); searchsorted needs the array's own dtype to compare.
    boundary_index = int(np.searchsorted(all_trading_dates, np.datetime64(boundary_date)))
    purge_index = max(0, boundary_index - label_horizon_days)
    return all_trading_dates[purge_index]


def walk_forward_eval(
    panel: pd.DataFrame,
    feature_columns,
    half_life_days: float,
    number_of_folds: int = 6,
    label_column: str = "label",
    date_column: str = "date",
    label_horizon_days: int = 21,
    return_scored_rows: bool = False,
    model_type: str = "logistic",
):
    """Score features out-of-sample by walking forward through validation.

    For each validation fold (a contiguous block of dates), train on everything
    before it — minus a purge gap of `label_horizon_days` trading days, so no
    training row's forward-return label overlaps the fold it's tested on — and
    predict the fold. Pool all the out-of-sample predictions, then score them
    against the base rate. The holdout is never used.

    `label_horizon_days` must match the horizon used to build `label_column`.

    Returns a metrics dict, including `tested_score` = PR-AUC minus the base rate,
    which is the honest "edge over guessing" the researcher ranks signals on.
    With `return_scored_rows=True`, returns (metrics, scored_rows) where
    scored_rows is every out-of-sample row with its fold number and the model's
    predicted P(up) — the full audit trail behind the score.
    """
    # Only train/validation rows, and only rows that have both a label and all features.
    usable_rows = (
        panel[panel["split"].isin(["train", "validation"])]
        .dropna(subset=list(feature_columns) + [label_column])
        .sort_values(date_column)
    )

    validation_dates = np.sort(
        usable_rows.loc[usable_rows["split"] == "validation", date_column].unique()
    )
    if len(validation_dates) == 0:
        error = {"error": "no validation rows"}
        return (error, None) if return_scored_rows else error

    # The panel's own sorted unique dates act as the trading calendar for purging.
    all_trading_dates = np.sort(usable_rows[date_column].unique())

    pooled_predicted_probabilities = []  # model's P(up) for each out-of-sample row
    pooled_actual_labels = []            # the true up/down for those same rows
    scored_row_frames = []               # full test rows + predictions (the audit trail)

    # Split the validation dates into N forward folds and evaluate each.
    for fold_number, validation_fold_dates in enumerate(
        np.array_split(validation_dates, number_of_folds), start=1
    ):
        if len(validation_fold_dates) == 0:
            continue

        fold_start_date = validation_fold_dates[0]
        purge_cutoff = _purge_cutoff_date(all_trading_dates, fold_start_date, label_horizon_days)
        training_rows = usable_rows[usable_rows[date_column] < purge_cutoff]
        test_rows = usable_rows[usable_rows[date_column].isin(validation_fold_dates)]

        # Need both classes present to train, and something to test on.
        if training_rows[label_column].nunique() < 2 or len(test_rows) == 0:
            continue

        # Weight recent training samples more heavily.
        training_sample_weights = recency_weights(
            training_rows[date_column],
            half_life_days,
            reference_date=training_rows[date_column].max(),
        )

        model = _train_model(
            training_rows[feature_columns].to_numpy(),
            training_rows[label_column].to_numpy(),
            training_sample_weights,
            model_type=model_type,
        )

        # Probability the price goes UP, for each out-of-sample test row.
        predicted_up_probability = model.predict_proba(test_rows[feature_columns].to_numpy())[:, 1]

        pooled_predicted_probabilities.append(pd.Series(predicted_up_probability, index=test_rows.index))
        pooled_actual_labels.append(test_rows[label_column])
        if return_scored_rows:
            fold_rows = test_rows.copy()
            fold_rows["fold"] = fold_number
            fold_rows["predicted_up_probability"] = predicted_up_probability
            scored_row_frames.append(fold_rows)

    if not pooled_predicted_probabilities:
        error = {"error": "insufficient data for any fold"}
        return (error, None) if return_scored_rows else error

    predicted_up_probability = pd.concat(pooled_predicted_probabilities)
    actual_label = pd.concat(pooled_actual_labels)

    base_rate = float(actual_label.mean())  # hit rate of always guessing "up"
    precision_recall_auc = float(average_precision_score(actual_label, predicted_up_probability))
    predicted_up_class = (predicted_up_probability >= 0.5).astype(int)

    metrics = {
        "n_oos": int(len(actual_label)),                       # out-of-sample sample size
        "base_rate": round(base_rate, 4),
        "pr_auc": round(precision_recall_auc, 4),
        "pr_auc_uplift": round(precision_recall_auc - base_rate, 4),  # edge over guessing
        "precision": round(float(precision_score(actual_label, predicted_up_class, zero_division=0)), 4),
        "recall": round(float(recall_score(actual_label, predicted_up_class, zero_division=0)), 4),
        "tested_score": round(precision_recall_auc - base_rate, 4),   # what the researcher ranks on
        "model_type": model_type,
    }
    # Information coefficient: rank correlation between the model's P(up) and the
    # realized forward RETURN (not just direction) — the industry-standard "does
    # ranking by this signal actually order future returns" number.
    if "forward_return" in usable_rows.columns:
        realized_forward_return = usable_rows.loc[actual_label.index, "forward_return"]
        ic = spearmanr(predicted_up_probability, realized_forward_return).statistic
        metrics["ic_spearman"] = round(float(ic), 4)
    if return_scored_rows:
        scored_rows = pd.concat(scored_row_frames).sort_values(date_column)
        scored_rows["model_says_up"] = (scored_rows["predicted_up_probability"] >= 0.5).astype(int)
        scored_rows["model_was_right"] = (
            scored_rows["model_says_up"] == scored_rows[label_column]
        ).astype(int)
        return metrics, scored_rows
    return metrics


def open_holdout_once(
    panel: pd.DataFrame,
    feature_columns,
    half_life_days: float,
    label_column: str = "label",
    date_column: str = "date",
    label_horizon_days: int = 21,
    acknowledge_this_is_the_final_run: bool = False,
):
    """Open the LOCKED HOLDOUT — call exactly once, at the very end of a run.

    Trains on train+validation and scores on the sealed holdout. The gap between
    the validation score and this holdout score is the verdict: a small gap means
    the edge generalized; a large gap means it was overfit to validation.

    Training stops a purge gap of `label_horizon_days` trading days before the
    holdout begins, so no training row's forward-return label overlaps the
    holdout it's judged on (same leak-prevention as walk_forward_eval).

    Refuses to run unless `acknowledge_this_is_the_final_run=True`, so the holdout
    can't be opened by accident mid-research.
    """
    if not acknowledge_this_is_the_final_run:
        raise RuntimeError(
            "The holdout is sealed. It opens once, at the very end of a run. "
            "Pass acknowledge_this_is_the_final_run=True only when you truly mean it."
        )

    train_and_validation_rows = panel[panel["split"].isin(["train", "validation"])].dropna(
        subset=list(feature_columns) + [label_column]
    )
    holdout_rows = panel[panel["split"] == "holdout"].dropna(
        subset=list(feature_columns) + [label_column]
    )

    # Purge: drop training rows whose label window reaches into the holdout.
    all_trading_dates = np.sort(panel[date_column].unique())
    holdout_start_date = holdout_rows[date_column].min()
    purge_cutoff = _purge_cutoff_date(all_trading_dates, holdout_start_date, label_horizon_days)
    train_and_validation_rows = train_and_validation_rows[
        train_and_validation_rows[date_column] < purge_cutoff
    ]

    training_sample_weights = recency_weights(
        train_and_validation_rows[date_column],
        half_life_days,
        reference_date=train_and_validation_rows[date_column].max(),
    )
    model = _train_model(
        train_and_validation_rows[feature_columns].to_numpy(),
        train_and_validation_rows[label_column].to_numpy(),
        training_sample_weights,
    )

    predicted_up_probability = model.predict_proba(holdout_rows[feature_columns].to_numpy())[:, 1]
    actual_label = holdout_rows[label_column].to_numpy()

    base_rate = float(actual_label.mean())
    precision_recall_auc = float(average_precision_score(actual_label, predicted_up_probability))

    return {
        "n_holdout": int(len(actual_label)),
        "base_rate": round(base_rate, 4),
        "pr_auc": round(precision_recall_auc, 4),
        "pr_auc_uplift": round(precision_recall_auc - base_rate, 4),
        "tested_score": round(precision_recall_auc - base_rate, 4),
    }


def compare_models(panel: pd.DataFrame, feature_columns, half_life_days: float,
                   label_horizon_days: int = 21, **eval_kwargs) -> dict:
    """Run the walk-forward for all three fixed models (Phase B comparison).

    The logistic score remains the official tested_score; this shows whether an
    edge is robust across model families or an artifact of one of them.
    """
    return {
        model_type: walk_forward_eval(
            panel, feature_columns, half_life_days,
            label_horizon_days=label_horizon_days, model_type=model_type, **eval_kwargs,
        )
        for model_type in MODEL_TYPES
    }


def per_industry_eval(panel: pd.DataFrame, feature_columns, half_life_days: float,
                      label_horizon_days: int = 21, industry_column: str = "industry") -> dict:
    """Walk-forward score per industry (spec: per-industry modeling).

    Each industry gets its own independently trained-and-tested model, so a
    signal that only works in, say, Financials isn't diluted by (or mistaken
    for) edge in the whole universe.
    """
    per_industry_metrics = {}
    for industry, industry_panel in panel.groupby(industry_column, sort=False):
        per_industry_metrics[str(industry)] = walk_forward_eval(
            industry_panel, feature_columns, half_life_days,
            label_horizon_days=label_horizon_days,
        )
    return per_industry_metrics
