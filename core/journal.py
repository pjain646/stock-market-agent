"""The journal — the research agent's memory across iterations.

Every proposed signal is recorded here with its hypothesis, its code, and the
deterministic evaluator's verdict. The researcher reads this at the start of
each iteration so it can build on what worked and avoid repeating what failed.

This is the RUNTIME experiment store (one of the three artifacts the spec keeps
separate): scratchpad.md is the build log, the research-methodology skill is
the how-to-research instructions, and this journal is the agent's memory.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_JOURNAL_PATH = Path(__file__).resolve().parent.parent / "journal.db"


def _connect(journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(journal_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_journal(journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> None:
    """Create the tables if they don't exist yet; add any missing columns."""
    with _connect(journal_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration INTEGER NOT NULL,
                recorded_at TEXT NOT NULL,
                signal_name TEXT NOT NULL,
                hypothesis TEXT NOT NULL,          -- the economic rationale, in the researcher's words
                feature_code_path TEXT NOT NULL,
                feature_columns TEXT NOT NULL,     -- JSON list of the new feature column names
                status TEXT NOT NULL,              -- 'proposed' -> 'tested' | 'error'
                tested_score REAL,                 -- PR-AUC uplift over base rate (the honest number)
                metrics TEXT,                      -- full evaluator output, JSON
                error TEXT,                        -- traceback/reason when status = 'error'
                researcher_notes TEXT              -- the researcher's own note on the result
            )
        """)
        # The final, open-once holdout verdicts (Phase D). Kept separate from
        # experiments because opening the holdout is a run-level event, not an iteration.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS holdout_verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                experiment_id INTEGER NOT NULL,    -- the experiment whose signal was judged
                validation_score REAL NOT NULL,    -- what walk-forward validation said
                holdout_score REAL NOT NULL,       -- what the sealed holdout said
                gap REAL NOT NULL,                 -- validation - holdout (big gap = overfit)
                gate1_passed INTEGER NOT NULL,     -- 1 if the signal beat base rate on the holdout
                metrics TEXT NOT NULL              -- full holdout evaluator output, JSON
            )
        """)
        # Columns added after the first release (ALTER is a no-op error if present).
        for added_column in ("transcript_path TEXT", "oos_csv_path TEXT", "cost_usd REAL"):
            try:
                connection.execute(f"ALTER TABLE experiments ADD COLUMN {added_column}")
            except sqlite3.OperationalError:
                pass  # column already exists


def record_proposal(iteration: int, signal_name: str, hypothesis: str,
                    feature_code_path: str, feature_columns: list[str],
                    journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> int:
    """Record a newly proposed signal; returns the experiment id."""
    with _connect(journal_path) as connection:
        cursor = connection.execute(
            "INSERT INTO experiments (iteration, recorded_at, signal_name, hypothesis,"
            " feature_code_path, feature_columns, status) VALUES (?, ?, ?, ?, ?, ?, 'proposed')",
            (iteration, datetime.now(timezone.utc).isoformat(), signal_name, hypothesis,
             feature_code_path, json.dumps(feature_columns)),
        )
        return int(cursor.lastrowid)


def record_verdict(experiment_id: int, metrics: dict,
                   journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> None:
    """Attach the deterministic evaluator's verdict to an experiment."""
    with _connect(journal_path) as connection:
        connection.execute(
            "UPDATE experiments SET status = 'tested', tested_score = ?, metrics = ? WHERE id = ?",
            (metrics.get("tested_score"), json.dumps(metrics), experiment_id),
        )


def record_error(experiment_id: int, error_message: str,
                 journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> None:
    """Mark an experiment as failed (e.g. the feature code crashed)."""
    with _connect(journal_path) as connection:
        connection.execute(
            "UPDATE experiments SET status = 'error', error = ? WHERE id = ?",
            (error_message, experiment_id),
        )


def record_researcher_notes(experiment_id: int, notes: str,
                            journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> None:
    """Store the researcher's own post-verdict reflection on why it worked/failed."""
    with _connect(journal_path) as connection:
        connection.execute(
            "UPDATE experiments SET researcher_notes = ? WHERE id = ?", (notes, experiment_id)
        )


def record_session_artifacts(experiment_id: int, transcript_path: str | None = None,
                             oos_csv_path: str | None = None, cost_usd: float | None = None,
                             journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> None:
    """Attach session artifacts (transcript, oos rows CSV, session cost) to an experiment."""
    with _connect(journal_path) as connection:
        connection.execute(
            "UPDATE experiments SET transcript_path = COALESCE(?, transcript_path),"
            " oos_csv_path = COALESCE(?, oos_csv_path), cost_usd = COALESCE(?, cost_usd)"
            " WHERE id = ?",
            (transcript_path, oos_csv_path, cost_usd, experiment_id),
        )


def record_holdout_verdict(experiment_id: int, validation_score: float, metrics: dict,
                           journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> dict:
    """Record the open-once holdout verdict for a signal; returns the verdict summary.

    Gate 1 (spec §6): the signal must beat the base rate on the sealed holdout —
    i.e. holdout tested_score > 0.
    """
    holdout_score = float(metrics["tested_score"])
    verdict = {
        "validation_score": validation_score,
        "holdout_score": holdout_score,
        "gap": round(validation_score - holdout_score, 4),
        "gate1_passed": holdout_score > 0,
    }
    with _connect(journal_path) as connection:
        connection.execute(
            "INSERT INTO holdout_verdicts (recorded_at, experiment_id, validation_score,"
            " holdout_score, gap, gate1_passed, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), experiment_id, validation_score,
             holdout_score, verdict["gap"], int(verdict["gate1_passed"]), json.dumps(metrics)),
        )
    return verdict


def next_iteration_number(journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> int:
    with _connect(journal_path) as connection:
        row = connection.execute("SELECT MAX(iteration) AS latest FROM experiments").fetchone()
        return (row["latest"] or 0) + 1


def journal_markdown(journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> str:
    """The journal rendered as readable markdown — what the researcher reads each iteration.

    Chronological, with the tested score front and center, so the researcher can
    see the arc of what's been tried and how each idea actually fared.
    """
    with _connect(journal_path) as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY iteration").fetchall()

    if not rows:
        return "(The journal is empty — this is the first iteration. No prior signals to build on.)"

    lines = []
    for row in rows:
        score = f"{row['tested_score']:+.4f}" if row["tested_score"] is not None else "n/a"
        lines.append(f"### Iteration {row['iteration']}: {row['signal_name']} — {row['status']}, tested_score {score}")
        lines.append(f"- Hypothesis: {row['hypothesis']}")
        lines.append(f"- Feature columns: {row['feature_columns']}")
        if row["metrics"]:
            lines.append(f"- Full metrics: {row['metrics']}")
        if row["error"]:
            lines.append(f"- ERROR: {row['error']}")
        if row["researcher_notes"]:
            lines.append(f"- Researcher's note: {row['researcher_notes']}")
        lines.append("")
    return "\n".join(lines)
