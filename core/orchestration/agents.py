"""The agent roster for the multi-agent research pipeline.

Role specialization is ported from TradingAgents (analyst team -> bull/bear
researcher debate -> research manager verdict) and PrimoAgent (a dedicated
news-intelligence agent emitting QUANTIFIED features rather than prose).

Adapted deliberately in two ways, because the reference repos publish no
out-of-sample validation and we do:

  1. The debate is about whether a proposed factor bundle will GENERALIZE, not
     about whether to buy a stock. The bear's explicit job is to attack
     overfitting risk — the failure mode that killed campaign 1 (validation
     +0.0521 -> sealed holdout -0.0118).
  2. No agent ever scores a signal. The deterministic evaluator still does that,
     exactly as before. Agents only decide WHAT to test.

The SDK dependency is isolated to `_llm_call` so the harness stays swappable
(spec 6 orchestration seam).
"""
from __future__ import annotations

import pathlib

from .state import FactorProposal, ResearchState

MODEL = "claude-opus-4-8"

_CHARTER_PATH = pathlib.Path(__file__).resolve().parent / "TEAM_CHARTER.md"


def team_charter() -> str:
    """Shared context prepended to every agent's system prompt.

    Single source of truth for roles, hierarchy, hard rules, and what the
    campaign has already learned — so those never drift between agents or get
    duplicated into individual prompts. Read fresh each call so editing the
    markdown changes team behaviour without touching Python.
    """
    try:
        return _CHARTER_PATH.read_text()
    except OSError:
        return ""


def _system_for(role_instructions: str) -> str:
    """Charter + this role's specific instructions."""
    charter = team_charter()
    return f"{charter}\n\n---\n\n## Your specific role\n\n{role_instructions}" if charter \
        else role_instructions


async def _llm_call(prompt: str, system: str, max_turns: int = 6,
                    budget_usd: float = 1.0, allowed_tools: list[str] | None = None,
                    cwd: str | None = None) -> tuple[str, float | None]:
    """One agent turn. The ONLY SDK-aware function in this module.

    Returns (text, cost_usd). Agents that need to look at data get tools;
    pure-reasoning agents (the debaters) get none.

    `max_turns` is deliberately loose. These agents have no tools, so they
    "should" answer in one turn — but a long reasoning pass can spill across
    turns, and a tight cap kills the agent mid-thought (observed: the macro
    analyst dying on `max_turns=2` while the fundamental analyst cleared it on
    the same setting). Spend is bounded by `budget_usd` regardless, so a loose
    turn cap costs nothing when unused and prevents a whole axis going missing.
    """
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions,
                                  ResultMessage, TextBlock, query)

    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system,
        allowed_tools=allowed_tools or [],
        max_turns=max_turns,
        max_budget_usd=budget_usd,
        **({"cwd": cwd} if cwd else {}),
    )

    fragments: list[str] = []
    cost: float | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            fragments.extend(b.text for b in message.content if isinstance(b, TextBlock))
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd
    return "\n".join(f.strip() for f in fragments).strip(), cost


# Codex is installed by npm to a prefix that is not always on PATH.
_CODEX_CANDIDATES = ("codex", str(pathlib.Path.home() / ".npm-global" / "bin" / "codex"))


def codex_available() -> bool:
    """Is the Codex CLI installed AND logged in?"""
    import shutil
    import subprocess

    for candidate in _CODEX_CANDIDATES:
        if candidate == "codex" and not shutil.which(candidate):
            continue
        if candidate != "codex" and not pathlib.Path(candidate).exists():
            continue
        try:
            result = subprocess.run([candidate, "login", "status"],
                                    capture_output=True, text=True, timeout=20)
            # Codex reports login status on STDERR, not stdout — check both
            # rather than assuming, or a working install reads as unavailable.
            combined = (result.stdout + result.stderr).lower()
            if "logged in" in combined:
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def _codex_binary() -> str | None:
    import shutil

    for candidate in _CODEX_CANDIDATES:
        if candidate == "codex" and shutil.which(candidate):
            return candidate
        if candidate != "codex" and pathlib.Path(candidate).exists():
            return candidate
    return None


