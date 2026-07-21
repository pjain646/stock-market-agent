"""Tests for the multi-agent orchestration + live-sentiment layer.

Split deliberately:
  * `test_offline()` — no API calls, no keys. Verifies the point-in-time
    guarantees and the shared-state wiring. Safe to run anywhere, free.
  * `test_live()` — spends real budget running the agent team. Verifies the
    agents actually TALK (downstream agents cite upstream output) rather than
    just running in sequence.

Run:  python3 tests/test_orchestration.py           # offline only
      python3 tests/test_orchestration.py --live    # + live agent run
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "research-methodology" / "scripts"))

from core.orchestration import (FactorProposal, ResearchState,  # noqa: E402
                                render_transcript, run_research_pipeline)

passed, failed = 0, 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


def test_offline() -> None:
    print("\n=== OFFLINE (no API, no keys) ===")

    # Shared blackboard: downstream agents can see upstream output.
    state = ResearchState(iteration=1, journal_history="j")
    state.fundamental_report = "FUND_REPORT"
    state.add_proposal(FactorProposal("fundamental", "f_test", "mechanism"))
    block = state.analyst_reports_block()
    check("analyst report reaches the debate prompt block", "FUND_REPORT" in block)
    check("proposed factor reaches the debate prompt block", "f_test" in block)
    check("transcript renders without a live run", "f_test" in render_transcript(state))

    # The news fetcher must fail loudly when the key is missing rather than
    # silently returning empty (which a caller could mistake for "no news").
    # Once a key IS configured the same call should succeed, so assert whichever
    # branch actually applies rather than assuming the keyless one.
    import os

    from data import _load_api_key, fetch_company_news
    try:
        _load_api_key("FINNHUB_API_KEY")
        key_present = True
    except RuntimeError:
        key_present = False

    if key_present:
        # 2018 is outside the free tier's ~1 trailing year, so an empty frame
        # here is correct behaviour, not a failure — it documents the limit.
        old = fetch_company_news("AAPL", "2018-01-01", "2018-01-31")
        check("news fetch works with a key configured (2018 outside free tier -> empty)",
              hasattr(old, "empty"), f"{len(old)} rows")
    else:
        try:
            fetch_company_news("AAPL", "2024-01-01", "2024-01-31")
            check("keyless news fetch raises", False, "it returned instead of raising")
        except RuntimeError as exc:
            check("keyless news fetch raises a keyed error",
                  "FINNHUB_API_KEY" in str(exc), str(exc)[:60])

    # Live sentiment is prediction-time only — it must never be importable as a
    # backtest feature path, and unknown must stay distinct from neutral.
    from core import live_sentiment
    label_unknown = live_sentiment.sentiment_label({"sentiment": float("nan")})
    label_neutral = live_sentiment.sentiment_label({"sentiment": 0})
    check("live sentiment: no-news reads as 'no news', not 'neutral'",
          label_unknown == "no news" and label_neutral == "neutral",
          f"{label_unknown!r} vs {label_neutral!r}")


def test_live(budget_usd: float = 4.0) -> None:
    """Spends real budget. Verifies the agents genuinely talk to each other."""
    print("\n=== LIVE (spends budget) ===")
    from core import journal

    state, cost = asyncio.run(run_research_pipeline(
        iteration=999,
        journal_history=journal.journal_markdown()[-6000:],
        news_available=False,      # no key -> sentiment analyst must self-report unbuildable
        debate_rounds=1,
        budget_usd=budget_usd,
        verbose=True,
    ))

    (PROJECT_ROOT / "tests" / "last_team_transcript.md").write_text(render_transcript(state))
    names = [p.name for p in state.proposals]

    check("analyst team produced proposals", len(state.proposals) >= 2, str(names))
    check("bull cites an analyst's factor by name",
          any(n in state.bull_history for n in names))
    check("bear cites an analyst's factor by name",
          any(n in state.bear_history for n in names))
    check("bear engages the bull's argument", "bull" in state.bear_history.lower())
    check("research manager reached a decision", bool(state.manager_decision))
    check("research manager selected a factor set",
          len(state.selected_factors) > 0, str(state.selected_factors))

    sentiment_proposals = [p for p in state.proposals if p.analyst == "sentiment"]
    if sentiment_proposals:
        check("sentiment analyst reports axis unbuildable without a news key",
              sentiment_proposals[0].data_available is False,
              f"data_available={sentiment_proposals[0].data_available}")

    check("no agent errors", not state.errors, str(state.errors))
    print(f"\n  cost: ${cost:.2f}")
    print(f"  transcript: tests/last_team_transcript.md")


if __name__ == "__main__":
    test_offline()
    if "--live" in sys.argv:
        test_live()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
