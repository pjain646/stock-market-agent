"""Phase A configuration. Assumptions are deliberately explicit so they're easy
to review and change.
"""

# ~150-170 liquid large-caps across 11 sectors (up from the original 24-ticker,
# 3-sector proof-of-harness set). The small universe was diagnosed as a real
# cause of the campaign's Gate 1 failure: too few, too correlated names meant
# low effective sample size, so validation scores were noisy enough for a
# best-of-17 search to find an artifact that didn't hold on holdout. The
# original three sector keys ("Financials", "Technology", "Pharma") are left
# unchanged — existing proposals/ feature code keys off these exact industry
# names — with more tickers added to each; new sectors are additive.
#
# Survivorship caveat unchanged: this is a *current* liquid set, not a
# survivorship-free historical universe (no delisted names). Still true here,
# just at a larger scale.
UNIVERSE = {
    "Financials": ["JPM", "BAC", "WFC", "C", "GS", "MS", "SCHW", "AXP",
                   "BLK", "SPGI", "ICE", "CME", "PNC", "USB", "TFC", "COF",
                   "MET", "PGR", "AIG", "TRV", "ALL", "MMC", "BK", "STT"],
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "CRM",
                   "ORCL", "ADBE", "CSCO", "INTC", "IBM", "TXN", "QCOM", "INTU",
                   "AMD", "NOW", "ADP", "ACN"],
    "Pharma":     ["JNJ", "PFE", "MRK", "ABBV", "LLY", "BMY", "AMGN", "GILD",
                   "UNH", "CVS", "ABT", "TMO", "DHR", "MDT", "CI", "ELV",
                   "HUM", "ZTS", "SYK", "BSX"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "OXY",
               "WMB", "KMI", "VLO", "HES", "BKR", "HAL", "DVN"],
    "ConsumerDiscretionary": ["HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG",
                              "ORLY", "MAR", "GM", "F", "YUM", "ROST", "AZO"],
    "ConsumerStaples": ["PG", "KO", "PEP", "WMT", "COST", "PM", "MO", "MDLZ",
                        "CL", "KMB", "GIS", "STZ", "SYY", "KR", "HSY"],
    "Industrials": ["HON", "UNP", "UPS", "CAT", "RTX", "BA", "LMT", "DE",
                    "GE", "MMM", "NOC", "GD", "FDX", "EMR", "ETN"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL",
                  "ED", "PEG", "WEC", "ES", "AWK", "DTE", "PPL"],
    "CommunicationServices": ["T", "VZ", "CMCSA", "DIS", "NFLX", "TMUS", "CHTR", "EA",
                              "TTWO", "OMC"],
    "Materials": ["LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DOW",
                  "DD", "PPG"],
    "RealEstate": ["PLD", "AMT", "EQIX", "PSA", "SPG", "O", "WELL", "DLR",
                   "AVB", "EQR"],
}

# Preyansh's personal watch list for the morning brief (core/morning_brief.py)
# — separate from UNIVERSE above, which is the prediction model's training/
# ranking universe. These are guaranteed news coverage every morning (not
# competitively curated against everything else), and are excluded from the
# brief's general "Top stories" section so that section stays about names
# NOT already being watched. Edit this list directly to add/remove tickers.
WATCHLIST_BENCHMARKS = ["SPY", "VGT", "QQQ"]  # shown first, as market context
WATCHLIST_TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META",  # mega-cap tech
    "MU", "SNDK", "DRAM",                              # memory/DRAM
    "USAR", "IREN", "OUST", "AMD", "RKLB", "PLTR", "MRVL",
]

# Company-name aliases for the watch-list tickers, used ONLY to filter out
# mismatched headlines in build_watchlist_articles — a news API can tag an
# article under a ticker's symbol even when the headline is really about a
# different company it happens to mention in passing (a comparison piece, a
# "which stocks are moving" roundup, etc). Requiring the ticker's own symbol
# OR one of these names to actually appear in the headline text is a cheap,
# no-API-call way to catch the obvious mismatches. Not exhaustive — just
# enough aliasing to cover common headline phrasing for each name.
WATCHLIST_ALIASES: dict[str, list[str]] = {
    "SPY": ["S&P 500", "S&P500"],
    "VGT": ["Vanguard Information Technology"],
    "QQQ": ["Nasdaq 100", "Nasdaq-100"],
    "AAPL": ["Apple"],
    "MSFT": ["Microsoft"],
    "NVDA": ["Nvidia"],
    "TSLA": ["Tesla"],
    "AMZN": ["Amazon"],
    "GOOGL": ["Google", "Alphabet"],
    "META": ["Meta", "Facebook"],
    "MU": ["Micron"],
    "SNDK": ["Sandisk"],
    "DRAM": [],
    "USAR": ["USA Rare Earth"],
    "IREN": ["Iris Energy"],
    "OUST": ["Ouster"],
    "AMD": ["Advanced Micro Devices"],
    "RKLB": ["Rocket Lab"],
    "PLTR": ["Palantir"],
    "MRVL": ["Marvell"],
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


# Carves "Semiconductors" out of the "Technology" bucket for DISPLAY purposes
# only (the morning brief's "By industry" movers chart) — never used for
# model features. `industry_map()` above is load-bearing for existing
# proposals/ feature code, which keys off its exact sector names, so it's
# left untouched; this is a separate, presentational-only view of the same
# universe. Doesn't add memory-specific names (MU, SNDK, etc.) — those are
# watch-list-only (config.WATCHLIST_TICKERS), not part of UNIVERSE, so they
# never appear in this movers panel regardless of labeling.
_SEMICONDUCTOR_TICKERS = {"NVDA", "AVGO", "INTC", "TXN", "QCOM", "AMD"}


def display_industry_map():
    base = industry_map()
    return {t: ("Semiconductors" if t in _SEMICONDUCTOR_TICKERS else ind)
            for t, ind in base.items()}