def _codex_call(prompt: str, timeout_s: int = 300) -> str:
    """Run one prompt through the Codex CLI (a DIFFERENT model family).

    This is the point of having it: the bull and bear are otherwise the same
    model arguing with itself, which tends to share blind spots. A genuinely
    different model reviewing the bundle catches a different error class.

    Billed to the user's ChatGPT subscription, not to API credits or the Claude
    plan — so this voice is free at the margin, unlike every other agent here.
    """
    import subprocess

    binary = _codex_binary()
    if not binary:
        raise RuntimeError("codex CLI not found")

    result = subprocess.run(
        [binary, "exec", "--sandbox", "read-only"],
        input=prompt, capture_output=True, text=True, timeout=timeout_s,
    )
    if result.returncode != 0:
        raise RuntimeError(f"codex exited {result.returncode}: {result.stderr[:300]}")

    # `codex exec` echoes banner/token lines around the actual reply; keep the
    # substantive middle rather than the wrapper.
    lines = [line for line in result.stdout.splitlines()
             if line.strip() and not line.strip().startswith(("codex", "tokens used"))
             and not line.strip().isdigit()]
    return "\n".join(lines).strip()


# --------------------------------------------------------------------------- #
# Analyst team — each owns ONE axis, so their proposals are orthogonal by
# construction rather than by the single researcher's self-assessment.
# --------------------------------------------------------------------------- #

# The charter (TEAM_CHARTER.md) now carries the rules, hierarchy, and campaign
# history that used to be duplicated here and inside the bear's prompt. What
# remains is only the output contract, which is genuinely role-specific.
_ANALYST_RULES = """You are an ANALYST. Propose exactly ONE factor on your
assigned axis — never on another analyst's axis.

Reply in this exact format:
FACTOR: <short_snake_case_name>
DATA_AVAILABLE: <true|false>
RATIONALE: <2-4 sentences naming the mechanism>
REPORT: <your reasoning, including what you ruled out and why>"""


def _parse_analyst(text: str, analyst: str) -> tuple[FactorProposal, str]:
    """Pull the structured fields out of an analyst reply."""
    name, rationale, report, available = "", "", text, True
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("factor:"):
            name = line.split(":", 1)[1].strip()
        elif low.startswith("data_available:"):
            available = "false" not in low
        elif low.startswith("rationale:"):
            rationale = line.split(":", 1)[1].strip()
        elif low.startswith("report:"):
            report = line.split(":", 1)[1].strip()
    if not name:
        name = f"{analyst}_unnamed"
    return FactorProposal(analyst=analyst, name=name, rationale=rationale,
                          data_available=available), report


async def fundamental_analyst(state: ResearchState, budget_usd: float = 1.0):
    """Owns the balance-sheet / profitability / valuation axis."""
    prompt = f"""Iteration {state.iteration}. You own the FUNDAMENTALS axis
(capital allocation, profitability, quality, valuation).

{state.journal_for("fundamental")}

{state.facts_for("fundamental")}

Propose ONE fundamental factor. Prefer something the journal has NOT exhausted.
Note: within-industry ranking has repeatedly been the load-bearing transform.
Check the coverage table before proposing — a factor built on a sparse concept
contributes nothing exactly where coverage is missing."""
    text, cost = await _llm_call(prompt, _system_for(_ANALYST_RULES), budget_usd=budget_usd)
    proposal, report = _parse_analyst(text, "fundamental")
    state.fundamental_report = report
    state.add_proposal(proposal)
    state.add_turn("fundamental", "Fundamental Analyst", text, cost)
    return cost


async def macro_analyst(state: ResearchState, budget_usd: float = 1.0):
    """Owns the regime / discount-rate / market-conditions axis."""
    prompt = f"""Iteration {state.iteration}. You own the MACRO axis (rates,
curve, volatility, credit, financial conditions).

{state.journal_for("macro")}

{state.facts_for("macro")}

Propose ONE macro factor. The journal shows macro timing has been the strongest
axis so far but is concentrated in rate-coupled sectors, and that sign-STABLE
conditions generalize while regime-dependent sign flips do not."""
    text, cost = await _llm_call(prompt, _system_for(_ANALYST_RULES), budget_usd=budget_usd)
    proposal, report = _parse_analyst(text, "macro")
    state.macro_report = report
    state.add_proposal(proposal)
    state.add_turn("macro", "Macro Analyst", text, cost)
    return cost


_NO_NEWS_SOURCE_REPORT = (
    "SENTIMENT AXIS UNBUILDABLE: no historical, point-in-time-safe news source is "
    "wired up. FMP's analyst-grades endpoint is paywalled, fetch_analyst_estimates "
    "returns only a CURRENT snapshot (using it historically would be lookahead), and "
    "Form-4 insider data is too sparse across 166 names x 10 years. This is a "
    "deterministic fact about data availability, not a judgment call, so no LLM call "
    "is spent reaching it — same conclusion iteration 23 reached by testing it directly."
)


