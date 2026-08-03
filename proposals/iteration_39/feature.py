"""Iteration 39 — three-leg orthogonal BUNDLE across three genuinely different
sources of edge: PROFITABILITY LEVEL (income-statement return-on-equity) +
INSIDER NET-BUYING (private-information / behavioural) + macro discount-rate
REGIME (timing).

WHY THIS BUNDLE, AND WHY IT IS NEW
----------------------------------
The campaign has decisively mapped a +0.075 ceiling for the three-axis STRUCTURE
"a cross-sectional LEVEL leg + a WHICH-names leg + macro TIMING". Iters 22-38
proved the WHICH-names leg is fungible: profmom, price-mom, insider and low-vol
each independently reach the same band inside the solvency+macro frame. But EVERY
winning bundle in the entire campaign has used the SAME fundamental as its LEVEL
anchor — equity-to-assets SOLVENCY. Nobody has ever asked whether the LEVEL leg
is likewise fungible, or whether solvency specifically is load-bearing.

This bundle answers that open question directly: it SWAPS the solvency LEVEL leg
for an OPERATING-PROFITABILITY LEVEL leg (operating income / book equity, the RMW
axis, a proven +0.064 leg in iter 28) while keeping the two other axes — the
strongest new WHICH-names leg found (insider net-buying, +0.0753 in iter 37) and
the proven macro timer. It is a combination the journal has never tried:
profitability-LEVEL + insider-behavioural + macro. Three legs, not four (the
journal shows a fourth cross-sectional leg cannibalises).

THE THREE LEGS (each a genuinely different source of edge):
  1. Operating-profitability LEVEL (RMW) — within-industry rank of annual
     OperatingIncomeLoss / StockholdersEquity from filed 10-K balance/income
     statements. High operating income per dollar of book equity marks a durably
     productive, cash-generative business; the robust-minus-weak profitability
     premium (Novy-Marx; Fama-French RMW) says the price-fixated market
     underweights this slow-moving quality. A LEVEL axis, strictly point-in-time
     (earliest filed_date per fiscal year; non-positive book equity excluded so
     the ratio cannot sign-invert; ranked WITHIN (date, industry)).
  2. Insider net-buying (proven-new) — within-industry rank of trailing-180-day
     net insider dollar flow: open-market PURCHASE value (code P, +) minus SALE
     value (code S, -) from Form 4 filings, counted only once each filing is
     PUBLIC (filing_date <= row date), a strict PIT rolling window. Insiders buy
     with their own money almost only when they believe the stock is cheap
     relative to private information; the insider-purchase anomaly (Lakonishok-
     Lee; Cohen-Malloy-Pomorski) says net-bought names out-drift. A
     PRIVATE-INFORMATION / behavioural axis.
  3. Macro discount-rate regime (PROVEN) — sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight. A market-TIMING
     axis (WHEN).

ORTHOGONALITY (why each PAIR is low-correlation — a different edge, not a
variation on the same idea):
  * (1) profitability vs (2) insider buying: profitability is a slow
    income-statement RATIO describing how efficiently the firm EARNS on its
    equity base; insider buying is an event-driven BEHAVIOURAL flow describing
    what management is DOING with its own money right now. Highly profitable firms
    are often fully valued and see little insider buying, while insider buying
    clusters in beaten-down names where the accounting ratio says little — the two
    ranks load different names. Different data domains (income statement vs Form
    4), different time character (annual-constant vs event-driven).
  * (2) insider buying vs (3) macro: insider flow is cross-sectional (differs
    across names on a date); the macro leg is a single time-series scaled by a
    constant sector weight (identical across names within a sector that day), so
    ~zero correlation by construction.
  * (1) profitability vs (3) macro: a cross-sectional accounting level differs
    across names while the macro leg is a date-level series constant within a
    sector — near-zero by construction, the same structure proven near-zero for
    the solvency LEVEL leg in the +0.075 frame.
  profitability + insider pick WHICH names, macro times WHEN.
NOTE: solvency is deliberately swapped OUT (not stacked) to test whether the
LEVEL anchor is fungible; three orthogonal axes, no fourth cross-sectional leg.
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
from data import (fetch_fundamentals, fetch_macro_series,  # noqa: E402
                  fetch_insider_transactions)

SIGNAL_NAME = "profitability_insider_macro_bundle"
HYPOTHESIS = (
    "Operating-profitability LEVEL (RMW; NEW as the LEVEL anchor): annual "
    "operating income per dollar of book equity marks a durably productive, "
    "cash-generative business; the robust-minus-weak profitability premium says "
    "the price-fixated market underweights this slow-moving quality, so high "
    "operating-profitability -> high rank -> bullish, point-in-time from filed "
    "10-K statements (earliest filed_date per fiscal year, non-positive book "
    "equity excluded so the ratio cannot sign-invert), ranked within industry — "
    "an income-statement LEVEL axis that REPLACES the previously-used solvency "
    "anchor to test whether the LEVEL leg's identity is fungible. Insider "
    "net-buying (proven-new): trailing-180-day net insider dollar flow "
    "(open-market PURCHASE value minus SALE value from Form 4, counted only once "
    "each filing is public) — insiders buy with their own money almost only when "
    "they believe the stock is cheap relative to private information, and the "
    "insider-purchase anomaly says net-bought names out-drift; a "
    "PRIVATE-INFORMATION / behavioural axis, ranked within industry. Macro "
    "discount-rate regime (PROVEN): low/falling Treasury yields, a steeper curve "
    "and an elevated VIX risk premium are a sign-stable bullish backdrop, the "
    "rate term scaled by each sector's cash-flow duration (Tech most hurt by "
    "rising yields; Energy an inflation/rate hedge, hence a negative weight) — a "
    "market-TIMING axis. Orthogonality: (profitability vs insider) a slow "
    "income-statement RATIO of how efficiently the firm EARNS vs an event-driven "
    "BEHAVIOURAL flow of what management is DOING with its own money — different "
    "data domains (income statement vs Form 4), profitable names are often fully "
    "valued while insider buying clusters in beaten-down names, so the two ranks "
    "load different names and are near-uncorrelated. (insider vs macro) insider "
    "flow is cross-sectional while macro is one time-series identical across names "
    "within a sector on a day, ~zero by construction. (profitability vs macro) "
    "cross-sectional accounting level vs date-level macro series, near-zero by "
    "construction. Profitability+insider pick WHICH names, macro times WHEN."
)

# Structural cash-flow-duration weights (train-only priors on duration
# economics, NOT fit to validation): iter-18/20's proven map.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55

_INSIDER_WINDOW_DAYS = 180


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals: operating-profitability = annual OperatingIncome /
# book equity, stamped by the later of the two source filings' filed_date.
# Operating income is taken ONLY from 10-K filings (clean annual flow); book
# equity is matched from 10-K/10-Q by nearest period_end.
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["OperatingIncomeLoss", "StockholdersEquity"],
    )
    empty = pd.DataFrame(columns=["ticker", "avail_date", "op_profitability"])
    if fund.empty:
        return empty
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    # Annual operating income: 10-K (and restated 10-K/A) only, so the flow is a
    # clean 12-month figure rather than a mix of YTD/quarterly 10-Q values.
    opinc = fund[(fund["concept"] == "OperatingIncomeLoss")
                 & (fund["form"].isin(["10-K", "10-K/A"]))].copy()
    opinc = (opinc.sort_values("filed_date")
                  .drop_duplicates(["ticker", "period_end"], keep="first"))

    # Book equity: any 10-K/10-Q, positive only.
    equity = fund[(fund["concept"] == "StockholdersEquity")
                  & (fund["form"].isin(["10-K", "10-Q"]))].copy()
    equity = equity[equity["value"] > 0]
    equity = (equity.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    records = []
    for ticker in pd.unique(opinc["ticker"]):
        o = (opinc[opinc["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        e = (equity[equity["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        if o.empty or e.empty:
            continue
        e_pe = e["period_end"]
        e_val = e["value"].astype(float).values
        e_fd = e["filed_date"].values

        for i in range(len(o)):
            pe = o["period_end"].iloc[i]
            oi_val = float(o["value"].iloc[i])
            if not np.isfinite(oi_val):
                continue
            diffs = np.abs((e_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] > 45 or e_val[j] <= 0:
                continue
            ratio = oi_val / e_val[j]
            # Winsorise to a sane band so extreme small-equity names can't
            # dominate the cross-sectional rank spuriously.
            ratio = min(max(ratio, -2.0), 3.0)
            fdate = max(o["filed_date"].iloc[i], pd.Timestamp(e_fd[j]))
            records.append({
                "ticker": ticker, "avail_date": fdate,
                "op_profitability": ratio,
            })

    out = pd.DataFrame(records)
    if out.empty:
        return empty
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"op_profitability": "last"}))
    return out


# --------------------------------------------------------------------------- #
# Point-in-time insider net-buying: trailing-180d net open-market dollar flow,
# available only once a Form 4 is public (filing_date <= row date).
# --------------------------------------------------------------------------- #
def _pit_insider_events(tickers):
    cols = ["ticker", "filing_date", "signed_value"]
    try:
        ins = fetch_insider_transactions(list(tickers))
    except Exception:
        return pd.DataFrame(columns=cols)
    if ins is None or ins.empty:
        return pd.DataFrame(columns=cols)

    ins = ins.copy()
    ins = ins[ins["transaction_code"].isin(["P", "S"])].copy()
    if ins.empty:
        return pd.DataFrame(columns=cols)

    ins["filing_date"] = pd.to_datetime(ins["filing_date"])
    ins["shares"] = pd.to_numeric(ins["shares"], errors="coerce")
    ins["price_per_share"] = pd.to_numeric(ins["price_per_share"], errors="coerce")
    ins = ins.dropna(subset=["filing_date", "shares"])
    ins = ins[ins["shares"] > 0]
    if ins.empty:
        return pd.DataFrame(columns=cols)

    med_price = ins.groupby("ticker")["price_per_share"].transform("median")
    price = ins["price_per_share"].fillna(med_price)
    price = price.fillna(price.median())
    ins["value"] = ins["shares"] * price

    sign = np.where(ins["transaction_code"] == "P", 1.0, -1.0)
    ins["signed_value"] = sign * ins["value"]

    ev = (ins.groupby(["ticker", "filing_date"], as_index=False)["signed_value"]
             .sum())
    return ev[cols].sort_values(["ticker", "filing_date"]).reset_index(drop=True)


def _rolling_net_insider(panel, events):
    panel = panel.copy()
    panel["insider_net_180d"] = 0.0
    if events.empty:
        return panel

    win = pd.Timedelta(days=_INSIDER_WINDOW_DAYS)
    ev_by_ticker = {t: g for t, g in events.groupby("ticker")}

    out_vals = np.zeros(len(panel), dtype=float)
    for t, g in panel.groupby("ticker", sort=False):
        ev = ev_by_ticker.get(t)
        idx = g.index.values
        if ev is None or ev.empty:
            continue
        fdates = ev["filing_date"].values.astype("datetime64[ns]")
        csum = np.concatenate([[0.0], np.cumsum(ev["signed_value"].values)])
        dates = g["date"].values.astype("datetime64[ns]")
        lo = (g["date"] - win).values.astype("datetime64[ns]")
        hi_i = np.searchsorted(fdates, dates, side="right")
        lo_i = np.searchsorted(fdates, lo, side="right")
        out_vals[idx] = csum[hi_i] - csum[lo_i]

    panel["insider_net_180d"] = out_vals
    return panel


def _trailing_z(s, min_periods=60):
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    tickers = panel["ticker"].unique()

    # ---------- Leg 2: insider net-buying (Form 4), point-in-time ----------
    events = _pit_insider_events(tickers)
    panel = _rolling_net_insider(panel, events)

    # ---------- point-in-time fundamentals, forward-filled per ticker ----------
    fpit = _pit_fundamentals(tickers)
    fpit = fpit.sort_values(["ticker", "avail_date"])
    if not fpit.empty:
        fpit["op_profitability"] = fpit.groupby("ticker")["op_profitability"].ffill()

    parts = []
    cols = ["avail_date", "op_profitability"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][cols] if not fpit.empty else None
        if f is None or f.empty:
            g["op_profitability"] = np.nan
        else:
            g = pd.merge_asof(g, f.sort_values("avail_date"),
                              left_on="date", right_on="avail_date",
                              direction="backward")
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # ---- Leg 1: operating profitability (high op-income/equity -> high rank) ----
    panel["op_profitability_rank"] = (
        panel.groupby(["date", "industry"])["op_profitability"]
        .rank(pct=True, ascending=True)
    )

    # ---- Leg 2: insider net-buy rank (more net buying -> high rank -> bullish)
    panel["insider_net_buy_rank"] = (
        panel.groupby(["date", "industry"])["insider_net_180d"]
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

    new_cols = ["op_profitability_rank", "insider_net_buy_rank",
                "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date", "op_profitability",
                                "insider_net_180d"],
                       errors="ignore")
    return panel, new_cols
