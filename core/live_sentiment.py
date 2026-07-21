"""Live news sentiment — a PREDICTION-TIME annotation, never a backtested signal.

Deliberate architectural split, and the reason this module exists separately
from `core/sentiment.py`:

  Finnhub's free tier serves ~1 trailing year of company news, but the research
  panel spans 2014-2024. A backtested sentiment factor would therefore be
  validated on a thin recent slice and then compared against decade-long
  fundamental factors as if the two were equal evidence. Rather than invent a
  credibility discount to paper over that, sentiment is kept OUT of the signal
  pipeline entirely: no sentiment feature is ever scored by the evaluator, ever
  enters a bundle, or can ever influence a tested_score or a Gate 1 verdict.

  Instead it answers a different, honest question at the moment a prediction is
  actually made: "the model likes this name on fundamentals and macro — what is
  the news saying about it RIGHT NOW?" That needs no history at all, so the
  1-year limit is irrelevant, and there is no lookahead risk because there is no
  backtest to leak into.

Read `core/sentiment.py` for the point-in-time machinery used if a sentiment
factor is ever backtested properly (it would need a paid historical feed).
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
_CACHE_DIR = pathlib.Path.home() / ".cache" / "stock_research_live_sentiment"

# Same quantified vocabulary as core/sentiment.py so the two stay comparable if
# a historical backtest is ever wired up.
LIVE_FEATURES = ["sentiment", "price_impact_potential", "trend_direction",
                 "investor_confidence", "risk_profile_change"]

MODEL = "claude-opus-4-8"


def _cache_path(ticker: str, as_of: str, lookback_days: int) -> pathlib.Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{ticker}__{as_of}__{lookback_days}d.json"


def fetch_headlines(ticker: str, as_of=None, lookback_days: int = 21,
                    max_articles: int = 25) -> pd.DataFrame:
    """Recent headlines for one ticker, ending at `as_of` (default: today)."""
    sys.path.insert(0, str(PROJECT_ROOT / "research-methodology" / "scripts"))
    from data import fetch_company_news

    end = pd.Timestamp(as_of).normalize() if as_of else pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=lookback_days)
    news = fetch_company_news(ticker, start, end)
    if news.empty:
        return news
    # Newest first — if we have to truncate, keep the most recent.
    return news.sort_values("datetime", ascending=False).head(max_articles)


async def _score_batch(payload: str) -> tuple[dict, float | None]:
    """One LLM call scoring several tickers' headlines at once.

    Batched deliberately: scoring per-ticker would be one call per candidate,
    which for a 20-name ranked list is 20 calls every time the dashboard is
    refreshed. Batching keeps the whole annotation to a single call.
    """
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions,
                                  ResultMessage, TextBlock, query)

    system = (
        "You score financial news sentiment for a quant dashboard. You are "
        "annotating a prediction that was already made by a statistical model — "
        "you are NOT predicting returns and NOT overriding the model. Report "
        "what the news says, not what you think the stock will do.\n"
        "For each ticker output integers in [-2,+2] for: sentiment, "
        "price_impact_potential, trend_direction, investor_confidence, "
        "risk_profile_change. Use 0 when the news is genuinely neutral or thin. "
        "Add a one-sentence `summary` naming the single most material item.\n"
        "Reply with ONLY a JSON object keyed by ticker. No prose, no code fence."
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
    # Models sometimes wrap JSON in a fence despite instructions.
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip()), cost
    except json.JSONDecodeError:
        return {}, cost


def score_tickers(tickers: list[str], as_of=None, lookback_days: int = 21,
                  use_cache: bool = True) -> tuple[pd.DataFrame, float]:
    """Fetch + score live news sentiment for several tickers.

    Returns (DataFrame, cost_usd). One row per ticker, with NaN scores where
    there is no news coverage — never 0, which would read as "neutral news"
    when the truth is "no news".
    """
    as_of_str = (pd.Timestamp(as_of) if as_of else pd.Timestamp.today()).strftime("%Y-%m-%d")

    cached, to_score, headline_counts = {}, {}, {}
    for ticker in tickers:
        path = _cache_path(ticker, as_of_str, lookback_days)
        if use_cache and path.exists():
            cached[ticker] = json.loads(path.read_text())
            continue
        news = fetch_headlines(ticker, as_of, lookback_days)
        headline_counts[ticker] = len(news)
        if news.empty:
            continue
        lines = [f"{row.datetime:%Y-%m-%d} | {row.headline}" for row in news.itertuples()]
        to_score[ticker] = "\n".join(lines)

    cost = 0.0
    if to_score:
        import asyncio

        payload = "\n\n".join(
            f"=== {ticker} ({len(block.splitlines())} recent headlines) ===\n{block}"
            for ticker, block in to_score.items()
        )
        scores, call_cost = asyncio.run(_score_batch(payload))
        cost = call_cost or 0.0
        for ticker in to_score:
            record = scores.get(ticker, {})
            record["n_articles"] = headline_counts.get(ticker, 0)
            cached[ticker] = record
            if use_cache:
                _cache_path(ticker, as_of_str, lookback_days).write_text(json.dumps(record))

    rows = []
    for ticker in tickers:
        record = cached.get(ticker, {})
        row = {"ticker": ticker,
               "n_articles": record.get("n_articles", headline_counts.get(ticker, 0)),
               "summary": record.get("summary", "")}
        for feature in LIVE_FEATURES:
            value = record.get(feature)
            try:
                row[feature] = float(min(max(int(value), -2), 2))
            except (TypeError, ValueError):
                row[feature] = float("nan")   # unknown, NOT neutral
        rows.append(row)
    return pd.DataFrame(rows), cost


def sentiment_label(row) -> str:
    """Short human label for the dashboard, or a clear 'no coverage' marker."""
    value = row.get("sentiment")
    if value is None or pd.isna(value):
        return "no news"
    return {2: "very positive", 1: "positive", 0: "neutral",
            -1: "negative", -2: "very negative"}.get(int(value), "unknown")
