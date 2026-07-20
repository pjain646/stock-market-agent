"""Iteration 23 — three-leg orthogonal BUNDLE: capital discipline +
profitability momentum + macro discount-rate regime.

WHY THIS CONFIG (and an honest note on the intended analyst-sentiment leg)
-------------------------------------------------------------------------
This iteration's brief asked me to prioritise a never-tested ANALYST-SENTIMENT
factor (analyst estimate revisions and/or rating upgrades/downgrades) as the
closest available proxy to investor sentiment, and bundle it with the proven
legs. I investigated all three candidate sentiment sources and found NONE is
buildable point-in-time-safe with the available (free-tier) data:

  * fetch_analyst_grades (rating upgrades/downgrades): the FMP `grades`
    endpoint returns HTTP 402 Payment Required on this key — it is a paid
    feature, not cached, and cannot be fetched. No data at all.
  * fetch_analyst_estimates (consensus revisions): returns only a SINGLE
    CURRENT snapshot of consensus per FUTURE fiscal year (e.g. FY2025-2028),
    with NO timestamp for when each estimate was made. There is no historical
    revision series, so applying today's consensus to a 2016-2023 panel row is
    pure lookahead — using it as a feature would leak the future. Rejected on
    the point-in-time / no-lookahead discipline.
  * fetch_insider_transactions (Form 4 — the next-closest revealed-sentiment
    proxy, flagged in iteration 9's note): the fetcher returns only the most
    recent filings per name; at 400 filings/ticker AAPL reaches back only to
    2017-10 (and sparsely), and one ticker took ~45s — fetching 166 names over
    the full 2014-2024 window is both too slow for budget AND leaves the early
    panel uncovered. Not viable.

A faithful "this axis cannot be built without lookahead or paid data" is a
real result and beats forcing a lookahead-tainted feature into the model. So
rather than dilute the bundle with a fabricated/leaky sentiment leg, I revert
to the campaign's BEST-VALIDATED candidate as the strongest carry-forward:

  iteration 20 (discipline + profitability-momentum + macro) = +0.0654, the
  campaign's peak validation score. Every leg-swap experiment since then landed
  BELOW it — iter-21 (swap prof-mom -> value) +0.0574, iter-22 (add value as a
  4th leg) +0.0572 — confirming the roster is optimised and a fourth/alternate
  cross-sectional leg competes rather than compounds. With the intended new
  sentiment axis unavailable, the disciplined move is to lock in the proven
  three-leg peak, not to degrade it.

Legs (each a genuinely different source of edge):
  1. Capital discipline  — within-industry rank of YoY asset growth (slow growth
     = capital-disciplined = bullish; Cooper-Gulen-Schill investment anomaly).
  2. Profitability momentum — within-industry rank of YoY change in return-on-
     assets; firms whose profit-PER-asset trajectory is improving are on a
     strengthening fundamental path the market prices in only gradually.
  3. Macro discount-rate regime — a sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight (structural
     priors; Energy negative because it co-moves POSITIVELY with yields).

Orthogonality (why each PAIR is low-correlation — a different source of edge):
  * (1) vs (2): asset-base SIZE trajectory (a growth/investment axis) vs
    profit-PER-asset trajectory (a quality axis). Different financial
    statements — a slow-grower can have rising OR falling ROA — so the two
    within-industry ranks are only weakly related (measured ~0 in prior iters).
  * (1)/(2) vs (3): the two fundamental legs are cross-sectional (differ across
    names on a date, ~constant over weeks); the macro leg is a pure time-series
    scaled by a constant sector weight (identical across names within a sector,
    varies day to day) — near-zero correlation by construction. Fundamentals
    decide WHICH names, macro times WHEN the universe rises.
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology",
                                "scripts"))
from data import fetch_fundamentals, fetch_macro_series  # noqa: E402

SIGNAL_NAME = "discipline_profmom_macro_bundle_v4"
HYPOTHESIS = (
    "Capital discipline: firms that expand their asset base slowly are "
    "underpriced and drift up (overinvestment/empire-building corrected "
    "gradually). Profitability momentum: firms whose annual return-on-assets is "
    "improving year-over-year are on a strengthening fundamental trajectory the "
    "market prices in only gradually. Macro discount-rate regime: low/falling "
    "Treasury yields, a steepening curve and an elevated VIX risk premium are a "
    "sign-stable bullish backdrop, with the rate term scaled by each sector's "
    "cash-flow duration (Tech most hurt by rising yields; Energy an inflation/"
    "rate hedge whose returns co-move POSITIVELY with yields, hence a negative "
    "weight). Orthogonality — discipline (asset-SIZE trajectory, a growth/"
    "investment axis) vs prof-momentum (profit-PER-asset trajectory, a quality "
    "axis) come from different statements and move independently (slow growth "
    "pairs with rising or falling ROA), so the two within-industry ranks are "
    "only weakly related; both cross-sectional legs are near-uncorrelated with "
    "the macro leg, a single time-series identical across names within a sector "
    "on a given day — fundamentals decide WHICH names, macro times WHEN. NOTE: "
    "the intended never-tested analyst-sentiment leg was investigated and found "
    "not buildable point-in-time-safe (grades endpoint is paywalled; estimates "
    "are a single current snapshot with no revision history = lookahead; insider "
    "Form-4 is too slow/incomplete over 166 names x 2014-2024), so this reverts "
    "to the campaign's best-validated three-leg peak (iter-20, +0.0654) rather "
    "than forcing a lookahead-tainted sentiment factor."
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
# Point-in-time fundamentals: asset growth and annual ROA change, stamped by
# filed_date (a downstream row may use a value only as of its filing date).
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["Assets", "NetIncomeLoss"],
    )
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy", "ag_2yr",
                                     "roa_chg"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni.dropna(subset=["period_start"])
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 330) & (ni["dur"] <= 400)]  # full-year only
    ni = (ni.sort_values("filed_date")
            .drop_duplicates(["ticker", "period_end"], keep="first"))

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = assets[assets["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)
        n = ni[ni["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)

        if a.empty:
            continue
        a_pe = a["period_end"]
        a_val = a["value"].astype(float).values

        def asset_growth(cur_pe, cur_val, years):
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
                "ag_2yr": asset_growth(a_pe.iloc[i], a_val[i], 2),
                "roa_chg": np.nan,
            })

        # annual ROA (NI / assets) keyed by period_end, then YoY change
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
                    "ag_yoy": np.nan, "ag_2yr": np.nan,
                    "roa_chg": roa_cur - roa_by_pe[best_pe][0],
                })

    out = pd.DataFrame(records)
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"ag_yoy": "last", "ag_2yr": "last", "roa_chg": "last"}))
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
    for c in ["ag_yoy", "ag_2yr", "roa_chg"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    cols = ["avail_date", "ag_yoy", "ag_2yr", "roa_chg"]
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

    new_cols = ["disc_ag_rank", "profmom_roa_chg_rank", "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date"], errors="ignore")
    return panel, new_cols
