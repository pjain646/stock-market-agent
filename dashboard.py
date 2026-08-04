"""Phase D — the live research dashboard (Streamlit), shadcn-styled.

Watchability, per the spec: a readable view of the journal and live scores.
Per experiment it shows the three things Preyansh asked for:
  1. the exact feature tested (the real code),
  2. why it was chosen (the researcher's hypothesis + post-verdict reflection),
  3. the exact out-of-sample rows behind the score, previewable and downloadable.
Plus: a Run tab that launches the researcher from the browser (local machine
for now; becomes a GitHub Actions trigger once deployed), and a glossary.

Look & feel: black-and-white shadcn aesthetic (per Preyansh's reference UIs):
white canvas, soft layered shadows, one inverse "hero" card, monochrome badges
where FILLED = positive and OUTLINED = negative (arrows carry the meaning, not
color), grayscale charts. Inter everywhere.

Run:  streamlit run dashboard.py
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from core import monetary_metric

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
JOURNAL_DB = PROJECT_ROOT / "journal.db"
RUN_STATE_PATH = PROJECT_ROOT / "data_cache" / "run_state.json"
RUN_LOGS_DIR = PROJECT_ROOT / "data_cache" / "run_logs"

st.set_page_config(page_title="Market Research Agent", layout="wide")

# ------------------------------------------------------------ monochrome CSS
ZINC = {"50": "#fafafa", "100": "#f4f4f5", "200": "#e4e4e7", "300": "#d4d4d8",
        "400": "#a1a1aa", "500": "#71717a", "700": "#3f3f46", "900": "#18181b",
        "950": "#09090b"}
SHADOW = "0 1px 3px rgba(0,0,0,.07), 0 6px 16px rgba(0,0,0,.06)"
SHADOW_LG = "0 2px 6px rgba(0,0,0,.10), 0 12px 28px rgba(0,0,0,.10)"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"] * {{
    font-family: 'Inter', -apple-system, sans-serif;
}}
/* Streamlit's icons are a ligature font — the Inter override above would turn
   them into literal text like "keyboard_arrow_right", so restore their font. */
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded' !important;
}}
[data-testid="stAppViewContainer"] {{ background: #ffffff; }}
.block-container {{ padding-top: 2.5rem; max-width: 1200px; }}

h1 {{ font-weight: 700 !important; letter-spacing: -0.03em; font-size: 1.7rem !important; }}
h2, h3 {{ font-weight: 600 !important; letter-spacing: -0.02em; }}

/* card primitives */
.sc-card {{
    background: #fff; border: 1px solid {ZINC["200"]}; border-radius: 14px;
    padding: 1.15rem 1.35rem; box-shadow: {SHADOW};
}}
.sc-card-dark {{
    background: {ZINC["950"]}; border: 1px solid {ZINC["950"]}; border-radius: 14px;
    padding: 1.15rem 1.35rem; box-shadow: {SHADOW_LG};
}}
.sc-card-dark .sc-label {{ color: {ZINC["400"]}; }}
.sc-card-dark .sc-value {{ color: #fff; }}
.sc-card-dark .sc-sub {{ color: {ZINC["400"]}; }}

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
.sc-badge-solid   {{ background: {ZINC["950"]}; color: #fff; border: 1px solid {ZINC["950"]}; }}
.sc-badge-outline {{ background: #fff; color: {ZINC["700"]}; border: 1px solid {ZINC["300"]}; }}
.sc-badge-muted   {{ background: {ZINC["100"]}; color: {ZINC["700"]}; border: 1px solid {ZINC["200"]}; }}

/* streamlit widget restyling */
[data-testid="stMetric"], [data-testid="stExpander"] {{
    background: #fff; border: 1px solid {ZINC["200"]}; border-radius: 14px;
    box-shadow: {SHADOW};
}}
[data-testid="stDataFrame"] {{
    border: 1px solid {ZINC["200"]}; border-radius: 14px; box-shadow: {SHADOW};
}}
.stTabs [data-baseweb="tab-list"] {{
    gap: .25rem; background: {ZINC["100"]}; padding: .3rem; border-radius: 12px;
    width: fit-content;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 9px; padding: .35rem .95rem; font-weight: 500; font-size: .85rem;
    color: {ZINC["500"]};
}}
.stTabs [aria-selected="true"] {{
    background: #fff !important; box-shadow: 0 1px 3px rgba(0,0,0,.10);
    color: {ZINC["950"]} !important; font-weight: 600;
}}
.stDownloadButton button, .stButton button {{
    border-radius: 10px; border: 1px solid {ZINC["300"]}; font-weight: 500;
    box-shadow: 0 1px 2px rgba(0,0,0,.05);
}}
.stButton button[kind="primary"] {{
    background: {ZINC["950"]}; border-color: {ZINC["950"]}; color: #fff;
    box-shadow: {SHADOW};
}}
.stButton button[kind="primary"]:hover {{ background: {ZINC["700"]}; border-color: {ZINC["700"]}; }}
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


MONEY_DISCLAIMER = "Past performance, not a forecast. Excludes trading costs and taxes."


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


def money_card(label: str, dollar_edge: float, sub: str = "", dark: bool = False) -> str:
    """Hero-style card for a $ edge, with the same up/down arrow convention
    used everywhere else — arrows carry the meaning, not color."""
    arrow = "↗" if dollar_edge >= 0 else "↘"
    value = f"{arrow} {'+' if dollar_edge >= 0 else '-'}${abs(dollar_edge):,.0f}"
    return card(label, value, sub, dark=dark)


def _escape_dollar(text) -> str:
    """Streamlit's markdown renders bare $..$ as LaTeX math, and two of these
    HTML fragments landing in the same st.markdown call can get their $ signs
    paired up across fragments into one garbled formula. A backslash escape
    ('\\$') doesn't help — Streamlit shows the backslash literally instead of
    stripping it — so use the HTML entity instead: it decodes to '$' in the
    browser but contains no literal '$' for the math scanner to catch."""
    return str(text).replace("$", "&#36;")


def card(label: str, value: str, sub: str = "", dark: bool = False) -> str:
    label, value, sub = _escape_dollar(label), _escape_dollar(value), _escape_dollar(sub)
    sub_html = f'<div class="sc-sub">{sub}</div>' if sub else ""
    css_class = "sc-card-dark" if dark else "sc-card"
    return (f'<div class="{css_class}"><div class="sc-label">{label}</div>'
            f'<div class="sc-value">{value}</div>{sub_html}</div>')


def badge(text: str, tone: str = "muted") -> str:
    return f'<span class="sc-badge sc-badge-{tone}">{_escape_dollar(text)}</span>'


# ------------------------------------------------------------- run controls
def load_run_state() -> dict | None:
    if RUN_STATE_PATH.exists():
        return json.loads(RUN_STATE_PATH.read_text())
    return None


def run_is_alive(state: dict | None) -> bool:
    if not state:
        return False
    try:
        os.kill(state["pid"], 0)  # signal 0 = existence check only
        return True
    except (OSError, ProcessLookupError):
        return False


def run_controls_unlocked() -> bool:
    """Gate the run-launch and holdout-open controls behind a shared passcode.

    Local `streamlit run dashboard.py` has no ADMIN_PASSCODE secret configured,
    so it stays open (localhost, trusted use). Once deployed publicly (per
    README: share.streamlit.io), set ADMIN_PASSCODE in the app's secrets —
    every visitor without it is left read-only on the rest of the dashboard.
    """
    try:
        required_passcode = st.secrets.get("ADMIN_PASSCODE")
    except Exception:
        required_passcode = None
    if not required_passcode:
        return True
    if st.session_state.get("run_controls_unlocked"):
        return True
    entered = st.text_input("passcode to unlock run controls", type="password",
                            key="run_passcode_input")
    if entered:
        if entered == required_passcode:
            st.session_state["run_controls_unlocked"] = True
            st.rerun()
        else:
            st.error("wrong passcode")
    return False


def launch_run(iterations: int, budget_usd: float) -> dict:
    """Start the research loop as a detached background process; log to a file."""
    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = RUN_LOGS_DIR / f"run_{started_at}.log"
    with log_path.open("w") as log_file:
        process = subprocess.Popen(
            [sys.executable, "run_phase_c_loop.py",
             "--iterations", str(iterations), "--budget-usd", str(budget_usd)],
            cwd=PROJECT_ROOT, stdout=log_file, stderr=subprocess.STDOUT,
            start_new_session=True,  # survives the dashboard restarting
        )
    state = {"pid": process.pid, "started_at": started_at, "iterations": iterations,
             "budget_usd": budget_usd, "log_path": str(log_path.relative_to(PROJECT_ROOT))}
    RUN_STATE_PATH.write_text(json.dumps(state))
    return state


def tail_of_log(state: dict, lines: int = 25) -> str:
    log_file = PROJECT_ROOT / state["log_path"]
    if not log_file.exists():
        return "(no log yet)"
    content = [line for line in log_file.read_text().splitlines()
               if "FutureWarning" not in line and "pct_change" not in line]
    return "\n".join(content[-lines:]) or "(log is empty so far)"


# ------------------------------------------------------------------ header
st.title("Self-Improving Market Research Agent")
st.markdown(
    f'<p style="color:{ZINC["500"]}; margin-top:-0.6rem; font-size:.92rem;">'
    "AI proposes stock-picking signals. Each one is tested on historical data "
    "before it's trusted.</p>", unsafe_allow_html=True,
)

experiments = load_experiments()
if experiments.empty:
    st.info("The journal is empty — run an iteration first (Run tab, or `python3 run_phase_c_loop.py`)")

tested = experiments[experiments["status"] == "tested"] if not experiments.empty else pd.DataFrame()
total_cost = experiments["cost_usd"].dropna().sum() if not experiments.empty else 0.0
monetary_summary = load_monetary_summary(tested) if not tested.empty else pd.DataFrame()
best_money_row = (monetary_summary.loc[monetary_summary["dollar_edge"].idxmax()]
                  if not monetary_summary.empty else None)
holdout_verdicts = load_holdout_verdicts()
run_state = load_run_state()
run_alive = run_is_alive(run_state)

# Hero (dark) card = the headline number; the rest stay light. Only the
# external ($) metric appears here — internal research metrics live behind
# "technical details" in the Experiment detail tab and on the Metrics page.
overview = st.columns(4)
if best_money_row is not None:
    overview[0].markdown(money_card("Best signal", best_money_row["dollar_edge"],
                                    display_name(best_money_row["signal_name"]), dark=True),
                         unsafe_allow_html=True)
else:
    overview[0].markdown(card("Best signal", "—", "no tested signals yet", dark=True),
                         unsafe_allow_html=True)
overview[1].markdown(card("Experiments", str(len(experiments)),
                          ("running now" if run_alive else f"{len(tested)} tested")),
                     unsafe_allow_html=True)
overview[2].markdown(card("Research spend", f"${total_cost:.2f}", ""), unsafe_allow_html=True)
if holdout_verdicts.empty:
    overview[3].markdown(card("Gate 1", "sealed", "opens at the end of a run"),
                         unsafe_allow_html=True)
else:
    latest = holdout_verdicts.iloc[-1]
    gate_passed = bool(latest["gate1_passed"])
    gate_text = "PASSED ↗" if gate_passed else "FAILED ↘"
    overview[3].markdown(card("Gate 1", gate_text, display_name(latest["signal_name"])),
                         unsafe_allow_html=True)

st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.78rem; margin-top:.5rem;">{MONEY_DISCLAIMER}</p>',
            unsafe_allow_html=True)
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------- tabs
signals_tab, candidates_tab, detail_tab, agents_tab, holdout_tab, metrics_tab, run_tab = st.tabs(
    ["Signals", "Stock predictions", "Experiment detail", "Agent team",
     "Holdout verdicts", "Metrics", "▶ Run the researcher"]
)

with signals_tab:
    if monetary_summary.empty:
        st.write("No tested signals with enough out-of-sample data yet.")
    else:
        ranking = monetary_summary.sort_values("dollar_edge", ascending=False).reset_index(drop=True)
        chart_data = ranking.copy()
        chart_data["positive"] = chart_data["dollar_edge"] >= 0
        # Monochrome: positive bars near-black, negative bars light gray.
        score_chart = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("dollar_edge:Q", title="$ gained vs. the market"),
                y=alt.Y("display_name:N", sort="-x", title=None),
                color=alt.condition(alt.datum.positive,
                                    alt.value(ZINC["900"]), alt.value(ZINC["300"])),
                tooltip=["display_name", "dollar_edge", "pct_edge"],
            )
            .properties(height=60 + 42 * len(chart_data))
            .configure_view(strokeOpacity=0)
            .configure_axis(labelFont="Inter", titleFont="Inter", labelColor=ZINC["500"],
                            titleColor=ZINC["500"], gridColor=ZINC["100"], labelLimit=280)
        )
        st.altair_chart(score_chart, use_container_width=True)
        display_ranking = ranking[["display_name", "top5_final_balance", "universe_final_balance",
                                   "dollar_edge", "pct_edge"]].rename(columns={
            "display_name": "Signal",
            "top5_final_balance": "Top 5 picks",
            "universe_final_balance": "Market average",
            "dollar_edge": "$ gained",
            "pct_edge": "% gained",
        })
        st.dataframe(display_ranking, use_container_width=True, hide_index=True)
        st.caption(MONEY_DISCLAIMER)

with candidates_tab:
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
        st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.85rem;">As of {as_of_date} · '
                    f'based on {len(signals_used)} proven signal(s): {signal_badges}</p>',
                    unsafe_allow_html=True)

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

with detail_tab:
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
        st.markdown(f'<div class="sc-card">{experiment["hypothesis"]}</div>', unsafe_allow_html=True)

        if experiment["researcher_notes"]:
            st.markdown('<div class="sc-label" style="margin-top:.9rem">What we learned</div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div class="sc-card">{experiment["researcher_notes"]}</div>',
                        unsafe_allow_html=True)

        st.markdown('<div class="sc-label" style="margin-top:.9rem">The verdict</div>',
                    unsafe_allow_html=True)
        if metrics and "error" not in money_result:
            verdict_columns = st.columns(4)
            verdict_columns[0].markdown(card("Top 5 picks", f"${money_result['top5_final_balance']:,.0f}",
                                             "", dark=True), unsafe_allow_html=True)
            verdict_columns[1].markdown(card("Market average", f"${money_result['universe_final_balance']:,.0f}",
                                             ""), unsafe_allow_html=True)
            verdict_columns[2].markdown(money_card("Gained", money_result["dollar_edge"],
                                                    f"{money_result['pct_edge']:+.1f}%"), unsafe_allow_html=True)
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
            balance_chart = (
                alt.Chart(balances_long)
                .mark_line()
                .encode(
                    x=alt.X("period_start:N", title=None, sort=None),
                    y=alt.Y("balance:Q", title="account balance ($)", scale=alt.Scale(zero=False)),
                    color=alt.Color("series:N", title=None,
                                    scale=alt.Scale(range=[ZINC["900"], ZINC["300"]])),
                )
                .properties(height=220)
                .configure_view(strokeOpacity=0)
                .configure_axis(labelFont="Inter", titleFont="Inter", labelColor=ZINC["500"],
                                titleColor=ZINC["500"], gridColor=ZINC["100"], labelAngle=-40)
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
                                                     "same folds, RF + boosted trees"), unsafe_allow_html=True)

                per_industry = metrics.get("per_industry", {})
                if per_industry:
                    st.markdown('<div class="sc-label" style="margin-top:.9rem">Per-industry breakdown</div>',
                                unsafe_allow_html=True)
                    industry_columns = st.columns(len(per_industry))
                    for column, (industry, industry_metrics) in zip(industry_columns, per_industry.items()):
                        industry_score = industry_metrics.get("tested_score")
                        industry_ic = industry_metrics.get("ic_spearman")
                        arrow = "↗" if (industry_score or 0) > 0 else "↘"
                        column.markdown(card(industry,
                                             f"{arrow} {industry_score:+.4f}" if industry_score is not None else "—",
                                             f"IC {industry_ic:+.3f}" if industry_ic is not None else ""),
                                        unsafe_allow_html=True)
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

        st.markdown('<div class="sc-label" style="margin-top:.9rem">The code behind this signal</div>',
                    unsafe_allow_html=True)
        feature_code_file = PROJECT_ROOT / experiment["feature_code_path"]
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

with agents_tab:
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

with holdout_tab:
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

with metrics_tab:
    st.markdown('<div class="sc-label">The metric on this dashboard</div>', unsafe_allow_html=True)
    st.markdown(f"""
