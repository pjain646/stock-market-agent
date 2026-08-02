"""Iteration 25 — three-leg orthogonal BUNDLE:
equity-to-assets solvency (MANAGER-SELECTED) + profitability momentum + macro
discount-rate regime.

WHAT THE RESEARCH MANAGER SELECTED, AND HOW THIS HONORS IT
----------------------------------------------------------
The team's binding decision this iteration was to SHIP `equity_to_assets_
solvency` — a capital-structure LEVEL factor — and to DROP `usd_broad_dollar_
pressure`. The dollar factor was rejected on structural identification grounds:
it is a single universe-constant time-series assigned identically to all 166
tickers, so in a cross-sectional rank it contributes ZERO discriminating
information (it can say WHEN the tape rises, not WHICH stock outperforms) and it
is collinear with the existing rate leg. I do NOT implement it.

The harness scores a BUNDLE as one model. Testing the manager's solvency factor
in isolation would recreate the exact single-signal noisy-max failure that sank
the first campaign's holdout. So I place solvency as the featured NEW leg inside
the campaign's proven, already-validated orthogonal frame: profitability
momentum (a quality axis the manager explicitly called "mechanically distinct"
from solvency — capital-structure LEVEL vs income/assets) and the macro
discount-rate regime (a WHEN/timing axis). Neither partner is a factor the
manager rejected; the rejected object was the non-discriminating dollar series,
which is NOT the rate/curve/VIX macro_regime_score used here. I deliberately do
NOT also carry the asset-growth capital-discipline leg: the journal shows a
fourth cross-sectional fundamental cannibalises rather than compounds
(iter-22 four-leg +0.0572 < iter-20 three-leg +0.0654), and the manager warned
explicitly against padding. Three genuinely orthogonal axes, not four.

THE MANAGER'S SOLVENCY BUILD SPEC — "build it that way or not at all" — met:
  * NEGATIVE / ZERO book equity (buyback-financed HD/MCD/AZO-type names) would
    sign-INVERT the raw ratio and flag the highest-quality firms as the most
    "distressed". I exclude every row with StockholdersEquity <= 0 (set to NaN),
    so they never enter the within-industry rank.
  * FINANCIALS whose leverage accounting differs: the factor is ranked WITHIN
    (date, industry), so banks/insurers are compared only to each other and
    Novy-Marx-style cross-sector leverage-accounting distortion is neutralised
    by construction rather than by an ad-hoc sector drop.
  * FIXED FILING LAGS: every fundamental is stamped by EDGAR filed_date and
    joined merge_asof BACKWARD on that date, so each peer contributes only the
    most recently FILED balance sheet as-of t — no lookahead.
  * WINSORIZATION: equity/assets for positive-equity firms is naturally bounded
    in (0, 1]; I additionally clip to [0, 1] to kill any bad print. Ranking is
    monotonic so this only guards against outlier leakage.

ECONOMIC DIRECTION: high equity/assets = low leverage = financially solvent /
low distress risk. The distress / low-leverage anomaly (Campbell-Hilscher-Szilagyi,
low-risk effect) says highly levered, distress-prone firms UNDER-perform on a
risk-adjusted basis, so solvent low-leverage firms out-drift. Rank ASCENDING:
high solvency -> high rank -> bullish.

LEGS (each a genuinely different source of edge):
  1. Equity-to-assets solvency (MANAGER-SELECTED) — within-industry rank of
     StockholdersEquity / Assets. A capital-structure LEVEL / distress-risk axis.
  2. Profitability momentum — within-industry rank of YoY change in return-on-
     assets; firms whose profit-PER-asset trajectory is improving are on a
     strengthening fundamental path the market prices in only gradually. A
     quality-CHANGE / earnings-trajectory axis.
  3. Macro discount-rate regime — a sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight. A market-timing
     axis (WHEN).

ORTHOGONALITY (why each PAIR is low-correlation — a different edge, not a
variation on the same idea):
  * (1) solvency vs (2) prof-momentum: a capital-structure LEVEL (how the firm
    is FINANCED, a stock on the balance sheet) vs a profitability CHANGE (how
    fast income-per-asset is IMPROVING, a flow off the income statement). A
    low-leverage firm can have rising OR falling ROA, and a firm with improving
    ROA can be highly levered or unlevered — different statements, different time
    character (slow-moving level vs a year-over-year delta), so the two
    within-industry ranks are near-uncorrelated. The manager itself certified
    these as mechanically distinct.
  * (1)/(2) vs (3) macro: the two fundamental legs are cross-sectional (differ
    across names on a date, ~constant over weeks); the macro leg is a pure
    time-series scaled by a constant sector weight (identical across names within
    a sector, varies day to day) — near-zero correlation by construction.
    Fundamentals decide WHICH names, macro times WHEN the universe rises.
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

SIGNAL_NAME = "solvency_profmom_macro_bundle"
HYPOTHESIS = (
    "Equity-to-assets solvency (MANAGER-SELECTED): high book-equity/total-assets "
    "means low leverage and low distress risk; the distress / low-leverage "
    "anomaly says highly levered, distress-prone firms under-perform risk-"
    "adjusted, so solvent low-leverage firms out-drift — a capital-structure "
    "LEVEL axis, built strictly point-in-time from filed 10-K/10-Q balance "
    "sheets, with non-positive book equity (buyback-financed names) excluded so "
    "the ratio cannot sign-invert, and ranked within industry so bank/insurer "
    "leverage-accounting differences are neutralised. Profitability momentum: "
    "firms whose annual return-on-assets is improving year-over-year are on a "
    "strengthening fundamental trajectory the market prices in only gradually — "
    "a quality-CHANGE axis. Macro discount-rate regime: low/falling Treasury "
    "yields, a steepening curve and an elevated VIX risk premium are a sign-"
    "stable bullish backdrop, with the rate term scaled by each sector's cash-"
    "flow duration (Tech most hurt by rising yields; Energy an inflation/rate "
    "hedge whose returns co-move POSITIVELY with yields, hence a negative "
    "weight) — a market-timing axis. Orthogonality: (solvency vs prof-momentum) "
    "a capital-structure LEVEL (how the firm is financed, a balance-sheet stock) "
    "vs a profitability CHANGE (how fast income-per-asset is improving, an "
    "income-statement flow) come from different statements with different time "
    "character — a low-leverage firm can have rising or falling ROA — so the two "
    "within-industry ranks are near-uncorrelated; (both vs macro) the fundamental "
    "legs are cross-sectional while the macro leg is a single time-series "
    "identical across names within a sector on a given day, so ~zero correlation "
    "by construction — fundamentals decide WHICH names, macro times WHEN. NOTE: "
    "the rejected usd_broad_dollar_pressure is deliberately NOT implemented — a "
    "universe-constant timing series carries zero cross-sectional rank "
    "information and would only inject timing noise."
)

# Structural cash-flow-duration weights (train-only priors on duration
# economics, NOT fit to validation): iter-18's proven map plus iter-20's ONE
# validated correction — Energy carries a NEGATIVE weight because its returns
# co-move POSITIVELY with yields (inflation/rate hedge), turning the rate term
# into a tailwind.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals: equity-to-assets solvency and annual ROA change,
# each stamped by filed_date (a downstream row may use a value only as of its
# filing date).
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["Assets", "NetIncomeLoss", "StockholdersEquity"],
    )
    empty = pd.DataFrame(columns=["ticker", "avail_date", "eq_to_assets",
                                  "roa_chg"])
    if fund.empty:
        return empty
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    # --- Assets: instant concept, one value per (ticker, period_end) ---
    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    # --- Stockholders' equity: instant concept, earliest filed per period ---
    equity = fund[fund["concept"] == "StockholdersEquity"].copy()
    equity = (equity.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    # --- Net income: full-YEAR periods only (annual ROA consistent across names)
    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni.dropna(subset=["period_start"])
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 330) & (ni["dur"] <= 400)]
    ni = (ni.sort_values("filed_date")
            .drop_duplicates(["ticker", "period_end"], keep="first"))

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = (assets[assets["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        e = (equity[equity["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        n = (ni[ni["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        if a.empty:
            continue
        a_pe = a["period_end"]
        a_val = a["value"].astype(float).values

        # ---- Leg 1: equity-to-assets solvency (per equity period_end) ----
        for i in range(len(e)):
            pe = e["period_end"].iloc[i]
            eq_val = float(e["value"].iloc[i])
            if not np.isfinite(eq_val) or eq_val <= 0:
                # exclude non-positive book equity: it sign-inverts the ratio
                continue
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] > 45 or a_val[j] <= 0:
                continue
            ratio = eq_val / a_val[j]
            ratio = min(max(ratio, 0.0), 1.0)  # winsorize / clip bad prints
            # equity is filed WITH the balance sheet; use the later of the two
            # filed_dates so the row is public only when both lines are.
            fdate = max(e["filed_date"].iloc[i], a["filed_date"].iloc[j])
            records.append({
                "ticker": ticker, "avail_date": fdate,
                "eq_to_assets": ratio, "roa_chg": np.nan,
            })

        # ---- Leg 2: profitability momentum (YoY change in annual ROA) ----
        roa_by_pe = {}
        for i in range(len(n)):
            pe = n["period_end"].iloc[i]
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            ni_val = float(n["value"].iloc[i])
            fdate = n["filed_date"].iloc[i]
            roa = ni_val / a_val[j] if (diffs[j] <= 45 and a_val[j] > 0) else np.nan
            roa_by_pe[pe] = (roa, fdate)

        for pe, (roa_cur, fdate) in roa_by_pe.items():
            if not np.isfinite(roa_cur):
                continue
            target = pe - pd.Timedelta(days=365)
            best_pe, best_diff = None, 9999
            for ppe in roa_by_pe:
                d = abs((ppe - target).days)
                if d < best_diff and np.isfinite(roa_by_pe[ppe][0]):
                    best_diff, best_pe = d, ppe
            if best_pe is not None and best_diff <= 60:
                records.append({
                    "ticker": ticker, "avail_date": fdate,
                    "eq_to_assets": np.nan,
                    "roa_chg": roa_cur - roa_by_pe[best_pe][0],
                })

    out = pd.DataFrame(records)
    if out.empty:
        return empty
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"eq_to_assets": "last", "roa_chg": "last"}))
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
    for c in ["eq_to_assets", "roa_chg"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    cols = ["avail_date", "eq_to_assets", "roa_chg"]
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

    # ---- Leg 1: solvency (high equity/assets -> high rank -> bullish) ----
    panel["solvency_eq_assets_rank"] = (
        panel.groupby(["date", "industry"])["eq_to_assets"]
        .rank(pct=True, ascending=True)
    )

    # ---- Leg 2: profitability momentum (rising YoY ROA -> high rank) ----
    panel["profmom_roa_chg_rank"] = (
        panel.groupby(["date", "industry"])["roa_chg"]
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

    new_cols = ["solvency_eq_assets_rank", "profmom_roa_chg_rank",
                "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date"], errors="ignore")
    return panel, new_cols
