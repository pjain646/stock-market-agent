"""Morning brief — a PREDICTION-TIME narrative, never a backtested signal.

Same architectural split as `core/live_sentiment.py`, and for the same reason:
this narrates what's happening in the market and the news right now, so
Preyansh can form his own view independently of the model. It NEVER touches
`predicted_up_probability` or the ranked candidate list — no agent scores or
predicts here, only reports (spec §6: "no agent scores or predicts").

Four tiers, deliberately not full-universe coverage every morning (cost
control). Tiers 1 and 3 each merge in a SECOND, differently-sourced feed —
Alpha Vantage's NEWS_SENTIMENT endpoint (`fetch_alpha_vantage_market_news`/
`fetch_alpha_vantage_company_news`) — alongside Finnhub, for outlet
diversity: Finnhub's general feed skews heavily Reuters (paywalled, filtered
out of `top_articles`), and Alpha Vantage in practice carries essentially
none. Not a new vendor either — `ALPHA_VANTAGE_API_KEY` was already wired up
for the earnings fallback in `research-methodology/scripts/data.py`. Both AV
functions degrade silently to "Finnhub only" on a missing key or an AV
outage (they never raise), and stay within its 25-calls/day free tier by
batching every ticker into ONE call rather than one call each.
  1. Macro/world — `fetch_market_news` (Finnhub) + `fetch_alpha_vantage_market_news`.
  2. Market internals — `market_internals`, pure pandas over the price panel
     `research_pipeline.py` already fetches for candidate ranking. Zero new
     network calls.
  3. Ticker-level news — "everything that matters," not everything:
     `select_brief_tickers` picks the day's movers plus one name per industry
     not already covered, then `fetch_ticker_briefs` merges
     `live_sentiment.fetch_headlines` (Finnhub) with
     `fetch_alpha_vantage_company_news`.
  4. Watch list — `build_watchlist_articles`, guaranteed (not competitively
     curated) coverage for Preyansh's own tracked tickers (`config.WATCHLIST_*`),
     excluded from tier 3's output so a name isn't shown twice.

One LLM call (`_synthesize`) turns all three into brief prose, and also picks
the most material headlines by id (`top_articles`) out of everything fetched —
`_index_headlines`/`synthesize_brief` resolve those ids back to their ORIGINAL
Finnhub records, so a linked article's url can never be something the LLM
invented. It authenticates via whatever the environment provides — a locally
logged-in Claude Code session, or `CLAUDE_CODE_OAUTH_TOKEN` in CI — and never
touches ANTHROPIC_API_KEY, so it draws from subscription usage, not metered
billing (Preyansh's explicit call: no metered spend on the unattended daily
cron).
"""
from __future__ import annotations