async def sentiment_analyst(state: ResearchState, budget_usd: float = 1.0,
                            news_available: bool = False):
    """Owns the news / sentiment axis (PrimoAgent's news-intelligence role).

    `news_available` reflects whether a historical, timestamped news source is
    actually wired up. When it is not, this agent is REQUIRED to report the axis
    unbuildable rather than invent a proxy — the exact discipline that stopped
    iteration 23 shipping a lookahead-tainted factor.

    That "unbuildable" outcome is deterministic given news_available=False — the
    prompt below leaves no other legal answer — so when it's False this SKIPS the
    LLM call entirely rather than paying ~$0.20-0.30 for a fixed non-answer. Real
    reasoning only happens once a news source actually exists to reason about.
    """
    if not news_available:
        state.sentiment_report = _NO_NEWS_SOURCE_REPORT
        state.add_proposal(FactorProposal(
            analyst="sentiment", name="sentiment_unavailable",
            rationale="No point-in-time-safe news source wired up.",
            data_available=False, notes=_NO_NEWS_SOURCE_REPORT,
        ))
        state.add_turn("sentiment", "Sentiment Analyst", _NO_NEWS_SOURCE_REPORT, 0.0)
        return 0.0

    # news_available is True past this point (the False case returned above).
    availability = (
        "A point-in-time news feed IS available: fetch_company_news(ticker, "
        "from_date, to_date) returns headlines/summaries timestamped by "
        "publication, so you may query a trailing window ending on each row's "
        "date with no lookahead."
    )
    prompt = f"""Iteration {state.iteration}. You own the SENTIMENT axis (news,
narrative, investor positioning) for a 166-ticker, 11-sector US large-cap
universe predicting 21-trading-day forward direction.

{availability}

Journal of everything tried so far:
{state.journal_history}

Propose ONE sentiment factor. If you propose one, specify how it would be
QUANTIFIED into numeric columns (the reference implementation extracts integer
features in [-2,+2] such as sentiment, price_impact_potential, trend_direction,
earnings_impact, investor_confidence, risk_profile_change)."""
    text, cost = await _llm_call(prompt, _ANALYST_RULES, budget_usd=budget_usd)
    proposal, report = _parse_analyst(text, "sentiment")
    state.sentiment_report = report
    state.add_proposal(proposal)
    state.add_turn("sentiment", "Sentiment Analyst", text, cost)
    return cost


# --------------------------------------------------------------------------- #
# Debate — TradingAgents' bull/bear loop, retargeted at generalization risk.
# --------------------------------------------------------------------------- #

async def bull_researcher(state: ResearchState, budget_usd: float = 0.6):
    prompt = f"""You are the BULL researcher. Argue the case FOR testing this
factor bundle as proposed.

{state.analyst_reports_block()}

Debate so far:
{state.debate_history or "(you open the debate)"}

Last bear argument: {state.current_response or "(none yet)"}

Make the strongest case that these factors are genuinely orthogonal, each has a
real economic mechanism, and the bundle is worth spending an iteration on.
Engage the bear's specific objections directly. Be concrete, not cheerful."""
    text, cost = await _llm_call(
        prompt, _system_for(
            "You are the BULL researcher. You do not propose new factors — you "
            "make the strongest honest case FOR what the analysts put on the "
            "table, and engage the bear's objections directly."),
        budget_usd=budget_usd)
    argument = f"Bull Researcher: {text}"
    state.debate_history += "\n" + argument
    state.bull_history += "\n" + argument
    state.current_response = argument
    state.debate_count += 1
    state.add_turn("bull", "Bull Researcher", text, cost)
    return cost


async def bear_researcher(state: ResearchState, budget_usd: float = 0.6):
    prompt = f"""You are the BEAR researcher. Your job is to find the reason this
bundle will FAIL out-of-sample.

{state.analyst_reports_block()}

Debate so far:
{state.debate_history or "(none yet)"}

Last bull argument: {state.current_response or "(none yet)"}

{state.facts_for("bear")}

Attack in these directions specifically:
- Are two of these factors actually the SAME axis wearing different names?
- Which factor is most likely a validation-set artifact rather than a mechanism?
- Is any of this implicitly fit to what already worked, i.e. selection pressure?
- Does any factor secretly need information unavailable at the row's date?
Be specific and cite the proposals. Do not be contrarian for its own sake."""
    text, cost = await _llm_call(
        prompt, _system_for(
            "You are the BEAR researcher and the team's hard skeptic. Your job "
            "is to find the reason this bundle will FAIL out-of-sample. A debate "
            "where you find nothing is a failed debate. Concrete objections "
            "only — never a numeric correlation you have not been shown."),
        budget_usd=budget_usd)
    argument = f"Bear Researcher: {text}"
    state.debate_history += "\n" + argument
    state.bear_history += "\n" + argument
    state.current_response = argument
    state.debate_count += 1
    state.add_turn("bear", "Bear Researcher", text, cost)
    return cost


