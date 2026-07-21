"""Wires the agents into a pipeline and runs it.

Flow (PrimoAgent's linear pipeline + TradingAgents' bounded debate loop):

    fundamental ─┐
    macro       ─┼─> [analyst team, sequential] ─> bull <-> bear (N rounds)
    sentiment   ─┘                                      │
                                                        v
                                                 research manager
                                                        │
                                                        v
                                            selected factor set

The manager's selection is handed to the feature-writing step in
run_phase_c_loop.py, which is unchanged in how it evaluates: the deterministic
judge still scores whatever gets written, and no agent here can influence a score.
"""
from __future__ import annotations

import time

from .agents import (bear_researcher, bull_researcher, codex_available,
                     external_reviewer, fundamental_analyst, macro_analyst,
                     research_manager)
from .state import ResearchState


async def run_research_pipeline(iteration: int, journal_history: str,
                                debate_rounds: int = 1,
                                budget_usd: float = 5.0,
                                verbose: bool = True,
                                role_journals: dict | None = None,
                                role_facts: dict | None = None,
                                use_external_review: bool = True) -> tuple[ResearchState, float]:
    """Run the full multi-agent pipeline. Returns (state, total_cost_usd).

    `role_journals` / `role_facts` map role name -> that role's context. When
    omitted every agent falls back to the shared `journal_history`, which is
    correct but costs ~9x more per iteration (see journal_digest_for_role).
    """
    state = ResearchState(iteration=iteration, journal_history=journal_history,
                          role_journals=role_journals or {},
                          role_facts=role_facts or {})
    total_cost = 0.0

    def log(msg: str) -> None:
        if verbose:
            print(msg, flush=True)

    # Per-agent budget so one runaway agent cannot eat the whole iteration cap.
    #
    # The floor matters more than the split: every agent pays to READ the journal
    # digest (~10k tokens by iteration 24), which costs real money at Opus input
    # pricing before a single output token. A floor below that makes agents fail
    # on budget the moment they start — which is exactly what happened with the
    # original 0.25 floor. This is a CAP, not an allocation; observed spend is
    # ~$0.10-0.25 per agent, so the team lands well under it in practice.
    n_agents = 2 + (2 * debate_rounds) + 1
    per_agent = max(budget_usd / n_agents, 0.90)

    # No sentiment analyst here, by design. Sentiment is deliberately NOT a
    # backtested axis: the free news feed covers ~1 trailing year against a
    # 2014-2024 panel, so any sentiment factor would be validated on a thin
    # slice and then weighed against decade-long fundamentals as equal evidence.
    # It lives instead in core/live_sentiment.py as a PREDICTION-TIME
    # annotation, where no history is needed and no backtest can be tainted.
    stages = [
        ("fundamental analyst", lambda: fundamental_analyst(state, per_agent)),
        ("macro analyst", lambda: macro_analyst(state, per_agent)),
    ]

    for label, fn in stages:
        started = time.time()
        # Retry once: a failed analyst costs an entire axis (macro, fundamentals,
        # or sentiment) for the whole iteration, which is a much worse outcome
        # than one extra call. Failures here are typically transient (turn caps,
        # transport hiccups), not deterministic.
        for attempt in (1, 2):
            try:
                cost = await fn()
                total_cost += cost or 0.0
                proposal = state.proposals[-1] if state.proposals else None
                flag = "" if (proposal and proposal.data_available) else "  [DATA UNAVAILABLE]"
                retry_note = " (retry)" if attempt == 2 else ""
                log(f"  {label}{retry_note}: {proposal.name if proposal else '?'}{flag} "
                    f"({time.time() - started:.0f}s, ${cost or 0:.2f})")
                break
            except Exception as exc:  # one agent failing must not kill the pipeline
                if attempt == 1:
                    log(f"  {label}: attempt 1 failed ({exc}) — retrying")
                    continue
                state.errors.append(f"{label}: {exc}")
                log(f"  {label}: FAILED after retry — {exc}")

    # Bounded debate: bull opens, bear responds, repeat.
    for round_index in range(debate_rounds):
        for label, fn in (("bull", lambda: bull_researcher(state, per_agent)),
                          ("bear", lambda: bear_researcher(state, per_agent))):
            try:
                cost = await fn()
                total_cost += cost or 0.0
                log(f"  debate r{round_index + 1} {label}: "
                    f"{len(state.current_response)} chars (${cost or 0:.2f})")
            except Exception as exc:
                state.errors.append(f"debate {label}: {exc}")
                log(f"  debate r{round_index + 1} {label}: FAILED — {exc}")

    # Cross-model second opinion before the manager rules. Optional and
    # non-fatal: it bills to a ChatGPT subscription rather than this plan, so
    # when it is unavailable the pipeline simply proceeds without it.
    if use_external_review and codex_available():
        try:
            started = time.time()
            await external_reviewer(state)
            log(f"  external reviewer (Codex): {len(state.external_review)} chars "
                f"({time.time() - started:.0f}s, $0.00 — billed to ChatGPT sub)")
        except Exception as exc:
            state.errors.append(f"external reviewer: {exc}")
            log(f"  external reviewer: unavailable — {exc}")

    try:
        cost = await research_manager(state, per_agent)
        total_cost += cost or 0.0
        log(f"  research manager selected: {state.selected_factors} (${cost or 0:.2f})")
    except Exception as exc:
        state.errors.append(f"research manager: {exc}")
        log(f"  research manager: FAILED — {exc}")

    # Persist what got killed, so the same analyst doesn't re-propose it next
    # iteration and burn a full debate re-litigating a settled call (observed:
    # credit_spread_momentum proposed in iter 24, rejected, proposed again in
    # iter 25 — rejections previously left no trace the next analyst could see).
    if state.selected_factors:
        rejected = [(p.analyst, p.name, state.manager_decision)
                   for p in state.proposals if p.name not in state.selected_factors]
        if rejected:
            from core import journal
            journal.record_rejected_factors(state.iteration, rejected)
            log(f"  recorded {len(rejected)} rejected factor(s) for future iterations")

    return state, total_cost


