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

from core import candidates as candidates_module, config, journal  # noqa: E402
from core.labeling import add_forward_direction_label  # noqa: E402
from core.splits import assign_time_split  # noqa: E402
from core.evaluator import compare_models, per_industry_eval, walk_forward_eval  # noqa: E402
from core.untrusted_exec import secrets_hidden  # noqa: E402

PANEL_CACHE_PATH = PROJECT_ROOT / "data_cache" / "panel.pkl"
PROPOSALS_DIR = PROJECT_ROOT / "proposals"
# NOT in data_cache/ (that's gitignored, regenerable local cache) — the
# deployed dashboard needs this file to show real output, so it's tracked,
# same principle as journal.db and proposals/.
CANDIDATES_PATH = PROJECT_ROOT / "candidates" / "candidates.csv"

# The contract every proposed feature module must satisfy. This text is shown
# to the researcher verbatim, and enforced when the module is loaded.
#
# Bundle, not single signal (post-Gate-1-failure redesign): a best-of-N search
# over single signals is a noisy max-order-statistic — the exact overfitting
# pattern that failed the campaign's first holdout (validation +0.0521,
# holdout -0.0118). Testing 2-3 deliberately orthogonal factors together as
# ONE combined model each iteration is the fix: the evaluator already scores
# whatever's in feature_columns as one model (core/evaluator.py's
# walk_forward_eval takes a list), so no evaluator change was needed — only
# this contract and the prompt below, which now require a bundle.
FEATURE_CONTRACT = '''\
SIGNAL_NAME = "a_short_snake_case_bundle_name"
HYPOTHESIS = (
    "For EACH factor in the bundle: 1-2 sentences on its own economic rationale. "
    "PLUS one sentence per factor pair on why you believe they're orthogonal — "
    "i.e. each captures a genuinely different source of edge, not a variation "
    "on the same idea."
)

def add_feature(panel):
    """Compute ALL factors in the bundle, point-in-time safe.

    Args:
        panel: pandas DataFrame with columns [date, ticker, industry, adj_close,
               label, split] (one row per ticker per trading day).
    Returns:
        (panel_with_new_columns, list_of_new_feature_column_names)
        — one column per factor in the bundle; the evaluator scores all of
        them together as a single combined model, not factor-by-factor.
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


def build_live_panel() -> pd.DataFrame:
    """Fetch prices through TODAY, for candidate ranking only.

    `build_panel()` uses `config.END`, a fixed historical window — correct for
    reproducible backtests, wrong for "today's picks" (which would otherwise be
    stuck on whatever date research happened to freeze). This fetches fresh, up
    to the actual current date, so the unlabeled tail is genuinely live. No
    train/validation/holdout split is applied — candidate ranking doesn't need
    one; only `positive_signals`' feature code and the label's NaN/non-NaN
    split (labeled = train on it, unlabeled = predict on it) matter here.
    """
    import datetime

    from data import fetch_prices

    tickers = config.all_tickers()
    today = datetime.date.today().isoformat()
    print(f"fetching {len(tickers)} tickers {config.START}..{today} (live, uncached) ...")
    panel = fetch_prices(tickers, config.START, today)
    panel["industry"] = panel["ticker"].map(config.industry_map())
    return add_forward_direction_label(panel, forward_horizon_days=config.LABEL_HORIZON)


def _news_source_available() -> bool:
    """Is a point-in-time news source actually usable right now?

    Gates the sentiment analyst: with no key it must report the axis unbuildable
    rather than invent a proxy (the discipline that stopped iteration 23 from
    shipping a lookahead-tainted factor).
    """
    import os

    if os.environ.get("FINNHUB_API_KEY"):
        return True
    keys_file = PROJECT_ROOT / "keys.local.json"
    if keys_file.exists():
        try:
            return bool(json.loads(keys_file.read_text()).get("FINNHUB_API_KEY"))
        except (json.JSONDecodeError, OSError):
            return False
    return False


def researcher_prompt(iteration: int, journal_history: str,
                      team_brief: str = "") -> str:
    """The task given to the researcher each iteration.

    `team_brief` is the multi-agent pipeline's output (analyst proposals, the
    bull/bear debate verdict, and the research manager's selected factor set)
    when --multi-agent is on. It front-loads the DECISION of what to build; this
    prompt still owns the implementation, so the feature contract, smoke-test,
    and evaluation path are unchanged either way.
    """
    brief_block = f"""
YOUR RESEARCH TEAM HAS ALREADY MET. Their decision is binding for this iteration:

{team_brief}

Implement exactly the factor set the research manager selected. Do not add
factors they rejected, and do not silently substitute a different mechanism —
if the manager's selection turns out to be unbuildable point-in-time-safe, say
so plainly in your code comments and implement the buildable subset.
""" if team_brief else ""

    return f"""You are the researcher in an automated quant research loop. This is iteration {iteration}.
Work under the research-methodology skill's discipline at all times.

CAMPAIGN CONTEXT: the first campaign's best single signal (validation +0.0521)
FAILED Gate 1 on the sealed holdout (-0.0118). A best-of-N search over single
signals is a noisy max — it finds artifacts that look real in validation and
don't generalize. The fix: stop searching for one winning signal. Propose
BUNDLES of orthogonal factors instead, tested together as one combined model.
The universe was also expanded (~166 liquid names across 11 sectors, up from
24 across 3) to raise the effective sample size behind every score.
{brief_block}
YOUR JOB THIS ITERATION — propose and implement a BUNDLE of 2-3 ORTHOGONAL factors,
tested together as ONE combined model:

1. Read your journal history (below). Build on what worked; do not repeat what failed.
   If a prior single-factor signal showed a real (if weak) mechanism, it's a candidate
   to pair with something uncorrelated now, not to re-test alone.
2. Pick 2-3 factors that each have their own clear ECONOMIC rationale, AND that you
   believe are ORTHOGONAL to each other — each capturing a genuinely different source
   of predictive edge (e.g. one macro/timing factor + one fundamental/quality factor +
   one price/momentum factor), not three variations on the same idea. State explicitly
   why you believe each pair is low-correlation, not just why each factor alone might work.
   Two genuinely orthogonal factors beats three overlapping ones — do not pad the bundle
   just to hit 3.
   - The labeled panel is at data_cache/panel.pkl (relative to your cwd, which IS the
     project root) — a pickled pandas DataFrame with columns [date, ticker, industry,
     adj_close, label, forward_return, split]. label = did the price rise over the next
     21 trading days; forward_return = the realized move itself (used only for scoring).
     NEVER use label, forward_return, or split to build a feature — all three contain
     the future.
   - Bundled point-in-time fetchers (import from research-methodology/scripts/data.py,
     also relative to your cwd): fetch_prices, fetch_fundamentals (SEC EDGAR,
     filed_date-stamped), fetch_earnings, fetch_insider_transactions (Form 4),
     fetch_analyst_estimates, fetch_analyst_grades, fetch_macro_series (FRED). All
     responses are disk-cached; re-calls are free.
   - These two paths are correct and stable every iteration — do NOT spend turns
     re-discovering them with `find` or similar; go straight to reading/importing them.
     A prior iteration's proposals/ directory (if you want to see the pattern another
     signal used) is at proposals/iteration_N/feature.py for any iteration N in the
     journal below.
3. Write your feature code to proposals/iteration_{iteration}/feature.py with EXACTLY this contract:

{FEATURE_CONTRACT}

   Every value must only use information public on that row's date (fundamentals by
   filed_date, insider trades by filing date — the fetchers give you the right columns).
4. Smoke-test your module: run it against the panel with python via bash, confirm it returns
   ALL the new columns and each is populated (not all-NaN) for each factor, then stop.

HARD BOUNDARIES:
- You do NOT run the evaluator, you do NOT score your own signal, and you NEVER touch
  holdout rows. The deterministic judge runs after you finish; its verdict lands in the
  journal for your next iteration. It scores your whole bundle as ONE model, not
  factor-by-factor — there is no partial credit for one good factor in a weak bundle.
- Propose a BUNDLE of 2-3 orthogonal factors, not a single signal.
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
                                 transcript_path: pathlib.Path,
                                 team_brief: str = "") -> tuple[str | None, float | None]:
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
        async for message in query(
                prompt=researcher_prompt(iteration, journal.journal_markdown(), team_brief),
                options=options):
            for line in _transcript_lines(message):
                transcript_file.write(line + "\n")
            if isinstance(message, ResultMessage):
                session_id, cost = message.session_id, message.total_cost_usd
                print(f"  researcher session done: subtype={message.subtype}"
                      + (f", cost=${cost:.2f}" if cost else ""))
    return session_id, cost


async def run_reflection(session_id: str, verdict_summary: str, budget_usd: float = 1.0) -> tuple[str, float | None]:
    """Resume the researcher's session with the verdict; get a short journal note back.

    The researcher saw its own exploration; the evaluator's number is news to it.
    This closes the loop the spec describes: the journal records not just the
    score but the researcher's own read on WHY it worked or failed.
    """
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

    options = ClaudeAgentOptions(
        model="claude-opus-4-8",
        cwd=str(PROJECT_ROOT),
        resume=session_id,                    # same session -> full research context intact
        allowed_tools=[],                     # reflection is thought, not action
        max_budget_usd=budget_usd,
        max_turns=4,
    )
    # The resumed session can carry stale state — notably a pending background
    # Bash notification, which the model would otherwise answer INSTEAD of the
    # verdict (observed polluting iterations 19 and 24: "that notification is
    # just cleanup of a stale background find"). The journal is the agent's
    # memory, so a junk note degrades every future iteration that reads it.
    prompt = (
        "IGNORE any pending notifications, background-task messages, or unfinished "
        "business from earlier in this session. They are irrelevant and must not be "
        "mentioned. Do not recap what you built — that is already recorded.\n\n"
        f"The deterministic evaluator has scored your signal:\n{verdict_summary}\n\n"
        "For the journal (your future iterations will read this): in 2-4 sentences, "
        "why do you think it got THIS SCORE, and what should the next iteration do "
        "differently because of it? Start your reply with the score itself. "
        "Reply with only the note text."
    )
    note_fragments = []
    reflection_cost = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            note_fragments.extend(b.text for b in message.content if isinstance(b, TextBlock))
        elif isinstance(message, ResultMessage):
            reflection_cost = message.total_cost_usd
    note = " ".join(fragment.strip() for fragment in note_fragments).strip()

    # Reject a note that answered something other than the verdict rather than
    # writing it to the journal as if it were a real reflection.
    pollution_markers = ("background command", "background task", "no action needed",
                         "already complete", "stale background")
    lowered = note.lower()
    if any(marker in lowered for marker in pollution_markers):
        print("  reflection: polluted by stale session state — discarded")
        return "", reflection_cost
    return note, reflection_cost



def load_feature_module(feature_code_path: pathlib.Path):
    """Import the researcher's feature module and validate the contract."""
    spec = importlib.util.spec_from_file_location("proposed_feature", feature_code_path)
    module = importlib.util.module_from_spec(spec)
    with secrets_hidden():
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
    with secrets_hidden():
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
    with secrets_hidden():
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


def rank_stock_candidates(panel: pd.DataFrame) -> None:
    """Phase D+ (task #10): combine every proven signal into ranked, live picks.

    This is the product's actual output: not "which signals scored well" but
    "which stocks look good right now, and why." Trains on every labeled row
    (train+validation+holdout combined — appropriate once holdout has served
    its one-time testing purpose) and predicts on the live unlabeled tail.
    """
    from core.journal import _connect

    with _connect() as connection:
        signals = candidates_module.positive_signals(connection)
    if not signals:
        print("no positive validated signals in the journal yet — nothing to combine")
        return

    print(f"combining {len(signals)} proven signal(s): "
          + ", ".join(f"{s['signal_name']} ({s['tested_score']:+.4f})" for s in signals))
    combined_panel, feature_columns = candidates_module.build_combined_panel(
        panel, signals, PROJECT_ROOT, load_feature_module
    )
    ranked = candidates_module.rank_candidates(
        combined_panel, feature_columns, half_life_days=config.RECENCY_HALFLIFE_DAYS
    )
    if ranked.empty:
        print("no live (unlabeled) rows with all combined features present — nothing to rank")
        return

    candidates_module.save_candidates(ranked, signals, CANDIDATES_PATH)
    print(f"\nTOP CANDIDATES (saved to {CANDIDATES_PATH.relative_to(PROJECT_ROOT)}):")
    print(ranked[["ticker", "date", "predicted_up_probability", "top_driver"]].head(10)
          .to_string(index=False))


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
    parser.add_argument("--rank-candidates", action="store_true",
                        help="combine all proven signals into ranked, live stock candidates")
    parser.add_argument("--push", action="store_true",
                        help="git commit + push journal/proposals after the run (updates the deployed dashboard)")
    parser.add_argument("--multi-agent", action="store_true",
                        help="run the multi-agent research team (analysts -> bull/bear debate -> "
                             "research manager) to decide the factor set before implementing it")
    parser.add_argument("--debate-rounds", type=int, default=1,
                        help="bull/bear debate rounds when --multi-agent is on")
    arguments = parser.parse_args()

    journal.init_journal()

    if arguments.rank_candidates:
        rank_stock_candidates(build_live_panel())
        return

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

        # Multi-agent phase (optional): the research team decides WHAT to build,
        # then the researcher session below implements it. Splitting the budget
        # keeps --budget-usd a true per-iteration cap across both phases.
        team_brief, team_cost = "", 0.0
        if arguments.multi_agent:
            from core.orchestration import conversation_json, render_transcript, run_research_pipeline

            print("  [multi-agent] research team convening")
            from core.orchestration import context as agent_context

            # Per-role context: each agent reads only its own slice of the
            # journal plus the grounding facts its axis needs. Sending every
            # agent the full digest cost ~47k tokens/iteration; this is ~5k.
            rejected = journal.rejected_factors_digest()
            role_journals = {
                role: (journal.journal_digest_for_role(role)
                       + ("\n\n" + rejected if rejected else ""))
                for role in ("fundamental", "macro", "bull", "bear", "manager")
            }
            # Concept coverage is hash-keyed on the ticker set, so this is a
            # ~2min compute the first time a universe is seen and instant after.
            # It exists because iteration 24 built a gross-profitability factor
            # without knowing GrossProfit is filed by only 42% of the universe.
            role_facts = {
                "fundamental": agent_context.fundamental_facts(
                    panel, agent_context.compute_concept_coverage(panel)),
                "macro": agent_context.macro_series_facts(),
                "bear": agent_context.bear_facts([]),
            }

            team_state, team_cost = asyncio.run(run_research_pipeline(
                iteration=iteration,
                # Shared fallback only; role_journals above is what agents read.
                journal_history=journal.journal_digest(),
                role_journals=role_journals,
                role_facts=role_facts,
                debate_rounds=arguments.debate_rounds,
                budget_usd=arguments.budget_usd * 0.4,
            ))
            (proposal_dir / "team_transcript.md").write_text(render_transcript(team_state))
            (proposal_dir / "team_conversation.json").write_text(
                conversation_json(team_state, team_cost))
            team_brief = team_state.manager_decision

        session_id, cost = asyncio.run(
            run_researcher_session(iteration, arguments.budget_usd - team_cost,
                                   transcript_path, team_brief=team_brief)
        )
        cost = (cost or 0.0) + team_cost

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
                note, reflection_cost = asyncio.run(run_reflection(session_id, verdict_summary))
                if note:
                    journal.record_researcher_notes(experiment_id, note)
                    print(f"  reflection: {note[:160]}{'...' if len(note) > 160 else ''}")
                # Roll reflection cost into the experiment's recorded cost, so
                # cost_usd reflects the FULL spend for this iteration, not just
                # the main research session (this was silently undercounting).
                if reflection_cost:
                    total_cost = (cost or 0) + reflection_cost
                    journal.record_session_artifacts(experiment_id, cost_usd=total_cost)
                    print(f"  reflection cost: ${reflection_cost:.2f} (iteration total: ${total_cost:.2f})")
            except Exception as reflection_error:
                print(f"  reflection step failed (non-fatal): {reflection_error}")

        # Push after EVERY iteration, not once at the end — a crash/timeout on
        # iteration 9 of 12 shouldn't cost iterations 1-8 too (learned this the
        # expensive way tonight: a failed once-at-the-end push discarded two
        # full paid research sessions).
        if arguments.push:
            push_results_to_git()

    print("\nJOURNAL:")
    print(journal.journal_markdown())


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