import json
import pathlib
import re
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
    """Recent headlines per ticker, from Finnhub AND Alpha Vantage merged.

    Finnhub via `live_sentiment.fetch_headlines`, short lookback (a few
    days) appropriate for "what happened before this morning," not the
    21-day rolling window `live_sentiment` uses for its sentiment score.

    Alpha Vantage's `fetch_alpha_vantage_company_news` is merged in (deduped
    by url) as a second, differently-sourced feed — ONE call covers every
    ticker passed in here, never one call per ticker, since its free tier is
    25 calls/day. A missing key or an AV outage degrades silently to
    Finnhub-only (that function never raises), so this never fails BECAUSE
    of the supplemental source.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "research-methodology" / "scripts"))
    from data import fetch_alpha_vantage_company_news

    finnhub_by_ticker = {
        ticker: fetch_headlines(ticker, as_of=as_of, lookback_days=lookback_days,
                               max_articles=5)
        for ticker in tickers
    }
    finnhub_total = sum(len(df) for df in finnhub_by_ticker.values())
    av_all = fetch_alpha_vantage_company_news(tickers)

    merged: dict[str, pd.DataFrame] = {}
    merged_total = 0
    for ticker in tickers:
        parts = [finnhub_by_ticker[ticker]]
        if not av_all.empty:
            parts.append(av_all[av_all["ticker"] == ticker])
        combined = pd.concat(parts, ignore_index=True)
        if not combined.empty:
            combined = (combined.drop_duplicates(subset=["url"])
                       .sort_values("datetime", ascending=False)
                       .reset_index(drop=True))
        merged[ticker] = combined
        merged_total += len(combined)
    print(f"  ticker news pool ({len(tickers)} tickers): {finnhub_total} Finnhub + "
          f"{len(av_all)} Alpha Vantage -> {merged_total} after url-dedup")
    return merged


def _mentions_ticker(text: str, ticker: str, aliases: list[str]) -> bool:
    """True if `text` actually names this company, not just a symbol a news
    API loosely tagged it with. Finnhub's and Alpha Vantage's per-ticker
    endpoints both occasionally return an article that only mentions the
    ticker in passing (a comparison piece, a "which stocks are moving"
    roundup) — this catches the obvious mismatches cheaply, no extra API
    call, by requiring the ticker's own symbol (whole word) or one of its
    `config.WATCHLIST_ALIASES` names to appear in the text."""
    text = text or ""
    if re.search(rf"\b{re.escape(ticker)}\b", text, re.IGNORECASE):
        return True
    return any(alias.lower() in text.lower() for alias in aliases)


def build_watchlist_articles(as_of=None, max_per_ticker: int = 3) -> dict[str, list[dict]]:
    """News for Preyansh's personal watch list (`config.WATCHLIST_*`).

    Deliberately NOT routed through the LLM's competitive `top_articles`
    ranking in `synthesize_brief` — that step rations to ~15 slots across the
    WHOLE universe, which could starve an individual watch-list name some
    morning. This guarantees every watch-list ticker gets its own coverage,
    every day, independent of what else is happening in the market.

    Reuters is still filtered out where possible (same paywall reasoning as
    `synthesize_brief`), but — unlike the general Top stories feed, which can
    just skip to the next-best story — a watch-list ticker with only Reuters
    coverage that day falls back to showing it anyway: for a name Preyansh is
    actively watching, a paywalled link beats no link at all.
    """
    tickers = list(dict.fromkeys(config.WATCHLIST_BENCHMARKS + config.WATCHLIST_TICKERS))
    headlines_by_ticker = fetch_ticker_briefs(tickers, as_of=as_of, lookback_days=3)

    articles_by_ticker: dict[str, list[dict]] = {}
    for ticker, headlines in headlines_by_ticker.items():
        if headlines.empty:
            articles_by_ticker[ticker] = []
            continue
        aliases = config.WATCHLIST_ALIASES.get(ticker, [])
        records = [
            {"ticker": ticker, "headline": row.headline, "source": row.source,
             "url": row.url, "datetime": row.datetime.isoformat()}
            for row in headlines.sort_values("datetime", ascending=False).itertuples()
            if _mentions_ticker(f"{row.headline} {getattr(row, 'summary', '')}", ticker, aliases)
        ]
        non_reuters = [r for r in records if "reuters" not in (r["source"] or "").lower()]
        # No fallback to Reuters-only or off-topic records here if `records`
        # itself is empty (unlike the non_reuters-vs-records fallback below)
        # — an off-topic headline is worse than none, so an empty result
        # after the relevance filter just means no headlines are shown.
        articles_by_ticker[ticker] = (non_reuters or records)[:max_per_ticker]
    return articles_by_ticker


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
        "Given raw macro headlines and raw per-ticker headlines, each prefixed "
        "with a bracketed id and source like [17](Reuters), plus computed "
        "market-internals numbers, write:\n"
        "  - `macro_bullets`: 3-5 short, single-sentence bullets, each a "
        "DISTINCT overnight macro/world theme that could move markets today — "
        "not a paragraph, not multiple sentences per bullet. Fewer than 3 if "
        "fewer distinct themes are genuinely there.\n"
        "  - `internals`: 1-2 sentences on today's market internals (movers, "
        "sector rotation) using the numbers given — don't invent numbers.\n"
        "  - `tickers`: one short sentence per ticker naming the single most "
        "material headline, keyed by ticker symbol. Omit a ticker entirely if "
        "it has no material news rather than inventing filler.\n"
        "  - `top_articles`: an array of the bracketed ids (integers) of the "
        "most material headlines across BOTH the macro and per-ticker "
        "sections combined, ranked most-material first. You are given far "
        "more headlines than you need, so aim for AT LEAST 10 — go below 10 "
        "only if the fetched headlines genuinely don't contain that many "
        "distinct material stories, which should be rare. Up to 20. Never "
        "pad with filler/duplicates just to hit a count, but do not "
        "under-pick either when there is clearly enough real material. SKIP "
        "any headline whose source is Reuters — it requires a paid "
        "subscription to read, so it must never be picked here even if it's "
        "the most material story; choose the next-best non-Reuters headline "
        "covering that story instead (this is exactly why you're given more "
        "headlines than the 10-20 you'll pick — there's room to skip past "
        "Reuters and still hit the floor). Reuters headlines are still fair "
        "game for `macro_bullets`/`internals`/`tickers` prose above, just "
        "never as a `top_articles` id.\n"
        "Reply with ONLY a JSON object with keys `macro_bullets`, `internals`, "
        "`tickers`, `top_articles`. No prose, no code fence."
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


def _index_headlines(market_news: pd.DataFrame,
                     ticker_headlines: dict[str, pd.DataFrame]
                     ) -> tuple[str | None, list[str], dict[int, dict]]:
    """Assign each raw headline a stable integer id so the synthesis LLM can
    point at "which headlines matter" by id (`[17]`) instead of retyping a
    url. Ids are resolved back to the ORIGINAL fetched record afterward —
    the actual url/source/datetime an "article" carries downstream always
    comes straight from Finnhub, never from the LLM, so a hallucinated or
    mangled link can't reach the dashboard.

    Returns (macro_section_text_or_None, [per-ticker section texts], id_map).
    """
    id_map: dict[int, dict] = {}
    next_id = 1

    macro_section = None
    if not market_news.empty:
        lines = []
        for row in market_news.itertuples():
            id_map[next_id] = {
                "ticker": None, "headline": row.headline, "source": row.source,
                "url": row.url, "datetime": row.datetime.isoformat(),
            }
            lines.append(f"[{next_id}]({row.source}) {row.datetime:%Y-%m-%d %H:%M} | {row.headline}")
            next_id += 1
        macro_section = "=== MACRO/MARKET HEADLINES ===\n" + "\n".join(lines)

    ticker_sections = []
    for ticker, headlines in ticker_headlines.items():
        if headlines.empty:
            continue
        lines = []
        for row in headlines.itertuples():
            id_map[next_id] = {
                "ticker": ticker, "headline": row.headline, "source": row.source,
                "url": row.url, "datetime": row.datetime.isoformat(),
            }
            lines.append(f"[{next_id}]({row.source}) {row.datetime:%Y-%m-%d} | {row.headline}")
            next_id += 1
        ticker_sections.append(f"=== {ticker} HEADLINES ===\n" + "\n".join(lines))

    return macro_section, ticker_sections, id_map


def synthesize_brief(market_news: pd.DataFrame, internals: dict,
                     ticker_headlines: dict[str, pd.DataFrame]
                     ) -> tuple[dict, float, list[dict]]:
    """Assemble the raw-data payload for the one synthesis LLM call, run it,
    and resolve the LLM's selected article ids back to their real records."""
    import asyncio

    macro_section, ticker_sections, id_map = _index_headlines(market_news, ticker_headlines)

    sections = []
    if macro_section:
        sections.append(macro_section)

    gainers = ", ".join(f"{m['ticker']} {m['pct_change']:+.1%}" for m in internals["gainers"][:10])
    losers = ", ".join(f"{m['ticker']} {m['pct_change']:+.1%}" for m in internals["losers"][:10])
    industries = ", ".join(f"{m['industry']} {m['pct_change']:+.1%}" for m in internals["industry_moves"])
    sections.append(
        "=== MARKET INTERNALS (computed, not narrated — use as-is, don't invent numbers) ===\n"
        f"Top gainers: {gainers}\nTop losers: {losers}\nBy industry: {industries}"
    )
    sections.extend(ticker_sections)

    payload = "\n\n".join(sections)
    if not payload.strip():
        return {"macro_bullets": [], "internals": "", "tickers": {}}, 0.0, []

    narrative, cost = asyncio.run(_synthesize(payload))

    raw_ids = narrative.get("top_articles", []) if isinstance(narrative, dict) else []
    articles: list[dict] = []
    seen_ids: set[int] = set()
    for raw_id in raw_ids if isinstance(raw_ids, list) else []:
        try:
            article_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if article_id not in id_map or article_id in seen_ids:
            continue
        record = id_map[article_id]
        # Reuters requires a paid subscription to read — never surface it as
        # a clickable link, even though its headlines still inform the prose
        # above. Enforced here too, not just via the system prompt, since a
        # prompt is a request, not a guarantee.
        if "reuters" in (record.get("source") or "").lower():
            continue
        seen_ids.add(article_id)
        articles.append(record)

    return narrative, cost or 0.0, articles[:20]


