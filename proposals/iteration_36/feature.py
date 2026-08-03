"""Iteration 36 — FOUR-leg orthogonal BUNDLE spanning FOUR distinct data
domains: capital-structure LEVEL (balance sheet) + profitability CHANGE (income
statement) + price MOMENTUM (market prices) + macro discount-rate REGIME (FRED
timing).

WHY THIS BUNDLE, AND WHY IT IS NEW
----------------------------------
The campaign's proven peak is the THREE-leg solvency + prof-momentum + macro
frame (+0.075, quadruple-reproduced, iters 25/29/30/31). Iter-35 then swapped
prof-momentum OUT for 12-1 price momentum and landed +0.061 — proving the price
axis is genuinely orthogonal (ρ≈0.016 vs solvency, ~0 vs macro) and additive,
just a weaker single partner than the ROA-change leg it replaced. Iter-35's own
closing note posed the exact open question this iteration answers:

    "test solvency + profmom + PRICE-momentum + macro to see whether the price
     axis COMPOUNDS when it is ADDED rather than substituted."

That four-leg combination has NEVER been tested in the journal. The only prior
four-leg experiment (iter-22) ADDED a fourth *fundamental* (value) and
cannibalised (+0.0572 < +0.0654) — but the diagnosis there was that a fourth
CROSS-SECTIONAL FUNDAMENTAL loads many of the same names as the existing
fundamentals (all value/quality ratios share a regime tilt, iters 32-34). Price
momentum is NOT a fundamental: it is a market-price trend from a completely
different data domain, historically low-to-negatively correlated with
value/leverage. So the fourth-leg cannibalisation logic does NOT automatically
apply — the price axis may add its independent lift instead of crowding the
fundamentals. This is the highest-information single experiment left in the
frame: does an ORTHOGONAL-DOMAIN fourth leg compound where an orthogonal-
CONSTRUCTION-but-same-domain fourth leg cannibalised?

THE FOUR LEGS (each a genuinely different source of edge):
  1. Equity-to-assets solvency (PROVEN) — within-industry rank of
     StockholdersEquity / Assets. Low leverage / low distress risk; the distress
     anomaly says highly-levered firms under-perform risk-adjusted. A capital-
     structure LEVEL axis, point-in-time from filed 10-K/10-Q balance sheets;
     non-positive book equity excluded so the ratio cannot sign-invert; ranked
     WITHIN (date, industry) to neutralise bank/insurer leverage accounting.
  2. Profitability momentum (PROVEN) — within-industry rank of the YoY change in
     annual return-on-assets. Firms whose profit-per-asset trajectory is
     improving are on a strengthening fundamental path the market prices in only
     gradually. A quality-CHANGE / income-statement FLOW axis.
  3. Price momentum 12-1 (NEW to this frame) — within-industry rank of the
     trailing return from t-252 to t-21 trading days (the Jegadeesh-Titman window
     that SKIPS the most recent month to dodge short-term reversal). Behavioural
     under-reaction: relative-strength winners keep out-drifting losers. A PRICE-
     TREND axis using ONLY past prices (point-in-time by construction).
  4. Macro discount-rate regime (PROVEN) — sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight. A market-TIMING
     axis (WHEN).

ORTHOGONALITY (why each PAIR is a genuinely different edge, not a variation):
  * (1) solvency vs (2) prof-momentum: a balance-sheet LEVEL (how the firm is
    FINANCED, a slow stock) vs an income-statement CHANGE (how fast income-per-
    asset is IMPROVING, a YoY flow). Different statements, different time
    character — a low-leverage firm can have rising or falling ROA — so the two
    within-industry ranks are near-uncorrelated (campaign-measured |ρ|≤0.013).
  * (1) solvency vs (3) momentum: a slow accounting stock vs a fast market-price
    trend with no accounting input; iter-35 measured ρ≈0.016. Different domains.
  * (2) prof-momentum vs (3) momentum: a FUNDAMENTAL change (realised earnings
    trajectory off filings) vs a PRICE change (crowd repricing). These can
    diverge sharply — a name whose ROA is improving may already be a price
    laggard (the classic post-earnings-drift / under-reaction gap is exactly the
    wedge between them), so fundamental-momentum and price-momentum are distinct
    behavioural channels, not the same trend measured twice.
  * (1)/(2)/(3) vs (4) macro: the three cross-sectional legs differ across names
    on a date; the macro leg is one time-series scaled by a constant sector
    weight (identical across names within a sector on a day), so ~zero
    correlation by construction — fundamentals + price pick WHICH names, macro
    times WHEN the universe rises.
NOTE: this deliberately ADDS the price leg to the proven three, rather than
substituting, precisely to test the compounding-vs-cannibalisation question
iter-35 left open. The rejected usd_broad_dollar_pressure (a universe-constant
timing series with zero cross-sectional rank content) is NOT implemented.
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

SIGNAL_NAME = "solvency_profmom_pricemom_macro_bundle"
HYPOTHESIS = (
    "Equity-to-assets solvency (PROVEN): high book-equity/total-assets means low "
    "leverage and low distress risk; the distress anomaly says highly levered "
    "firms under-perform risk-adjusted, so solvent firms out-drift — a capital-"
    "structure LEVEL axis, point-in-time from filed 10-K/10-Q balance sheets, "
    "non-positive book equity excluded so the ratio cannot sign-invert, ranked "
    "within industry. Profitability momentum (PROVEN): firms whose annual return-"
    "on-assets is improving year-over-year are on a strengthening fundamental "
    "trajectory the market prices in only gradually — a quality-CHANGE / income-"
    "statement FLOW axis. Price momentum 12-1 (NEW to this frame): the trailing "
    "return from t-252 to t-21 trading days (skipping the last month to dodge "
    "short-term reversal); behavioural under-reaction means relative-strength "
    "winners keep out-drifting losers — a PRICE-TREND axis using only past "
    "prices. Macro discount-rate regime (PROVEN): low/falling Treasury yields, a "
    "steeper curve and an elevated VIX risk premium are a sign-stable bullish "
    "backdrop, the rate term scaled by each sector's cash-flow duration (Tech "
    "most hurt by rising yields; Energy an inflation/rate hedge, hence a negative "
    "weight) — a market-TIMING axis. This ADDS the price leg to the proven three-"
    "leg frame (never tested in the journal) to answer whether an orthogonal-"
    "DOMAIN fourth leg compounds where iter-22's fourth FUNDAMENTAL cannibalised. "
    "Orthogonality: (solvency vs prof-momentum) a balance-sheet LEVEL vs an "
    "income-statement CHANGE — different statements, |rho|<=0.013; (solvency vs "
    "price momentum) a slow accounting stock vs a fast market-price trend, "
    "rho~0.016; (prof-momentum vs price momentum) a realised-earnings trajectory "
    "off filings vs crowd repricing off prices — the post-earnings-drift wedge "
    "between them makes them distinct behavioural channels, not the same trend "
    "twice; (all three vs macro) cross-sectional legs differ across names while "
    "macro is one time-series identical across names within a sector on a day, so "
    "~zero correlation by construction — fundamentals+price pick WHICH names, "
    "macro times WHEN."
)

# Structural cash-flow-duration weights (train-only priors on duration
# economics, NOT fit to validation): iter-18/20's proven map. Energy carries a
# NEGATIVE weight because its returns co-move POSITIVELY with yields
# (inflation/rate hedge), turning the rate term into a tailwind.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55


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

    # --- Assets: instant concept, earliest filed per (ticker, period_end) ---
    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    # --- Stockholders' equity: instant concept, earliest filed per period ---
    equity = fund[fund["concept"] == "StockholdersEquity"].copy()
    equity = (equity.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    # --- Net income: full-YEAR periods only (annual ROA consistent) ---
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
                continue  # non-positive book equity would sign-invert the ratio
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] > 45 or a_val[j] <= 0:
                continue
            ratio = eq_val / a_val[j]
            ratio = min(max(ratio, 0.0), 1.0)
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

    # ---------- Leg 3: price momentum 12-1 (past prices only) ----------
    panel = panel.sort_values(["ticker", "date"])
    px = panel.groupby("ticker")["adj_close"]
    p_21 = px.shift(21)
    p_252 = px.shift(252)
    panel["mom_12_1"] = (p_21 / p_252) - 1.0

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

    # ---- Leg 3: price momentum rank (high 12-1 return -> high rank) ----
    panel["price_mom_12_1_rank"] = (
        panel.groupby(["date", "industry"])["mom_12_1"]
        .rank(pct=True, ascending=True)
    )

    # ---------- Leg 4: macro discount-rate regime (date-level, PIT) ----------
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
                "price_mom_12_1_rank", "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date", "mom_12_1", "eq_to_assets",
                                "roa_chg"], errors="ignore")
    return panel, new_cols
