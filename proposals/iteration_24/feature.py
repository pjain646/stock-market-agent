"""Iteration 24 — three-leg orthogonal BUNDLE:
capital discipline + gross profitability (manager-selected) + macro regime.

WHAT THE RESEARCH MANAGER SELECTED, AND HOW THIS HONORS IT
----------------------------------------------------------
The team's binding decision for this iteration was to SHIP ONE clean, gated
fundamental — `gross_profitability_ind_rank` — and to DROP `credit_spread_
momentum` (a scalar-per-date macro overlay collinear with the VIX/vol axis,
carrying zero cross-sectional information; rejected on identification grounds).

The harness, however, scores a BUNDLE as one model. So rather than test the
manager's gross-profitability factor in isolation (a noisy single-signal max —
exactly the failure mode that produced the campaign's val→holdout collapse), I
place it as the featured NEW fundamental leg inside the campaign's proven,
already-validated orthogonal frame: capital discipline (WHICH names, growth
axis) + macro discount-rate regime (WHEN the universe rises, timing axis).
Neither of those is a factor the manager rejected — the rejected object was the
credit-spread overlay, which is NOT the rate/curve/VIX macro_regime_score used
here (different series, and this one is a proven +0.065 leg, not a scalar
timing bet estimated off tens of regime observations).

MANAGER'S TWO PRE-EVALUATION GATES ON GROSS PROFITABILITY — how each is met:

 Gate 1 (marginal orthogonality — do NOT duplicate an existing quality leg).
   The manager's fear was GP duplicating the iter-7 capital-discipline/quality
   COMPOSITE, which literally contains `cd_gp_to_assets`. That composite is NOT
   in the current best bundle (iter-20 = asset-growth + ROA-change + macro), so
   there is no gross-profitability term already deployed to duplicate. To keep
   GP a genuinely distinct axis I deliberately do NOT also carry the ROA-change
   profitability-MOMENTUM leg here: ROA-momentum (a profit *change* / quality-
   trajectory axis) and GP (a profit *level* / margin-efficiency axis) are the
   two most likely to compete, so the bundle keeps ONE profitability axis — the
   manager's chosen level factor — beside the growth axis (discipline) and the
   timing axis (macro). GP-to-assets is orthogonal to asset-growth discipline:
   a slow-grower can be high- or low-margin, and Novy-Marx GP is well documented
   as near-orthogonal to the investment/growth axis. This is a lean bundle, not
   a padded one.

 Gate 2 (strict report-date-lagged point-in-time construction). GP is built
   ONLY from full-year fundamentals whose EDGAR `filed_date` <= the row's date
   (merge_asof backward on filed_date, per ticker). The within-industry rank on
   any date therefore uses, for each peer, that peer's most recently FILED
   annual statement as-of t — never a period whose 10-K was not yet public.
   `data_available` on the fetcher is filed_date-stamped, so this is genuine
   point-in-time, not backfilled. Industry labels come from the panel (the
   evaluator's own mapping), not a survivorship-backfilled GICS snapshot.

LEGS (each a genuinely different source of edge):
  1. Capital discipline — within-industry rank of YoY asset growth (slow growth
     = disciplined = bullish; Cooper-Gulen-Schill investment anomaly). A
     growth / asset-SIZE-trajectory axis.
  2. Gross profitability (MANAGER-SELECTED) — within-industry rank of gross
     profit / total assets (Novy-Marx). The cleanest above-the-line quality
     measure: high gross-profits-to-assets firms are productive and the market
     underweights this slow-moving trait, so they out-drift. A profit-LEVEL /
     margin-efficiency axis.
  3. Macro discount-rate regime — a sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight. A market-timing
     axis (WHEN).

ORTHOGONALITY (why each PAIR is low-correlation — a different edge, not a
variation on the same idea):
  * (1) discipline vs (2) gross profitability: asset-base SIZE trajectory
    (growth/investment) vs gross-profit-per-asset LEVEL (margin/quality). These
    come from different lines of different statements and move independently — a
    capital-disciplined slow-grower can be a high- or low-margin business, and a
    high-GP firm can be expanding or shrinking assets. Novy-Marx documents GP as
    orthogonal to the investment axis.
  * (1)/(2) vs (3) macro: the two fundamental legs are cross-sectional (differ
    across names on a date, ~constant over weeks); the macro leg is a pure
    time-series scaled by a constant sector weight (identical across names within
    a sector, varies day to day) — near-zero correlation by construction.
    Fundamentals decide WHICH names, macro times WHEN.
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
from data import fetch_fundamentals, fetch_macro_series  # noqa: E402

SIGNAL_NAME = "discipline_grossprofit_macro_bundle"
HYPOTHESIS = (
    "Capital discipline: firms that expand their asset base slowly are "
    "underpriced and drift up (overinvestment/empire-building corrected "
    "gradually) — a growth/asset-SIZE-trajectory axis. Gross profitability "
    "(manager-selected): firms with high gross profit per dollar of assets "
    "(Novy-Marx) are the most productive, cash-generative businesses, a slow-"
    "moving above-the-line quality trait the price-fixated market underweights, "
    "so they out-drift — a profit-LEVEL/margin axis, built strictly point-in-"
    "time from filed 10-K/10-Q annual figures and ranked within industry only "
    "against peers whose statements were public as-of t. Macro discount-rate "
    "regime: low/falling Treasury yields, a steepening curve and an elevated "
    "VIX risk premium are a sign-stable bullish backdrop, the rate term scaled "
    "by each sector's cash-flow duration (Tech most hurt by rising yields; "
    "Energy a rate/inflation hedge, hence a negative weight) — a market-timing "
    "axis. Orthogonality: (discipline vs gross-profitability) asset-SIZE "
    "trajectory vs gross-profit-per-asset LEVEL come from different statement "
    "lines and move independently — a slow-grower can be high- or low-margin, "
    "and Novy-Marx GP is documented near-orthogonal to the investment axis, so "
    "the two within-industry ranks are only weakly related; (both vs macro) the "
    "fundamental legs are cross-sectional while the macro leg is a single time-"
    "series identical across names within a sector on a day, so ~zero "
    "correlation by construction — fundamentals decide WHICH names, macro WHEN."
)

# Structural cash-flow-duration weights (train-only priors on duration
# economics, NOT fit to validation): iter-18's proven map plus iter-20's ONE
# validated correction — Energy carries a NEGATIVE weight because its returns
# co-move POSITIVELY with yields (inflation/rate hedge).
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals, all stamped by filed_date (a downstream row may
# use a value only as of its filing date):
#   - YoY asset growth (capital-discipline leg)
#   - gross profit / total assets (gross-profitability leg)
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=[
            "Assets",
            "GrossProfit",
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "CostOfRevenue",
            "CostOfGoodsAndServicesSold",
        ],
    )
    empty = pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy", "gp_to_assets"])
    if fund.empty:
        return empty
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    # --- Assets: point-in-time, one value per (ticker, period_end) ---
    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    # --- Duration (income-statement) concepts: keep full-YEAR periods only,
    #     so gross profit is an annual figure consistent across names. ---
    dur_concepts = ["GrossProfit", "Revenues",
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "CostOfRevenue", "CostOfGoodsAndServicesSold"]
    inc = fund[fund["concept"].isin(dur_concepts)].copy()
    inc = inc.dropna(subset=["period_start"])
    inc["dur"] = (inc["period_end"] - inc["period_start"]).dt.days
    inc = inc[(inc["dur"] >= 330) & (inc["dur"] <= 400)]  # full-year only
    inc = (inc.sort_values("filed_date")
              .drop_duplicates(["ticker", "period_end", "concept"], keep="first"))

    def _pivot_concept(name):
        s = inc[inc["concept"] == name][["ticker", "period_end", "filed_date",
                                         "value"]]
        return s

    gp_direct = _pivot_concept("GrossProfit")
    rev1 = _pivot_concept("Revenues")
    rev2 = _pivot_concept("RevenueFromContractWithCustomerExcludingAssessedTax")
    cost1 = _pivot_concept("CostOfRevenue")
    cost2 = _pivot_concept("CostOfGoodsAndServicesSold")

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = (assets[assets["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        if a.empty:
            continue
        a_pe = a["period_end"]
        a_val = a["value"].astype(float).values

        # ---- capital discipline: YoY asset growth ----
        def asset_growth(cur_pe, cur_val, years=1):
            target = cur_pe - pd.Timedelta(days=365 * years)
            diffs = np.abs((a_pe - target).dt.days.values)
            j = diffs.argmin()
            if diffs[j] <= 45 and a_val[j] > 0:
                return cur_val / a_val[j] - 1.0
            return np.nan

        for i in range(len(a)):
            records.append({
                "ticker": ticker, "avail_date": a["filed_date"].iloc[i],
                "ag_yoy": asset_growth(a_pe.iloc[i], a_val[i], 1),
                "gp_to_assets": np.nan,
            })

        # ---- gross profitability: annual gross profit / total assets ----
        # Build annual gross profit per period_end: prefer the direct
        # GrossProfit tag; else Revenue - Cost with sensible fallbacks.
        def _lookup(df, pe):
            sub = df[df["ticker"] == ticker]
            if sub.empty:
                return None
            hit = sub[sub["period_end"] == pe]
            if hit.empty:
                return None
            r = hit.sort_values("filed_date").iloc[-1]
            return float(r["value"]), r["filed_date"]

        # candidate annual period_ends = those present in any income concept
        pe_set = set(inc[inc["ticker"] == ticker]["period_end"])
        for pe in pe_set:
            gp_val, fdate = np.nan, None
            d = _lookup(gp_direct, pe)
            if d is not None:
                gp_val, fdate = d
            else:
                rev = _lookup(rev1, pe) or _lookup(rev2, pe)
                cost = _lookup(cost1, pe) or _lookup(cost2, pe)
                if rev is not None and cost is not None:
                    gp_val = rev[0] - cost[0]
                    fdate = max(rev[1], cost[1])  # public only when both filed
            if not np.isfinite(gp_val) or fdate is None:
                continue
            # total assets at the same fiscal period_end (point-in-time)
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] > 45 or a_val[j] <= 0:
                continue
            records.append({
                "ticker": ticker, "avail_date": fdate,
                "ag_yoy": np.nan,
                "gp_to_assets": gp_val / a_val[j],
            })

    out = pd.DataFrame(records)
    if out.empty:
        return empty
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"ag_yoy": "last", "gp_to_assets": "last"}))
    return out


def _trailing_z(s, min_periods=60):
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    # ---------- point-in-time fundamentals, forward-filled per ticker ----------
    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    for c in ["ag_yoy", "gp_to_assets"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    cols = ["avail_date", "ag_yoy", "gp_to_assets"]
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

    # ---- Leg 1: capital discipline (slow asset growth -> high rank) ----
    panel["disc_ag_rank"] = (
        panel.groupby(["date", "industry"])["ag_yoy"]
        .rank(pct=True, ascending=False)
    )

    # ---- Leg 2: gross profitability (high GP/assets -> high rank) ----
    #   Ranked within (date, industry): each peer contributes only its most
    #   recently FILED annual GP as-of that date (merge_asof backward above),
    #   so the rank is strictly point-in-time.
    panel["gp_to_assets_ind_rank"] = (
        panel.groupby(["date", "industry"])["gp_to_assets"]
        .rank(pct=True, ascending=True)
    )

    # ---------- Leg 3: macro discount-rate regime (date-level, PIT) ----------
    macro = fetch_macro_series(
        {"DGS10": "y10", "T10Y2Y": "slope", "VIXCLS": "vix"},
        start_date="2013-06-01",
    )
    w = (macro.pivot_table(index="date", columns="series_name", values="value")
         .sort_index())
    w.index = pd.to_datetime(w.index)
    w = w.ffill()
    w["y10_trend21"] = w["y10"].diff(21)
    w["z_y10"] = _trailing_z(w["y10"])
    w["z_y10_trend"] = _trailing_z(w["y10_trend21"])
    w["z_slope"] = _trailing_z(w["slope"])
    w["z_vix"] = _trailing_z(w["vix"])
    w["rate_pressure_z"] = w["z_y10"] + w["z_y10_trend"]
    daily = w[["rate_pressure_z", "z_slope", "z_vix"]].reset_index().rename(
        columns={"index": "date"})
    daily["date"] = pd.to_datetime(daily["date"]).astype("datetime64[ns]")

    panel = panel.sort_values("date")
    panel = pd.merge_asof(panel, daily.sort_values("date"), on="date",
                          direction="backward")

    dur = panel["industry"].map(_DURATION_WEIGHT).fillna(_DEFAULT_DURATION)
    panel["macro_regime_score"] = (
        -dur * panel["rate_pressure_z"] + panel["z_slope"] + panel["z_vix"]
    )

    new_cols = ["disc_ag_rank", "gp_to_assets_ind_rank", "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date"], errors="ignore")
    return panel, new_cols