def build_morning_brief(panel: pd.DataFrame, as_of=None) -> tuple[dict, float]:
    """Public entry point — fetch, select, and synthesize the whole brief.

    Mirrors `live_sentiment.score_tickers`'s role: the one function a caller
    needs. Never touches `predicted_up_probability` or the candidate ranking.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "research-methodology" / "scripts"))
    from data import fetch_alpha_vantage_market_news, fetch_market_news

    from .timing import timed

    industry_map = config.display_industry_map()
    with timed("market_internals (pandas, no network)"):
        internals = market_internals(panel, industry_map)

    with timed("fetch_market_news (Finnhub)"):
        # Reuters dominates Finnhub's general-news feed in practice, and all
        # of it gets skipped for top_articles (see _synthesize's system
        # prompt) — a wider raw pull gives the LLM enough non-Reuters
        # alternatives left to still clear the 10-article floor.
        market_news = fetch_market_news(max_articles=50)
    finnhub_market_count = len(market_news)
    with timed("fetch_alpha_vantage_market_news"):
        # Merged in as a second, differently-sourced pool (zero Reuters in
        # practice) — degrades silently to Finnhub-only if AV has no key or
        # is down, since that function never raises.
        av_market_news = fetch_alpha_vantage_market_news()
    if not av_market_news.empty:
        market_news = (pd.concat([market_news, av_market_news], ignore_index=True)
                       .drop_duplicates(subset=["url"])
                       .sort_values("datetime", ascending=False)
                       .reset_index(drop=True))
    print(f"  macro news pool: {finnhub_market_count} Finnhub + {len(av_market_news)} Alpha Vantage "
          f"-> {len(market_news)} after url-dedup")

    brief_tickers = select_brief_tickers(internals, industry_map)
    with timed(f"fetch_ticker_briefs — movers ({len(brief_tickers)} tickers, Finnhub+AV)"):
        ticker_headlines = fetch_ticker_briefs(brief_tickers, as_of=as_of)

    with timed("synthesize_brief (the one LLM call)"):
        narrative, cost, articles = synthesize_brief(market_news, internals, ticker_headlines)

    with timed("build_watchlist_articles (Finnhub+AV, watch list tickers)"):
        watchlist_articles = build_watchlist_articles(as_of=as_of)
    # Top stories is "what else is happening" — a watch-list name already
    # gets its own guaranteed section below, so drop it here rather than
    # showing it twice.
    watchlist_set = set(config.WATCHLIST_BENCHMARKS) | set(config.WATCHLIST_TICKERS)
    articles = [a for a in articles if a.get("ticker") not in watchlist_set]

    as_of_str = (pd.Timestamp(as_of) if as_of else pd.Timestamp.today()).strftime("%Y-%m-%d")
    # The LLM is only asked (via the system prompt), never forced, to shape
    # `tickers` as an object keyed by ticker — a plain JSON parse success
    # doesn't guarantee that shape. Coerce here so a drifted reply degrades
    # to "no ticker notes" instead of crashing whatever reads the saved file.
    ticker_notes = narrative.get("tickers", {})
    if not isinstance(ticker_notes, dict):
        ticker_notes = {}
    macro_bullets = narrative.get("macro_bullets", [])
    if not isinstance(macro_bullets, list):
        macro_bullets = []
    macro_bullets = [b.strip() for b in macro_bullets if isinstance(b, str) and b.strip()]
    return {
        "as_of": as_of_str,
        "macro_bullets": macro_bullets,
        "internals_narrative": narrative.get("internals", ""),
        "gainers": internals["gainers"],
        "losers": internals["losers"],
        "industry_moves": internals["industry_moves"],
        "ticker_notes": ticker_notes,
        "articles": articles,
        "watchlist_articles": watchlist_articles,
    }, cost


def save_brief(brief: dict, output_path: pathlib.Path) -> None:
    """Persist to disk.

    Deliberately saved under `candidates/` by the caller so the existing
    `push_candidates_to_git()` picks it up for free via its `git add --
    candidates` scope — no change needed to the push path for this feature.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(brief, indent=2, default=str))
