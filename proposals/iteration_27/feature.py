"""Iteration 27 — two-leg orthogonal BUNDLE (MANAGER-SELECTED, binding):
  1. cash_to_assets_liquidity         (NEW fundamental, asset-side balance sheet)
  2. real_rate_duration_scaled_pressure (macro leg, real-rate decomposition of the
                                         proven iter-16/20/25 rate leg)

WHAT THE RESEARCH MANAGER SELECTED, AND HOW THIS HONORS IT
----------------------------------------------------------
The team's binding ruling this iteration selected EXACTLY two factors:
`cash_to_assets_liquidity` and `real_rate_duration_scaled_pressure`. Two
genuinely orthogonal axes — one asset-side balance-sheet trait, one macro
discount-rate repair — is the design shape the charter wants (not a best-of-N
single-signal draw). I implement precisely this pair; I do NOT pad to three, and
I do NOT re-add solvency / prof-momentum / discipline just because they scored
well before (the manager explicitly froze the spec).

MANAGER BUILD SPEC — followed to the letter:
  * cash/assets: SECTOR-DEMEANED WITHIN SECTOR (binding). The raw cross-sectional
    version is forbidden because cash intensity is sector-STRUCTURAL (tech /
    healthcare hold lots of cash, utilities / industrials little) — an unranked
    raw factor would only sort sectors and add nothing orthogonal. I neutralise
    sector structure by ranking cash/assets WITHIN (date, industry); a percentile
    rank inside the sector is a robust, monotone demeaning that removes the
    sector-level mean by construction. FIXED, UNCONDITIONAL sign — high internal
    liquidity -> high rank -> bullish (Palazzo: cash holdings carry a premium).
    NO regime story, NO 2022-24 tuning, NO per-sector hand weights. If it only
    works because the rate regime is on, it does not survive — it is tested as a
    plain cross-sectional factor. I deliberately do NOT carry the (unmeasured)
    "negative ROA correlation" claim into the build as fact.
  * real rate: DGS10 - T10YIE (10y nominal Treasury minus the 10y breakeven
    inflation rate = a synthetic 10y real yield) SUBSTITUTED into the existing
    duration-scaled rate-pressure term of the proven macro_regime_score. Slope
    (T10Y2Y) and VIX legs are UNTOUCHED, and the per-sector cash-flow-duration
    weights are UNCHANGED from the validated iter-20/25 map. This is a
    DECOMPOSITION of an existing winner (isolate the real discount-rate channel
    from the inflation-expectations channel), not a new bet — the lowest-risk
    change on the table. Acknowledged residual: a nominal-Treasury-minus-breakeven
    real rate mixes mismatched liquidity/risk premia vs a true TIPS yield; a TIPS
    (DFII10) comparison is a refinement, not a blocker, and is noted not hidden.

POINT-IN-TIME SAFETY
  * Every fundamental is stamped by EDGAR filed_date and joined merge_asof
    BACKWARD on date, so each name contributes only its most recently FILED
    balance sheet as-of t — no lookahead.
  * Macro series are daily FRED prints, merge_asof BACKWARD, z-scored on an
    EXPANDING (trailing-only) window so no future distributional info leaks.

ORTHOGONALITY (why this PAIR is low-correlation — a genuinely different edge):
  cash/assets is a CROSS-SECTIONAL, left-side (asset) balance-sheet trait that
  differs across names within a sector and moves slowly (quarterly). The
  real-rate macro leg is a pure TIME-SERIES scaled by a constant per-sector
  weight — identical across every name within a sector on a given day, varying
  day to day. A cross-sectional stock-selection axis and a universe-wide timing
  axis are near-uncorrelated by construction: the fundamental leg decides WHICH
  names, the macro leg times WHEN the universe is supported. cash/assets is also
  on a truly new axis vs every prior leg tested (income-statement profitability,
  leverage/solvency, asset-growth) — it is the asset-side liquidity trait none of
  them measured — so it breaks the max-over-tries single-signal pattern.
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

SIGNAL_NAME = "cash_liquidity_realrate_bundle"
HYPOTHESIS = (
    "Cash-to-assets liquidity (MANAGER-SELECTED): cash and equivalents as a share "
    "of total assets is an asset-side balance-sheet trait; firms holding more "
    "internal liquidity carry a valuation premium and financial flexibility "
    "(Palazzo) that the price-fixated market underweights, so cash-rich firms "
    "out-drift — a fixed, unconditional bullish sign with NO regime conditioning. "
    "Because cash intensity is sector-structural, the factor is SECTOR-DEMEANED "
    "by ranking cash/assets WITHIN (date, industry), so it sorts names against "
    "sector peers rather than sorting sectors. Real-rate duration-scaled pressure "
    "(MANAGER-SELECTED): the 10y real yield (DGS10 minus the T10YIE breakeven) is "
    "substituted for the nominal rate inside the proven duration-scaled "
    "discount-rate leg; a low/falling real rate is a sign-stable bullish backdrop, "
    "the real-rate term scaled by each sector's cash-flow duration (Tech most hurt "
    "by rising real yields; Energy an inflation/rate hedge, hence a negative "
    "weight), with the curve-slope and VIX legs untouched — a decomposition of an "
    "existing macro winner that isolates the real discount-rate channel from "
    "inflation expectations, a market-timing axis. Orthogonality: cash/assets is a "
    "cross-sectional, slow-moving asset-side stock trait that differs across names "
    "within a sector, while the real-rate leg is a universe-wide time-series "
    "identical across names within a sector on a given day — a stock-SELECTION "
    "axis vs a market-TIMING axis, near-uncorrelated by construction (fundamentals "
    "decide WHICH names, macro times WHEN); and cash/assets is on a genuinely new "
    "asset-side liquidity axis distinct from every prior profitability, leverage, "
    "or asset-growth leg."
)

# Structural cash-flow-duration weights — validated iter-20/25 map, UNCHANGED.
# Energy carries a NEGATIVE weight (returns co-move POSITIVELY with yields:
# inflation/rate hedge). These are train-only duration-economics priors, NOT fit
# to validation, and are NOT touched by the real-rate substitution.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals: cash / total assets, stamped by filed_date.
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["Assets", "CashAndCashEquivalentsAtCarryingValue"],
    )
    empty = pd.DataFrame(columns=["ticker", "avail_date", "cash_to_assets"])
    if fund.empty:
        return empty
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    # Assets: instant concept, earliest filed per (ticker, period_end).
    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    # Cash & equivalents: instant concept, earliest filed per period.
    cash = fund[fund["concept"] == "CashAndCashEquivalentsAtCarryingValue"].copy()
    cash = (cash.sort_values("filed_date")
                .drop_duplicates(["ticker", "period_end"], keep="first"))

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = (assets[assets["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        c = (cash[cash["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        if a.empty or c.empty:
            continue
        a_pe = a["period_end"]
        a_val = a["value"].astype(float).values
        for i in range(len(c)):
            pe = c["period_end"].iloc[i]
            cash_val = float(c["value"].iloc[i])
            if not np.isfinite(cash_val) or cash_val < 0:
                continue
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] > 45 or a_val[j] <= 0:
                continue
            ratio = cash_val / a_val[j]
            ratio = min(max(ratio, 0.0), 1.0)  # bound / winsorize bad prints
            # both lines are filed together; use the later filed_date so the row
            # is public only once both are.
            fdate = max(c["filed_date"].iloc[i], a["filed_date"].iloc[j])
            records.append({
                "ticker": ticker, "avail_date": fdate,
                "cash_to_assets": ratio,
            })

    out = pd.DataFrame(records)
    if out.empty:
        return empty
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"cash_to_assets": "last"}))
    return out


def _trailing_z(s, min_periods=60):
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    # ---------- Leg 1: cash/assets, PIT, ffilled per ticker ----------
    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    fpit["cash_to_assets"] = fpit.groupby("ticker")["cash_to_assets"].ffill()

    parts = []
    cols = ["avail_date", "cash_to_assets"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][cols]
        if f.empty:
            g["cash_to_assets"] = np.nan
        else:
            g = pd.merge_asof(g, f.sort_values("avail_date"),
                              left_on="date", right_on="avail_date",
                              direction="backward")
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # SECTOR-DEMEANED within (date, industry): high cash/assets -> high rank ->
    # bullish. Percentile rank removes the sector-level mean by construction.
    panel["cash_to_assets_rank"] = (
        panel.groupby(["date", "industry"])["cash_to_assets"]
        .rank(pct=True, ascending=True)
    )

    # ---------- Leg 2: real-rate duration-scaled macro regime (PIT) ----------
    macro = fetch_macro_series(
        {"DGS10": "y10", "T10YIE": "be10", "T10Y2Y": "slope", "VIXCLS": "vix"},
        start_date="2013-06-01",
    )
    w = (macro.pivot_table(index="date", columns="series_name", values="value")
         .sort_index())
    w.index = pd.to_datetime(w.index)
    w = w.ffill()
    # Real 10y yield = nominal 10y (DGS10) - 10y breakeven inflation (T10YIE).
    # This substitutes the REAL rate for the nominal rate in the pressure term;
    # slope and VIX are untouched.
    w["rreal"] = w["y10"] - w["be10"]
    w["rreal_trend21"] = w["rreal"].diff(21)
    w["z_rreal"] = _trailing_z(w["rreal"])
    w["z_rreal_trend"] = _trailing_z(w["rreal_trend21"])
    w["z_slope"] = _trailing_z(w["slope"])
    w["z_vix"] = _trailing_z(w["vix"])
    w["real_pressure_z"] = w["z_rreal"] + w["z_rreal_trend"]
    daily = w[["real_pressure_z", "z_slope", "z_vix"]].reset_index().rename(
        columns={"index": "date"})
    daily["date"] = pd.to_datetime(daily["date"]).astype("datetime64[ns]")

    panel = panel.sort_values("date")
    panel = pd.merge_asof(panel, daily.sort_values("date"), on="date",
                          direction="backward")

    dur = panel["industry"].map(_DURATION_WEIGHT).fillna(_DEFAULT_DURATION)
    panel["real_rate_regime_score"] = (
        -dur * panel["real_pressure_z"] + panel["z_slope"] + panel["z_vix"]
    )

    new_cols = ["cash_to_assets_rank", "real_rate_regime_score"]

    panel = panel.drop(columns=["real_pressure_z", "z_slope", "z_vix",
                                "avail_date"], errors="ignore")
    return panel, new_cols
