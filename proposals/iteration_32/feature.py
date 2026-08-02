"""Iteration 32 — two-leg orthogonal BUNDLE (MANAGER-SELECTED, EXACT):
operating_margin_pricing_power + free_cash_flow_yield.

WHAT THE RESEARCH MANAGER SELECTED, AND HOW THIS HONORS IT
----------------------------------------------------------
Binding ruling this iteration: SHIP exactly two orthogonal fundamental legs —
(1) operating margin (pure profitability LEVEL, NO price term) and (2) free-cash-
flow yield (a cash numerator OVER market cap, a CHEAPNESS axis). The third
candidate, `real_rate_pressure_scaled_beta`, was DROPPED by the team (its novelty
— a per-date real-yield scalar — carries zero cross-sectional information, and the
part that ranks names is just iter-17's weak nominal-rate beta ranker). I do NOT
implement any macro leg, and I do NOT re-add the campaign's proven
solvency/profmom/macro frame even though it scored +0.075 — re-adding dropped
factors overrides the team's decision. TWO legs are selected; TWO legs are built.

WHY THESE TWO ARE A GENUINE BUNDLE, NOT A LONE FACTOR
----------------------------------------------------
Margin (OperatingIncome / Revenues) has NO denominator involving price — it is a
pure profitability/quality ratio. FCF yield (FCF / market cap) divides by market
cap — it is a valuation/cheapness ratio. Orthogonal BY CONSTRUCTION: the
presence/absence of the price denominator is what separates "is this a good
business?" (quality) from "is this business cheap?" (cheapness), not a tuning
knob. Two real cross-sectional rankers = the Fundamental/Valuation split, which is
NOT a best-of-N single-signal max, so it does not inherit Campaign-1's Gate-1
selection-pressure failure.

BINDING BUILD CONSTRAINTS (from the ruling — applied to BOTH legs):
  (a) SECTOR-RELATIVE: both legs are ranked WITHIN (date, industry) — the
      within-industry percentile rank IS the sector-demeaning, so names sort
      against sector peers, not sectors against each other.
  (b) FINANCIALS & REAL ESTATE EXPLICITLY EXCLUDED from BOTH legs — set to NaN,
      never imputed, never patched with hand-set per-sector weights.
      Rationale: OperatingIncome/Revenues is undefined for Financials and
      degenerate for Real Estate; OCF-capex is dominated by financing/deposit
      flows in Financials and mishandles property capex in REITs (AFFO != FCF).
      Sector-demeaning cannot repair a ratio whose economic MEANING changes by
      sector, so those rows are dropped to NaN, not rescued.
  (c) TRAILING-ANNUAL FCF (full-year OCF and full-year capex) to smooth the
      lumpiness of quarterly cash flows; RANK-based, never raw magnitude.
  (d) The evaluator scores the two-leg bundle as ONE model; the deterministic
      judge's per-leg ablation (bundle vs each leg alone) will show whether the
      two compound or partially cancel. That is a real result either way.

POINT-IN-TIME DISCIPLINE
------------------------
Every fundamental line is taken AS-FIRST-REPORTED (earliest filed_date per fiscal
period, so a later restatement never leaks backward), stamped by that ORIGINAL
filing date (never by period_end), and forward-filled per ticker. A panel row uses
a value only as of the date it became public. Full-year duration periods only
(330-400 days) so levels are annual and comparable. Non-positive revenue excluded
(margin cannot sign-invert). Market cap = point-in-time shares outstanding x that
row's adj_close.

CAVEAT (stated, not hidden): adj_close is split/dividend-adjusted, so historical
market caps built from it are biased downward for high-dividend names relative to
a raw price. FCF yield is a within-(date,industry) RANK, which absorbs a common
level shift, but the dividend-adjustment drift is name-specific; this is a known,
flagged limitation of using the only price series available in the panel, not a
silent substitution.

LEGS:
  1. operating_margin_rank (MANAGER-SELECTED) — within-industry rank of annual
     OperatingIncomeLoss / Revenues. Pricing-power / profitability LEVEL: firms
     that convert each sales dollar into more operating profit have durable
     pricing power / cost advantage the price-fixated market underweights.
     High margin -> high rank -> bullish.
  2. fcf_yield_rank (MANAGER-SELECTED) — within-industry rank of trailing-annual
     (OCF - capex) / market cap. CHEAPNESS: firms generating more free cash per
     dollar of market value are underpriced relative to the cash they throw off.
     High FCF yield -> high rank -> bullish.

ORTHOGONALITY (why the PAIR is a different edge, not one idea twice): margin has
NO market-price term (a pure income-statement quality ratio); FCF yield's entire
denominator IS market price (a valuation ratio). A high-margin firm can be
expensive (low FCF yield) or cheap; a cheap firm can be high- or low-margin. The
price denominator being present in one and absent in the other makes them
near-uncorrelated by construction — quality vs cheapness.
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

SIGNAL_NAME = "operating_margin_fcf_yield_bundle"
HYPOTHESIS = (
    "Operating margin / pricing power (MANAGER-SELECTED): annual OperatingIncome "
    "/ Revenues is a pure profitability LEVEL with NO price term; firms that "
    "convert each sales dollar into more operating profit have durable pricing "
    "power or a cost advantage the price-fixated market underweights, so high-"
    "margin firms out-drift — ranked WITHIN industry (sector-demeaned) and built "
    "strictly point-in-time from filed 10-K/10-Q operating income and revenue "
    "taken AS-FIRST-REPORTED (earliest filed_date per fiscal period, never "
    "restated-in-place, never stamped by period-end), full-year periods only, "
    "non-positive revenue excluded so the ratio cannot sign-invert. Free-cash-"
    "flow yield (MANAGER-SELECTED): trailing-annual (operating cash flow - capex) "
    "/ market cap is a CHEAPNESS ratio whose denominator IS market price; firms "
    "throwing off more free cash per dollar of market value are underpriced "
    "relative to the cash they generate, so high-FCF-yield firms out-drift — "
    "trailing-annual to smooth quarterly lumpiness, ranked WITHIN industry, "
    "market cap = point-in-time shares outstanding x adj_close. BOTH legs "
    "EXCLUDE Financials and Real Estate (NaN, not imputed): OperatingIncome/"
    "Revenues is undefined for banks and degenerate for REITs, and OCF-capex is "
    "dominated by financing/deposit flows in Financials and mishandles property "
    "capex in REITs (AFFO != FCF) — sector-demeaning cannot repair a ratio whose "
    "meaning changes by sector. Orthogonality: margin has NO market-price term (a "
    "pure income-statement quality ratio) while FCF yield's entire denominator IS "
    "market price (a valuation ratio); a high-margin firm can be expensive or "
    "cheap and a cheap firm can be high- or low-margin, so the presence/absence "
    "of the price denominator makes them near-uncorrelated by construction — "
    "quality vs cheapness, the Fundamental/Valuation split, not a lone factor. "
    "NOTE: the dropped real_rate_pressure_scaled_beta macro leg is deliberately "
    "NOT implemented (its real-yield novelty is a per-date scalar with zero "
    "cross-sectional information), and the campaign's prior solvency/profmom/"
    "macro frame is NOT re-added — the team selected exactly these two legs."
)

# Sectors where BOTH ratios are economically ill-defined -> excluded to NaN.
_EXCLUDED_SECTORS = {"Financials", "RealEstate"}

# Revenue is reported under two common XBRL tags; combine, prefer whichever a
# company actually files.
_REVENUE_TAGS = ["Revenues",
                 "RevenueFromContractWithCustomerExcludingAssessedTax"]


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
    return (df.sort_values("filed_date")
              .drop_duplicates(["ticker", "period_end"], keep="first"))


def _nearest(series_pe, series_val, series_fd, target_pe, tol_days=45):
    """Nearest period_end match within tol_days; returns (value, filed_date)."""
    if len(series_pe) == 0:
        return None, None
    diffs = np.abs((series_pe - target_pe).dt.days.values)
    k = diffs.argmin()
    if diffs[k] > tol_days:
        return None, None
    return float(series_val.iloc[k]), series_fd.iloc[k]


def _pit_fundamentals(tickers):
    """Per (ticker, avail_date): op_margin, fcf_annual (dollars), shares."""
    cols = ["ticker", "avail_date", "op_margin", "fcf_annual", "shares"]
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["OperatingIncomeLoss",
                  "Revenues",
                  "RevenueFromContractWithCustomerExcludingAssessedTax",
                  "NetCashProvidedByUsedInOperatingActivities",
                  "PaymentsToAcquirePropertyPlantAndEquipment",
                  "CommonStockSharesOutstanding",
                  "WeightedAverageNumberOfDilutedSharesOutstanding"],
    )
    if fund.empty:
        return pd.DataFrame(columns=cols)
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()

    opinc = _annual_flows(fund[fund["concept"] == "OperatingIncomeLoss"])
    rev = _annual_flows(fund[fund["concept"].isin(_REVENUE_TAGS)])
    # if a period has both revenue tags, keep the earliest-filed single value
    rev = (rev.sort_values("filed_date")
              .drop_duplicates(["ticker", "period_end"], keep="first"))
    ocf = _annual_flows(fund[fund["concept"] ==
                             "NetCashProvidedByUsedInOperatingActivities"])
    capex = _annual_flows(fund[fund["concept"] ==
                               "PaymentsToAcquirePropertyPlantAndEquipment"])
    shares_inst = _instant_first(fund[fund["concept"] ==
                                      "CommonStockSharesOutstanding"])
    shares_wavg = _annual_flows(fund[fund["concept"] ==
                                     "WeightedAverageNumberOfDilutedSharesOutstanding"])

    records = []
    for ticker in pd.unique(fund["ticker"]):
        op = opinc[opinc["ticker"] == ticker].sort_values("period_end")
        rv = rev[rev["ticker"] == ticker].sort_values("period_end")
        oc = ocf[ocf["ticker"] == ticker].sort_values("period_end")
        cx = capex[capex["ticker"] == ticker].sort_values("period_end")
        shi = shares_inst[shares_inst["ticker"] == ticker].sort_values("period_end")
        shw = shares_wavg[shares_wavg["ticker"] == ticker].sort_values("period_end")

        # ---- Leg 1: operating margin = annual OperatingIncome / annual Revenue
        for i in range(len(op)):
            pe = op["period_end"].iloc[i]
            oi = float(op["value"].iloc[i])
            rev_val, rev_fd = _nearest(rv["period_end"], rv["value"],
                                       rv["filed_date"], pe)
            if rev_val is None or not np.isfinite(rev_val) or rev_val <= 0:
                continue
            fdate = max(op["filed_date"].iloc[i], rev_fd)
            records.append({"ticker": ticker, "avail_date": fdate,
                            "op_margin": oi / rev_val,
                            "fcf_annual": np.nan, "shares": np.nan})

        # ---- Leg 2 numerator: trailing-annual FCF = annual OCF - annual capex
        for i in range(len(oc)):
            pe = oc["period_end"].iloc[i]
            ocf_val = float(oc["value"].iloc[i])
            cx_val, cx_fd = _nearest(cx["period_end"], cx["value"],
                                     cx["filed_date"], pe)
            if cx_val is None or not np.isfinite(cx_val):
                continue  # require an explicit capex line rather than assume 0
            fdate = max(oc["filed_date"].iloc[i], cx_fd)
            records.append({"ticker": ticker, "avail_date": fdate,
                            "op_margin": np.nan,
                            "fcf_annual": ocf_val - cx_val, "shares": np.nan})

        # ---- Leg 2 denominator: shares outstanding (prefer instant count,
        #      fall back to weighted-average diluted)
        sh_src = shi if len(shi) else shw
        for i in range(len(sh_src)):
            sh_val = float(sh_src["value"].iloc[i])
            if not np.isfinite(sh_val) or sh_val <= 0:
                continue
            records.append({"ticker": ticker,
                            "avail_date": sh_src["filed_date"].iloc[i],
                            "op_margin": np.nan, "fcf_annual": np.nan,
                            "shares": sh_val})

    out = pd.DataFrame(records)
    if out.empty:
        return pd.DataFrame(columns=cols)
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"op_margin": "last", "fcf_annual": "last", "shares": "last"}))
    return out


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    for c in ["op_margin", "fcf_annual", "shares"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    cols = ["avail_date", "op_margin", "fcf_annual", "shares"]
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

    # ---- market cap = point-in-time shares x that row's adj_close ----
    mktcap = panel["shares"] * panel["adj_close"]
    panel["fcf_yield"] = np.where(mktcap > 0, panel["fcf_annual"] / mktcap, np.nan)

    # ---- BOTH legs: exclude Financials & Real Estate (NaN, not imputed) ----
    excl = panel["industry"].isin(_EXCLUDED_SECTORS)
    panel.loc[excl, "op_margin"] = np.nan
    panel.loc[excl, "fcf_yield"] = np.nan

    # ---- Leg 1: operating-margin rank WITHIN (date, industry) ----
    panel["operating_margin_rank"] = (
        panel.groupby(["date", "industry"])["op_margin"]
        .rank(pct=True, ascending=True)
    )

    # ---- Leg 2: FCF-yield rank WITHIN (date, industry) ----
    panel["fcf_yield_rank"] = (
        panel.groupby(["date", "industry"])["fcf_yield"]
        .rank(pct=True, ascending=True)
    )

    new_cols = ["operating_margin_rank", "fcf_yield_rank"]
    panel = panel.drop(columns=["avail_date", "op_margin", "fcf_annual",
                                "shares", "fcf_yield"], errors="ignore")
    return panel, new_cols
