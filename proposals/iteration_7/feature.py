"""Iteration 7 signal: capital-allocation-discipline & quality COMPOSITE.

Motivation from my own journal: across six iterations, every *lone* slow-moving
fundamental factor (profitability quality iter-4, asset growth iter-5, net payout
iter-6) landed flat/negative on the pooled logistic model (uplift ~ -0.02..+0.01)
yet showed real, consistent NON-linear tree edge (GBM +0.02..+0.05) and the SAME
positive economic sign in Tech/Pharma. The recurring lesson: the common "quality /
capital-discipline" component is real, but each single ratio is too noisy and
non-monotone on its own for a linear model to use.

This signal tests that lesson directly. HYPOTHESIS: a firm's true, slow-moving
capital-allocation discipline and cash-backed quality is a *latent* trait that the
market underweights. No single accounting ratio measures it cleanly (each is
polluted by sector accounting, one-offs, and definitional noise), but averaging
several orthogonal, industry-standardized measures of it CANCELS that idiosyncratic
noise and leaves a monotone signal. So a composite z-score built from capital
discipline (slow asset growth, deleveraging) + cash-backed profitability (ROA,
cash-flow-on-assets, gross profitability) + earnings quality (low accruals),
each standardized within industry, should predict a higher probability of a
positive 21-day return — and, unlike the lone factors, should finally register on
the linear model, not only the trees. All inputs are SEC-EDGAR point-in-time
(stamped by filed_date) and ranked within industry, so it is split-immune and
neutral to the structural Tech/Pharma/Financials profitability differences that
flipped my earlier signals. (Banks don't report GrossProfit or LongTermDebt, so
those legs simply drop out of the Financials composite via nan-aware averaging.)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology", "scripts"))
import numpy as np
import pandas as pd
from data import fetch_fundamentals

SIGNAL_NAME = "capital_discipline_quality_composite"
HYPOTHESIS = (
    "A firm's slow-moving capital-allocation discipline and cash-backed quality is "
    "a latent trait the market underweights; no single accounting ratio measures it "
    "cleanly, but averaging several orthogonal, industry-standardized measures — slow "
    "asset growth, deleveraging, high return-on-assets, high cash-flow-on-assets, high "
    "gross profitability, and low accruals — cancels idiosyncratic accounting noise and "
    "leaves a monotone quality signal that predicts a higher chance of a positive 21-day "
    "return, industry-relative so it is neutral to sector accounting differences."
)

_STOCK_CONCEPTS = ["Assets", "LongTermDebtNoncurrent", "StockholdersEquity"]
_FLOW_CONCEPTS = ["GrossProfit", "NetIncomeLoss",
                  "NetCashProvidedByUsedInOperatingActivities"]
_ALL_CONCEPTS = _STOCK_CONCEPTS + _FLOW_CONCEPTS


def _pit_series(fund, concept):
    """Point-in-time cleaned rows for one concept: earliest-filed value per
    fiscal period_end (so a later restatement never leaks backward)."""
    s = fund[fund["concept"] == concept].copy()
    s = s[s["form"].isin(["10-K", "10-Q"])]
    s = s.dropna(subset=["period_end", "filed_date", "value"])
    if s.empty:
        return s
    s = (s.sort_values("filed_date")
           .drop_duplicates(["ticker", "period_end"], keep="first"))
    return s


def _annual(s):
    """Keep ~annual (350-380 day) periods of a flow concept, earliest-filed per
    fiscal year-end (so a later restatement never leaks backward)."""
    if s.empty:
        return s
    plen = (s["period_end"] - s["period_start"]).dt.days
    a = s[(plen >= 350) & (plen <= 380)].copy()
    a = (a.sort_values("filed_date")
           .drop_duplicates(["ticker", "period_end"], keep="first"))
    return a


def _nearest_assets(assets, ticker, target_pe, tol=45):
    """Assets value at the period_end nearest `target_pe` (within `tol` days)."""
    sub = assets[assets["ticker"] == ticker]
    if sub.empty:
        return np.nan
    d = np.abs((sub["period_end"] - target_pe).dt.days.values)
    j = d.argmin()
    v = float(sub["Assets"].iloc[j])
    return v if (d[j] <= tol and v > 0) else np.nan


def _balance_sheet_legs(assets, ltd_tbl):
    """Point-in-time asset-growth (YoY) and leverage-change (YoY), stamped by the
    filing date of the CURRENT period's balance sheet."""
    recs = []
    for ticker, ga in assets.groupby("ticker"):
        ga = ga.sort_values("period_end").reset_index(drop=True)
        pe = ga["period_end"]
        aval = ga["Assets"].astype(float).values
        afd = ga["fd_Assets"].values
        for i in range(len(ga)):
            cur_pe, cur_assets = pe.iloc[i], aval[i]
            if not (cur_assets > 0):
                continue
            tgt = cur_pe - pd.Timedelta(days=365)
            dd = np.abs((pe - tgt).dt.days.values)
            k = dd.argmin()
            prev_ok = dd[k] <= 45 and aval[k] > 0
            asset_growth = (cur_assets / aval[k] - 1.0) if prev_ok else np.nan

            ltd = _lookup(ltd_tbl, ticker, cur_pe)
            leverage = (ltd / cur_assets) if np.isfinite(ltd) else np.nan
            lev_prev = np.nan
            if np.isfinite(leverage) and prev_ok:
                ltd_p = _lookup(ltd_tbl, ticker, pe.iloc[k])
                if np.isfinite(ltd_p):
                    lev_prev = ltd_p / aval[k]
            leverage_change = (leverage - lev_prev) if np.isfinite(lev_prev) else np.nan

            recs.append({
                "ticker": ticker,
                "avail_date": pd.Timestamp(afd[i]),
                "cd_asset_growth": asset_growth,
                "cd_leverage_change": leverage_change,
            })
    out = pd.DataFrame(recs)
    if out.empty:
        return out
    return (out.dropna(subset=["cd_asset_growth", "cd_leverage_change"], how="all")
               .sort_values(["ticker", "avail_date"])
               .drop_duplicates(["ticker", "avail_date"], keep="last")
               .reset_index(drop=True))


