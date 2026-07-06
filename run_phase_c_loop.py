"""Phase C — the self-improving research loop.

Each iteration:
  1. The RESEARCHER (Claude Opus via the Claude Agent SDK, governed by the
     research-methodology skill) reads the journal, explores data, proposes ONE
     signal with an economic rationale, and writes point-in-time feature code.
  2. The EVALUATOR (deterministic, core/evaluator.py) scores the feature
     out-of-sample. The researcher never runs it and cannot talk it around.
  3. The JOURNAL records the proposal, the verdict, and the researcher's note.

Orchestration-seam note (spec §6): everything imported from core/ and the
skill's scripts/ is harness-independent. ONLY this file knows about the
Claude Agent SDK, so the SDK can later be swapped for our own loop.

Run:  python run_phase_c_loop.py [--iterations N] [--budget-usd X] [--refresh-data]
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import pathlib
import pickle
import sys
import traceback

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "research-methodology" / "scripts"))

import pandas as pd  # noqa: E402

from core import config, journal  # noqa: E402
from core.labeling import add_forward_direction_label  # noqa: E402
from core.splits import assign_time_split  # noqa: E402
from core.evaluator import compare_models, per_industry_eval, walk_forward_eval  # noqa: E402

PANEL_CACHE_PATH = PROJECT_ROOT / "data_cache" / "panel.pkl"
PROPOSALS_DIR = PROJECT_ROOT / "proposals"

# The contract every proposed feature module must satisfy. This text is shown
# to the researcher verbatim, and enforced when the module is loaded.
FEATURE_CONTRACT = '''\
SIGNAL_NAME = "a_short_snake_case_name"
HYPOTHESIS = "One or two sentences: the economic rationale — WHY this should predict 21-day direction."

def add_feature(panel):
    """Compute the feature(s), point-in-time safe.

    Args:
        panel: pandas DataFrame with columns [date, ticker, industry, adj_close,
               label, split] (one row per ticker per trading day).
    Returns:
        (panel_with_new_columns, list_of_new_feature_column_names)
    """
'''


def build_panel(refresh: bool = False) -> pd.DataFrame:
    """Fetch prices, label, and split — cached to disk so iterations start fast."""
    if PANEL_CACHE_PATH.exists() and not refresh:
        print(f"loading cached panel from {PANEL_CACHE_PATH}")
        return pickle.loads(PANEL_CACHE_PATH.read_bytes())

    from data import fetch_prices  # the skill's bundled fetcher

    tickers = config.all_tickers()
    print(f"fetching {len(tickers)} tickers {config.START}..{config.END} ...")
    panel = fetch_prices(tickers, config.START, config.END)
    panel["industry"] = panel["ticker"].map(config.industry_map())
    panel = add_forward_direction_label(panel, forward_horizon_days=config.LABEL_HORIZON)
    panel, _, _ = assign_time_split(panel, split_fractions=config.SPLIT_FRACS)

    PANEL_CACHE_PATH.parent.mkdir(exist_ok=True)
    PANEL_CACHE_PATH.write_bytes(pickle.dumps(panel))
    return panel


def researcher_prompt(iteration: int, journal_history: str) -> str:
    """The task given to the researcher each iteration."""
    return f"""You are the researcher in an automated quant research loop. This is iteration {iteration}.
Work under the research-methodology skill's discipline at all times.

YOUR JOB THIS ITERATION — propose and implement exactly ONE new signal:

1. Read your journal history (below). Build on what worked; do not repeat what failed.
2. Explore the data and form a hypothesis with a clear ECONOMIC rationale.
   - The labeled panel is at data_cache/panel.pkl — a pickled pandas DataFrame with columns
     [date, ticker, industry, adj_close, label, forward_return, split]. label = did the price
     rise over the next 21 trading days; forward_return = the realized move itself (used only
     for scoring). NEVER use label, forward_return, or split to build a feature — all three
     contain the future.
   - Bundled point-in-time fetchers (import from research-methodology/scripts/data.py):
     fetch_prices, fetch_fundamentals (SEC EDGAR, filed_date-stamped), fetch_earnings,
     fetch_insider_transactions (Form 4), fetch_analyst_estimates, fetch_analyst_grades,
     fetch_macro_series (FRED). All responses are disk-cached; re-calls are free.
