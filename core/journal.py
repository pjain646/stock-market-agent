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

        # Multi-agent debate outcomes the analysts read next iteration, so a
        # factor the research manager already killed isn't re-proposed and
        # re-litigated from scratch (observed: credit_spread_momentum proposed
        # in iteration 24, rejected, then proposed AGAIN in iteration 25 — a
        # full analyst+debate+manager cycle spent re-arguing settled ground,
        # because rejections previously left no trace the next analyst could see).
        connection.execute("""
            CREATE TABLE IF NOT EXISTS rejected_factors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration INTEGER NOT NULL,
                analyst TEXT NOT NULL,
                factor_name TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        """)


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


def journal_markdown(journal_path: Path | str = DEFAULT_JOURNAL_PATH,
                     recent_full: int = 5) -> str:
    """The journal rendered as markdown — what the implementing researcher reads.

    Chronological, with the tested score front and center, so the researcher can
    see the arc of what's been tried and how each idea actually fared.

    Bounded by design: only the last `recent_full` iterations get the full
    metrics blob; everything older gets one compact line (score + one-line
    takeaway). Sent in FULL every iteration, this was growing ~4k chars per
    iteration with no ceiling (99.8k chars / ~25k tokens by iteration 24) — the
    single biggest and worst-scaling cost in the loop, since it means iteration
    40 costs more just to START than iteration 20 did. Old metrics blobs are
    rarely what the researcher needs anyway; the hypothesis, the score, and the
    self-reflection's takeaway are what actually inform the next idea.
    """
    with _connect(journal_path) as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY iteration").fetchall()

    if not rows:
        return "(The journal is empty — this is the first iteration. No prior signals to build on.)"

    cutoff = len(rows) - recent_full
    lines = []
    for index, row in enumerate(rows):
        score = f"{row['tested_score']:+.4f}" if row["tested_score"] is not None else "n/a"
        if index < cutoff:
            # Older iteration: one line. Full text still lives in the DB and in
            # proposals/iteration_N/ if anyone needs to go back to it.
            takeaway = _clip(row["researcher_notes"] or row["hypothesis"], 220)
            lines.append(f"- Iter {row['iteration']}: {row['signal_name']} "
                         f"({row['status']}, {score}) — {takeaway}")
            continue
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


def _clip(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit].rstrip() + " [...]"


# Keyword -> axis, for role-filtered journal views. Deliberately matched against
# BOTH signal_name and feature_columns, since a bundle's name may not mention
# every leg it carries.
_AXIS_KEYWORDS = {
    "fundamental": ("disc", "profmom", "quality", "value", "gp_", "grossprofit",
                    "asset", "payout", "earnings", "accrual", "fcf", "piotroski",
                    "roa", "profitability", "noa", "dividend", "stability", "ey_"),
    "macro": ("macro", "rate", "credit", "spread", "vix", "duration", "curve",
              "slope", "regime", "financial_conditions", "yield"),
}


def _axes_for(row) -> set[str]:
    """Which axes an experiment touched, from its name + feature columns."""
    haystack = f"{row['signal_name']} {row['feature_columns'] or ''}".lower()
    return {axis for axis, keywords in _AXIS_KEYWORDS.items()
            if any(keyword in haystack for keyword in keywords)}