def _lookup(tbl, ticker, target_pe, tol=45):
    """Value of a (ticker, period_end, value) table at nearest period_end."""
    if tbl is None or tbl.empty:
        return np.nan
    sub = tbl[tbl["ticker"] == ticker]
    if sub.empty:
        return np.nan
    d = np.abs((sub["period_end"] - target_pe).dt.days.values)
    j = d.argmin()
    return float(sub["value"].iloc[j]) if d[j] <= tol else np.nan


def _flow_legs(assets, gp_tbl, ni_tbl, ocf_tbl):
    """Point-in-time annual quality ratios (ROA, cash-flow-on-assets, gross
    profitability, accruals) = annual flow / fiscal-year-end assets, stamped by
    the latest filing date among the inputs used."""
    # union of annual fiscal year-ends across the flow concepts
    frames = [t for t in (gp_tbl, ni_tbl, ocf_tbl) if t is not None and not t.empty]
    if not frames:
        return pd.DataFrame(columns=["ticker", "avail_date"])
    year_ends = (pd.concat([t[["ticker", "period_end"]] for t in frames])
                 .drop_duplicates().reset_index(drop=True))
    recs = []
    for _, row in year_ends.iterrows():
        ticker, fy = row["ticker"], row["period_end"]
        denom = _nearest_assets(assets, ticker, fy)
        if not (denom > 0):
            continue
        gp = _lookup(gp_tbl, ticker, fy)
        ni = _lookup(ni_tbl, ticker, fy)
        ocf = _lookup(ocf_tbl, ticker, fy)
        gp_to_assets = (gp / denom) if np.isfinite(gp) else np.nan
        roa = (ni / denom) if np.isfinite(ni) else np.nan
        cfoa = (ocf / denom) if np.isfinite(ocf) else np.nan
        accruals = ((ni - ocf) / denom) if (np.isfinite(ni) and np.isfinite(ocf)) else np.nan

        fds = []
        for tbl in (gp_tbl, ni_tbl, ocf_tbl):
            if tbl is None or tbl.empty:
                continue
            sub = tbl[(tbl["ticker"] == ticker) & (tbl["period_end"] == fy)]
            if not sub.empty:
                fds.append(pd.Timestamp(sub["filed_date"].iloc[0]))
        # also require assets known by then
        asub = assets[(assets["ticker"] == ticker)]
        d = np.abs((asub["period_end"] - fy).dt.days.values)
        jj = d.argmin()
        if d[jj] <= 45:
            fds.append(pd.Timestamp(asub["fd_Assets"].iloc[jj]))
        if not fds:
            continue
        recs.append({
            "ticker": ticker,
            "avail_date": max(fds),
            "cd_roa": roa,
            "cd_cfoa": cfoa,
            "cd_gp_to_assets": gp_to_assets,
            "cd_accruals": accruals,
        })
    out = pd.DataFrame(recs)
    if out.empty:
        return out
    return (out.sort_values(["ticker", "avail_date"])
               .drop_duplicates(["ticker", "avail_date"], keep="last")
               .reset_index(drop=True))


