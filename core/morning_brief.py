"""Morning brief — a PREDICTION-TIME narrative, never a backtested signal.

Same architectural split as `core/live_sentiment.py`, and for the same reason:
this narrates what's happening in the market and the news right now, so
Preyansh can form his own view independently of the model. It NEVER touches
`predicted_up_probability` or the ranked candidate list — no agent scores or
predicts here, only reports (spec §6: "no agent scores or predicts").

Three tiers, deliberately not full-universe coverage every morning (cost
control):
  1. Macro/world — `fetch_market_news` (Finnhub's general-news endpoint, the
     same provider/key already used for per-ticker sentiment, just a
     different endpoint — no new vendor).
  2. Market internals — `market_internals`, pure pandas over the price panel
     `research_pipeline.py` already fetches for candidate ranking. Zero new
     network calls.
  3. Ticker-level news — "everything that matters," not everything:
     `select_brief_tickers` picks the day's movers plus one name per industry
     not already covered, then reuses `live_sentiment.fetch_headlines`.

One LLM call (`_synthesize`) turns all three into brief prose. It authenticates
via whatever the environment provides — a locally logged-in Claude Code
session, or `CLAUDE_CODE_OAUTH_TOKEN` in CI — and never touches
ANTHROPIC_API_KEY, so it draws from subscription usage, not metered billing
(Preyansh's explicit call: no metered spend on the unattended daily cron).
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd

from . import config
from .live_sentiment import fetch_headlines

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

MODEL = "claude-opus-4-8"


def market_internals(panel: pd.DataFrame, industry_map: dict[str, str],
                     top_n: int = 10) -> dict:
    """Day-over-day price moves across the whole universe.

    Zero new network calls — `panel` is the same price data
    `build_live_panel()` already fetched for candidate ranking.

    Returns {"gainers": [...], "losers": [...], "industry_moves": [...]},
    each a list of dicts (ticker/industry/pct_change/as_of, or
    industry/pct_change), sorted by move size.
    """
    prices = panel[["ticker", "date", "adj_close"]].dropna(subset=["adj_close"])
    latest_two = (
        prices.sort_values("date")
        .groupby("ticker", as_index=False, group_keys=False)
        .tail(2)
    )

    moves = []
    for ticker, group in latest_two.groupby("ticker"):
        if len(group) < 2:
            continue  # not enough history yet (e.g. a very new listing)
        prior_close, latest_row = group.iloc[-2]["adj_close"], group.iloc[-1]
        if prior_close == 0:
            continue
        moves.append({
            "ticker": ticker,
            "industry": industry_map.get(ticker, "Unknown"),
            "pct_change": (latest_row["adj_close"] / prior_close) - 1.0,
            "as_of": latest_row["date"].strftime("%Y-%m-%d"),
        })

    if not moves:
        return {"gainers": [], "losers": [], "industry_moves": []}

    moves_df = pd.DataFrame(moves)
    gainers = moves_df.sort_values("pct_change", ascending=False).head(top_n)
    losers = moves_df.sort_values("pct_change", ascending=True).head(top_n)
    industry_moves = (
        moves_df.groupby("industry")["pct_change"].mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    return {
        "gainers": gainers.to_dict("records"),
        "losers": losers.to_dict("records"),
        "industry_moves": industry_moves.to_dict("records"),
    }


def select_brief_tickers(internals: dict, industry_map: dict[str, str],
                         n_movers: int = 15) -> list[str]:
    """"Everything that matters," not everything.

    The day's biggest movers, plus one representative name per industry not
    already covered by a mover, so no sector goes dark without asking Finnhub
    for all ~169 names every morning.
    """
    movers = internals["gainers"][: n_movers // 2] + internals["losers"][: n_movers // 2]
    tickers = [m["ticker"] for m in movers]
    covered_industries = {m["industry"] for m in movers}

    for industry in sorted(set(industry_map.values()) - covered_industries):
        # First ticker alphabetically in the industry — arbitrary but stable;
        # this just needs to be A representative, not THE most important name.
        industry_tickers = sorted(t for t, ind in industry_map.items() if ind == industry)
        if industry_tickers:
            tickers.append(industry_tickers[0])

    seen: set[str] = set()
    return [t for t in tickers if not (t in seen or seen.add(t))]


def fetch_ticker_briefs(tickers: list[str], as_of=None,
                        lookback_days: int = 3) -> dict[str, pd.DataFrame]:
    """Recent headlines per ticker.

    Reuses `live_sentiment.fetch_headlines` with a short lookback (a few
    days) appropriate for "what happened before this morning," not the
    21-day rolling window `live_sentiment` uses for its sentiment score.
    """
    return {
        ticker: fetch_headlines(ticker, as_of=as_of, lookback_days=lookback_days,
                               max_articles=5)
        for ticker in tickers
    }


async def _synthesize(payload: str) -> tuple[dict, float | None]:
    """One LLM call turning raw headlines + computed moves into brief prose.

    Same pattern as `live_sentiment._score_batch`: JSON-only response, a hard
    cost cap, and the query() call reads whatever Claude Code credentials the
    environment provides — it is never pointed at ANTHROPIC_API_KEY directly.
    """
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions,
                                  ResultMessage, TextBlock, query)

    system = (
        "You write a pre-market briefing for a self-directed investor. You are "
        "NOT predicting returns, NOT recommending trades, and NOT scoring any "
        "stock — a separate statistical model already does that elsewhere and "
        "you must not influence it. Just report what's happening, factually.\n"
        "Given raw macro headlines, computed market-internals numbers, and raw "
        "per-ticker headlines, write:\n"
        "  - `macro`: 2-4 sentences on overnight macro/world news that could "
        "move markets today.\n"
        "  - `internals`: 1-2 sentences on today's market internals (movers, "
        "sector rotation) using the numbers given — don't invent numbers.\n"
        "  - `tickers`: one short sentence per ticker naming the single most "
        "material headline, keyed by ticker symbol. Omit a ticker entirely if "
        "it has no material news rather than inventing filler.\n"
        "Reply with ONLY a JSON object with keys `macro`, `internals`, "
        "`tickers`. No prose, no code fence."
    )
    fragments: list[str] = []
    cost: float | None = None
    options = ClaudeAgentOptions(model=MODEL, system_prompt=system,
                                 allowed_tools=[], max_turns=4,
                                 max_budget_usd=1.5)
    async for message in query(prompt=payload, options=options):
        if isinstance(message, AssistantMessage):
            fragments.extend(b.text for b in message.content if isinstance(b, TextBlock))
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd

    text = "\n".join(fragments).strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip()), cost
    except json.JSONDecodeError:
        return {}, cost


def synthesize_brief(market_news: pd.DataFrame, internals: dict,
                     ticker_headlines: dict[str, pd.DataFrame]) -> tuple[dict, float]:
    """Assemble the raw-data payload for the one synthesis LLM call, run it."""
    import asyncio

    sections = []
    if not market_news.empty:
        lines = [f"{row.datetime:%Y-%m-%d %H:%M} | {row.headline}"
                for row in market_news.itertuples()]
        sections.append("=== MACRO/MARKET HEADLINES ===\n" + "\n".join(lines))

    gainers = ", ".join(f"{m['ticker']} {m['pct_change']:+.1%}" for m in internals["gainers"][:10])
    losers = ", ".join(f"{m['ticker']} {m['pct_change']:+.1%}" for m in internals["losers"][:10])
    industries = ", ".join(f"{m['industry']} {m['pct_change']:+.1%}" for m in internals["industry_moves"])
    sections.append(
        "=== MARKET INTERNALS (computed, not narrated — use as-is, don't invent numbers) ===\n"
        f"Top gainers: {gainers}\nTop losers: {losers}\nBy industry: {industries}"
    )

    for ticker, headlines in ticker_headlines.items():
        if headlines.empty:
            continue
        lines = [f"{row.datetime:%Y-%m-%d} | {row.headline}" for row in headlines.itertuples()]
        sections.append(f"=== {ticker} HEADLINES ===\n" + "\n".join(lines))

    payload = "\n\n".join(sections)
    if not payload.strip():
        return {"macro": "", "internals": "", "tickers": {}}, 0.0

    brief, cost = asyncio.run(_synthesize(payload))
    return brief, cost or 0.0


def build_morning_brief(panel: pd.DataFrame, as_of=None) -> tuple[dict, float]:
    """Public entry point — fetch, select, and synthesize the whole brief.

    Mirrors `live_sentiment.score_tickers`'s role: the one function a caller
    needs. Never touches `predicted_up_probability` or the candidate ranking.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "research-methodology" / "scripts"))
    from data import fetch_market_news

    industry_map = config.industry_map()
    internals = market_internals(panel, industry_map)
    market_news = fetch_market_news()
    brief_tickers = select_brief_tickers(internals, industry_map)
    ticker_headlines = fetch_ticker_briefs(brief_tickers, as_of=as_of)

    narrative, cost = synthesize_brief(market_news, internals, ticker_headlines)

    as_of_str = (pd.Timestamp(as_of) if as_of else pd.Timestamp.today()).strftime("%Y-%m-%d")
    # The LLM is only asked (via the system prompt), never forced, to shape
    # `tickers` as an object keyed by ticker — a plain JSON parse success
    # doesn't guarantee that shape. Coerce here so a drifted reply degrades
    # to "no ticker notes" instead of crashing whatever reads the saved file.
    ticker_notes = narrative.get("tickers", {})
    if not isinstance(ticker_notes, dict):
        ticker_notes = {}
    return {
        "as_of": as_of_str,
        "macro": narrative.get("macro", ""),
        "internals_narrative": narrative.get("internals", ""),
        "gainers": internals["gainers"],
        "losers": internals["losers"],
        "industry_moves": internals["industry_moves"],
        "ticker_notes": ticker_notes,
    }, cost


def save_brief(brief: dict, output_path: pathlib.Path) -> None:
    """Persist to disk.

    Deliberately saved under `candidates/` by the caller so the existing
    `push_candidates_to_git()` picks it up for free via its `git add --
    candidates` scope — no change needed to the push path for this feature.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(brief, indent=2, default=str))
