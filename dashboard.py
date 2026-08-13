"""Phase D — the live research dashboard (Streamlit), shadcn-styled.

Watchability, per the spec: a readable view of the journal and live scores.
Per experiment it shows the three things Preyansh asked for:
  1. the exact feature tested (the real code),
  2. why it was chosen (the researcher's hypothesis + post-verdict reflection),
  3. the exact out-of-sample rows behind the score, previewable and downloadable.
Read-only: the research loop runs from the CLI (`python3 run_phase_c_loop.py`),
not from this dashboard.

Look & feel: black-and-white shadcn aesthetic (per Preyansh's reference UIs):
white canvas, soft layered shadows, one inverse "hero" card, monochrome badges
where FILLED = positive and OUTLINED = negative (arrows carry the meaning, not
color), grayscale charts. Inter everywhere.

Run:  streamlit run dashboard.py
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
import sqlite3

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from core import monetary_metric

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
JOURNAL_DB = PROJECT_ROOT / "journal.db"

st.set_page_config(page_title="Market Research Agent", layout="wide")

# ------------------------------------------------------- dark / accent theme
ZINC = {"100": "#151517", "200": "#232326", "300": "#33333a",
        "500": "#9a9aa5", "700": "#c8c8cf", "950": "#f5f5f6"}
PAGE_BG = "#0a0a0b"
SURFACE = "#141416"
SURFACE_2 = "#1a1a1d"
ACCENT = "#3ecf8e"
ACCENT_TEXT = "#04140c"
ACCENT_SOFT = "rgba(62,207,142,.14)"
ACCENT_BORDER_SOFT = "rgba(62,207,142,.3)"
ACCENT_HOVER = "#34b87c"
SHADOW = "0 1px 2px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.03)"
SHADOW_LG = f"0 1px 2px rgba(0,0,0,.35), 0 0 0 1px {ACCENT_BORDER_SOFT}, 0 10px 28px rgba(62,207,142,.10)"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,1,0&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"] * {{
    font-family: 'Inter', -apple-system, sans-serif;
}}
/* Streamlit's icons are a ligature font — the Inter override above would turn
   them into literal text like "keyboard_arrow_right", so restore their font.
   Also used directly for the icons this theme adds to cards/pipeline steps. */
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded' !important;
    font-variation-settings: 'FILL' 1;
}}
[data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(ellipse 900px 500px at 15% -5%, rgba(62,207,142,.10), transparent 60%),
        {PAGE_BG};
}}
.block-container {{ padding-top: 2.5rem; max-width: 1200px; }}

h1 {{ font-weight: 800 !important; letter-spacing: -0.04em; font-size: 1.85rem !important; }}
h2, h3 {{ font-weight: 600 !important; letter-spacing: -0.02em; }}

/* card primitives */
.sc-card {{
    background: {SURFACE}; border: 1px solid {ZINC["200"]}; border-radius: 16px;
    padding: 1.15rem 1.35rem; box-shadow: {SHADOW};
}}
.sc-card-dark {{
    background: {SURFACE_2}; border: 1px solid {ACCENT}; border-radius: 16px;
    padding: 1.15rem 1.35rem; box-shadow: {SHADOW_LG};
}}
.sc-card-dark .sc-label {{ color: {ACCENT}; }}

.sc-label {{
    font-size: .72rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: .06em; color: {ZINC["500"]}; margin-bottom: .35rem;
}}
.sc-value {{ font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; color: {ZINC["950"]};
    white-space: nowrap; }}
.sc-sub {{ font-size: .78rem; color: {ZINC["500"]}; margin-top: .3rem; }}

/* badges: FILLED = positive/active, OUTLINED = negative/neutral */
.sc-badge {{
    display: inline-block; font-size: .72rem; font-weight: 600;
    border-radius: 9999px; padding: .18rem .65rem;
}}
.sc-badge-solid   {{ background: {ACCENT}; color: {ACCENT_TEXT}; border: 1px solid {ACCENT}; }}
.sc-badge-outline {{ background: transparent; color: {ZINC["700"]}; border: 1px solid {ZINC["300"]}; }}
.sc-badge-muted   {{ background: {ZINC["100"]}; color: {ZINC["700"]}; border: 1px solid {ZINC["200"]}; }}
.sc-badge-warn    {{ background: rgba(245,158,11,.15); color: #f5a623; border: 1px solid rgba(245,158,11,.4); }}

/* streamlit widget restyling */
[data-testid="stMetric"], [data-testid="stExpander"] {{
    background: {SURFACE}; border: 1px solid {ZINC["200"]}; border-radius: 16px;
    box-shadow: {SHADOW};
}}
[data-testid="stDataFrame"] {{
    border: 1px solid {ZINC["200"]}; border-radius: 16px; box-shadow: {SHADOW};
}}
/* tab-like nav — st.pills backed by session_state, see comment at call site */
[data-testid="stPills"] {{
    gap: .25rem; background: {ZINC["100"]}; padding: .3rem; border-radius: 12px;
    width: fit-content; margin-bottom: .75rem;
}}
[data-testid="stPills"] [data-testid="stBaseButton-pills"] {{
    border-radius: 9px !important; padding: .35rem .95rem !important;
    font-weight: 500 !important; font-size: .85rem !important; border: none !important;
    background: transparent !important; color: {ZINC["500"]} !important; box-shadow: none !important;
}}
[data-testid="stPills"] [data-testid="stBaseButton-pillsActive"] {{
    background: {ACCENT_SOFT} !important; box-shadow: inset 0 0 0 1px {ACCENT_BORDER_SOFT} !important;
    color: {ACCENT} !important; font-weight: 600 !important;
}}
.stDownloadButton button, .stButton button {{
    border-radius: 10px; border: 1px solid {ZINC["300"]}; font-weight: 500;
    box-shadow: 0 1px 2px rgba(0,0,0,.2);
}}
.stButton button[kind="primary"] {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_TEXT};
    box-shadow: {SHADOW};
}}
.stButton button[kind="primary"]:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
code {{ background: {ZINC["100"]}; border-radius: 6px; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=10)  # refresh every 10s so a running loop shows up live
def load_experiments() -> pd.DataFrame:
    with sqlite3.connect(JOURNAL_DB) as connection:
        return pd.read_sql("SELECT * FROM experiments ORDER BY iteration", connection)


@st.cache_data(ttl=10)
def find_agent_conversations() -> list[int]:
    """Which iterations have --multi-agent output at all (JSON or legacy markdown)."""
    found = []
    proposals_dir = PROJECT_ROOT / "proposals"
    if not proposals_dir.exists():
        return found
    for path in sorted(proposals_dir.glob("iteration_*")):
        if (path / "team_conversation.json").exists() or (path / "team_transcript.md").exists():
            try:
                found.append(int(path.name.split("_")[1]))
            except (IndexError, ValueError):
                continue
    return sorted(found)


@st.cache_data(ttl=10)
def load_agent_conversation(iteration: int) -> dict | None:
    """The structured team conversation for one iteration, or None if only the
    legacy markdown transcript exists (pre-dates this dashboard tab)."""
    path = PROJECT_ROOT / "proposals" / f"iteration_{iteration}" / "team_conversation.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


@st.cache_data(ttl=10)
def load_holdout_verdicts() -> pd.DataFrame:
    with sqlite3.connect(JOURNAL_DB) as connection:
        return pd.read_sql(
            "SELECT v.*, e.signal_name FROM holdout_verdicts v"
            " JOIN experiments e ON e.id = v.experiment_id ORDER BY v.recorded_at",
            connection,
        )


_JARGON_EXPANSIONS = {
    "profmom": "profitability momentum", "fcf": "free cash flow",
    "pead": "post-earnings drift", "sue": "earnings surprise",
    "mom": "momentum", "roe": "return on equity", "roa": "return on assets",
    "chg": "change", "rank": "", "yoy": "year-over-year",
}


def display_name(signal_name: str) -> str:
    """Turn a researcher-assigned code name ('discipline_profmom_macro_bundle_v2')
    into a readable label. Display only — every lookup (files, journal rows)
    still uses the original signal_name."""
    tokens = [t for t in signal_name.split("_") if t and t != "bundle"]
    words = [f"({t})" if t in ("v2", "v3", "v4", "v5") else _JARGON_EXPANSIONS.get(t, t)
             for t in tokens]
    label = " ".join(w for w in words if w)
    return (label[0].upper() + label[1:]) if label else signal_name


def display_driver(top_driver: str) -> str:
    """Turn a combined-model column name ('iter29__profmom_roa_chg_rank') into
    a short readable label. These are namespaced per source signal
    (core/candidates.py) to avoid column collisions — strip that prefix, then
    humanize the rest the same way as a signal name. Capped in length so it
    never overflows the card that shows it."""
    raw_column_name = re.sub(r"^iter\d+__", "", top_driver)
    label = display_name(raw_column_name)
    return label if len(label) <= 42 else label[:39] + "..."


# Plain-English, human-written summaries of each signal_name's hypothesis —
# the raw hypothesis text is written by the researcher for other researchers
# (dense finance jargon), so truncating it doesn't make it readable. Written
# once per distinct signal_name; iterations that re-run the same signal_name
# (e.g. re-tests) share the same summary. New signal_names not yet in this
# dict fall back to a truncated first sentence — see _one_liner below.
SIGNAL_SUMMARIES = {
    "mom_12_1": "Looks at how much a stock's price has climbed over the past year "
                "(ignoring the most recent month) — stocks on a long upward run tend to "
                "keep climbing a little longer.",
    "pead_earnings_surprise": "Looks at whether a company just reported earnings well "
                "above what analysts expected — stocks tend to keep drifting up for weeks "
                "after a surprisingly good earnings report.",
    "low_volatility": "Looks at how much a stock's price has been swinging around lately "
                "— calmer, steadier stocks tend to do better than wildly volatile ones.",
    "fundamental_quality": "Looks at how profitable a company is and whether that profit "
                "shows up as real cash rather than just accounting numbers — companies "
                "with genuine, cash-backed profits tend to be undervalued.",
    "asset_growth_investment": "Looks at how fast a company has been growing its assets — "
                "buying things, expanding, acquiring other companies — companies that "
                "expand aggressively tend to underperform, while slower, careful ones do better.",
    "net_payout_yield": "Looks at how much cash a company is handing back to "
                "shareholders through buybacks and dividends, versus how much new stock "
                "it's issuing — companies giving cash back tend to outperform those diluting shareholders.",
    "capital_discipline_quality_composite": "Looks at several signs of a well-run company "
                "at once — slow, careful growth; paying down debt; strong, consistent "
                "profits — and combines them into one \"how disciplined is this company\" score.",
    "profitability_acceleration": "Looks at whether a company's profit relative to its "
                "assets has been improving over the past year — companies getting more "
                "profitable tend to keep outperforming as the market gradually catches on.",
    "capital_discipline_x_profit_momentum": "Looks at two things about a company at once: "
                "is it growing carefully (not overspending) AND getting more profitable at "
                "the same time? Only companies doing both get flagged as attractive.",
    "short_term_reversal": "Looks at how a stock moved over just the last week or month — "
                "stocks that moved sharply in one direction recently tend to bounce back "
                "the other way shortly after.",
    "earnings_stability": "Looks at how steady a company's profits have been from year to "
                "year — companies with consistent, predictable earnings tend to outperform "
                "companies with erratic, unpredictable ones.",
    "quality_composite_zscore": "Looks at three signs of a well-run company — careful "
                "growth, improving profits, and consistent earnings — and combines them "
                "into one overall \"quality\" score.",
    "macro_financial_conditions": "Looks at economy-wide interest rates and market "
                "volatility, not any single company — leans bullish on the whole market "
                "when rates are low/falling and conditions look calm.",
    "macro_timed_capital_discipline": "Looks at whether a company is growing carefully, "
                "but only treats that as a bullish sign when the broader economic backdrop "
                "— interest rates, investor risk appetite — is favorable.",
    "credit_broadened_financial_conditions": "Looks at economy-wide interest rates and "
                "volatility, plus how expensive it currently is for companies in general to "
                "borrow money — a fuller read on whether financial conditions favor stocks.",
    "duration_scaled_rate_pressure": "Looks at economy-wide interest rates, applying the "
                "effect more heavily to industries most sensitive to rate changes (like "
                "tech) and less to industries that aren't (like utilities).",
    "rate_beta_scaled_rate_pressure": "Looks at economy-wide interest rates, but instead "
                "of guessing by industry, measures each individual company's own actual "
                "historical sensitivity to rate changes.",
    "discipline_profmom_macro_bundle": "Looks at three things: is the company growing its "
                "assets carefully (not overexpanding)? Is its profitability improving? And "
                "are economy-wide interest rates in a favorable place right now?",
    "discipline_profmom_macro_bundle_v2": "The same three checks as the original bundle — "
                "careful growth, improving profits, favorable rates — with the interest-rate "
                "effect fine-tuned per industry.",
    "discipline_profmom_macro_bundle_v3": "The same three-part check, adjusted for energy "
                "companies, which tend to benefit from rising rates while most other "
                "industries don't.",
    "discipline_value_macro_bundle": "Looks at whether a company is growing its assets "
                "carefully, whether its stock is cheap relative to its earnings, and "
                "whether economy-wide interest rates are favorable.",
    "discipline_profmom_value_macro_bundle": "Looks at four things about a company: "
                "careful asset growth, improving profitability, a cheap stock price "
                "relative to earnings, and favorable economy-wide interest rates.",
    "discipline_profmom_macro_bundle_v4": "The same three-part check — careful growth, "
                "improving profits, favorable rates — after a fourth factor based on "
                "analyst sentiment was tried and dropped for risking look-ahead bias.",
    "discipline_grossprofit_macro_bundle": "Looks at whether a company is growing its "
                "assets carefully, how much gross profit it keeps per dollar of assets, "
                "and whether economy-wide interest rates are favorable.",
    "solvency_profmom_macro_bundle": "Looks at how much debt a company carries relative "
                "to its assets (less debt means less risk of financial trouble), whether "
                "its profitability is improving, and whether economy-wide interest rates "
                "are favorable.",
    "asset_turnover_profmom_macro_bundle": "Looks at how efficiently a company turns its "
                "assets into sales, whether its profitability is improving, and whether "
                "economy-wide interest rates are favorable.",
    "cash_liquidity_realrate_bundle": "Looks at how much cash a company is holding "
                "relative to its assets, and separately, whether inflation-adjusted "
                "interest rates make the overall market backdrop favorable.",
    "operating_profitability_rmw_profmom_macro_bundle": "Looks at how much operating "
                "profit a company makes relative to its equity, whether that "
                "profitability is improving, and whether economy-wide interest rates are favorable.",
    "operating_margin_fcf_yield_bundle": "Looks at how much profit a company keeps from "
                "each dollar of sales, and separately, how cheap its stock is relative to "
                "the actual cash it generates.",
    "accruals_earnings_quality_sales_yield_bundle": "Looks at whether a company's "
                "reported profits are backed by real cash rather than accounting "
                "adjustments, and separately, how cheap its stock is relative to its revenue.",
    "book_to_market_deleveraging_momentum_bundle": "Looks at how cheap a company's stock "
                "is relative to its book value, and whether it's been paying down debt and "
                "strengthening its balance sheet.",
    "solvency_pricemom_macro_bundle": "Looks at how much debt a company carries, whether "
                "its stock price has been trending up over the past year, and whether "
                "economy-wide interest rates are favorable.",
    "solvency_profmom_pricemom_macro_bundle": "Looks at how much debt a company carries, "
                "whether its profitability is improving, whether its stock price is "
                "trending up, and whether economy-wide interest rates are favorable — four checks at once.",
    "solvency_insider_macro_bundle": "Looks at how much debt a company carries, and "
                "whether company insiders — executives, board members — have recently "
                "bought shares with their own money, plus whether economy-wide interest "
                "rates are favorable.",
    "solvency_lowvol_macro_bundle": "Looks at how much debt a company carries, and "
                "separately how calm or volatile its stock price has been, plus whether "
                "economy-wide interest rates are favorable.",
    "profitability_insider_macro_bundle": "Looks at how much operating profit a company "
                "makes relative to its equity, whether company insiders have recently been "
                "buying shares with their own money, and whether economy-wide interest "
                "rates are favorable.",
}

MONEY_DISCLAIMER = "Past performance, not a forecast. Excludes trading costs and taxes."
MONEY_EXPLAINER = (
    "How to read this: two hypothetical $500 accounts trade through the signal's test "
    "period. One rebalances into the model's top 5 highest-ranked stocks every ~21 "
    "trading days (about a month). The other spreads the same $500 evenly across every "
    "stock the model was scoring that period — a plain average, not a real market index. "
    "The gap between the two ending balances is the signal's edge."
)


@st.cache_data(ttl=15)
def compute_monetary_metric(oos_csv_path: str) -> dict:
    """The external, dashboard-facing metric for one experiment: $500 in the
    model's top-5 picks every 21 trading days vs. $500 spread across every
    stock it was choosing from, compounded. See core/monetary_metric.py."""
    csv_file = PROJECT_ROOT / oos_csv_path
    if not csv_file.exists():
        return {"error": "no out-of-sample data on disk"}
    return monetary_metric.top5_vs_universe(pd.read_csv(csv_file))


@st.cache_data(ttl=15)
def load_monetary_summary(tested_experiments: pd.DataFrame) -> pd.DataFrame:
    """One row per tested signal with its external ($) metric, for the
    Signals tab. Skips signals with no saved out-of-sample rows or too
    little validation data for two non-overlapping periods."""
    rows = []
    for record in tested_experiments.itertuples():
        oos_csv_path = getattr(record, "oos_csv_path", None)
        if not oos_csv_path or pd.isna(oos_csv_path):
            continue
        result = compute_monetary_metric(oos_csv_path)
        if "error" in result:
            continue
        rows.append({
            "iteration": record.iteration,
            "signal_name": record.signal_name,
            "display_name": display_name(record.signal_name),
            "top5_final_balance": result["top5_final_balance"],
            "universe_final_balance": result["universe_final_balance"],
            "dollar_edge": result["dollar_edge"],
            "pct_edge": result["pct_edge"],
            "n_periods": result["n_periods"],
        })
    return pd.DataFrame(rows)


def money_card(label: str, dollar_edge: float, sub: str = "", dark: bool = False, icon: str = "") -> str:
    """Hero-style card for a $ edge, with the same up/down arrow convention
    used everywhere else — arrows carry the meaning, not color."""
    arrow = "↗" if dollar_edge >= 0 else "↘"
    value = f"{arrow} {'+' if dollar_edge >= 0 else '-'}${abs(dollar_edge):,.0f}"
    return card(label, value, sub, dark=dark, icon=icon)


def _escape_dollar(text) -> str:
    """Streamlit's markdown renders bare $..$ as LaTeX math, and two of these
    HTML fragments landing in the same st.markdown call can get their $ signs
    paired up across fragments into one garbled formula. A backslash escape
    ('\\$') doesn't help — Streamlit shows the backslash literally instead of
    stripping it — so use the HTML entity instead: it decodes to '$' in the
    browser but contains no literal '$' for the math scanner to catch."""
    return str(text).replace("$", "&#36;")


def card(label: str, value: str, sub: str = "", dark: bool = False, icon: str = "",
         wrap: bool = False) -> str:
    label, value, sub = _escape_dollar(label), _escape_dollar(value), _escape_dollar(sub)
    sub_html = f'<div class="sc-sub">{sub}</div>' if sub else ""
    css_class = "sc-card-dark" if dark else "sc-card"
    icon_html = (f'<span class="material-symbols-rounded" '
                 f'style="font-size:1rem; vertical-align:-3px; margin-right:.35rem; opacity:.75;">'
                 f'{icon}</span>') if icon else ""
    # Long values (e.g. multi-model comparisons) overflow the nowrap default —
    # let those wrap onto multiple lines at a smaller size instead.
    value_style = ' style="white-space:normal; font-size:1.05rem; line-height:1.4;"' if wrap else ""
    return (f'<div class="{css_class}"><div class="sc-label">{icon_html}{label}</div>'
            f'<div class="sc-value"{value_style}>{value}</div>{sub_html}</div>')


def badge(text: str, tone: str = "muted", title: str = "") -> str:
    title_attr = f' title="{title}"' if title else ""
    return f'<span class="sc-badge sc-badge-{tone}"{title_attr}>{_escape_dollar(text)}</span>'


# ------------------------------------------------------------------ header
header_left, header_right = st.columns([3, 1])
with header_left:
    st.markdown('<h1 style="margin-bottom:0;">Self-Improving Market Research Agent</h1>',
                unsafe_allow_html=True)
    st.markdown(
        f'<p style="color:{ZINC["500"]}; margin-top:-0.3rem; font-size:.92rem;">'
        "AI proposes stock-picking signals. A deterministic judge tests each one on "
        "data it's never seen before trusting it.</p>", unsafe_allow_html=True,
    )
with header_right:
    st.markdown(
        f'<div style="text-align:right; font-size:.8rem; color:{ZINC["500"]}; '
        'white-space:nowrap; padding-top:.35rem;">'
        f'<div style="font-weight:600; color:{ZINC["950"]};">Preyansh Jain</div>'
        '<div style="margin-top:.15rem;">'
        '<a href="https://github.com/pjain646/stock-market-agent" target="_blank" '
        f'style="color:{ZINC["500"]}; text-decoration:none; border-bottom:1px solid {ZINC["300"]};">'
        'GitHub</a>&nbsp;&middot;&nbsp;'
        '<a href="https://www.linkedin.com/in/preyanshjain/" target="_blank" '
        f'style="color:{ZINC["500"]}; text-decoration:none; border-bottom:1px solid {ZINC["300"]};">'
        'LinkedIn</a></div></div>', unsafe_allow_html=True,
    )

experiments = load_experiments()
if experiments.empty:
    st.info("The journal is empty — run an iteration first (`python3 run_phase_c_loop.py`)")

tested = experiments[experiments["status"] == "tested"] if not experiments.empty else pd.DataFrame()
total_cost = experiments["cost_usd"].dropna().sum() if not experiments.empty else 0.0
monetary_summary = load_monetary_summary(tested) if not tested.empty else pd.DataFrame()
best_money_row = (monetary_summary.loc[monetary_summary["dollar_edge"].idxmax()]
                  if not monetary_summary.empty else None)
holdout_verdicts = load_holdout_verdicts()

# Architecture strip — the whole point is to make the validation discipline
# visible without anyone having to click into the Metrics tab.
_ARROW = f'<div style="color:{ZINC["300"]}; font-size:1.1rem; padding:0 .4rem;">&rarr;</div>'


def _arch_step(name: str, caption: str, icon: str) -> str:
    return (f'<div style="flex:1; text-align:center;">'
            f'<span class="material-symbols-rounded" '
            f'style="font-size:1.3rem; color:{ACCENT};">{icon}</span>'
            f'<div style="font-weight:600; font-size:.85rem; margin-top:.3rem;">{name}</div>'
            f'<div style="font-size:.72rem; color:{ZINC["500"]}; margin-top:.15rem;">{caption}</div>'
            f'</div>')


st.markdown(
    '<div class="sc-card" style="margin-top:1rem; margin-bottom:1rem;">'
    '<div class="sc-label" style="margin-bottom:.9rem;">How it works</div>'
    '<div style="display:flex; align-items:center;">'
    + _arch_step("Researcher", "Claude proposes a signal", "auto_awesome") + _ARROW
    + _arch_step("Judge", "Purged walk-forward test", "gavel") + _ARROW
    + _arch_step("Sealed holdout", "One shot on unseen data", "lock") + _ARROW
    + _arch_step("Live picks", "Only proven signals ship", "rocket_launch")
    + '</div></div>', unsafe_allow_html=True,
)

rigor_badges = " ".join([
    badge("Purged walk-forward validation",
          title="Tested on 6 chronological chunks of data, always training on the past and "
                "predicting the future — with a gap before each test chunk so no training "
                "row can accidentally peek at test-period information."),
    badge("Sealed one-time holdout",
          title="A slice of data the model never saw during development, checked exactly "
                "once at the very end of a run — the closest thing to a real, honest final exam."),
    badge("3-model cross-check",
          title="Every signal is scored by three different model types. If only one of them "
                "sees an edge, that's treated as a red flag, not a win."),
    badge(f"{len(experiments)} experiments, ${total_cost:,.0f} spent",
          title="Every signal this project has ever tried, including the ones that failed."),
])
st.markdown(f'<div style="margin-bottom:1.2rem;">{rigor_badges}</div>', unsafe_allow_html=True)

# Hero (dark) card = the headline number; the rest stay light. Only the
# external ($) metric appears here — internal research metrics live behind
# "technical details" in the Experiment detail tab and on the Metrics page.
overview = st.columns(4)
if best_money_row is not None:
    overview[0].markdown(money_card("Best signal", best_money_row["dollar_edge"],
                                    display_name(best_money_row["signal_name"]), dark=True,
                                    icon="trending_up"),
                         unsafe_allow_html=True)
else:
    overview[0].markdown(card("Best signal", "—", "no tested signals yet", dark=True,
                              icon="trending_up"),
                         unsafe_allow_html=True)
overview[1].markdown(card("Experiments", str(len(experiments)), f"{len(tested)} tested",
                          icon="science"), unsafe_allow_html=True)
overview[2].markdown(card("Research spend", f"${total_cost:.2f}", "", icon="payments"),
                     unsafe_allow_html=True)
if holdout_verdicts.empty:
    overview[3].markdown(card("Gate 1", "sealed", "opens at the end of a run", icon="verified"),
                         unsafe_allow_html=True)
else:
    latest = holdout_verdicts.iloc[-1]
    gate_passed = bool(latest["gate1_passed"])
    gate_text = "PASSED ↗" if gate_passed else "FAILED ↘"
    overview[3].markdown(card("Gate 1", gate_text, display_name(latest["signal_name"]),
                              icon="verified"),
                         unsafe_allow_html=True)

st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.78rem; margin-top:.5rem;">{MONEY_DISCLAIMER}</p>',
            unsafe_allow_html=True)
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------- tabs
# st.tabs() doesn't persist the active tab across reruns triggered by a
# widget elsewhere on the page (e.g. the iteration selectors below) — any
# interaction resets it to tab 0. st.pills backed by session_state does
# persist, so it's used here as tab-like nav instead.
TAB_NAMES = ["Signals", "Signal library", "Stock predictions", "Experiment detail",
             "Research debate", "Holdout verdicts", "Metrics"]
active_tab = st.pills("Navigation", TAB_NAMES, default=TAB_NAMES[0],
                      key="active_tab", label_visibility="collapsed")

if active_tab == "Signals":
    if monetary_summary.empty:
        st.write("No tested signals with enough out-of-sample data yet.")
    else:
        ranking = monetary_summary.sort_values("dollar_edge", ascending=False).reset_index(drop=True)
        chart_data = ranking.copy()
        chart_data["positive"] = chart_data["dollar_edge"] >= 0
        # Accent: positive bars in emerald, negative bars in muted gray.
        score_chart = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("dollar_edge:Q", title="$ edge vs. the average stock"),
                y=alt.Y("display_name:N", sort="-x", title=None),
                color=alt.condition(alt.datum.positive,
                                    alt.value(ACCENT), alt.value(ZINC["300"])),
                tooltip=["display_name", "dollar_edge", "pct_edge"],
            )
            .properties(height=60 + 42 * len(chart_data), background="transparent")
            .configure_view(strokeOpacity=0)
            .configure_axis(labelFont="Inter", titleFont="Inter", labelColor=ZINC["500"],
                            titleColor=ZINC["500"], gridColor=ZINC["200"],
                            domainColor=ZINC["300"], tickColor=ZINC["300"], labelLimit=280)
        )
        st.altair_chart(score_chart, use_container_width=True)
        st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.82rem;">{MONEY_EXPLAINER}</p>',
                    unsafe_allow_html=True)
        display_ranking = ranking[["display_name", "top5_final_balance", "universe_final_balance",
                                   "dollar_edge", "pct_edge"]].rename(columns={
            "display_name": "Signal",
            "top5_final_balance": "Top 5 picks — ending $",
            "universe_final_balance": "Average stock — ending $",
            "dollar_edge": "$ edge",
            "pct_edge": "% edge",
        })
        st.dataframe(display_ranking, use_container_width=True, hide_index=True)
        st.caption(MONEY_DISCLAIMER)

if active_tab == "Signal library":
    st.markdown('<div class="sc-label">Every signal tried so far</div>', unsafe_allow_html=True)
    st.markdown(
        f'<p style="color:{ZINC["500"]}; font-size:.85rem;">One line on the idea behind each of the '
        f'{len(experiments)} feature bundles the researcher has proposed, newest first.</p>',
        unsafe_allow_html=True,
    )
    if experiments.empty:
        st.write("Nothing tested yet.")
    else:
        def _one_liner(signal_name: str, hypothesis: str, limit: int = 160) -> str:
            if signal_name in SIGNAL_SUMMARIES:
                return SIGNAL_SUMMARIES[signal_name]
            # Fallback for a signal_name not yet written up above — the raw
            # hypothesis is researcher-to-researcher jargon, so this is a
            # stopgap, not a real summary.
            if not hypothesis:
                return "—"
            first = hypothesis.split(". ")[0].strip()
            if not first.endswith((".", "!", "?")):
                first += "."
            if len(first) > limit:
                first = first[:limit].rsplit(" ", 1)[0] + "…"
            return first

        library_rows = pd.DataFrame([
            {
                "Iteration": int(row.iteration),
                "Signal": display_name(row.signal_name),
                "The idea, in plain English": _one_liner(row.signal_name, row.hypothesis),
                "Status": row.status,
            }
            for row in experiments.itertuples()
        ]).sort_values("Iteration", ascending=False)
        st.dataframe(library_rows, use_container_width=True, hide_index=True)

if active_tab == "Stock predictions":
    # The product's actual output: per-stock predictions from COMBINED proven
    # signals (core/candidates.py, task #10). Reads whatever
    # `python3 run_phase_c_loop.py --rank-candidates` last produced.
    positive_signals = tested[tested["tested_score"] > 0] if not tested.empty else pd.DataFrame()
    candidates_csv_path = PROJECT_ROOT / "candidates" / "candidates.csv"
    candidates_manifest_path = PROJECT_ROOT / "candidates" / "candidates.manifest.json"

    if candidates_csv_path.exists():
        candidate_rows = pd.read_csv(candidates_csv_path)
        manifest = (json.loads(candidates_manifest_path.read_text())
                   if candidates_manifest_path.exists() else {})
        as_of_date = candidate_rows["date"].iloc[0] if not candidate_rows.empty else "unknown"

        st.markdown('<div class="sc-label">Today\'s stock picks</div>', unsafe_allow_html=True)
        signals_used = manifest.get("signals_used", [])
        signal_badges = " ".join(badge(display_name(s["signal_name"]), "muted") for s in signals_used)

        # Freshness indicator — derived purely from the committed data's own
        # date vs. today's date, not from any live signal about the GitHub
        # Action. That's deliberate: this dashboard (Streamlit Community
        # Cloud) sleeps when idle and only wakes on a visit, so anything
        # relying on the app being awake DURING a refresh would miss it. A
        # date comparison is correct the instant the app wakes up, however
        # long it was asleep, with zero coordination needed.
        try:
            data_date = pd.to_datetime(as_of_date).date()
            trading_days_stale = int(np.busday_count(data_date, datetime.date.today()))
        except (ValueError, TypeError):
            trading_days_stale = None

        if trading_days_stale is None:
            freshness_badge = badge("date unknown", "muted")
        elif trading_days_stale <= 0:
            freshness_badge = badge("Updated today", "solid")
        elif trading_days_stale == 1:
            freshness_badge = badge("Updated as of yesterday's close", "muted")
        else:
            # The daily workflow runs every weekday, so a >1-trading-day gap
            # means at least one scheduled refresh didn't land (workflow
            # failure, paused schedule, etc.), not just an off day.
            freshness_badge = badge(
                f"Stale — {trading_days_stale} trading days since last refresh", "warn",
                title="The daily refresh workflow may have failed — check the "
                      "\"daily candidate refresh\" runs in the GitHub Actions tab.")

        st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.85rem;">As of {as_of_date} '
                    f'{freshness_badge} · based on {len(signals_used)} proven signal(s): '
                    f'{signal_badges}</p>', unsafe_allow_html=True)

        if not candidate_rows.empty:
            top_pick = candidate_rows.iloc[0]
            hero_columns = st.columns(3)
            hero_columns[0].markdown(card("Top pick", top_pick["ticker"],
                                          f"{top_pick['predicted_up_probability']:.0%} confidence", dark=True),
                                     unsafe_allow_html=True)
            hero_columns[1].markdown(card("Stocks ranked", str(len(candidate_rows)),
                                          f"{candidate_rows['industry'].nunique()} industries"),
                                     unsafe_allow_html=True)
            driver_label = display_driver(top_pick["top_driver"])
            driver_label = driver_label if len(driver_label) <= 24 else driver_label[:21] + "..."
            hero_columns[2].markdown(card("Top driver", driver_label, ""), unsafe_allow_html=True)

            display_columns = ["ticker", "industry", "predicted_up_probability", "top_driver"]
            display_table = candidate_rows[display_columns].copy()
            display_table["predicted_up_probability"] = display_table["predicted_up_probability"].map("{:.0%}".format)
            display_table["top_driver"] = display_table["top_driver"].map(display_driver)
            display_table = display_table.rename(
                columns={"predicted_up_probability": "Confidence", "top_driver": "Signal",
                         "ticker": "Ticker", "industry": "Industry"}
            )
            st.dataframe(display_table, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", candidate_rows.to_csv(index=False),
                               file_name=f"candidates_{as_of_date}.csv", mime="text/csv")

            # ---------------- live news sentiment (annotation ONLY) -------------
            st.markdown('<div class="sc-label" style="margin-top:1.4rem">'
                        'Recent news on these stocks</div>', unsafe_allow_html=True)
            st.markdown(
                f'<p style="color:{ZINC["500"]}; font-size:.85rem;">Extra context from the last 21 '
                "days of news — not part of the prediction above.</p>",
                unsafe_allow_html=True)

            sentiment_state_key = f"live_sentiment_{as_of_date}"
            if st.button("Fetch live news sentiment", key="fetch_sentiment"):
                from core import live_sentiment

                tickers = candidate_rows["ticker"].head(15).tolist()
                with st.spinner(f"Reading recent news for {len(tickers)} names ..."):
                    try:
                        table, sentiment_cost = live_sentiment.score_tickers(tickers)
                        st.session_state[sentiment_state_key] = (table, sentiment_cost)
                    except Exception as exc:  # missing key, rate limit, etc.
                        st.session_state[sentiment_state_key] = (None, str(exc))

            if sentiment_state_key in st.session_state:
                table, meta = st.session_state[sentiment_state_key]
                if table is None:
                    st.warning(f"Could not fetch sentiment: {meta}")
                else:
                    from core import live_sentiment

                    annotated = table.copy()
                    annotated["news"] = annotated.apply(live_sentiment.sentiment_label, axis=1)
                    covered = int((annotated["n_articles"] > 0).sum())
                    st.markdown(
                        badge(f"${meta:.2f}", "muted") + " " +
                        badge(f"{covered}/{len(annotated)} names with news coverage", "muted"),
                        unsafe_allow_html=True)
                    st.dataframe(
                        annotated[["ticker", "news", "n_articles", "sentiment",
                                   "price_impact_potential", "trend_direction",
                                   "investor_confidence", "risk_profile_change", "summary"]],
                        use_container_width=True, hide_index=True)
                    st.caption("Scores range -2 to +2. Blank means no news found.")
    else:
        st.markdown('<div class="sc-label">Today\'s stock picks</div>', unsafe_allow_html=True)
        eligible = (", ".join(positive_signals["signal_name"].map(display_name))
                   if not positive_signals.empty else "none yet")
        st.markdown(
            f'<div class="sc-card"><strong>No picks yet.</strong>'
            f'<div class="sc-sub" style="margin-top:.5rem; line-height:1.6">'
            f'Proven signals so far: {eligible} '
            f'({len(positive_signals)} of {len(tested)} tested).</div></div>',
            unsafe_allow_html=True,
        )

if active_tab == "Experiment detail":
    if experiments.empty:
        st.write("Nothing to show yet.")
    else:
        labels = [f"iter {int(row.iteration)} — {display_name(row.signal_name)}" for row in experiments.itertuples()]
        selected_label = st.selectbox("Experiment", labels, index=len(labels) - 1,
                                      label_visibility="collapsed")
        experiment = experiments.iloc[labels.index(selected_label)]
        metrics = json.loads(experiment["metrics"]) if experiment["metrics"] else None
        oos_csv_path = experiment.get("oos_csv_path")
        money_result = (compute_monetary_metric(oos_csv_path)
                        if oos_csv_path and pd.notna(oos_csv_path) else {"error": "not tested yet"})

        if "error" not in money_result:
            edge = money_result["dollar_edge"]
            header_badges = badge(f"{'↗ +' if edge >= 0 else '↘ -'}${abs(edge):,.0f} vs. market",
                                  "solid" if edge >= 0 else "outline")
        else:
            header_badges = badge("not tested yet", "muted")
        if pd.notna(experiment.get("cost_usd")):
            header_badges += " " + badge(f"${experiment['cost_usd']:.2f}", "muted")
        st.markdown(f"### {display_name(experiment['signal_name'])} &nbsp; {header_badges}", unsafe_allow_html=True)

        st.markdown('<div class="sc-label" style="margin-top:.6rem">Why we tried this</div>',
                    unsafe_allow_html=True)
        plain_summary = SIGNAL_SUMMARIES.get(experiment["signal_name"])
        if plain_summary:
            st.markdown(f'<div class="sc-card">{plain_summary}</div>', unsafe_allow_html=True)
            with st.expander("Full technical hypothesis (researcher's own words)"):
                st.write(experiment["hypothesis"])
        else:
            st.markdown(f'<div class="sc-card">{experiment["hypothesis"]}</div>', unsafe_allow_html=True)

        if experiment["researcher_notes"]:
            with st.expander("What we learned (researcher's reflection after testing)"):
                st.write(experiment["researcher_notes"])

        st.markdown('<div class="sc-label" style="margin-top:.9rem">The verdict</div>',
                    unsafe_allow_html=True)
        if metrics and "error" not in money_result:
            st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.82rem; margin-bottom:.6rem;">'
                        f'{MONEY_EXPLAINER}</p>', unsafe_allow_html=True)
            verdict_columns = st.columns(4)
            verdict_columns[0].markdown(card("Top 5 picks — ending balance",
                                             f"${money_result['top5_final_balance']:,.0f}",
                                             "started at $500", dark=True), unsafe_allow_html=True)
            verdict_columns[1].markdown(card("Average stock — ending balance",
                                             f"${money_result['universe_final_balance']:,.0f}",
                                             "started at $500"), unsafe_allow_html=True)
            verdict_columns[2].markdown(money_card("Edge vs. average", money_result["dollar_edge"],
                                                    f"{money_result['pct_edge']:+.1f}% ahead of average"),
                                        unsafe_allow_html=True)
            verdict_columns[3].markdown(card("Tested", money_result["first_period"],
                                             f"through {money_result['last_period']}"),
                                        unsafe_allow_html=True)
            st.caption(MONEY_DISCLAIMER)

            periods_df = pd.DataFrame(money_result["periods"])
            balances_long = periods_df.melt(
                id_vars=["period_start"], value_vars=["top5_balance", "universe_balance"],
                var_name="series", value_name="balance",
            )
            balances_long["series"] = balances_long["series"].map(
                {"top5_balance": "top 5 picks", "universe_balance": "avg stock"})
            balance_base = alt.Chart(balances_long).encode(
                x=alt.X("period_start:N", title=None, sort=None),
                y=alt.Y("balance:Q", title="account balance ($)", scale=alt.Scale(zero=False)),
                color=alt.Color("series:N", title=None,
                                scale=alt.Scale(domain=["top 5 picks", "avg stock"],
                                                range=[ACCENT, ZINC["300"]])),
            )
            # Fill only under the winning line — draws the eye to what matters.
            balance_area = (balance_base.transform_filter(alt.datum.series == "top 5 picks")
                            .mark_area(opacity=0.16, line=False))
            balance_line = balance_base.mark_line(strokeWidth=2.5)
            balance_chart = (
                (balance_area + balance_line)
                .properties(height=220, background="transparent")
                .configure_view(strokeOpacity=0)
                .configure_axis(labelFont="Inter", titleFont="Inter", labelColor=ZINC["500"],
                                titleColor=ZINC["500"], gridColor=ZINC["200"],
                                domainColor=ZINC["300"], tickColor=ZINC["300"], labelAngle=-40)
            )
            st.altair_chart(balance_chart, use_container_width=True)

            with st.expander("Technical details (for researchers — see the Metrics tab)"):
                internal_columns = st.columns(4)
                internal_columns[0].markdown(card("tested score",
                                                 f"{'↗' if metrics['tested_score'] > 0 else '↘'} {metrics['tested_score']:+.4f}",
                                                 f"base rate {metrics['base_rate']}", dark=True),
                                            unsafe_allow_html=True)
                internal_columns[1].markdown(card("precision / recall",
                                                 f"{metrics['precision']:.3f} / {metrics['recall']:.3f}",
                                                 f"{metrics['n_oos']:,} oos rows"), unsafe_allow_html=True)
                ic_value = metrics.get("ic_spearman")
                internal_columns[2].markdown(card("information coefficient",
                                                 f"{ic_value:+.4f}" if ic_value is not None else "—",
                                                 "Spearman vs realized return"), unsafe_allow_html=True)
                models = metrics.get("models", {})
                if models:
                    comparison_text = " · ".join(
                        f"{name.replace('_', ' ')} {m['tested_score']:+.3f}" for name, m in models.items()
                    )
                    internal_columns[3].markdown(card("model robustness", comparison_text,
                                                     "same folds, RF + boosted trees", wrap=True),
                                                unsafe_allow_html=True)

                per_industry = metrics.get("per_industry", {})
                if per_industry:
                    st.markdown('<div class="sc-label" style="margin-top:.9rem">Per-industry breakdown</div>',
                                unsafe_allow_html=True)
                    # A card grid doesn't scale past a handful of columns — with
                    # 10+ industries the cards get too narrow and names/values
                    # clip or wrap letter-by-letter. A table has no such limit.
                    industry_rows = pd.DataFrame([
                        {"Industry": industry,
                         "Tested score": industry_metrics.get("tested_score"),
                         "IC": industry_metrics.get("ic_spearman")}
                        for industry, industry_metrics in per_industry.items()
                    ]).sort_values("Tested score", ascending=False)
                    st.dataframe(industry_rows, use_container_width=True, hide_index=True,
                                column_config={
                                    "Tested score": st.column_config.NumberColumn(format="%+.4f"),
                                    "IC": st.column_config.NumberColumn(format="%+.3f"),
                                })
                st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
                st.json(metrics)
        elif metrics:
            st.write("Not enough data yet for this comparison.")
            with st.expander("Technical details (for researchers)"):
                st.json(metrics)
        elif experiment["error"]:
            st.error(experiment["error"])
        else:
            st.write("not tested yet")

        feature_code_file = PROJECT_ROOT / experiment["feature_code_path"]
        with st.expander("The code behind this signal"):
            if feature_code_file.exists():
                st.code(feature_code_file.read_text(), language="python")
            else:
                st.warning(f"feature code not found at {experiment['feature_code_path']}")

        st.markdown('<div class="sc-label" style="margin-top:.9rem">The test data</div>',
                    unsafe_allow_html=True)
        oos_csv_path = experiment.get("oos_csv_path")
        if oos_csv_path and (PROJECT_ROOT / oos_csv_path).exists():
            oos_rows = pd.read_csv(PROJECT_ROOT / oos_csv_path)
            st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.85rem;">{len(oos_rows):,} test rows — '
                        "each with the feature value, the model's prediction, and the actual outcome.</p>",
                        unsafe_allow_html=True)
            st.dataframe(oos_rows.head(200), use_container_width=True, hide_index=True)
            st.download_button("Download CSV", oos_rows.to_csv(index=False),
                               file_name=f"oos_rows_iteration_{int(experiment['iteration'])}.csv",
                               mime="text/csv")
        else:
            st.write("no test data recorded for this experiment")

if active_tab == "Research debate":
    st.markdown('<div class="sc-label">The research team\'s conversation</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<p style="color:{ZINC["500"]}; font-size:.85rem;">Three AI analysts debate, then a '
        "manager decides what to test. They choose what's tested — they never influence "
        "the score.</p>", unsafe_allow_html=True)

    conversations = find_agent_conversations()
    if not conversations:
        st.info("No team conversations recorded yet.")
    else:
        labels = [f"iteration {n}" for n in conversations]
        selected = st.selectbox("Iteration", labels, index=len(labels) - 1,
                                label_visibility="collapsed")
        iteration_n = conversations[labels.index(selected)]
        convo = load_agent_conversation(iteration_n)

        if convo is None:
            # Ran before this dashboard tab existed (team_transcript.md only,
            # no structured team_conversation.json) — fall back to raw markdown
            # rather than showing nothing.
            st.markdown(badge("legacy run — raw transcript only", "muted"), unsafe_allow_html=True)
            raw = (PROJECT_ROOT / "proposals" / f"iteration_{iteration_n}" / "team_transcript.md")
            st.markdown(raw.read_text() if raw.exists() else "*(no transcript found)*")
        else:
            header = badge(f"${convo.get('total_cost_usd', 0):.2f} spent", "muted")
            if convo.get("selected_factors"):
                selected_display = ", ".join(display_name(f) for f in convo["selected_factors"])
                header += " " + badge(f"chose: {selected_display}", "solid")
            else:
                header += " " + badge("nothing selected", "outline")
            for error in convo.get("errors", []):
                header += " " + badge(f"⚠ {error[:40]}", "outline")
            st.markdown(header, unsafe_allow_html=True)
            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

            avatars = {
                "fundamental": "📊", "valuation": "💰", "macro": "🌐", "sentiment": "📰",
                "bull": "🐂", "bear": "🐻", "manager": "⚖️", "external": "🔍",
            }
            for turn in convo.get("turns", []):
                speaker = turn.get("speaker", "?")
                with st.chat_message(name=speaker, avatar=avatars.get(speaker, "🤖")):
                    cost_note = (f"  ·  &#36;{turn['cost_usd']:.2f}"
                                if turn.get("cost_usd") else "  ·  &#36;0.00 (no LLM call)")
                    st.markdown(f"**{turn.get('label', speaker)}**{cost_note}")
                    st.markdown(turn.get("content") or "*(no output)*")

            if not convo.get("turns"):
                st.write("No conversation recorded for this run.")

if active_tab == "Holdout verdicts":
    if holdout_verdicts.empty:
        st.markdown('<div class="sc-card">The final test hasn\'t run yet — it opens once, '
                    'at the very end of a research run.</div>',
                    unsafe_allow_html=True)
    else:
        for _, verdict in holdout_verdicts.iterrows():
            gate_badge = (badge("PASSED ↗", "solid") if verdict["gate1_passed"]
                          else badge("FAILED ↘", "outline"))
            st.markdown(
                f'<div class="sc-card" style="margin-bottom:.6rem">'
                f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                f'<strong>{display_name(verdict["signal_name"])}</strong>{gate_badge}</div>'
                f'<div class="sc-sub">validation {verdict["validation_score"]:+.4f} · '
                f'holdout {verdict["holdout_score"]:+.4f} · gap {verdict["gap"]:+.4f} · '
                f'{verdict["recorded_at"][:19]}</div></div>',
                unsafe_allow_html=True,
            )

if active_tab == "Metrics":
    st.markdown('<div class="sc-label">The metric on this dashboard</div>', unsafe_allow_html=True)
    st.markdown(f"""
