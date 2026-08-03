"""Iteration 38 — three-leg orthogonal BUNDLE across THREE genuinely different
data domains: capital-structure LEVEL (fundamental) + LOW-VOLATILITY / RISK
(price-based, defensive) + macro discount-rate REGIME (timing).

WHY THIS BUNDLE, AND WHY IT IS NEW
----------------------------------
The campaign has repeatedly confirmed that its +0.075 ceiling is a property of a
THREE-orthogonal-axis STRUCTURE: a capital-structure LEVEL leg (solvency), one
cross-sectional WHICH-names signal, and a macro TIMING leg. Three different
WHICH-names legs have independently reached that ceiling — profitability
momentum (iter 25/29-31, +0.075), price momentum (iter 35, +0.061) and INSIDER
net-buying (iter 37, +0.075) — all TREND/FLOW-type signals.

Two candidate NEW sources are unavailable point-in-time-safe: analyst RATING
revisions (FMP grades endpoint returns HTTP 402 Payment Required) and forward
analyst ESTIMATES (only a single latest-consensus snapshot, no historical
as-of, so using it leaks the future — iter-23's note). So this iteration draws
on the campaign's OWN journal: iteration 3 tested the LOW-VOLATILITY anomaly as a
lone signal and found it real-but-weak (+0.0029) AND — uniquely among the early
signals — SIGN-CONSISTENT across every sector. The instructions flag exactly
such a factor as a candidate to pair with something uncorrelated. Low-vol has
NEVER been tested inside the proven solvency+macro frame, so this bundle is new.

Low volatility is a RISK / defensive axis, a fundamentally different WHICH-names
SOURCE from the trend/flow legs tried so far: the low-volatility anomaly
(Ang-Hodrick-Xing-Zhang; Baker-Bradley-Wurgler; Frazzini-Pedersen BAB) says
low-realised-volatility stocks earn higher risk-adjusted returns because
leverage-constrained investors bid up high-beta/high-vol names, leaving low-vol
names systematically cheap. It is measured PURELY from each name's own past
daily prices, so it is trivially point-in-time safe.

This keeps the two proven workhorses (solvency LEVEL + macro TIMING) and SWAPS in
the low-volatility leg (three legs, not four — the journal shows a fourth
cross-sectional leg cannibalises, iters 22/36).

THE THREE LEGS (each a genuinely different source of edge):
  1. Equity-to-assets solvency (PROVEN) — within-industry rank of
     StockholdersEquity / Assets. Low leverage / low distress risk; the distress
     anomaly says highly-levered firms under-perform risk-adjusted. A
     capital-structure LEVEL axis, strictly point-in-time from filed 10-K/10-Q
     balance sheets (non-positive book equity excluded; ranked WITHIN
     (date, industry)).
  2. Low volatility (NEW to the campaign as a bundle leg) — within-industry rank
     of NEGATIVE trailing-126-trading-day daily-return volatility, so LOW vol ->
     HIGH rank -> bullish. Computed only from each name's own past adj_close, a
     strict backward window. A defensive RISK axis with no accounting or macro
     input.
  3. Macro discount-rate regime (PROVEN) — sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight. A market-timing
     axis (WHEN).

ORTHOGONALITY (why each PAIR is low-correlation — a different edge, not a
variation on the same idea):
  * (1) solvency vs (2) low-vol: solvency is a slow ACCOUNTING measure of how the
    firm is FINANCED (leverage on the balance sheet); low-vol is a PRICE measure
    of how the market TRADES the stock (realised return dispersion). They touch
    the same broad theme of "safety" but through different data and mechanisms —
    a low-leverage firm can still be a violently volatile stock (many low-debt
    high-growth names) and a stable, low-vol stock can carry heavy leverage
    (regulated utilities), so the two ranks load different names. Correlation is
    checked in the smoke test and expected modest, not degenerate.
  * (2) low-vol vs (3) macro: low-vol is cross-sectional (differs across names on
    a date); the macro leg is a single time-series scaled by a constant sector
    weight (identical across names within a sector that day), so ~zero
    correlation by construction.
  * (1) solvency vs (3) macro: proven near-zero in the campaign's +0.075 frame
    (cross-sectional accounting level vs date-level macro series).
  fundamentals + low-vol pick WHICH names, macro times WHEN.
NOTE: this is a RISK/defensive WHICH-names source, distinct from the trend/flow
legs (profmom, price-mom, insider) already tested. No macro-free two-fundamental
pair is proposed — that space has failed (iters 32-34); no fourth leg is stacked.
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

SIGNAL_NAME = "solvency_lowvol_macro_bundle"
HYPOTHESIS = (
    "Equity-to-assets solvency (PROVEN): high book-equity/total-assets means low "
    "leverage and low distress risk; the distress anomaly says highly levered "
    "firms under-perform risk-adjusted, so solvent firms out-drift — a "
    "capital-structure LEVEL axis, point-in-time from filed 10-K/10-Q balance "
    "sheets, non-positive book equity excluded so the ratio cannot sign-invert, "
    "ranked within industry. Low volatility (NEW as a bundle leg): NEGATIVE "
    "trailing-126-trading-day daily-return volatility, so low realised vol -> "
    "high rank -> bullish; the low-volatility anomaly (Ang et al.; "
    "Baker-Bradley-Wurgler; Frazzini-Pedersen BAB) says low-vol stocks earn "
    "higher risk-adjusted returns because leverage-constrained investors bid up "
    "high-vol names, leaving low-vol names systematically cheap — a DEFENSIVE "
    "RISK axis measured purely from each name's own past prices, ranked within "
    "industry, never before tested inside the proven solvency+macro frame. Macro "
    "discount-rate regime (PROVEN): low/falling Treasury yields, a steeper curve "
    "and an elevated VIX risk premium are a sign-stable bullish backdrop, the "
    "rate term scaled by each sector's cash-flow duration (Tech most hurt by "
    "rising yields; Energy an inflation/rate hedge, hence a negative weight) — a "
    "market-TIMING axis. Orthogonality: (solvency vs low-vol) a slow ACCOUNTING "
    "measure of how the firm is FINANCED vs a PRICE measure of how the market "
    "TRADES the stock — a low-leverage firm can be a wildly volatile stock and a "
    "stable low-vol stock can carry heavy leverage (utilities), so the two ranks "
    "load different names; same broad safety theme, genuinely different data and "
    "mechanism. (low-vol vs macro) low-vol is cross-sectional while macro is one "
    "time-series identical across names within a sector on a day, ~zero by "
    "construction. (solvency vs macro) proven near-zero in the +0.075 frame. "
    "Fundamentals+low-vol pick WHICH names, macro times WHEN. This is a "
    "RISK/defensive WHICH-names source, distinct from the trend/flow legs "
    "(profmom, price-mom, insider) already tested."
)

# Structural cash-flow-duration weights (train-only priors on duration
# economics, NOT fit to validation): iter-18/20's proven map.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55

_VOL_WINDOW = 126        # ~6 trading months
_VOL_MIN_PERIODS = 90


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals: equity-to-assets solvency, stamped by filed_date.
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

    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

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
                continue
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] > 45 or a_val[j] <= 0:
                continue
            ratio = eq_val / a_val[j]
            ratio = min(max(ratio, 0.0), 1.0)
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
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    tickers = panel["ticker"].unique()

    # ---------- Leg 2: low volatility (from own past prices, PIT) ----------
    # trailing 126-day std of daily returns; NEGATED so low vol -> high value.
    ret = panel.groupby("ticker", sort=False)["adj_close"].pct_change()
    panel["ret"] = ret
    panel["trail_vol"] = (
        panel.groupby("ticker", sort=False)["ret"]
        .transform(lambda s: s.rolling(_VOL_WINDOW,
                                       min_periods=_VOL_MIN_PERIODS).std())
    )
    panel["neg_vol"] = -panel["trail_vol"]

    # ---------- point-in-time fundamentals, forward-filled per ticker ----------
    fpit = _pit_fundamentals(tickers)
    fpit = fpit.sort_values(["ticker", "avail_date"])
    if not fpit.empty:
        fpit["eq_to_assets"] = fpit.groupby("ticker")["eq_to_assets"].ffill()

    parts = []
    cols = ["avail_date", "eq_to_assets"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][cols] if not fpit.empty else None
        if f is None or f.empty:
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

    # ---- Leg 2: low-vol rank (low vol / high neg_vol -> high rank -> bullish)
    panel["low_vol_rank"] = (
        panel.groupby(["date", "industry"])["neg_vol"]
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

    new_cols = ["solvency_eq_assets_rank", "low_vol_rank", "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date", "eq_to_assets",
                                "ret", "trail_vol", "neg_vol"],
                       errors="ignore")
    return panel, new_cols