<div class="sc-card">
<strong>Top 5 picks vs. the market, on &#36;500.</strong>
<p style="margin-top:.5rem; line-height:1.6;">
&#36;500 in the model's top 5 picks, compared to &#36;500 spread across the market
it was picking from, over the same period. The difference is the number shown
here.
</p>
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

with run_tab:
    st.markdown('<div class="sc-label">Send the researcher on a run</div>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.85rem;">Proposes a signal, tests it, '
                "and records the result. Updates automatically while running.</p>", unsafe_allow_html=True)

    if not run_controls_unlocked():
        st.info("This deployment requires a passcode to launch runs or open the holdout "
                 "— read-only for everyone else. Enter it above to unlock.")
    else:
        control_columns = st.columns([1, 1, 2])
        run_iterations = control_columns[0].number_input("iterations", min_value=1, max_value=30,
                                                         value=1, disabled=run_alive)
        run_budget = control_columns[1].number_input("budget per iteration (USD)", min_value=0.5, max_value=10.0,
                                                     value=5.0, step=0.5, disabled=run_alive)
        estimated = run_iterations * 0.65
        control_columns[2].markdown(card("estimated cost", f"~${estimated:.2f}",
                                         f"hard cap ${run_iterations * run_budget:.0f} "
                                         f"(observed ≈ $0.55–0.65/iteration)"), unsafe_allow_html=True)

        if run_alive:
            st.markdown(badge("RESEARCHER RUNNING", "solid") + " " +
                        badge(f"pid {run_state['pid']} · started {run_state['started_at']}", "muted"),
                        unsafe_allow_html=True)
            st.code(tail_of_log(run_state), language=None)
            if st.button("Refresh status"):
                st.rerun()
        else:
            if st.button("▶ Send the researcher on a run", type="primary"):
                state = launch_run(int(run_iterations), float(run_budget))
                st.success(f"Run launched (pid {state['pid']}) — {run_iterations} iteration(s), "
                           f"&#36;{run_budget}/iteration cap. Watch progress here or in the Signals tab.")
                st.rerun()
            if run_state:  # a previous run exists but is finished
                with st.expander(f"last run's log ({run_state['started_at']})"):
                    st.code(tail_of_log(run_state, lines=60), language=None)

        st.markdown('<div class="sc-label" style="margin-top:1.2rem">Final verdict</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<p style="color:{ZINC["500"]}; font-size:.85rem;">Opens the sealed holdout '
                    "once, for the best signal. Manual and permanent — not part of a normal run.</p>",
                    unsafe_allow_html=True)
        acknowledge = st.checkbox("I understand the holdout opens once, at the true end of a run")
        if st.button("Open the holdout (Gate 1 verdict)", disabled=not acknowledge or run_alive):
            with st.spinner("Opening the holdout ..."):
                result = subprocess.run(
                    [sys.executable, "run_phase_c_loop.py", "--final-verdict"],
                    cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=600,
                )
            verdict_lines = [line for line in result.stdout.splitlines() if "VERDICT" in line or "holdout" in line]
            (st.success if result.returncode == 0 else st.error)("\n".join(verdict_lines) or result.stderr[-500:])
            load_holdout_verdicts.clear()
