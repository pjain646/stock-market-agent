"""Per-role grounding facts, computed deterministically and injected per agent.

Two design decisions worth stating, because both were deliberate:

WHY INJECTED, NOT TOOL-CALLED. These agents could be given tools to look this
up themselves, but the queries are entirely predictable per role, and every tool
round-trip costs an extra turn. Turn-cap and budget exhaustion were the two
failure modes that killed agents repeatedly in early runs, so a fact that can be
computed once for free is not worth a turn to fetch.

WHY PER-ROLE, NOT SHARED. A shared blob makes every agent pay to read facts only
one of them needs. The fundamental analyst does not need FRED series coverage;
the macro analyst does not need SEC concept coverage. Splitting it means each
agent reads roughly a third of what a shared block would cost.

Everything here is derived from `panel.pkl` (already in memory when the pipeline
runs) or from a cheap metadata call, so nothing is cached and nothing goes stale.
"""
from __future__ import annotations

import pandas as pd


def panel_facts(panel: pd.DataFrame) -> str:
    """Universe shape — cheap, always fresh, useful to every analyst."""
    by_sector = panel.groupby("industry").agg(
        rows=("ticker", "size"), tickers=("ticker", "nunique"))
    lines = [
        f"UNIVERSE: {len(panel):,} rows, {panel['ticker'].nunique()} tickers, "
        f"{panel['date'].min():%Y-%m-%d} to {panel['date'].max():%Y-%m-%d}",
        "Rows/tickers per sector (thin sectors produce unstable per-sector scores):",
    ]
    for sector, row in by_sector.sort_values("rows", ascending=False).iterrows():
        lines.append(f"  {sector}: {int(row.rows):,} rows / {int(row.tickers)} tickers")
    return "\n".join(lines)


def fundamental_facts(panel: pd.DataFrame, concept_coverage: dict | None = None) -> str:
    """What the fundamental analyst needs: which SEC concepts are actually usable.

    `concept_coverage` maps concept -> fraction of tickers with any data. Pass it
    when available; when absent this still reports the sector shape, which is the
    part that is free.

    The motivating failure: an analyst proposed a gross-profitability factor
    without knowing GrossProfit is absent for banks/utilities/REITs, so the
    feature came back NaN for roughly half the panel — discovered only AFTER it
    was built and scored.
    """
    parts = [panel_facts(panel)]
    if concept_coverage:
        parts.append(
            "\nSEC CONCEPT COVERAGE (fraction of tickers with ANY filed value; a "
            "low number means the factor will be NaN for most of the panel and "
            "contribute nothing exactly where coverage is missing):")
        for concept, fraction in sorted(concept_coverage.items(),
                                        key=lambda kv: -kv[1]):
            flag = "  <-- SPARSE" if fraction < 0.6 else ""
            parts.append(f"  {concept}: {fraction:.0%}{flag}")
    return "\n".join(parts)


# FRED series the bundled fetcher can retrieve, with the axis each represents.
# Listed rather than fetched: the set is stable, and the macro analyst's real
# need is "what CAN I ask for", not the observation counts.
KNOWN_FRED_SERIES = {
    "DGS10": "10y Treasury yield (rate level)",
    "DGS2": "2y Treasury yield (short rate)",
    "T10Y2Y": "10y-2y spread (curve slope)",
    "VIXCLS": "VIX (equity vol / risk premium)",
    "BAMLH0A0HYM2": "high-yield OAS (credit spread)",
    "BAMLC0A0CM": "investment-grade OAS (credit spread)",
    "DTWEXBGS": "trade-weighted USD index",
    "T10YIE": "10y breakeven inflation",
    "UNRATE": "unemployment rate (monthly)",
    "INDPRO": "industrial production (monthly)",
}


def macro_series_facts() -> str:
    """What the macro analyst can actually fetch, and the caveat that matters."""
    lines = ["FRED SERIES AVAILABLE via fetch_macro_series():"]
    for series_id, description in KNOWN_FRED_SERIES.items():
        lines.append(f"  {series_id}: {description}")
    lines.append(
        "\nEFFECTIVE SAMPLE SIZE WARNING: a macro factor is a single time-series "
        "shared by every name, so its effective sample size is the number of "
        "independent CYCLES in 2014-2024 — roughly 3-5 for rates or credit — NOT "
        "the 458,011 panel rows. A sign that looks stable across 3 cycles is one "
        "degree of freedom, not confirmation. Weight claims accordingly.")
    return "\n".join(lines)