def journal_digest_for_role(role: str,
                            journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> str:
    """Journal filtered to what ONE role actually needs.

    Every role still sees the FULL arc as one-liners — that is what stops an
    analyst re-proposing something already tried — but only gets the expensive
    detail (hypothesis + reflection) for experiments touching its own axis.

    Motivation: the unfiltered digest is ~9k tokens and every one of the 5 agents
    reads all of it, so ~45k tokens per iteration go on journal reading alone —
    an order of magnitude more than the role facts or the charter. The macro
    analyst does not need the full reasoning behind eight fundamental
    experiments, and vice versa.

    `role` is "fundamental", "macro", or anything else (bull/bear/manager), which
    gets the compact arc only — the debaters reason about the CURRENT proposals
    in front of them, not the archaeology.
    """
    with _connect(journal_path) as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY iteration").fetchall()

    if not rows:
        return "(The journal is empty — this is the first iteration.)"

    lines = ["FULL HISTORY (every experiment ever run — do not re-propose these):"]
    detailed = []
    for row in rows:
        score = f"{row['tested_score']:+.4f}" if row["tested_score"] is not None else "n/a"
        lines.append(f"- Iter {row['iteration']}: {row['signal_name']} ({score})")
        if role in _AXIS_KEYWORDS and role in _axes_for(row):
            detailed.append(row)

    if detailed:
        # Recent experiments are nearly all multi-axis bundles, so "touched this
        # axis" alone barely discriminates between roles. The PURE single-axis
        # experiments are where an axis's own lesson is isolated and readable
        # (e.g. iter 13's pure macro timer, iter 5's pure asset-growth), so carry
        # those too even when older — otherwise every role reads the same thing.
        pure = [row for row in detailed if _axes_for(row) == {role}]
        recent = [row for row in detailed[-4:] if row not in pure]
        chosen = sorted(pure[-2:] + recent, key=lambda r: r["iteration"])

        lines.append(f"\nDETAIL FOR YOUR AXIS ({role}):")
        for row in chosen:
            score = f"{row['tested_score']:+.4f}" if row["tested_score"] is not None else "n/a"
            tag = "  [pure single-axis]" if row in pure else ""
            lines.append(f"\n### Iter {row['iteration']}: {row['signal_name']} ({score}){tag}")
            lines.append(f"- Hypothesis: {_clip(row['hypothesis'], 500)}")
            if row["researcher_notes"]:
                lines.append(f"- What was learned: {_clip(row['researcher_notes'], 600)}")
    return "\n".join(lines)


def record_rejected_factors(iteration: int, rejected: list[tuple[str, str, str]],
                            journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> None:
    """Record factors the research manager killed in debate.

    `rejected` is a list of (analyst, factor_name, reason) tuples — the reason
    should be a short excerpt from the manager's own ruling, not a paraphrase,
    so the next analyst sees why in the manager's own words.
    """
    if not rejected:
        return
    with _connect(journal_path) as connection:
        connection.executemany(
            "INSERT INTO rejected_factors (iteration, analyst, factor_name, reason) "
            "VALUES (?, ?, ?, ?)",
            [(iteration, analyst, name, reason) for analyst, name, reason in rejected],
        )


def rejected_factors_digest(journal_path: Path | str = DEFAULT_JOURNAL_PATH,
                            limit: int = 15) -> str:
    """Compact list of recently-killed factors, for the analyst team's prompt.

    Most-recent-first, capped, so this stays small even deep into a campaign —
    a factor rejected 20 iterations ago with a since-changed universe/prompt is
    less load-bearing than a fresh rejection.
    """
    with _connect(journal_path) as connection:
        rows = connection.execute(
            "SELECT iteration, analyst, factor_name, reason FROM rejected_factors "
            "ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    if not rows:
        return ""
    lines = ["REJECTED IN A PRIOR DEBATE — do not re-propose these without a genuinely "
             "new argument the manager hasn't already heard:"]
    for row in rows:
        lines.append(f"- [{row['analyst']}] {row['factor_name']} (iter {row['iteration']}): "
                     f"{_clip(row['reason'], 200)}")
    return "\n".join(lines)


def journal_digest(journal_path: Path | str = DEFAULT_JOURNAL_PATH) -> str:
    """A compact journal view — same arc, without the raw metrics blobs.

    `journal_markdown()` embeds the full evaluator output as JSON per iteration,
    which is right for the implementing researcher (it may want a per-sector
    number) but is ~23k tokens by iteration 24. The analyst agents only need to
    know WHAT was tried, HOW it scored, and WHY it worked or failed — feeding
    them the blobs burned their whole per-agent budget on reading.
    """
    with _connect(journal_path) as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY iteration").fetchall()

    if not rows:
        return "(The journal is empty — this is the first iteration. No prior signals to build on.)"

    lines = []
    for row in rows:
        score = f"{row['tested_score']:+.4f}" if row["tested_score"] is not None else "n/a"
        lines.append(f"### Iteration {row['iteration']}: {row['signal_name']} "
                     f"— {row['status']}, tested_score {score}")
        lines.append(f"- Hypothesis: {_clip(row['hypothesis'], 700)}")
        lines.append(f"- Feature columns: {row['feature_columns']}")
        if row["error"]:
            # Tracebacks are long; the failure mode is the useful part.
            lines.append(f"- ERROR: {_clip(row['error'], 300)}")
        if row["researcher_notes"]:
            # The reflection is the most valuable part of the journal, but the
            # full text runs ~2k chars x 24 iterations. The lead sentences carry
            # the verdict and the recommendation; the rest is supporting detail.
            lines.append(f"- Researcher's note: {_clip(row['researcher_notes'], 800)}")
        lines.append("")
    return "\n".join(lines)
