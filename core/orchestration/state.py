"""Shared state passed between agents in the multi-agent research pipeline.

Ported from the shared-state pattern used by PrimoAgent (LangGraph `AgentState`)
and TradingAgents (`investment_debate_state`): every agent reads the whole state
and writes its own slice, so downstream agents see upstream output. That is what
makes this multi-agent rather than N independent prompts — the debate agents
literally cannot function without the analyst reports already in state.

Kept as a plain dataclass (no LangGraph dependency): the graph here is a fixed
sequence plus one bounded debate loop, which does not need a graph engine.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field


@dataclass
class FactorProposal:
    """One analyst's proposed factor."""
    analyst: str                 # which agent proposed it
    name: str                    # short snake_case factor name
    rationale: str               # the economic mechanism
    data_available: bool = True  # False if the analyst found it unbuildable PIT-safe
    notes: str = ""


@dataclass
class Turn:
    """One discrete message in the conversation — what the group-chat dashboard renders.

    Kept separate from the accumulated `*_history` strings below (which exist
    because that's the shape each agent's prompt actually needs) so the
    dashboard can render true chat bubbles instead of re-parsing markdown.
    """
    speaker: str        # "fundamental" | "macro" | "sentiment" | "bull" | "bear" | "manager"
    label: str          # display name, e.g. "Fundamental Analyst"
    content: str
    cost_usd: float | None = None


@dataclass
class ResearchState:
    """The blackboard every agent reads from and writes to."""
    iteration: int
    journal_history: str = ""

    # Analyst phase — each writes one slice.
    fundamental_report: str = ""
    macro_report: str = ""
    sentiment_report: str = ""
    proposals: list[FactorProposal] = field(default_factory=list)

    # Debate phase — accumulates, TradingAgents-style.
    debate_history: str = ""
    bull_history: str = ""
    bear_history: str = ""
    current_response: str = ""
    debate_count: int = 0

    # Cross-model second opinion (Codex). Advisory input to the manager, not a
    # tiebreaker — a different model is a different perspective, not a better one.
    external_review: str = ""

    # Synthesis phase.
    manager_decision: str = ""
    selected_factors: list[str] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)

    # Ordered conversation for the dashboard's group-chat view.
    turns: list[Turn] = field(default_factory=list)

    # Per-role context, injected by the caller. Each agent reads only its own
    # slice: the unfiltered journal is ~9.5k tokens and having all 5 agents read
    # all of it cost ~47k tokens per iteration, an order of magnitude more than
    # the charter or the grounding facts combined.
    role_journals: dict[str, str] = field(default_factory=dict)
    role_facts: dict[str, str] = field(default_factory=dict)

    def add_proposal(self, proposal: FactorProposal) -> None:
        self.proposals.append(proposal)

    def journal_for(self, role: str) -> str:
        """This role's journal slice, falling back to the shared history."""
        return self.role_journals.get(role) or self.journal_history

    def facts_for(self, role: str) -> str:
        """This role's grounding facts; empty string when none were supplied."""
        return self.role_facts.get(role, "")

    def external_review_block(self) -> str:
        """The cross-model reviewer's opinion, formatted for the manager."""
        if not self.external_review:
            return ""
        return ("EXTERNAL REVIEWER (a DIFFERENT model family, no stake in the "
                "outcome — weigh this as one more input, not as a tiebreaker):\n"
                f"{self.external_review}")

    def add_turn(self, speaker: str, label: str, content: str,
                cost_usd: float | None = None) -> None:
        self.turns.append(Turn(speaker=speaker, label=label, content=content,
                               cost_usd=cost_usd))

    def analyst_reports_block(self) -> str:
        """All analyst output, formatted for the debate agents' prompts."""
        parts = []
        if self.fundamental_report:
            parts.append(f"FUNDAMENTAL ANALYST REPORT:\n{self.fundamental_report}")
        if self.macro_report:
            parts.append(f"MACRO ANALYST REPORT:\n{self.macro_report}")
        if self.sentiment_report:
            parts.append(f"SENTIMENT ANALYST REPORT:\n{self.sentiment_report}")
        if self.proposals:
            listed = "\n".join(
                f"  - [{p.analyst}] {p.name} (data_available={p.data_available}): {p.rationale}"
                for p in self.proposals
            )
            parts.append(f"PROPOSED FACTORS:\n{listed}")
        return "\n\n".join(parts) or "(no analyst reports yet)"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def summary(self) -> str:
        return json.dumps(
            {
                "iteration": self.iteration,
                "proposals": [p.name for p in self.proposals],
                "debate_rounds": self.debate_count,
                "selected_factors": self.selected_factors,
                "errors": self.errors,
            },
            indent=2,
        )
