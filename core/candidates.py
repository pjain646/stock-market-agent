"""Candidate ranking — the product's actual output.

Scored signals alone aren't the goal (spec §1: "surface high-quality trade
candidates"; §5 P0: "learned-weight multi-factor scoring; rank candidates by
tested score"). This module is the last mile: take every journal signal that
proved a real out-of-sample edge, combine them into ONE model (weights learned
from data, never hand-picked — the spec's rule, satisfied literally by
LogisticRegression.coef_), and predict on today's data.

"Today's data" = the unlabeled tail of the panel. Labeling deliberately leaves
the most recent ~label-horizon days per ticker unlabeled (no future to check
yet) — those rows exist for exactly this purpose.

This is a LIVE-USE model, not a test: once a signal has cleared the holdout
ceremony, held-back data no longer serves a purpose, so the ranking model
trains on every labeled row available (train + validation + holdout combined).
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

from .evaluator import _train_model
from .splits import recency_weights


def positive_signals(journal_connection) -> list[dict]:
    """Every journal experiment with a positive validated tested_score.

    Returns the raw rows (as dicts) needed to reload each signal's feature
    code: iteration, signal_name, feature_code_path, feature_columns.
    """
    rows = journal_connection.execute(
        "SELECT iteration, signal_name, feature_code_path, feature_columns, tested_score"
        " FROM experiments WHERE status = 'tested' AND tested_score > 0 ORDER BY tested_score DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def build_combined_panel(panel: pd.DataFrame, signals: list[dict],
                         project_root: pathlib.Path, load_feature_module) -> tuple[pd.DataFrame, list[str]]:
    """Apply every proven signal's feature code to the panel, in sequence.

    `load_feature_module` is passed in (from run_phase_c_loop) rather than
    imported, so this module stays free of any orchestration/SDK dependency —
    it only ever touches already-written feature code, never writes any.
    """
    combined_panel = panel.copy()
    all_feature_columns: list[str] = []
    for signal in signals:
        module = load_feature_module((project_root / signal["feature_code_path"]).resolve())
        combined_panel, new_columns = module.add_feature(combined_panel)
        all_feature_columns.extend(new_columns)
    return combined_panel, all_feature_columns


def rank_candidates(combined_panel: pd.DataFrame, feature_columns: list[str],
                    half_life_days: float, label_column: str = "label",
                    date_column: str = "date") -> pd.DataFrame:
    """Train the fixed model on ALL labeled history; predict on the live tail.

    Returns one row per (ticker, as-of date) with the model's P(up) and the
    per-signal feature values that drove it, ranked highest-conviction first.
    """
    labeled_rows = combined_panel.dropna(subset=feature_columns + [label_column])
    live_rows = combined_panel[combined_panel[label_column].isna()].dropna(subset=feature_columns)
    # Only the single most recent row per ticker is "today's" candidate.
    live_rows = live_rows.sort_values(date_column).groupby("ticker", as_index=False).tail(1)

    if labeled_rows.empty or live_rows.empty:
        return pd.DataFrame()

    training_sample_weights = recency_weights(
        labeled_rows[date_column], half_life_days, reference_date=labeled_rows[date_column].max()
    )
    model = _train_model(
        labeled_rows[feature_columns].to_numpy(), labeled_rows[label_column].to_numpy(),
        training_sample_weights, model_type="logistic",
    )

    predicted_up_probability = model.predict_proba(live_rows[feature_columns].to_numpy())[:, 1]
    candidates = live_rows[["ticker", "industry", date_column] + feature_columns].copy()
    candidates["predicted_up_probability"] = predicted_up_probability
    # Which signal contributed most for THIS row: coefficient * (standardized-ish) feature value.
    # A simple, honest attribution — not a claim of causality, just "what moved the needle."
    coefficients = dict(zip(feature_columns, model.coef_[0]))
    candidates["top_driver"] = candidates[feature_columns].apply(
        lambda row: max(feature_columns, key=lambda col: abs(row[col] * coefficients[col])), axis=1
    )
    return candidates.sort_values("predicted_up_probability", ascending=False).reset_index(drop=True)


def save_candidates(candidates: pd.DataFrame, signals: list[dict], output_path: pathlib.Path) -> None:
    """Persist the ranked list + which signals fed it, for the dashboard to read."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output_path, index=False)
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps({
        "signals_used": [{"signal_name": s["signal_name"], "tested_score": s["tested_score"]} for s in signals],
        "n_candidates": len(candidates),
    }, indent=2))