def conversation_json(state: ResearchState, total_cost: float) -> str:
    """Ordered, structured conversation for the dashboard's group-chat view.

    Kept separate from `render_transcript` (markdown, for humans reading a
    file) because the dashboard renders real chat bubbles via st.chat_message,
    which needs discrete {speaker, label, content} turns, not a markdown blob.
    """
    import json

    return json.dumps({
        "iteration": state.iteration,
        "turns": [
            {"speaker": t.speaker, "label": t.label, "content": t.content,
             "cost_usd": t.cost_usd}
            for t in state.turns
        ],
        "proposals": [
            {"analyst": p.analyst, "name": p.name, "rationale": p.rationale,
             "data_available": p.data_available}
            for p in state.proposals
        ],
        "selected_factors": state.selected_factors,
        "errors": state.errors,
        "total_cost_usd": total_cost,
    }, indent=2)


def render_transcript(state: ResearchState) -> str:
    """Human-readable record of the whole multi-agent exchange, for proposals/."""
    parts = [
        f"# Multi-agent research pipeline — iteration {state.iteration}\n",
        "## Analyst team\n",
        f"### Fundamental analyst\n{state.fundamental_report or '(no output)'}\n",
        f"### Macro analyst\n{state.macro_report or '(no output)'}\n",
        f"### Sentiment analyst\n{state.sentiment_report or '(no output)'}\n",
        "## Proposed factors\n",
    ]
    for proposal in state.proposals:
        parts.append(
            f"- **{proposal.name}** [{proposal.analyst}] "
            f"(data_available={proposal.data_available})\n  {proposal.rationale}\n"
        )
    parts += [
        f"\n## Bull/bear debate ({state.debate_count} turns)\n",
        state.debate_history or "(no debate)",
        "\n\n## Research manager decision\n",
        state.manager_decision or "(no decision)",
        f"\n\n## Selected factors\n{', '.join(state.selected_factors) or '(none)'}\n",
    ]
    if state.errors:
        parts.append(f"\n## Errors\n" + "\n".join(f"- {e}" for e in state.errors))
    return "\n".join(parts)
