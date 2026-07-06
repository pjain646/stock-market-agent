"""Phase A end-to-end demo: fetch prices -> label -> split -> evaluate.

This proves the "honest judge" pipeline runs on real data. The features here are
PLACEHOLDERS (simple price transforms) used only to exercise the machinery — they
are NOT proposed signals. Real features come from the LLM researcher later
(Phase C); the evaluator doesn't care where a feature came from.

Run:  python run_phase_a_demo.py
(Needs internet for yfinance; ~24 tickers x ~10 years.)
"""
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
# Make the domain core ('core') and the skill's bundled fetcher ('data') importable.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "research-methodology" / "scripts"))

from data import fetch_prices, fetch_fundamentals, fetch_earnings, fetch_insider_transactions  # noqa: E402  (bundled fetchers inside the skill)
from core import config  # noqa: E402
from core.labeling import add_forward_direction_label  # noqa: E402
from core.splits import assign_time_split  # noqa: E402
from core.evaluator import walk_forward_eval  # noqa: E402
from core.features import build_feature_panel  # noqa: E402

# The real feature set: technicals + earnings + insider conviction + fundamentals.
# NOTE: `pe_ratio` is computed by features.py but deliberately left OUT here —
# it divides split-adjusted price by non-split-adjusted SEC EPS, so it's
# distorted around any stock-split event (confirmed on AAPL). Needs a split-
# ratio adjustment before it's trustworthy; excluded from scoring until fixed.
# NOTE: `revenue_growth_yoy` (earnings-based) is also excluded — the Alpha
# Vantage earnings fallback carries no revenue figures, so requiring it would
# drop every fallback ticker from the eval, and EDGAR fundamentals already
# provide revenue growth independently (`revenue_growth_yoy_fundamental`).
FEATURE_COLUMNS = [
    "momentum_21d", "momentum_63d", "momentum_252d", "volatility_21d",
    "last_eps_surprise", "eps_surprise_avg_4q", "eps_growth_yoy", "days_since_earnings",
    "insider_net_shares_90d",
    "gross_margin", "operating_margin", "net_margin", "debt_to_equity", "cash_to_assets",
    "ocf_to_net_income", "revenue_growth_yoy_fundamental", "net_income_growth_yoy_fundamental",
]


def main():
    tickers = config.all_tickers()
    print(f"Fetching {len(tickers)} tickers {config.START}..{config.END} ...")

    # 1) Real adjusted prices, long format.
    price_history = fetch_prices(tickers, config.START, config.END)
    price_history["industry"] = price_history["ticker"].map(config.industry_map())

    # 2) Label: did the price rise over the next LABEL_HORIZON trading days?
    price_history = add_forward_direction_label(price_history, forward_horizon_days=config.LABEL_HORIZON)

    # 3) Real point-in-time features: technicals + earnings + insider + fundamentals.
    print("Fetching fundamentals (SEC EDGAR), earnings (FMP), insider trades (SEC Form 4) ...")
    fundamentals = fetch_fundamentals(tickers)
    earnings = fetch_earnings(tickers)
    insider_transactions = fetch_insider_transactions(tickers)
    price_history = build_feature_panel(
        price_history, earnings=earnings, insider_transactions=insider_transactions, fundamentals=fundamentals
    )

    # 4) Time-ordered split into train / validation / locked holdout.
    price_history, train_end_date, validation_end_date = assign_time_split(
        price_history, split_fractions=config.SPLIT_FRACS
    )
    print(
        f"split:  train <= {train_end_date.date()}   "
        f"validation <= {validation_end_date.date()}   holdout > {validation_end_date.date()}"
    )
    print(f"rows: {len(price_history)}  labeled: {int(price_history['label'].notna().sum())}")

    # 5) Score the real features out-of-sample (holdout stays sealed).
    print("\nWALK-FORWARD (validation, out-of-sample):")
    print(walk_forward_eval(price_history, FEATURE_COLUMNS, half_life_days=config.RECENCY_HALFLIFE_DAYS))

    # The holdout opens only at the very END of a real run, exactly once:
    #   from core.evaluator import open_holdout_once
    #   print(open_holdout_once(price_history, feature_columns,
    #                           config.RECENCY_HALFLIFE_DAYS,
    #                           acknowledge_this_is_the_final_run=True))


if __name__ == "__main__":
    main()
