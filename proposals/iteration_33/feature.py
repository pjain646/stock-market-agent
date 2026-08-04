"""Iteration 33 — two-leg orthogonal BUNDLE (MANAGER-SELECTED, EXACT):
accrual_reliability_earnings_quality (TRUE operating accruals) + sales_yield_within_sector.

WHAT THE RESEARCH MANAGER SELECTED, AND HOW THIS HONORS IT
----------------------------------------------------------
Binding ruling this iteration: SHIP exactly two orthogonal cross-sectional legs —
(1) earnings-quality via TRUE operating accruals (Sloan balance-sheet method,
low-accrual = good), and (2) sales yield (revenue / market cap) ranked within
sector. The macro leg `rate_pressure_duration_timer` was DROPPED by the team
(|beta| destroys sign information; its repeated +0.075 replication reused one
validation-era rate path and is not independent confirmation). I do NOT implement
any macro leg, and I do NOT re-add the campaign's prior solvency/profmom/macro
frame even though it scored +0.075 — re-adding a dropped factor overrides the
team's decision. TWO legs are selected; TWO legs are built.

CRITICAL RESPECIFICATION (the whole point of this iteration)
------------------------------------------------------------
The prior accrual proxy (NetIncome - ChangeInCash) is a FCF/financing HYBRID:
balance-sheet ChangeInCash is dominated by buybacks, debt issuance, capex and
M&A, so it leaks straight into the capital-structure axis and cannot inherit
Sloan's out-of-sample pedigree. This iteration builds the REAL thing — Sloan
(1996) balance-sheet operating accruals:

    Accruals = [ Delta(non-cash working capital) - Depreciation ] / avg total assets

  Delta non-cash working capital (year-over-year, fiscal-year-end to prior FYE):
    NWC   = (AssetsCurrent - Cash) - (LiabilitiesCurrent - ShortTermDebt)
    dNWC  = NWC_t - NWC_{t-1}
  Depreciation = full-year DepreciationDepletionAndAmortization (annual flow).
  avg total assets = (Assets_t + Assets_{t-1}) / 2.

LOW accruals = HIGH earnings quality (cash-backed earnings) = BULLISH; high
accruals mean reported income is running ahead of the cash/working-capital reality
and mean-reverts down (the accrual anomaly). So the RANK is on -accruals: low
accrual -> high rank -> bullish.

This is a genuinely NEW axis for the campaign (the peak solvency/profmom/macro
bundle never carried an accrual/cash-quality-of-earnings leg), and it is a pure
earnings-QUALITY screen with NO price term.

LEG 2 — sales_yield_within_sector (MANAGER-SELECTED)
----------------------------------------------------
Revenue / market cap (annual sales over point-in-time market cap). A pure value /
cheapness ratio whose denominator IS market price: firms priced low relative to
the sales they generate are cheap and out-drift (the sales-to-price value effect,
robust because revenue is the hardest line to manipulate). High sales yield ->
high rank -> bullish. Ranked WITHIN (date, industry) = sector-demeaned.

ORTHOGONALITY (why the PAIR is a different edge, not one idea twice)
-------------------------------------------------------------------
Revenue sits ABOVE the accrual line on the income statement, and sales yield's
edge comes entirely from the PRICE denominator (cheapness), whereas accruals carry
NO price term and measure the cash QUALITY of earnings below the revenue line. A
cheap stock can have clean or dirty accruals; a clean-accrual firm can be
expensive or cheap. So a cash-quality-of-earnings screen and a sales-to-price
screen do not load the same names through the mechanism that drives either —
QUALITY vs CHEAPNESS, two genuinely different cross-sectional axes. This is the
Fundamental(quality)/Valuation split the design wants, not a lone factor
(Gate-1 failure mode) and not the degenerate fundamental+macro pair.

BINDING BUILD CONSTRAINTS (from the ruling)
-------------------------------------------
  (1) accrual respecified to REAL operating accruals (done above — NOT the FCF hybrid);
  (2) both legs sector-demeaned = ranked WITHIN (date, industry);
  (3) NO per-sector weights — the two legs are returned as two equal-status rank
      columns and the evaluator equal-weights them as one model; no hand-tuning.

NATURAL (data-driven) sector coverage, NOT a hand-set exclusion: banks/insurers
do not report a classified balance sheet (no AssetsCurrent / LiabilitiesCurrent),
so their accrual value is simply NaN by absence of the input concepts — they drop
out of the accrual rank organically rather than by a hard-coded sector list.
Sales yield is defined for every sector and is computed everywhere.

POINT-IN-TIME DISCIPLINE
------------------------
Every fundamental line is taken AS-FIRST-REPORTED (earliest filed_date per fiscal
period, so a later restatement never leaks backward), stamped by that ORIGINAL
filing date (never by period_end), and forward-filled per ticker. A year-over-year
accrual becomes available only on the filing date of the CURRENT fiscal year's
10-K (the last input to become public). Market cap = point-in-time shares
outstanding x that row's adj_close.
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology",
                                "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "research-methodology", "scripts"))
from data import fetch_fundamentals  # noqa: E402

SIGNAL_NAME = "accruals_earnings_quality_sales_yield_bundle"
HYPOTHESIS = (
    "Operating-accruals earnings quality (MANAGER-SELECTED, RESPECIFIED to true "
    "Sloan balance-sheet accruals): accruals = [Delta(non-cash working capital) - "
    "depreciation] / average total assets, where non-cash working capital = "
    "(AssetsCurrent - Cash) - (LiabilitiesCurrent - ShortTermDebt), measured "
    "year-over-year fiscal-year-end to prior FYE and scaled by (Assets_t + "
    "Assets_{t-1})/2. LOW accruals mean reported earnings are cash-backed (high "
    "quality) and do NOT mean-revert down, so low-accrual firms out-drift (the "
    "accrual anomaly); the rank is on -accruals so low accrual -> high rank -> "
    "bullish. This is a pure earnings-QUALITY axis below the revenue line with NO "
    "price term, built strictly point-in-time from filed 10-K/10-Q balance sheets "
    "taken AS-FIRST-REPORTED and stamped by the current year's filing date. It "
    "deliberately REPLACES the old NetIncome-minus-ChangeInCash proxy, which was "
    "an FCF/financing hybrid (balance-sheet cash change is dominated by buybacks/"
    "debt/capex) that leaked into the capital-structure axis and could not inherit "
    "Sloan's OOS pedigree. Sales yield (MANAGER-SELECTED): annual Revenue / market "
    "cap is a pure value/CHEAPNESS ratio whose denominator IS market price; firms "
    "priced low relative to the sales they generate are cheap and out-drift (the "
    "sales-to-price effect, robust because revenue is the hardest line to "
    "manipulate); high sales yield -> high rank -> bullish, ranked WITHIN (date, "
    "industry). Orthogonality: revenue sits ABOVE the accrual line and sales "
    "yield's edge is entirely the PRICE denominator (cheapness), whereas accruals "
    "carry NO price term and measure the cash QUALITY of earnings below revenue; a "
    "cheap stock can have clean or dirty accruals and a clean-accrual firm can be "
    "cheap or expensive, so the two do not load the same names through the "
    "mechanism that drives either — QUALITY vs CHEAPNESS, the Fundamental/"
    "Valuation split, not a lone factor and not the degenerate fundamental+macro "
    "pair. NOTE: the dropped rate_pressure_duration_timer macro leg is deliberately "
    "NOT implemented (|beta| destroys rate-sign information and its repeated "
    "validation score reused one rate path, not independent confirmation), and the "
    "prior solvency/profmom/macro frame is NOT re-added — the team selected exactly "
    "these two legs."
)

# XBRL concept tags used to reconstruct Sloan operating accruals + sales yield.
_ASSETS_CUR = "AssetsCurrent"
_CASH = "CashAndCashEquivalentsAtCarryingValue"
_LIAB_CUR = "LiabilitiesCurrent"
_ASSETS = "Assets"
# short-term debt: try several tags; treated as 0 when a name reports none.
_STD_TAGS = ["DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"]
# depreciation (annual flow): prefer the broadest cash-flow D&A line.
_DEP_TAGS = ["DepreciationDepletionAndAmortization",
             "DepreciationAndAmortization",
             "DepreciationAmortizationAndAccretionNet"]
_REVENUE_TAGS = ["Revenues",
                 "RevenueFromContractWithCustomerExcludingAssessedTax"]
_SHARES_TAGS_INSTANT = ["CommonStockSharesOutstanding"]
_SHARES_TAGS_ANNUAL = ["WeightedAverageNumberOfDilutedSharesOutstanding"]

_ALL_CONCEPTS = ([_ASSETS_CUR, _CASH, _LIAB_CUR, _ASSETS] + _STD_TAGS + _DEP_TAGS
                 + _REVENUE_TAGS + _SHARES_TAGS_INSTANT + _SHARES_TAGS_ANNUAL)


def _annual_flows(df):
    """Full-year (330-400 day) duration rows, AS-FIRST-REPORTED per period_end."""
    df = df.dropna(subset=["period_start", "period_end", "filed_date", "value"]).copy()
    df["dur"] = (df["period_end"] - df["period_start"]).dt.days
    df = df[(df["dur"] >= 330) & (df["dur"] <= 400)]
    return (df.sort_values("filed_date")
              .drop_duplicates(["ticker", "period_end"], keep="first"))


def _instant_first(df):
    """Instant concept, EARLIEST filed per (ticker, period_end)."""
    df = df.dropna(subset=["period_end", "filed_date", "value"]).copy()
    # instants have no period_start; guard in case a duration row slipped in
    return (df.sort_values("filed_date")
              .drop_duplicates(["ticker", "period_end"], keep="first"))


def _pick_instant(series_pe, series_val, series_fd, target_pe, tol_days):
    """Nearest instant to target_pe within tol_days -> (value, filed_date)."""
    if len(series_pe) == 0:
        return None, None
    diffs = np.abs((series_pe - target_pe).dt.days.values)
    k = int(diffs.argmin())
    if diffs[k] > tol_days:
        return None, None
    return float(series_val.iloc[k]), series_fd.iloc[k]


def _combine_first_reported(fund, tags, kind):
    """Union several tags into one first-reported series (annual or instant)."""
    sub = fund[fund["concept"].isin(tags)]
    if sub.empty:
        return sub
    if kind == "annual":
        out = _annual_flows(sub)
    else:
        out = _instant_first(sub)
    # if multiple tags cover the same period, keep the earliest-filed single value
    return (out.sort_values("filed_date")
               .drop_duplicates(["ticker", "period_end"], keep="first"))


def _pit_fundamentals(tickers):
    """Per (ticker, avail_date): accrual (Sloan), rev_annual (dollars), shares."""
    cols = ["ticker", "avail_date", "accrual", "rev_annual", "shares"]
    fund = fetch_fundamentals(list(tickers), concepts=_ALL_CONCEPTS)
    if fund.empty:
        return pd.DataFrame(columns=cols)
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()

    assets_cur = _combine_first_reported(fund, [_ASSETS_CUR], "instant")
    cash = _combine_first_reported(fund, [_CASH], "instant")
    liab_cur = _combine_first_reported(fund, [_LIAB_CUR], "instant")
    assets = _combine_first_reported(fund, [_ASSETS], "instant")
    std = _combine_first_reported(fund, _STD_TAGS, "instant")
    dep = _combine_first_reported(fund, _DEP_TAGS, "annual")
    rev = _combine_first_reported(fund, _REVENUE_TAGS, "annual")
    shares_inst = _combine_first_reported(fund, _SHARES_TAGS_INSTANT, "instant")
    shares_wavg = _combine_first_reported(fund, _SHARES_TAGS_ANNUAL, "annual")

    records = []
    for ticker in pd.unique(fund["ticker"]):
        ac = assets_cur[assets_cur["ticker"] == ticker].sort_values("period_end")
        ca = cash[cash["ticker"] == ticker].sort_values("period_end")
        lc = liab_cur[liab_cur["ticker"] == ticker].sort_values("period_end")
        at = assets[assets["ticker"] == ticker].sort_values("period_end")
        sd = std[std["ticker"] == ticker].sort_values("period_end")
        dp = dep[dep["ticker"] == ticker].sort_values("period_end")
        rv = rev[rev["ticker"] == ticker].sort_values("period_end")
        shi = shares_inst[shares_inst["ticker"] == ticker].sort_values("period_end")
        shw = shares_wavg[shares_wavg["ticker"] == ticker].sort_values("period_end")

        # ---- Leg 1: Sloan operating accruals, anchored on annual-depreciation FYEs
        for i in range(len(dp)):
            fye = dp["period_end"].iloc[i]
            dep_val = float(dp["value"].iloc[i])
            prior = fye - pd.Timedelta(days=365)

            def nwc(target, tol):
                acv, acf = _pick_instant(ac["period_end"], ac["value"], ac["filed_date"], target, tol)
                cav, caf = _pick_instant(ca["period_end"], ca["value"], ca["filed_date"], target, tol)
                lcv, lcf = _pick_instant(lc["period_end"], lc["value"], lc["filed_date"], target, tol)
                if acv is None or cav is None or lcv is None:
                    return None, None
                # short-term debt: missing name -> treated as 0 (standard Sloan practice)
                sdv, sdf = _pick_instant(sd["period_end"], sd["value"], sd["filed_date"], target, tol)
                if sdv is None:
                    sdv, sdf = 0.0, None
                val = (acv - cav) - (lcv - sdv)
                fds = [f for f in (acf, caf, lcf, sdf) if f is not None]
                return val, (max(fds) if fds else None)

            nwc_t, fd_t = nwc(fye, tol=15)
            nwc_p, fd_p = nwc(prior, tol=50)
            at_t, atf_t = _pick_instant(at["period_end"], at["value"], at["filed_date"], fye, 15)
            at_p, atf_p = _pick_instant(at["period_end"], at["value"], at["filed_date"], prior, 50)
            if (nwc_t is None or nwc_p is None or at_t is None or at_p is None):
                continue
            avg_assets = (at_t + at_p) / 2.0
            if not np.isfinite(avg_assets) or avg_assets <= 0:
                continue
            accrual = ((nwc_t - nwc_p) - dep_val) / avg_assets
            if not np.isfinite(accrual):
                continue
            # avail_date = latest filing among all current-year inputs
            fds = [dp["filed_date"].iloc[i], fd_t, atf_t]
            fds = [f for f in fds if f is not None]
            avail = max(fds)
            records.append({"ticker": ticker, "avail_date": avail,
                            "accrual": accrual, "rev_annual": np.nan,
                            "shares": np.nan})

        # ---- Leg 2 numerator: annual revenue
        for i in range(len(rv)):
            rv_val = float(rv["value"].iloc[i])
            if not np.isfinite(rv_val) or rv_val <= 0:
                continue
            records.append({"ticker": ticker,
                            "avail_date": rv["filed_date"].iloc[i],
                            "accrual": np.nan, "rev_annual": rv_val,
                            "shares": np.nan})

        # ---- Leg 2 denominator: shares (prefer instant count, fall back to wavg)
        sh_src = shi if len(shi) else shw
        for i in range(len(sh_src)):
            sh_val = float(sh_src["value"].iloc[i])
            if not np.isfinite(sh_val) or sh_val <= 0:
                continue
            records.append({"ticker": ticker,
                            "avail_date": sh_src["filed_date"].iloc[i],
                            "accrual": np.nan, "rev_annual": np.nan,
                            "shares": sh_val})

    out = pd.DataFrame(records)
    if out.empty:
        return pd.DataFrame(columns=cols)
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"accrual": "last", "rev_annual": "last", "shares": "last"}))
    return out


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    for c in ["accrual", "rev_annual", "shares"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    cols = ["avail_date", "accrual", "rev_annual", "shares"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][cols]
        if f.empty:
            for c in cols[1:]:
                g[c] = np.nan
        else:
            g = pd.merge_asof(g, f.sort_values("avail_date"),
                              left_on="date", right_on="avail_date",
                              direction="backward")
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # ---- Leg 2: sales yield = annual revenue / point-in-time market cap ----
    mktcap = panel["shares"] * panel["adj_close"]
    panel["sales_yield"] = np.where(mktcap > 0, panel["rev_annual"] / mktcap, np.nan)

    # ---- Leg 1: earnings-quality rank WITHIN (date, industry). LOW accrual =
    #      GOOD, so rank on -accrual: low accrual -> high rank -> bullish. ----
    panel["accrual_reliability_rank"] = (
        panel.assign(_neg_accrual=-panel["accrual"])
        .groupby(["date", "industry"])["_neg_accrual"]
        .rank(pct=True, ascending=True)
    )

    # ---- Leg 2: sales-yield rank WITHIN (date, industry). HIGH yield = cheap =
    #      bullish -> high rank. ----
    panel["sales_yield_rank"] = (
        panel.groupby(["date", "industry"])["sales_yield"]
        .rank(pct=True, ascending=True)
    )

    new_cols = ["accrual_reliability_rank", "sales_yield_rank"]
    panel = panel.drop(columns=["avail_date", "accrual", "rev_annual",
                                "shares", "sales_yield"], errors="ignore")
    return panel, new_cols