3. Write your feature code to proposals/iteration_{iteration}/feature.py with EXACTLY this contract:

{FEATURE_CONTRACT}

   Every value must only use information public on that row's date (fundamentals by
   filed_date, insider trades by filing date — the fetchers give you the right columns).
4. Smoke-test your module: run it against the panel with python via bash, confirm it returns
   the new columns and they are populated (not all-NaN), then stop.

HARD BOUNDARIES:
- You do NOT run the evaluator, you do NOT score your own signal, and you NEVER touch
  holdout rows. The deterministic judge runs after you finish; its verdict lands in the
  journal for your next iteration.
- Propose ONE signal (a feature family with a shared rationale counts as one).
- Keep the feature code self-contained: imports, SIGNAL_NAME, HYPOTHESIS, add_feature.

YOUR JOURNAL SO FAR:
{journal_history}
"""


def _transcript_lines(message) -> list[str]:
    """Render one SDK assistant message as readable transcript lines."""
    from claude_agent_sdk import AssistantMessage, TextBlock, ThinkingBlock, ToolUseBlock

    lines = []
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                lines.append(f"**researcher:** {block.text}\n")
            elif isinstance(block, ToolUseBlock):
                compact_input = json.dumps(block.input)[:400]
                lines.append(f"- tool `{block.name}`: {compact_input}\n")
            elif isinstance(block, ThinkingBlock):
                lines.append(f"<details><summary>thinking</summary>\n\n{block.thinking}\n</details>\n")
    return lines


async def run_researcher_session(iteration: int, budget_usd: float,
                                 transcript_path: pathlib.Path) -> tuple[str | None, float | None]:
    """One researcher session via the Claude Agent SDK (the only SDK-aware function).

    Writes the full session transcript (visible reasoning + tool calls) to
    `transcript_path` and returns (session_id, cost_usd) so the verdict can be
    fed back into the same session for a reflection note.
    """
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(
        model="claude-opus-4-8",              # spec: Opus is the researcher in v1
        cwd=str(PROJECT_ROOT),
        skills=["research-methodology"],      # auto-loads from .claude/skills/
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"],
        max_budget_usd=budget_usd,            # hard credit cap per iteration
        max_turns=80,
    )

    session_id, cost = None, None
    with transcript_path.open("w") as transcript_file:
        transcript_file.write(f"# Researcher session — iteration {iteration}\n\n")
        async for message in query(prompt=researcher_prompt(iteration, journal.journal_markdown()),
                                   options=options):
            for line in _transcript_lines(message):
                transcript_file.write(line + "\n")
            if isinstance(message, ResultMessage):
                session_id, cost = message.session_id, message.total_cost_usd
                print(f"  researcher session done: subtype={message.subtype}"
                      + (f", cost=${cost:.2f}" if cost else ""))
    return session_id, cost


async def run_reflection(session_id: str, verdict_summary: str, budget_usd: float = 1.0) -> str:
    """Resume the researcher's session with the verdict; get a short journal note back.

    The researcher saw its own exploration; the evaluator's number is news to it.
    This closes the loop the spec describes: the journal records not just the
    score but the researcher's own read on WHY it worked or failed.
    """
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

    options = ClaudeAgentOptions(
        model="claude-opus-4-8",
        cwd=str(PROJECT_ROOT),
        resume=session_id,                    # same session -> full research context intact
        allowed_tools=[],                     # reflection is thought, not action
        max_budget_usd=budget_usd,
        max_turns=4,
    )
    prompt = (
        f"The deterministic evaluator has scored your signal:\n{verdict_summary}\n\n"
        "For the journal (your future iterations will read this): in 2-4 sentences, "
        "why do you think it got this result, and what should the next iteration do "
        "differently because of it? Reply with only the note text."
    )
    note_fragments = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            note_fragments.extend(b.text for b in message.content if isinstance(b, TextBlock))
    return " ".join(fragment.strip() for fragment in note_fragments).strip()


def load_feature_module(feature_code_path: pathlib.Path):
    """Import the researcher's feature module and validate the contract."""
    spec = importlib.util.spec_from_file_location("proposed_feature", feature_code_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for required in ("SIGNAL_NAME", "HYPOTHESIS", "add_feature"):
        if not hasattr(module, required):
            raise ValueError(f"feature module is missing required attribute: {required}")
    return module


def evaluate_proposal(panel: pd.DataFrame, feature_code_path: pathlib.Path,
                      iteration: int) -> tuple[int, dict | None]:
    """The deterministic half of the iteration: score the proposal, journal the verdict.

    Saves the exact out-of-sample rows behind the score (with per-row model
    predictions) next to the proposal, so every verdict is fully auditable.
    Returns (experiment_id, metrics_or_None).
    """
    feature_code_path = feature_code_path.resolve()
    module = load_feature_module(feature_code_path)
    panel_with_feature, new_feature_columns = module.add_feature(panel.copy())

    experiment_id = journal.record_proposal(
        iteration=iteration,
        signal_name=module.SIGNAL_NAME,
        hypothesis=module.HYPOTHESIS,
        feature_code_path=str(feature_code_path.relative_to(PROJECT_ROOT)),
        feature_columns=list(new_feature_columns),
    )
    try:
        metrics, scored_rows = walk_forward_eval(
            panel_with_feature, list(new_feature_columns),
            half_life_days=config.RECENCY_HALFLIFE_DAYS,
            label_horizon_days=config.LABEL_HORIZON,
            return_scored_rows=True,
        )
    except Exception:
        journal.record_error(experiment_id, traceback.format_exc(limit=5))
        print("  VERDICT: feature evaluation crashed (recorded in journal)")
        return experiment_id, None
    if "error" in metrics:
        journal.record_error(experiment_id, f"evaluator: {metrics['error']}")
        print(f"  VERDICT: evaluator error — {metrics['error']}")
        return experiment_id, None

    oos_csv_path = feature_code_path.parent / "oos_rows.csv"
    scored_rows.to_csv(oos_csv_path, index=False)

    # Phase B context: robustness across the two comparison models, and the
    # per-industry breakdown. The LR pooled number stays the tested_score.
    comparison = compare_models(
        panel_with_feature, list(new_feature_columns),
        half_life_days=config.RECENCY_HALFLIFE_DAYS, label_horizon_days=config.LABEL_HORIZON,
    )
    metrics["models"] = {name: m for name, m in comparison.items() if name != "logistic"}
    metrics["per_industry"] = per_industry_eval(
        panel_with_feature, list(new_feature_columns),
        half_life_days=config.RECENCY_HALFLIFE_DAYS, label_horizon_days=config.LABEL_HORIZON,
    )
    journal.record_verdict(experiment_id, metrics)
    journal.record_session_artifacts(
        experiment_id, oos_csv_path=str(oos_csv_path.relative_to(PROJECT_ROOT))
    )
    print(f"  VERDICT: {module.SIGNAL_NAME} tested_score={metrics['tested_score']:+.4f} "
          f"(n_oos={metrics['n_oos']}, base_rate={metrics['base_rate']})")
    return experiment_id, metrics


def final_holdout_verdict(panel: pd.DataFrame) -> None:
    """Phase D: open the sealed holdout ONCE for the journal's best tested signal.

    The validation->holdout gap is the run's verdict; Gate 1 (spec) passes only
    if the signal still beats the base rate on the holdout.
    """
    from core.evaluator import open_holdout_once
    from core.journal import _connect  # read-only query of the experiments table

    with _connect() as connection:
        best = connection.execute(
            "SELECT * FROM experiments WHERE status = 'tested' AND iteration > 0"
            " ORDER BY tested_score DESC LIMIT 1"
        ).fetchone()
    if best is None:
        print("no tested signals in the journal — nothing to judge")
        return

    print(f"opening the holdout for the best journal signal: {best['signal_name']} "
          f"(validation tested_score {best['tested_score']:+.4f})")
    module = load_feature_module(PROJECT_ROOT / best["feature_code_path"])
    panel_with_feature, new_feature_columns = module.add_feature(panel.copy())

    metrics = open_holdout_once(
        panel_with_feature, list(new_feature_columns),
        half_life_days=config.RECENCY_HALFLIFE_DAYS,
        label_horizon_days=config.LABEL_HORIZON,
        acknowledge_this_is_the_final_run=True,
    )
    verdict = journal.record_holdout_verdict(best["id"], best["tested_score"], metrics)
    gate = "PASSED" if verdict["gate1_passed"] else "FAILED"
    print(f"HOLDOUT VERDICT: holdout_score={verdict['holdout_score']:+.4f} "
          f"(validation {verdict['validation_score']:+.4f}, gap {verdict['gap']:+.4f}) "
          f"— GATE 1 {gate}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=2,
                        help="research iterations to run (spec target is 20-30; start small)")
    parser.add_argument("--budget-usd", type=float, default=5.0,
                        help="hard USD cap PER ITERATION for the researcher session")
    parser.add_argument("--refresh-data", action="store_true",
                        help="refetch the price panel instead of using the disk cache")
    parser.add_argument("--final-verdict", action="store_true",
                        help="open the sealed holdout ONCE for the best journal signal (end of run)")
    parser.add_argument("--push", action="store_true",
                        help="git commit + push journal/proposals after the run (updates the deployed dashboard)")
    arguments = parser.parse_args()

    journal.init_journal()
    panel = build_panel(refresh=arguments.refresh_data)
    print(f"panel ready: {len(panel)} rows, {panel['ticker'].nunique()} tickers")

    if arguments.final_verdict:
        final_holdout_verdict(panel)
        return

    for _ in range(arguments.iterations):
        iteration = journal.next_iteration_number()
        print(f"\n=== ITERATION {iteration} ===")
        proposal_dir = PROPOSALS_DIR / f"iteration_{iteration}"
        proposal_dir.mkdir(parents=True, exist_ok=True)

        transcript_path = proposal_dir / "session_transcript.md"
        session_id, cost = asyncio.run(
            run_researcher_session(iteration, arguments.budget_usd, transcript_path)
        )

        feature_code_path = proposal_dir / "feature.py"
        if not feature_code_path.exists():
            print("  researcher did not produce feature.py — skipping evaluation")
            continue
        experiment_id, metrics = evaluate_proposal(panel, feature_code_path, iteration)
        journal.record_session_artifacts(
            experiment_id, transcript_path=str(transcript_path.relative_to(PROJECT_ROOT)),
            cost_usd=cost,
        )

        # Feed the verdict back to the same session for a short journal reflection.
        if metrics is not None and session_id is not None:
            verdict_summary = json.dumps(metrics)
            try:
                note = asyncio.run(run_reflection(session_id, verdict_summary))
                if note:
                    journal.record_researcher_notes(experiment_id, note)
                    print(f"  reflection: {note[:160]}{'...' if len(note) > 160 else ''}")
            except Exception as reflection_error:
                print(f"  reflection step failed (non-fatal): {reflection_error}")

    print("\nJOURNAL:")
    print(journal.journal_markdown())

    if arguments.push:
        push_results_to_git()


def push_results_to_git() -> None:
    """Commit journal + proposals and push, so the deployed dashboard updates."""
    import subprocess

    subprocess.run(["git", "add", "journal.db", "proposals"], cwd=PROJECT_ROOT, check=True)
    commit = subprocess.run(
        ["git", "commit", "-m", "research run: update journal + proposals"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    if commit.returncode != 0:
        print(f"nothing to push ({commit.stdout.strip() or commit.stderr.strip()})")
        return
    push = subprocess.run(["git", "push"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    print("pushed — deployed dashboard will refresh" if push.returncode == 0
          else f"push failed: {push.stderr.strip()}")


if __name__ == "__main__":
    main()