<div class="sc-card">
<strong>Top 5 picks vs. the average stock, on &#36;500 each.</strong>
<p style="margin-top:.5rem; line-height:1.6;">{MONEY_EXPLAINER}</p>
<p style="margin-top:.5rem; color:{ZINC["500"]}; font-size:.85rem;">{MONEY_DISCLAIMER}</p>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="sc-label" style="margin-top:1.4rem">How signals get chosen</div>',
                unsafe_allow_html=True)
    st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.85rem;">Used to judge whether a signal '
                "is real — not shown elsewhere on the dashboard. Full numbers are in each "
                "experiment's technical details.</p>", unsafe_allow_html=True)
    st.markdown("""
| Internal metric | What it means |
|---|---|
| **tested score** (PR-AUC uplift) | How much better the model ranks "will go up" days above "will go down" days than random guessing, on data it never trained on. Decides whether a signal is kept. |
| **IC (information coefficient)** | Correlation between the model's confidence and how big the stock's move actually was — not just direction. |
| **precision / recall** | Precision: when the model says "up," how often it's right. Recall: how many of the actual "up" days it caught. |
| **cross-model comparison** | The same signal, tested with three different model types. An edge only one of them sees is a red flag. |
| **per-industry breakdown** | The same test, run separately per sector — checks whether the edge is broad or concentrated in one industry. |
| **holdout / Gate 1** | The final exam: a sealed slice of data, opened once at the end of a run. If the score holds up there, the edge is real. |
""")

    with st.expander("Glossary — other terms used on this page"):
        st.markdown("""
| Term | What it means |
|---|---|
| **base rate** | The score you'd get for free by always guessing the majority outcome. Here ≈ 0.55, because stocks in this universe rose in ~55% of all 21-day windows. |
| **oos / out-of-sample** | Scored on data the model never trained on. The only kind of score this project reports. |
| **walk-forward** | The testing method: split validation into 6 chronological chunks; for each chunk, train only on data from *before* it, then predict it. Mimics how the model would actually be used in real time. |
| **purge gap** | A 21-trading-day buffer before each test chunk. Training rows inside it are dropped because their labels peek into the test period. Prevents a subtle form of cheating. |
| **train / validation / holdout** | The data timeline split 60/20/20. Train = learn on it. Validation = tune and rank signals on it. Holdout = the newest 20%, kept sealed until the very end. |
| **SUE** | Standardized Unexpected Earnings — how much a company's reported earnings beat or missed analyst estimates, scaled to be comparable across companies. |
| **PEAD** | Post-Earnings Announcement Drift — a well-documented market anomaly: prices keep drifting in the direction of an earnings surprise for weeks after the announcement, instead of adjusting instantly. |
| **point-in-time** | The golden rule of honest backtesting: a feature on date X may only use information that was *public* on date X (e.g. financials count from their SEC filing date, not the quarter they describe). |
| **researcher / judge / journal** | The three parts of the loop: Claude Opus proposes signals and writes feature code (researcher); a fixed statistical pipeline scores them out-of-sample (judge — the LLM can't influence it); every hypothesis, verdict, and reflection is stored (journal) and fed back to the researcher next iteration. |
""")
