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

START = "2014-01-01"
END = "2024-12-31"

LABEL_HORIZON = 21            # forward trading days for the direction label
SPLIT_FRACS = (0.6, 0.2, 0.2) # train / validation / locked-holdout, time-ordered
RECENCY_HALFLIFE_DAYS = 365   # exp-decay half-life for training sample weights


def all_tickers():
    return [t for ts in UNIVERSE.values() for t in ts]


def industry_map():
    return {t: ind for ind, ts in UNIVERSE.items() for t in ts}
