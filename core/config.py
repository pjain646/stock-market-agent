"""Phase A configuration. Assumptions are deliberately explicit so they're easy
to review and change. Focused, liquid universe first (per spec); scale later.
"""

# ~8 liquid large-caps per industry. Survivorship caveat: this is a *current*
# liquid set used to prove the harness end-to-end; a survivorship-free
# historical universe (incl. delisted names) is required before any result is
# trusted, and comes with the EDGAR/point-in-time work.
UNIVERSE = {
    "Financials": ["JPM", "BAC", "WFC", "C", "GS", "MS", "SCHW", "AXP"],
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "CRM"],
    "Pharma":     ["JNJ", "PFE", "MRK", "ABBV", "LLY", "BMY", "AMGN", "GILD"],
}

START = "2014-01-01"
END = "2024-12-31"

LABEL_HORIZON = 21            # forward trading days for the direction label
SPLIT_FRACS = (0.6, 0.2, 0.2) # train / validation / locked-holdout, time-ordered
RECENCY_HALFLIFE_DAYS = 365   # exp-decay half-life for training sample weights


def all_tickers():
    return [t for ts in UNIVERSE.values() for t in ts]


def industry_map():
    return {t: ind for ind, ts in UNIVERSE.items() for t in ts}
