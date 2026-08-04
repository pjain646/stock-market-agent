"""Iteration 35 — three-leg orthogonal BUNDLE across THREE genuinely different
data domains: capital-structure LEVEL (fundamental) + price MOMENTUM (market
prices) + macro discount-rate REGIME (timing).

WHY THIS BUNDLE, AND WHY IT IS NEW
----------------------------------
The journal's clearest, most-repeated lesson (iters 32/33/34) is that a bundle
of TWO cross-sectional FUNDAMENTAL factors — no matter how orthogonal in
*construction* (measured leg-ρ ≈ 0.01) — fails, because both value/quality
ratios share the same macro-REGIME exposure (fundamental value bleeds down when
rates rise) and so reinforce one losing tilt instead of hedging it. Three
consecutive macro-free fundamental pairs landed flat-to-negative
(−0.0108, −0.0037, +0.0079). The campaign's proven +0.075 peak
(solvency + prof-momentum + macro) always carried the macro TIMING leg, which
the diagnosis says did the real work.

Every bundle in the campaign so far has combined fundamentals with the macro
leg. NOT ONE has ever included a PRICE-based leg. That is the single untested
axis and therefore the highest-information experiment. This bundle keeps the two
proven workhorses (solvency LEVEL + macro TIMING) and replaces the
profitability-momentum leg with **12-1 price momentum** — a market-price signal
from an entirely different data domain than the balance sheet or FRED. I keep
the bundle at THREE legs (not four): the journal shows a fourth cross-sectional
fundamental cannibalises rather than compounds (iter-22), so I swap rather than
add.

THE THREE LEGS (each a genuinely different source of edge):
  1. Equity-to-assets solvency (proven) — within-industry rank of
     StockholdersEquity / Assets. Low leverage / low distress risk; the
     distress anomaly says highly-levered firms under-perform risk-adjusted.
     A capital-structure LEVEL axis, built strictly point-in-time from filed
     10-K/10-Q balance sheets (non-positive book equity excluded so the ratio
     cannot sign-invert; ranked WITHIN (date, industry) to neutralise
     bank/insurer leverage-accounting differences).
  2. Price momentum 12-1 (NEW) — within-industry rank of the trailing return
     from t-252 to t-21 trading days (the classic Jegadeesh-Titman window that
     SKIPS the most recent month to avoid the short-term reversal contaminant).
     Behavioural under-reaction / slow information diffusion: relative-strength
     winners keep out-drifting losers over the next 1-3 months. A PRICE-TREND
     axis using ONLY past prices (fully point-in-time by construction).
  3. Macro discount-rate regime (proven) — sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight. A market-timing
     axis (WHEN).

ORTHOGONALITY (why each PAIR is low-correlation — a different edge, not a
variation on the same idea):
  * (1) solvency vs (2) momentum: solvency is a slow-moving BALANCE-SHEET stock
    (how a firm is FINANCED, updated only on filings, ~constant for months);
    momentum is a fast-moving MARKET-PRICE trend (how the crowd is REPRICING the
    name over the past year) with no accounting input at all. A low-leverage
    firm can be a price winner or a loser and a momentum winner can be solvent or
    highly levered — different data domains, different time character, so the two
    within-industry ranks are near-uncorrelated. Crucially, momentum is the ONE
    axis that does NOT belong to the value/quality family that iters 32-34 showed
    all share the same regime tilt — it is a price-trend factor, historically
    low-to-negatively correlated with value/leverage, so it is the genuine
    diversifier those failed bundles lacked.
  * (1)/(2) vs (3) macro: the two cross-sectional legs differ across names on a
    date; the macro leg is a single time-series scaled by a constant sector
    weight (identical across names within a sector on a given day), so ~zero
    correlation by construction — fundamentals + price pick WHICH names, macro
    times WHEN the universe rises.
NOTE: prof-momentum (an income-statement CHANGE) is deliberately swapped OUT,
not stacked, to keep three orthogonal axes and avoid the fourth-leg
cannibalisation the journal documents. No macro-free two-fundamental pair is
proposed — that space has failed three times running.
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

SIGNAL_NAME = "solvency_pricemom_macro_bundle"
HYPOTHESIS = (
    "Equity-to-assets solvency (PROVEN): high book-equity/total-assets means low "
    "leverage and low distress risk; the distress / low-leverage anomaly says "
    "highly levered firms under-perform risk-adjusted, so solvent firms out-drift "
    "— a capital-structure LEVEL axis, point-in-time from filed 10-K/10-Q balance "
    "sheets, non-positive book equity excluded so the ratio cannot sign-invert, "
    "ranked within industry. Price momentum 12-1 (NEW): the trailing return from "
    "t-252 to t-21 trading days (skipping the last month to dodge short-term "
    "reversal); behavioural under-reaction means relative-strength winners keep "
    "out-drifting losers — a PRICE-TREND axis using only past prices, the ONE "
    "domain no prior bundle has ever included. Macro discount-rate regime "
    "(PROVEN): low/falling Treasury yields, a steeper curve and an elevated VIX "
    "risk premium are a sign-stable bullish backdrop, the rate term scaled by "
    "each sector's cash-flow duration (Tech most hurt by rising yields; Energy an "
    "inflation/rate hedge, hence a negative weight) — a market-TIMING axis. "
    "Orthogonality: (solvency vs momentum) a slow balance-sheet stock — how the "
    "firm is FINANCED — versus a fast market-price trend — how the crowd is "
    "REPRICING it; different data domains, near-zero rank correlation, and "
    "momentum is the one axis OUTSIDE the value/quality family that iters 32-34 "
    "showed all share the same regime tilt, so it is the genuine diversifier "
    "those macro-free pairs lacked. (both vs macro) the two cross-sectional legs "
    "differ across names while the macro leg is one time-series identical across "
    "names within a sector on a day, so ~zero correlation by construction — "
    "fundamentals+price pick WHICH names, macro times WHEN."
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


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals: equity-to-assets solvency, stamped by filed_date
# (a downstream row may use a value only as of its filing date).
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["Assets", "StockholdersEquity"],
    )
    empty = pd.DataFrame(columns=["ticker", "avail_date", "eq_to_assets"])
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

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = (assets[assets["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        e = (equity[equity["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        if a.empty:
            continue
        a_pe = a["period_end"]
        a_val = a["value"].astype(float).values

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
            ratio = min(max(ratio, 0.0), 1.0)  # clip bad prints
            fdate = max(e["filed_date"].iloc[i], a["filed_date"].iloc[j])
            records.append({
                "ticker": ticker, "avail_date": fdate, "eq_to_assets": ratio,
            })

    out = pd.DataFrame(records)
    if out.empty:
        return empty
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"eq_to_assets": "last"}))
    return out


def _trailing_z(s, min_periods=60):
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    # ---------- Leg 2: price momentum 12-1 (past prices only) ----------
    # Trailing return from t-252 to t-21 trading days: skip the most recent
    # month to avoid the short-term-reversal contaminant. Uses ONLY prices at or
    # before each row's date -> point-in-time safe by construction.
    panel = panel.sort_values(["ticker", "date"])
    px = panel.groupby("ticker")["adj_close"]
    p_21 = px.shift(21)
    p_252 = px.shift(252)
    panel["mom_12_1"] = (p_21 / p_252) - 1.0

    # ---------- point-in-time fundamentals, forward-filled per ticker ----------
    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    fpit["eq_to_assets"] = fpit.groupby("ticker")["eq_to_assets"].ffill()

    parts = []
    cols = ["avail_date", "eq_to_assets"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][cols]
        if f.empty:
            g["eq_to_assets"] = np.nan
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

    # ---- Leg 2: momentum rank (high 12-1 return -> high rank -> bullish) ----
    panel["price_mom_12_1_rank"] = (
        panel.groupby(["date", "industry"])["mom_12_1"]
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

    new_cols = ["solvency_eq_assets_rank", "price_mom_12_1_rank",
                "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date", "mom_12_1", "eq_to_assets"],
                       errors="ignore")
    return panel, new_cols
