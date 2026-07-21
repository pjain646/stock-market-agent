"""Multi-agent research orchestration.

Architecture ported from TradingAgents (analyst team -> bull/bear debate ->
research manager) and PrimoAgent (dedicated news-intelligence agent emitting
quantified features), reimplemented on the Claude Agent SDK this project already
uses. See agents.py for why the debate was retargeted at generalization risk.
"""
from .orchestrator import conversation_json, render_transcript, run_research_pipeline
from .state import FactorProposal, ResearchState, Turn

__all__ = [
    "run_research_pipeline",
    "render_transcript",
    "conversation_json",
    "ResearchState",
    "FactorProposal",
    "Turn",
]