def _build_leg_tables(tickers):
    """Return (balance_sheet_legs, flow_legs) — two PIT tables merged separately."""
    fund = fetch_fundamentals(list(tickers), concepts=_ALL_CONCEPTS)
    empty = pd.DataFrame(columns=["ticker", "avail_date"])
    if fund.empty:
        return empty, empty

    assets = _pit_series(fund, "Assets")
    if assets.empty:
        return empty, empty
    assets = assets[["ticker", "period_end", "filed_date", "value"]].rename(
        columns={"value": "Assets", "filed_date": "fd_Assets"})

    def stock_tbl(concept):
        s = _pit_series(fund, concept)
        if s.empty:
            return None
        return s[["ticker", "period_end", "filed_date", "value"]]

    def annual_flow_tbl(concept):
        s = _annual(_pit_series(fund, concept))
        if s.empty:
            return None
        return s[["ticker", "period_end", "filed_date", "value"]]

    bs = _balance_sheet_legs(assets, stock_tbl("LongTermDebtNoncurrent"))
    fl = _flow_legs(assets,
                    annual_flow_tbl("GrossProfit"),
                    annual_flow_tbl("NetIncomeLoss"),
                    annual_flow_tbl("NetCashProvidedByUsedInOperatingActivities"))
    return bs, fl


def _zscore(s):
    m = s.mean()
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return s * 0.0
    return (s - m) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    bs_tbl, fl_tbl = _build_leg_tables(panel["ticker"].unique())
    bs_cols = ["cd_asset_growth", "cd_leverage_change"]
    fl_cols = ["cd_roa", "cd_cfoa", "cd_gp_to_assets", "cd_accruals"]
    raw_cols = bs_cols + fl_cols

    def _merge_pit(panel, tbl, cols):
        for c in cols:
            if c not in panel.columns:
                panel[c] = np.nan
        if tbl is None or tbl.empty:
            return panel
        tbl = tbl.copy()
        tbl["avail_date"] = pd.to_datetime(tbl["avail_date"]).astype("datetime64[ns]")
        tbl = tbl.sort_values("avail_date")
        parts = []
        for ticker, g in panel.groupby("ticker", sort=False):
            g = g.sort_values("date")
            gt = tbl[tbl["ticker"] == ticker][["avail_date"] + cols]
            if not gt.empty:
                g = g.drop(columns=[c for c in cols if c in g.columns])
                g = pd.merge_asof(g, gt, left_on="date", right_on="avail_date",
                                  direction="backward")
                g = g.drop(columns=["avail_date"])
            parts.append(g)
        return pd.concat(parts, ignore_index=True)

    panel = _merge_pit(panel, bs_tbl, bs_cols)
    panel = _merge_pit(panel, fl_tbl, fl_cols)

    # ---- sign so that HIGHER = more disciplined / higher quality = bullish ----
    # slow asset growth, deleveraging, low accruals are GOOD -> invert them.
    panel["cd_asset_growth_inv"] = -panel["cd_asset_growth"]
    panel["cd_leverage_change_inv"] = -panel["cd_leverage_change"]
    panel["cd_neg_accruals"] = -panel["cd_accruals"]

    leg_cols = ["cd_asset_growth_inv", "cd_leverage_change_inv", "cd_roa",
                "cd_cfoa", "cd_gp_to_assets", "cd_neg_accruals"]

    # Industry-relative z-score of each leg, same-date only (no lookahead).
    z_cols = []
    for c in leg_cols:
        zc = c + "_z"
        panel[zc] = (panel.groupby(["date", "industry"])[c]
                     .transform(_zscore))
        z_cols.append(zc)

    # Composite = nan-aware mean of the standardized legs (banks: GP/leverage
    # legs are NaN and simply drop out). This is the headline feature.
    panel["cad_quality_composite"] = panel[z_cols].mean(axis=1, skipna=True)

    # Industry percentile rank of the composite (tree-friendly monotone view).
    panel["cad_quality_ind_rank"] = (
        panel.groupby(["date", "industry"])["cad_quality_composite"]
        .rank(pct=True, ascending=True)
    )

    new_cols = ["cad_quality_composite", "cad_quality_ind_rank",
                "cd_asset_growth", "cd_leverage_change", "cd_roa",
                "cd_cfoa", "cd_gp_to_assets", "cd_accruals"]
    return panel, new_cols