def macro_facts(series_coverage: dict | None = None) -> str:
    """What the macro analyst needs: which FRED series exist and over what span.

    `series_coverage` maps series id -> (start, end, n_observations).
    """
    if not series_coverage:
        return ("FRED series coverage unavailable this run — state explicitly if "
                "your factor depends on a series you have not confirmed exists.")
    lines = ["FRED SERIES AVAILABLE (id: span, observations). A macro factor's "
             "EFFECTIVE sample size is the number of independent CYCLES in the "
             "span, not the row count of the panel — a series with 3-5 cycles "
             "supports far weaker claims than its observation count suggests:"]
    for series_id, (start, end, n) in sorted(series_coverage.items()):
        lines.append(f"  {series_id}: {start} to {end}, {n:,} obs")
    return "\n".join(lines)


def bear_facts(proposed_names: list[str], correlations: dict | None = None) -> str:
    """What the bear needs: measured correlations, so objections cite numbers.

    `correlations` maps "factor_a|factor_b" -> pearson r. Without it the bear can
    still argue mechanism, but cannot claim a redundancy it has not measured —
    and it should say so rather than assert one.
    """
    if not correlations:
        return ("No measured correlations available for this bundle. You may "
                "argue redundancy from MECHANISM, but do not state a numeric "
                "correlation you have not been shown — say it is unmeasured.")
    lines = ["MEASURED PAIRWISE CORRELATIONS (|r| > 0.3 suggests the two legs are "
             "not independent axes regardless of how differently they are "
             "described):"]
    for pair, value in sorted(correlations.items(), key=lambda kv: -abs(kv[1])):
        flag = "  <-- HIGH" if abs(value) > 0.3 else ""
        lines.append(f"  {pair.replace('|', ' vs ')}: r = {value:+.3f}{flag}")
    return "\n".join(lines)


DEFAULT_CONCEPTS = [
    "Assets", "NetIncomeLoss", "GrossProfit", "Revenues", "CostOfRevenue",
    "StockholdersEquity", "OperatingIncomeLoss",
    "CashAndCashEquivalentsAtCarryingValue",
]


def compute_concept_coverage(panel: pd.DataFrame, concepts: list[str] | None = None,
                             use_cache: bool = True) -> dict:
    """Fraction of tickers with any filed value per SEC concept.

    Takes ~2 minutes even with the fundamentals fetcher's disk cache warm (the
    cost is parsing/aggregating, not the network), which is too slow to redo
    every iteration.

    So it IS cached — but keyed on a hash of the exact ticker set plus the
    concept list, which is precisely what determines the answer. Change the
    universe and the key changes and it recomputes; leave the universe alone and
    the cached value cannot be wrong. That is a correctness-preserving cache
    rather than a time-based one that silently rots, which was the specific
    failure mode worth avoiding here.
    """
    import hashlib
    import json
    import pathlib
    import sys

    concepts = concepts or DEFAULT_CONCEPTS
    tickers = sorted(panel["ticker"].unique())

    signature = hashlib.sha256(
        json.dumps({"tickers": tickers, "concepts": sorted(concepts)}).encode()
    ).hexdigest()[:16]
    cache_dir = pathlib.Path.home() / ".cache" / "stock_research_concept_coverage"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{signature}.json"

    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text())

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]
                           / "research-methodology" / "scripts"))
    from data import fetch_fundamentals

    fundamentals = fetch_fundamentals(list(tickers), concepts=concepts)
    if fundamentals.empty:
        coverage = {concept: 0.0 for concept in concepts}
    else:
        coverage = {
            concept: fundamentals[fundamentals["concept"] == concept]["ticker"].nunique()
                     / max(len(tickers), 1)
            for concept in concepts
        }
    cache_file.write_text(json.dumps(coverage))
    return coverage