async def external_reviewer(state: ResearchState):
    """Cross-model review via Codex — a genuinely different model family.

    Every other agent here is the same underlying model, so the bull and bear
    largely share priors and blind spots: an error neither is disposed to notice
    survives the debate intact. A different model reviewing the same bundle is
    the cheapest available correction for that, and since it bills to the user's
    ChatGPT subscription it costs nothing at the margin.

    Deliberately advisory, not authoritative. It sees the proposals and the
    debate, and its opinion goes to the Research Manager as ONE input — a
    different model is not a better model, and treating it as a tiebreaker would
    just move the blind spot rather than remove it.
    """
    prompt = f"""You are an external reviewer from a different firm, brought in for a
second opinion on a quant research decision. You have no stake in the outcome.

The team researches factor bundles for a 166-ticker, 11-sector US large-cap
universe, predicting 21-trading-day forward direction. A deterministic evaluator
(purged walk-forward + a sealed holdout) scores whatever gets built — you cannot
influence that score and neither can they.

Context you need: this project's first campaign produced a signal scoring +0.0521
on validation that scored -0.0118 on the sealed holdout. The cause was selection
pressure — keeping the best of many tries. Scores have since plateaued at
+0.057-0.065 across many permutations of the same axes.

{state.analyst_reports_block()}

THE INTERNAL DEBATE:
{state.debate_history}

In under 250 words:
1. What is the single strongest objection the internal debate MISSED?
2. Is any proposed factor likely to be a validation artifact rather than a real
   mechanism? Name which and why.
3. Would you test this bundle, or not?

Be concrete and terse. If the internal debate already covered everything well,
say so plainly rather than inventing an objection."""
    try:
        text = _codex_call(prompt)
    except Exception as exc:  # never let the optional voice break the pipeline
        raise RuntimeError(f"codex review unavailable: {exc}") from exc

    state.external_review = text
    state.add_turn("external", "External Reviewer (Codex)", text, 0.0)
    return 0.0


async def research_manager(state: ResearchState, budget_usd: float = 0.8):
    """Judges the debate and picks the final factor set (TradingAgents' Research Manager)."""
    prompt = f"""You are the RESEARCH MANAGER. Read the analyst reports and the
bull/bear debate, then decide the final factor set for this iteration.

{state.analyst_reports_block()}

FULL DEBATE:
{state.debate_history}

{state.external_review_block()}

Decide:
- Which factors go into the bundle (2-3 max; two genuinely orthogonal factors
  beat three overlapping ones — do NOT pad).
- Drop any factor the bear showed is redundant, unbuildable point-in-time-safe,
  or likely a validation artifact.
- If the bear's overfitting objection is decisive, say so.

On bundle size — read this before selecting ONE factor. A lone factor is exactly
the shape that failed Gate 1 (+0.0521 validation -> -0.0118 holdout): with one
factor, the iteration becomes another draw in a best-of-N search, which is the
selection pressure this whole design exists to avoid. Two mediocre but genuinely
orthogonal factors generalize better than one clean factor, because the bundle
is not a max over tries. Selecting a single factor is permitted only if you
argue explicitly why no second axis survives — "the others were weaker" is not
sufficient, since a weaker orthogonal factor still breaks the best-of-N pattern.

Reply in this exact format:
SELECTED: <comma-separated factor names>
REASONING: <why these, why the others were dropped, what the bear got right. If
you selected only one, justify why no second axis survived.>"""
    text, cost = await _llm_call(
        prompt, _system_for(
            "You are the RESEARCH MANAGER. Your ruling is final for this "
            "iteration. Be decisive and evidence-led — name what the bear got "
            "right rather than splitting the difference."),
        budget_usd=budget_usd)
    state.manager_decision = text
    for line in text.splitlines():
        if line.strip().lower().startswith("selected:"):
            state.selected_factors = [
                f.strip() for f in line.split(":", 1)[1].split(",") if f.strip()
            ]
            break
    state.add_turn("manager", "Research Manager", text, cost)
    return cost
