"""Bundled market-data fetcher — the skill's portable, self-contained data layer.

This file lives INSIDE the skill (research-methodology/scripts/) on purpose: it
makes the skill self-contained, so the skill can pull its own data and be used
outside this project. The project's domain core imports these same functions, so
research and backtest always see identical data (no second, drifting copy).

Honesty rules are enforced here in code, not left to the caller to remember:
  - Prices: yfinance with auto_adjust=True returns SPLIT- and DIVIDEND-adjusted
    prices, satisfying the corporate-actions rule.
  - Fundamentals: each value carries the date it was actually FILED (became
    public), so a feature built from it can never peek at a number that wasn't
    yet known — the point-in-time rule, in code.

Functions:
  fetch_prices         -- adjusted daily closes (yfinance)
  fetch_fundamentals   -- point-in-time financial-statement line items (SEC EDGAR)
"""
from __future__ import annotations

import json
import os
import pathlib
import time

import pandas as pd


# --------------------------------------------------------------------------- #
# Prices
# --------------------------------------------------------------------------- #
def fetch_prices(tickers, start_date, end_date) -> pd.DataFrame:
    """Download adjusted daily closing prices for one or more tickers.

    Returns a long-format DataFrame: [date, ticker, adj_close], sorted by
    ticker then date. adj_close is split/dividend-adjusted.
    """
    import yfinance  # imported lazily so importing this module is cheap

    if isinstance(tickers, str):
        tickers = [tickers]

    downloaded_prices = yfinance.download(
        list(tickers), start=start_date, end=end_date,
        auto_adjust=True, progress=False, group_by="column",
    )

    adjusted_close_wide = (
        downloaded_prices["Close"]
        if "Close" in getattr(downloaded_prices, "columns", [])
        else downloaded_prices
    )
    if isinstance(adjusted_close_wide, pd.Series):
        adjusted_close_wide = adjusted_close_wide.to_frame(tickers[0])

    date_index_name = adjusted_close_wide.index.name or "Date"
    price_history_long = (
        adjusted_close_wide.reset_index()
        .melt(id_vars=date_index_name, var_name="ticker", value_name="adj_close")
        .rename(columns={date_index_name: "date"})
        .dropna(subset=["adj_close"])
    )
    price_history_long["date"] = pd.to_datetime(price_history_long["date"])
    return price_history_long.sort_values(["ticker", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Fundamentals (SEC EDGAR — free, no API key, point-in-time by filing date)
# --------------------------------------------------------------------------- #

# SEC requires a contact in the User-Agent header — set SEC_CONTACT_EMAIL to
# YOUR email (env var or keys.local.json), per their fair-access policy.
def _sec_contact_user_agent() -> str:
    try:
        contact_email = _load_api_key("SEC_CONTACT_EMAIL")
    except RuntimeError:
        contact_email = "your-email@example.com"  # placeholder; please set your own
    return f"stock-research-agent {contact_email}"

# Maps every ticker to its SEC CIK (central index key).
_SEC_TICKER_TO_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
# All XBRL facts ever filed by a company, each stamped with its filing date.
_SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Default financial-statement line items to pull (US-GAAP XBRL concept tags).
# Companies don't all use the same tags, so we ask for several and keep whatever
# each company actually reports.
DEFAULT_FUNDAMENTAL_CONCEPTS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",  # common modern revenue tag
    "GrossProfit",
    "OperatingIncomeLoss",
    "NetIncomeLoss",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "NetCashProvidedByUsedInOperatingActivities",
    "LongTermDebtNoncurrent",
    "EarningsPerShareDiluted",
]

# Cache the (large) ticker->CIK map so we fetch it at most once per process.
_cached_ticker_to_cik_map = None


def _get_json_from_sec(url: str):
    """GET a SEC JSON endpoint with the required contact User-Agent header."""
    import requests

    response = requests.get(url, headers={"User-Agent": _sec_contact_user_agent()}, timeout=30)
    response.raise_for_status()
    return response.json()


def _ticker_to_cik_map() -> dict:
    """Return {TICKER: cik_int}, fetching and caching SEC's master list once."""
    global _cached_ticker_to_cik_map
    if _cached_ticker_to_cik_map is None:
        raw_listing = _get_json_from_sec(_SEC_TICKER_TO_CIK_URL)  # {idx: {cik_str, ticker, title}}
        _cached_ticker_to_cik_map = {
            row["ticker"].upper(): int(row["cik_str"]) for row in raw_listing.values()
        }
    return _cached_ticker_to_cik_map


def fetch_fundamentals(tickers, concepts=None, start_date=None, end_date=None) -> pd.DataFrame:
    """Point-in-time financial-statement values from SEC EDGAR.

    For each ticker, pulls the requested XBRL concepts and returns every reported
    value WITH the date it was filed — which is what makes this point-in-time:
    a downstream feature can use a value only as of its `filed_date`, never
    earlier.

    Args:
        tickers: ticker string or list of tickers.
        concepts: list of US-GAAP XBRL concept tags (defaults to a sensible set).
        start_date / end_date: optional filters on `filed_date`.

    Returns:
        Long-format DataFrame with columns:
            ticker, concept, unit, period_start, period_end, filed_date, value,
            fiscal_year, fiscal_period, form
        sorted by ticker, concept, period_end, filed_date.
        (`filed_date` is the point-in-time stamp; `period_end` is the fiscal
        period the number describes — never join on period_end alone.
        `period_start` is only present for duration concepts like revenue or
        net income — SEC reports both single-quarter and cumulative
        year-to-date totals under the same `period_end`, and `period_start`
        is what tells them apart.)
    """
    if isinstance(tickers, str):
        tickers = [tickers]
    concepts = concepts or DEFAULT_FUNDAMENTAL_CONCEPTS

    ticker_to_cik = _ticker_to_cik_map()
    fundamental_records = []

    for ticker in tickers:
        central_index_key = ticker_to_cik.get(ticker.upper())
        if central_index_key is None:
            continue  # ticker not found in SEC's list (e.g., a non-US or private name)

        company_facts = _get_json_from_sec(_SEC_COMPANY_FACTS_URL.format(cik=central_index_key))
        us_gaap_facts = company_facts.get("facts", {}).get("us-gaap", {})

        for concept in concepts:
            concept_facts = us_gaap_facts.get(concept)
            if not concept_facts:
                continue  # this company doesn't report this particular tag

            # A concept reports values under one or more units (e.g. USD, USD/shares).
            for unit_name, reported_values in concept_facts.get("units", {}).items():
                for reported_value in reported_values:
                    fundamental_records.append({
                        "ticker": ticker.upper(),
                        "concept": concept,
                        "unit": unit_name,
                        "period_start": reported_value.get("start"),   # None for instant concepts (e.g. Assets)
                        "period_end": reported_value.get("end"),       # fiscal period described
                        "filed_date": reported_value.get("filed"),     # POINT-IN-TIME: when it became public
                        "value": reported_value.get("val"),
                        "fiscal_year": reported_value.get("fy"),
                        "fiscal_period": reported_value.get("fp"),
                        "form": reported_value.get("form"),            # e.g. 10-K, 10-Q
                    })

        time.sleep(0.2)  # be polite to SEC's servers (well under their rate limit)

    fundamentals = pd.DataFrame.from_records(fundamental_records)
    if fundamentals.empty:
        return fundamentals

    fundamentals["period_start"] = pd.to_datetime(fundamentals["period_start"])
    fundamentals["period_end"] = pd.to_datetime(fundamentals["period_end"])
    fundamentals["filed_date"] = pd.to_datetime(fundamentals["filed_date"])
    if start_date is not None:
        fundamentals = fundamentals[fundamentals["filed_date"] >= pd.to_datetime(start_date)]
    if end_date is not None:
        fundamentals = fundamentals[fundamentals["filed_date"] <= pd.to_datetime(end_date)]

    return fundamentals.sort_values(
        ["ticker", "concept", "period_end", "filed_date"]
    ).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# FMP (Financial Modeling Prep) — earnings & analyst data
# Free tier is ~250 calls/day, so every response is cached to disk and reused;
# a cached call costs zero against the daily limit.
# --------------------------------------------------------------------------- #

_FMP_BASE_URL = "https://financialmodelingprep.com/stable"
# Cache lives in the user's home dir so it survives between runs and doesn't
# clutter the project (or the skill, when used standalone).
_FMP_CACHE_DIR = pathlib.Path.home() / ".cache" / "stock_research_fmp"


def _load_api_key(key_name: str) -> str:
    """Find an API key without hardcoding it: env var first, then keys.local.json.

    Args:
        key_name: e.g. "FMP_API_KEY" or "FRED_API_KEY".

    Checked in order:
      1. the matching environment variable (preferred — never on disk in the repo)
      2. a local keys.local.json file (in the current dir or the project root)
    """
    api_key_from_env = os.environ.get(key_name)
    if api_key_from_env:
        return api_key_from_env

    possible_key_files = [
        pathlib.Path.cwd() / "keys.local.json",
        pathlib.Path(__file__).resolve().parents[2] / "keys.local.json",  # project root
    ]
    for key_file in possible_key_files:
        if key_file.exists():
            stored_key = json.loads(key_file.read_text()).get(key_name)
            if stored_key:
                return stored_key

    raise RuntimeError(
        f"No {key_name} found. Set the {key_name} environment variable or add it to keys.local.json."
    )


def _load_fmp_api_key() -> str:
    """Convenience wrapper for the FMP key (see _load_api_key)."""
    return _load_api_key("FMP_API_KEY")


def _fmp_get(endpoint_path: str, query_params: dict | None = None, cache_max_age_days: float = 1.0):
    """GET an FMP 'stable' endpoint, caching the response to disk to save calls.

    A cached response newer than `cache_max_age_days` is returned without spending
    an API call. Earnings/analyst data changes slowly, so a 1-day cache keeps us
    far under the 250/day free-tier limit even across many re-runs.
    """
    import requests

    query_params = dict(query_params or {})
    query_params["apikey"] = _load_fmp_api_key()

    # Cache filename built from the endpoint + params, but NOT the secret key.
    cache_signature = endpoint_path.replace("/", "_") + "__" + "_".join(
        f"{name}={value}" for name, value in sorted(query_params.items()) if name != "apikey"
    )
    _FMP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _FMP_CACHE_DIR / f"{cache_signature}.json"

    # Reuse a fresh-enough cached copy instead of spending a call.
    if cache_file.exists():
        cache_age_in_days = (time.time() - cache_file.stat().st_mtime) / 86400.0
        if cache_age_in_days <= cache_max_age_days:
            return json.loads(cache_file.read_text())

    response = requests.get(f"{_FMP_BASE_URL}/{endpoint_path}", params=query_params, timeout=30)
    response.raise_for_status()
    response_payload = response.json()
    cache_file.write_text(json.dumps(response_payload))
    return response_payload


# --------------------------------------------------------------------------- #
# Alpha Vantage — earnings fallback for tickers FMP's free tier blocks
# Free tier is only 25 calls/day, so responses are cached for 30 days
# (historical earnings surprises don't change).
# --------------------------------------------------------------------------- #

_ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
_ALPHA_VANTAGE_CACHE_DIR = pathlib.Path.home() / ".cache" / "stock_research_alpha_vantage"


def _alpha_vantage_get(query_params: dict, cache_max_age_days: float = 30.0):
    """GET an Alpha Vantage endpoint, caching the response to disk to save calls.

    The free tier allows only 25 calls/day, so the cache TTL is long — the data
    fetched here (historical earnings) is append-only in practice.
    """
    import requests

    query_params = dict(query_params)
    cache_signature = "_".join(
        f"{name}={value}" for name, value in sorted(query_params.items())
    )
    _ALPHA_VANTAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _ALPHA_VANTAGE_CACHE_DIR / f"{cache_signature}.json"

    if cache_file.exists():
        cache_age_in_days = (time.time() - cache_file.stat().st_mtime) / 86400.0
        if cache_age_in_days <= cache_max_age_days:
            return json.loads(cache_file.read_text())

    query_params["apikey"] = _load_api_key("ALPHA_VANTAGE_API_KEY")

    # Alpha Vantage signals rate-limiting with HTTP 200 + a "Note"/"Information"
    # message instead of an error status. The free tier throttles bursts (~1
    # request/second), so pace requests and retry with a backoff before giving up.
    last_notice = None
    for attempt in range(3):
        time.sleep(2 if attempt == 0 else 25)  # pace the first try; back off on retries
        response = requests.get(_ALPHA_VANTAGE_BASE_URL, params=query_params, timeout=30)
        response.raise_for_status()
        response_payload = response.json()

        is_throttle_notice = isinstance(response_payload, dict) and (
            "Note" in response_payload or "Information" in response_payload
        )
        if not is_throttle_notice:
            cache_file.write_text(json.dumps(response_payload))
            return response_payload
        last_notice = response_payload.get("Note") or response_payload.get("Information")

    raise RuntimeError(f"Alpha Vantage rate limit / notice: {last_notice}")


def _fetch_earnings_alpha_vantage(ticker: str) -> list[dict]:
    """Historical quarterly EPS surprises for one ticker via Alpha Vantage EARNINGS.

    Returns records in the same schema as fetch_earnings. Alpha Vantage doesn't
    provide revenue actual/estimate on this endpoint, so those stay None (revenue
    growth is covered independently by the EDGAR fundamentals features).
    """
    payload = _alpha_vantage_get({"function": "EARNINGS", "symbol": ticker.upper()})

    def _to_float(raw_value):
        try:
            return float(raw_value)
        except (TypeError, ValueError):  # Alpha Vantage uses the string "None"
            return None

    earnings_records = []
    for quarterly_report in payload.get("quarterlyEarnings", []):
        earnings_records.append({
            "ticker": ticker.upper(),
            "date": quarterly_report.get("reportedDate"),
            "eps_actual": _to_float(quarterly_report.get("reportedEPS")),
            "eps_estimated": _to_float(quarterly_report.get("estimatedEPS")),
            "eps_surprise": _to_float(quarterly_report.get("surprise")),
            "revenue_actual": None,
            "revenue_estimated": None,
            "revenue_surprise": None,
        })
    return earnings_records


def fetch_earnings(tickers) -> pd.DataFrame:
    """Earnings dates and surprises (actual vs. estimated EPS and revenue).

    Primary source is FMP; for symbols FMP's free tier blocks (it 402s a subset
    of tickers on this endpoint), falls back to Alpha Vantage's EARNINGS endpoint
    (EPS surprises only — no revenue, which EDGAR fundamentals cover anyway).

    Returns a long DataFrame with columns:
        ticker, date, eps_actual, eps_estimated, eps_surprise,
        revenue_actual, revenue_estimated, revenue_surprise
    A "surprise" is actual minus estimate. Future/just-scheduled earnings have no
    actual yet, so their surprise columns are left as None.

    Note: the FMP free tier returns the full available history when no row limit
    is sent (passing a large `limit` is treated as a premium request), so we
    simply fetch everything the endpoint gives.
    """
    import requests

    if isinstance(tickers, str):
        tickers = [tickers]

    earnings_records = []
    for ticker in tickers:
        try:
            reported_earnings = _fmp_get("earnings", {"symbol": ticker.upper()})
        except requests.exceptions.HTTPError:
            # FMP's free tier only covers a subset of symbols for this endpoint
            # (confirmed: blocks MS, SCHW even though it allows AAPL).
            try:
                earnings_records.extend(_fetch_earnings_alpha_vantage(ticker))
                print(f"  earnings for {ticker}: FMP blocked on free tier -> used Alpha Vantage fallback")
            except Exception as fallback_error:
                print(f"  earnings unavailable for {ticker} (FMP blocked; Alpha Vantage fallback failed: {fallback_error}); skipping")
            continue
        for earnings_event in reported_earnings or []:
            eps_actual = earnings_event.get("epsActual")
            eps_estimated = earnings_event.get("epsEstimated")
            revenue_actual = earnings_event.get("revenueActual")
            revenue_estimated = earnings_event.get("revenueEstimated")

            eps_surprise = (
                eps_actual - eps_estimated
                if eps_actual is not None and eps_estimated is not None
                else None
            )
            revenue_surprise = (
                revenue_actual - revenue_estimated
                if revenue_actual is not None and revenue_estimated is not None
                else None
            )

            earnings_records.append({
                "ticker": ticker.upper(),
                "date": earnings_event.get("date"),
                "eps_actual": eps_actual,
                "eps_estimated": eps_estimated,
                "eps_surprise": eps_surprise,
                "revenue_actual": revenue_actual,
                "revenue_estimated": revenue_estimated,
                "revenue_surprise": revenue_surprise,
            })

    earnings = pd.DataFrame.from_records(earnings_records)
    if not earnings.empty:
        earnings["date"] = pd.to_datetime(earnings["date"])
        earnings = earnings.sort_values(["ticker", "date"]).reset_index(drop=True)
    return earnings


def fetch_analyst_estimates(tickers) -> pd.DataFrame:
    """Forward analyst estimates (annual) via FMP — consensus revenue/EBITDA/EPS, etc.

    Returns a long DataFrame: [ticker, date, <metric>Avg ...] where each row is a
    future fiscal year and the *Avg columns are the consensus estimate for it.
    (FMP free tier supports annual estimates; quarterly is premium.)
    """
    if isinstance(tickers, str):
        tickers = [tickers]
    estimate_frames = []
    for ticker in tickers:
        estimate_rows = _fmp_get("analyst-estimates", {"symbol": ticker.upper(), "period": "annual"})
        if not estimate_rows:
            continue
        estimates_for_ticker = pd.DataFrame(estimate_rows).rename(columns={"symbol": "ticker"})
        # Keep the identifying columns plus the consensus ("average") estimate columns.
        consensus_columns = [c for c in estimates_for_ticker.columns if c.endswith("Avg")]
        estimate_frames.append(estimates_for_ticker[["ticker", "date"] + consensus_columns])
    if not estimate_frames:
        return pd.DataFrame()
    analyst_estimates = pd.concat(estimate_frames, ignore_index=True)
    analyst_estimates["date"] = pd.to_datetime(analyst_estimates["date"])
    return analyst_estimates.sort_values(["ticker", "date"]).reset_index(drop=True)


def fetch_analyst_grades(tickers) -> pd.DataFrame:
    """Analyst rating changes (upgrades/downgrades) over time via FMP.

    Returns a long DataFrame: [ticker, date, grading_company, previous_grade,
    new_grade, action]. This is the revisions signal — who changed their call,
    when, and which direction.
    """
    if isinstance(tickers, str):
        tickers = [tickers]
    grade_records = []
    for ticker in tickers:
        grade_rows = _fmp_get("grades", {"symbol": ticker.upper()})
        for grade_change in grade_rows or []:
            grade_records.append({
                "ticker": ticker.upper(),
                "date": grade_change.get("date"),
                "grading_company": grade_change.get("gradingCompany"),
                "previous_grade": grade_change.get("previousGrade"),
                "new_grade": grade_change.get("newGrade"),
                "action": grade_change.get("action"),  # upgrade / downgrade / maintain / initiate
            })
    analyst_grades = pd.DataFrame.from_records(grade_records)
    if not analyst_grades.empty:
        analyst_grades["date"] = pd.to_datetime(analyst_grades["date"])
        analyst_grades = analyst_grades.sort_values(["ticker", "date"]).reset_index(drop=True)
    return analyst_grades


# --------------------------------------------------------------------------- #
# FRED (Federal Reserve Economic Data) — macro & rates. Free key, generous limits.
# --------------------------------------------------------------------------- #

_FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"

# A sensible default macro panel: rates, the yield curve, inflation, jobs, risk.
DEFAULT_MACRO_SERIES = {
    "FEDFUNDS": "fed_funds_rate",
    "DGS10": "treasury_yield_10y",
    "DGS2": "treasury_yield_2y",
    "T10Y2Y": "yield_curve_10y_minus_2y",
    "CPIAUCSL": "cpi_index",
    "UNRATE": "unemployment_rate",
    "VIXCLS": "vix",
}


def fetch_macro_series(series_ids=None, start_date=None) -> pd.DataFrame:
    """Macro time series from FRED (rates, yield curve, inflation, jobs, VIX).

    Args:
        series_ids: dict of {fred_series_id: friendly_name}, or a list of ids.
            Defaults to DEFAULT_MACRO_SERIES.
        start_date: optional 'YYYY-MM-DD' lower bound on observations.

    Returns:
        Long DataFrame: [series_id, series_name, date, value].
    """
    import requests

    if series_ids is None:
        series_ids = DEFAULT_MACRO_SERIES
    if isinstance(series_ids, (list, tuple)):
        series_ids = {sid: sid for sid in series_ids}

    fred_api_key = _load_api_key("FRED_API_KEY")
    macro_records = []
    for fred_series_id, friendly_name in series_ids.items():
        request_params = {
            "series_id": fred_series_id,
            "api_key": fred_api_key,
            "file_type": "json",
        }
        if start_date is not None:
            request_params["observation_start"] = start_date
        response = requests.get(_FRED_OBSERVATIONS_URL, params=request_params, timeout=30)
        response.raise_for_status()
        for observation in response.json().get("observations", []):
            raw_value = observation.get("value")
            if raw_value in (None, ".", ""):  # FRED uses "." for missing values
                continue
            macro_records.append({
                "series_id": fred_series_id,
                "series_name": friendly_name,
                "date": observation.get("date"),
                "value": float(raw_value),
            })
        time.sleep(0.1)  # polite pause; FRED limits are generous

    macro_data = pd.DataFrame.from_records(macro_records)
    if not macro_data.empty:
        macro_data["date"] = pd.to_datetime(macro_data["date"])
        macro_data = macro_data.sort_values(["series_id", "date"]).reset_index(drop=True)
    return macro_data


# --------------------------------------------------------------------------- #
# Scaffolded fetchers — structure is in place; each needs heavier parsing or
# paid access, so they raise a clear error rather than returning fake data.
# (Honesty rule: never fabricate. A stub that says "not built" beats one that
# quietly returns made-up numbers.)
# --------------------------------------------------------------------------- #

_SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_SEC_ARCHIVE_FILE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{document}"


def _strip_xml_namespaces(xml_root):
    """Remove XML namespaces in place so we can find tags by their plain name.

    Form 4 documents sometimes carry a namespace; stripping it lets us use
    simple tag paths like 'transactionCode' instead of namespaced ones.
    """
    for element in xml_root.iter():
        if "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
    return xml_root


def fetch_insider_transactions(tickers, max_form4_filings_per_ticker: int = 40) -> pd.DataFrame:
    """Insider buys/sells (SEC Form 4) — what a company's own officers/directors trade.

    This is data the base model has no access to, and it's genuinely point-in-time:
    Form 4 must be filed within ~2 business days of the trade, so the filing date
    is when the information became public.

    How it works: look up the company's recent filings, keep the Form 4s, fetch
    each one's XML, and parse the actual share transactions out of it.

    Returns a long DataFrame:
        [ticker, filing_date, insider_name, is_director, is_officer, officer_title,
         transaction_date, transaction_code, acquired_or_disposed, shares, price_per_share]
    transaction_code meanings worth knowing: P = open-market purchase (bullish),
    S = open-market sale, A = grant/award, M = option exercise, F = tax withholding.
    """
    import requests
    import xml.etree.ElementTree as ElementTree

    if isinstance(tickers, str):
        tickers = [tickers]
    ticker_to_cik = _ticker_to_cik_map()
    insider_records = []

    for ticker in tickers:
        central_index_key = ticker_to_cik.get(ticker.upper())
        if central_index_key is None:
            continue

        # The submissions endpoint lists a company's recent filings as parallel arrays.
        submissions = _get_json_from_sec(_SEC_SUBMISSIONS_URL.format(cik=central_index_key))
        recent_filings = submissions.get("filings", {}).get("recent", {})
        form_types = recent_filings.get("form", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        primary_documents = recent_filings.get("primaryDocument", [])
        filing_dates = recent_filings.get("filingDate", [])

        form4_seen = 0
        for form_type, accession_number, primary_document, filing_date in zip(
            form_types, accession_numbers, primary_documents, filing_dates
        ):
            if form_type != "4":
                continue
            if form4_seen >= max_form4_filings_per_ticker:
                break
            form4_seen += 1

            # primaryDocument often points to the styled HTML view in an "xsl.../"
            # subfolder; the raw, parseable XML is the same filename at the accession
            # root, so strip any leading subfolder.
            raw_xml_document = primary_document.rsplit("/", 1)[-1]
            filing_url = _SEC_ARCHIVE_FILE_URL.format(
                cik=central_index_key,
                accession_no_dashes=accession_number.replace("-", ""),
                document=raw_xml_document,
            )
            try:
                filing_response = requests.get(
                    filing_url, headers={"User-Agent": _sec_contact_user_agent()}, timeout=30
                )
                ownership_document = _strip_xml_namespaces(ElementTree.fromstring(filing_response.content))
            except Exception:
                continue  # skip a filing we can't fetch/parse rather than fail the whole pull

            # Who filed it, and their relationship to the company.
            insider_name = ownership_document.findtext(".//reportingOwnerId/rptOwnerName")
            is_director = ownership_document.findtext(".//reportingOwnerRelationship/isDirector")
            is_officer = ownership_document.findtext(".//reportingOwnerRelationship/isOfficer")
            officer_title = ownership_document.findtext(".//reportingOwnerRelationship/officerTitle")

            # Non-derivative transactions are the actual common-share buys/sells.
            for transaction in ownership_document.findall(".//nonDerivativeTransaction"):
                insider_records.append({
                    "ticker": ticker.upper(),
                    "filing_date": filing_date,
                    "insider_name": insider_name,
                    "is_director": is_director in ("1", "true"),
                    "is_officer": is_officer in ("1", "true"),
                    "officer_title": officer_title,
                    "transaction_date": transaction.findtext(".//transactionDate/value"),
                    "transaction_code": transaction.findtext(".//transactionCoding/transactionCode"),
                    "acquired_or_disposed": transaction.findtext(
                        ".//transactionAmounts/transactionAcquiredDisposedCode/value"
                    ),
                    "shares": transaction.findtext(".//transactionAmounts/transactionShares/value"),
                    "price_per_share": transaction.findtext(
                        ".//transactionAmounts/transactionPricePerShare/value"
                    ),
                })
            time.sleep(0.12)  # stay well under SEC's rate limit

    insider_transactions = pd.DataFrame.from_records(insider_records)
    if insider_transactions.empty:
        return insider_transactions

    # Make dates and numbers real types instead of strings.
    insider_transactions["filing_date"] = pd.to_datetime(insider_transactions["filing_date"])
    insider_transactions["transaction_date"] = pd.to_datetime(
        insider_transactions["transaction_date"], errors="coerce"
    )
    for numeric_column in ("shares", "price_per_share"):
        insider_transactions[numeric_column] = pd.to_numeric(
            insider_transactions[numeric_column], errors="coerce"
        )
    return insider_transactions.sort_values(["ticker", "transaction_date"]).reset_index(drop=True)


def fetch_institutional_holdings_13f(tickers):  # pragma: no cover - scaffold
    """13F institutional holdings (SEC EDGAR). ~45-day reporting lag.

    Plan: parse 13F-HR information-table XML per filer. Aggregate holdings of a
    given ticker across filers, respecting the 45-day lag for point-in-time use.
    """
    raise NotImplementedError("13F fetcher: scaffolded, needs 13F information-table XML parsing.")


def fetch_short_interest(tickers):  # pragma: no cover - scaffold
    """Short interest. FMP free does not provide it; pull from FINRA directly.

    Plan: FINRA publishes bi-monthly short interest + daily short-sale volume as
    downloadable files; parse and align to settlement dates (point-in-time).
    """
    raise NotImplementedError("Short interest fetcher: scaffolded, source = FINRA files (free).")


def fetch_news(tickers):  # pragma: no cover - scaffold
    """Timestamped news. FMP free tier blocks news (premium); needs an alt source.

    Plan: a timestamped provider (e.g. a news API with history) for backtests;
    live scraping is acceptable only for forward predictions, per the honesty rule.
    """
    raise NotImplementedError("News fetcher: scaffolded, needs a (paid) timestamped news source.")


def fetch_social_sentiment(tickers):  # pragma: no cover - scaffold
    """LIVE credibility-weighted social sentiment — a forward validation layer.

    Not a backtested feature (per the spec): once the agent has a thesis, this
    checks whether credibility-weighted public sentiment agrees. Needs paid /
    restricted X / Reddit API access and an as-of credibility model.
    """
    raise NotImplementedError("Social sentiment: scaffolded, needs paid X/Reddit access (last, forward-only).")
