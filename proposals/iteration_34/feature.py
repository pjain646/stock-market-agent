"""Iteration 34 — two-leg orthogonal BUNDLE (MANAGER-SELECTED, EXACT):
book_to_market_within_sector + deleveraging_momentum.

WHAT THE RESEARCH MANAGER SELECTED, AND HOW THIS HONORS IT
----------------------------------------------------------
Binding ruling this iteration: SHIP exactly two orthogonal cross-sectional legs —
(1) book-to-market ranked within sector (a value / cheapness LEVEL), and (2)
deleveraging momentum = YoY change in book-equity/assets (a balance-sheet-repair
CHANGE). The macro discount-rate timer was DROPPED by the team (its only ranking
content is a coarse hand-set duration weight — the tuning-attributable, artifact-
prone component — and one value-per-date inflates apparent robustness). I do NOT
implement any macro leg, and I do NOT re-add the campaign's prior
solvency/profmom/macro frame even though it scored +0.075 — re-adding a dropped
factor overrides the team's decision. TWO legs are selected; TWO legs are built.

LEG 1 — book_to_market_within_sector (MANAGER-SELECTED)
------------------------------------------------------
Book equity (StockholdersEquity) / market cap. A pure value / cheapness ratio
whose denominator IS market price: firms priced low relative to their book equity
are cheap and out-drift (the classic HML value effect). High B/M -> high rank ->
bullish, ranked WITHIN (date, industry) so leverage/accounting differences across
sectors are neutralised. Non-positive book equity (buyback-financed names) is
excluded so the ratio cannot sign-invert. Market cap = point-in-time shares
outstanding x that row's adj_close. (CAVEAT, stated plainly: adj_close is split-
AND dividend-adjusted while reported shares are not, so shares x adj_close is a
dividend-adjusted proxy for market cap, not exact market cap; this is the same
established denominator prior campaign value legs used (iters 27/32/33), and the
within-sector rank is monotone in it. No unadjusted price is available from the
data layer, so this is the buildable point-in-time-safe form.)

LEG 2 — deleveraging_momentum (MANAGER-SELECTED)
------------------------------------------------
delev = (book-equity/assets)_t - (book-equity/assets)_{t-1}, the year-over-year
CHANGE in the equity-to-assets ratio. A RISING equity/assets ratio means the firm
is repairing its balance sheet (paying down debt and/or retaining earnings faster
than assets grow) — the trajectory of balance-sheet repair that the market prices
in only gradually. High delev -> high rank -> bullish, ranked WITHIN (date,
industry).

*** BINDING BUILD CONSTRAINT (from the bear, honored below) ***
The year-ago equity/assets MUST be the figure known AS OF THE YEAR-AGO FILING
DATE, never a later-restated value. Reading current-database state for the prior
year would be lookahead and disqualify the leg. I honor this by taking BOTH the
current and prior year's StockholdersEquity and Assets AS-FIRST-REPORTED (earliest
filed_date per fiscal period_end), so a later 10-K/A restatement can never leak
backward into either the t or the t-1 term. The CHANGE becomes available only on
the CURRENT year's filing date (the last input to become public).

ORTHOGONALITY (why the PAIR is a different edge, not one idea twice)
-------------------------------------------------------------------
The bear correctly flagged that both legs share a book-equity-accretion driver.
That coupling is REAL but PARTIAL: leg 1 is a LEVEL dominated by PRICE (book/price;
its cross-sectional spread is driven overwhelmingly by the price denominator, which
leg 2 does not contain), while leg 2 is a YoY CHANGE gated by DEBT and ASSET
dynamics (no price term at all). Levels and changes of related quantities are
typically only weakly correlated, and the value-trap quadrant — cheap on book
while re-levering (high B/M, negative delev) — is real and populated. So a
cheapness-on-book screen and a balance-sheet-repair-trajectory screen do not load
the same names through the mechanism that drives either: VALUE-LEVEL vs
REPAIR-CHANGE. Per the ruling, the smoke test MEASURES the within-sector
correlation between the two ranks; if it comes back materially positive that
confirms the coupling and the bundle collapses toward a one-directional value
tilt, which must be flagged loudly rather than reported as a clean two-factor
score.
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

SIGNAL_NAME = "book_to_market_deleveraging_momentum_bundle"
HYPOTHESIS = (
    "Book-to-market within sector (MANAGER-SELECTED): book equity "
    "(StockholdersEquity) / market cap is a pure value/CHEAPNESS ratio whose "
    "denominator IS market price; firms priced low relative to their book equity "
    "are cheap and out-drift (the HML value effect), so high book-to-market -> "
    "high rank -> bullish, ranked WITHIN (date, industry), with non-positive book "
    "equity excluded so the ratio cannot sign-invert and market cap = point-in-"
    "time shares outstanding x that row's adj_close. Deleveraging momentum "
    "(MANAGER-SELECTED): the year-over-year CHANGE in book-equity/assets; a rising "
    "equity/assets ratio means the firm is repairing its balance sheet (retiring "
    "debt and/or retaining earnings faster than assets grow), a trajectory of "
    "balance-sheet repair the market prices in only gradually, so high delta -> "
    "high rank -> bullish, ranked WITHIN (date, industry). Both the current and "
    "the YEAR-AGO equity and assets are taken AS-FIRST-REPORTED (earliest "
    "filed_date per fiscal period), so the year-ago equity/assets is the figure "
    "known as of the year-ago filing date and a later restatement can never leak "
    "backward — the change becomes available only on the current year's filing "
    "date. Orthogonality: the two legs share a book-equity-accretion driver "
    "(acknowledged), but the coupling is partial — leg 1 is a LEVEL dominated by "
    "the PRICE denominator (which leg 2 does not contain) while leg 2 is a YoY "
    "CHANGE gated by debt and asset dynamics with no price term; levels and changes "
    "of related quantities are typically weakly correlated and the value-trap "
    "quadrant (cheap on book while re-levering) is real and populated, so cheapness-"
    "on-book (VALUE-LEVEL) and balance-sheet-repair trajectory (REPAIR-CHANGE) are "
    "two genuinely different cross-sectional axes. NOTE: the dropped macro discount-"
    "rate timer is deliberately NOT implemented (its only ranking content is a "
    "coarse hand-set duration weight — the tuning-attributable, artifact-prone "
    "component — and one value-per-date inflates apparent robustness), and the "
    "prior solvency/profmom/macro frame is NOT re-added; the team selected exactly "
    "these two legs."
)

_ASSETS = "Assets"
_EQUITY = "StockholdersEquity"
_SHARES_TAGS_INSTANT = ["CommonStockSharesOutstanding"]
_SHARES_TAGS_ANNUAL = ["WeightedAverageNumberOfDilutedSharesOutstanding"]

_ALL_CONCEPTS = [_ASSETS, _EQUITY] + _SHARES_TAGS_INSTANT + _SHARES_TAGS_ANNUAL


def _instant_first_reported(df):
    """Instant concept, EARLIEST filed per (ticker, period_end) — as-first-reported,
    so a later restatement (10-K/A) never leaks backward."""
    df = df.dropna(subset=["period_end", "filed_date", "value"]).copy()
    return (df.sort_values("filed_date")
              .drop_duplicates(["ticker", "period_end"], keep="first"))


def _annual_first_reported(df):
    """Full-year (330-400 day) duration rows, earliest filed per period_end."""
    df = df.dropna(subset=["period_start", "period_end", "filed_date", "value"]).copy()
    df["dur"] = (df["period_end"] - df["period_start"]).dt.days
    df = df[(df["dur"] >= 330) & (df["dur"] <= 400)]
    return (df.sort_values("filed_date")
              .drop_duplicates(["ticker", "period_end"], keep="first"))


def _pit_fundamentals(tickers):
    """Per (ticker, avail_date): book_equity (dollars), shares, delev (YoY change
    in book-equity/assets). All inputs point-in-time, taken as-first-reported."""
    cols = ["ticker", "avail_date", "book_equity", "shares", "delev"]
    fund = fetch_fundamentals(list(tickers), concepts=_ALL_CONCEPTS)
    if fund.empty:
        return pd.DataFrame(columns=cols)
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()

    assets = _instant_first_reported(fund[fund["concept"] == _ASSETS])
    assets = assets[assets["value"] > 0]
    equity = _instant_first_reported(fund[fund["concept"] == _EQUITY])
    shares_inst = _instant_first_reported(
        fund[fund["concept"].isin(_SHARES_TAGS_INSTANT)])
    shares_wavg = _annual_first_reported(
        fund[fund["concept"].isin(_SHARES_TAGS_ANNUAL)])

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = assets[assets["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)
        e = equity[equity["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)
        shi = shares_inst[shares_inst["ticker"] == ticker].sort_values("period_end")
        shw = shares_wavg[shares_wavg["ticker"] == ticker].sort_values("period_end")

        if a.empty or e.empty:
            a_pe = pd.Series([], dtype="datetime64[ns]")
            a_val = np.array([])
        else:
            a_pe = a["period_end"]
            a_val = a["value"].astype(float).values

        # ---- eq/assets per equity period_end (as-first-reported both lines) ----
        # store (eq_assets, avail_date=max(eq_filed, assets_filed)) keyed by period_end
        eqa_by_pe = {}
        for i in range(len(e)):
            pe = e["period_end"].iloc[i]
            eq_val = float(e["value"].iloc[i])
            if not np.isfinite(eq_val) or eq_val <= 0:
                continue  # non-positive book equity sign-inverts the ratio
            if len(a_pe) == 0:
                continue
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = int(diffs.argmin())
            if diffs[j] > 45 or a_val[j] <= 0:
                continue
            eqa = eq_val / a_val[j]
            avail = max(e["filed_date"].iloc[i], a["filed_date"].iloc[j])
            eqa_by_pe[pe] = (eqa, avail)

            # ---- Leg 1 numerator: book equity (dollars), available at equity filing
            records.append({"ticker": ticker,
                            "avail_date": e["filed_date"].iloc[i],
                            "book_equity": eq_val, "shares": np.nan,
                            "delev": np.nan})

        # ---- Leg 2: deleveraging momentum = YoY change in eq/assets ----
        # prior-year value is LOCKED as-first-reported (no restatement leak); the
        # change is available only on the current year's filing date.
        for pe, (eqa_cur, avail_cur) in eqa_by_pe.items():
            target = pe - pd.Timedelta(days=365)
            best_pe, best_diff = None, 9999
            for ppe in eqa_by_pe:
                d = abs((ppe - target).days)
                if d < best_diff:
                    best_diff, best_pe = d, ppe
            if best_pe is not None and best_diff <= 60 and best_pe != pe:
                eqa_prior = eqa_by_pe[best_pe][0]
                records.append({"ticker": ticker, "avail_date": avail_cur,
                                "book_equity": np.nan, "shares": np.nan,
                                "delev": eqa_cur - eqa_prior})

        # ---- Leg 1 denominator: shares (prefer instant count, fall back to wavg)
        sh_src = shi if len(shi) else shw
        for i in range(len(sh_src)):
            sh_val = float(sh_src["value"].iloc[i])
            if not np.isfinite(sh_val) or sh_val <= 0:
                continue
            records.append({"ticker": ticker,
                            "avail_date": sh_src["filed_date"].iloc[i],
                            "book_equity": np.nan, "shares": sh_val,
                            "delev": np.nan})

    out = pd.DataFrame(records)
    if out.empty:
        return pd.DataFrame(columns=cols)
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"book_equity": "last", "shares": "last", "delev": "last"}))
    return out


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    for c in ["book_equity", "shares", "delev"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    cols = ["avail_date", "book_equity", "shares", "delev"]
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

    # ---- Leg 1: book-to-market = book equity / point-in-time market cap ----
    mktcap = panel["shares"] * panel["adj_close"]
    panel["book_to_market"] = np.where(mktcap > 0,
                                       panel["book_equity"] / mktcap, np.nan)
    panel["book_to_market_rank"] = (
        panel.groupby(["date", "industry"])["book_to_market"]
        .rank(pct=True, ascending=True)  # high B/M = cheap = bullish -> high rank
    )

    # ---- Leg 2: deleveraging momentum rank (rising eq/assets -> high rank) ----
    panel["deleveraging_momentum_rank"] = (
        panel.groupby(["date", "industry"])["delev"]
        .rank(pct=True, ascending=True)
    )

    new_cols = ["book_to_market_rank", "deleveraging_momentum_rank"]
    panel = panel.drop(columns=["avail_date", "book_equity", "shares", "delev",
                                "book_to_market"], errors="ignore")
    return panel, new_cols
