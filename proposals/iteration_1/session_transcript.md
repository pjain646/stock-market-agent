# Researcher session — iteration 1

<details><summary>thinking</summary>


</details>

**researcher:** I'll start by loading the research methodology skill to work under its discipline.

- tool `Skill`: {"skill": "research-methodology"}

<details><summary>thinking</summary>


</details>

**researcher:** Let me explore the data and the available fetchers.

- tool `Bash`: {"command": "ls && echo \"---PANEL---\" && python -c \"\nimport pandas as pd\np = pd.read_pickle('data_cache/panel.pkl')\nprint(p.shape)\nprint(p.dtypes)\nprint(p.head())\nprint('---')\nprint('date range', p['date'].min(), p['date'].max())\nprint('tickers', p['ticker'].nunique())\nprint('industries', p['industry'].nunique())\nprint('splits', p['split'].value_counts())\nprint('label mean', p['label

<details><summary>thinking</summary>


</details>

- tool `Bash`: {"command": "python -c \"\nimport pandas as pd\np = pd.read_pickle('data_cache/panel.pkl')\nprint('tickers:', sorted(p.ticker.unique()))\nprint('industries:', p.industry.unique())\nprint(p.groupby('ticker').size())\n\"\necho \"===DATA.PY===\"\nsed -n '1,80p' research-methodology/scripts/data.py"}

<details><summary>thinking</summary>


</details>

**researcher:** The panel is 24 large-cap liquid names across Tech/Financials/Pharma, 2014–2024, daily. Label = up over next 21 trading days. This is a clean setup for a price-based cross-sectional signal. Let me verify I have enough price history in-panel to build momentum without fetching.

- tool `Bash`: {"command": "python -c \"\nimport pandas as pd\np = pd.read_pickle('data_cache/panel.pkl')\n# per ticker trading days, check monotonic dates\ng = p.sort_values(['ticker','date'])\nprint('rows per ticker:', p.groupby('ticker').size().min(), p.groupby('ticker').size().max())\n# ~2767 days over 11y -> plenty for 252-day lookback\n# check split composition over time\nprint(p.groupby(['split'])['date']

<details><summary>thinking</summary>


</details>

**researcher:** Splits are chronological (train → validation → holdout), so this is a genuine time-based out-of-sample design. Each ticker has full daily history, so a 252-day lookback is available point-in-time.

**My hypothesis for iteration 1: 12-1 month momentum.** This is the single best-documented cross-sectional return predictor, with a clear economic mechanism — gradual diffusion of information and investor underreaction cause past medium-term winners to keep outperforming over the next month. I skip the most recent 21 days to avoid contaminating it with the well-known 1-month reversal effect. I'll provide the raw momentum plus a cross-sectional rank (comparable across dates/regimes) as one signal family.

- tool `Write`: {"file_path": "/home/runner/work/stock-market-agent/stock-market-agent/proposals/iteration_1/feature.py", "content": "\"\"\"Iteration 1 signal: 12-1 month cross-sectional price momentum.\n\nEconomic rationale\n------------------\nMedium-term momentum (Jegadeesh & Titman 1993) is the most robustly documented\ncross-sectional return predictor. Its mechanism is behavioral: information\ndiffuses gradu

**researcher:** Now let me smoke-test the module against the panel.

- tool `Bash`: {"command": "python -c \"\nimport pandas as pd, importlib.util\nspec = importlib.util.spec_from_file_location('feat','proposals/iteration_1/feature.py')\nm = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\np = pd.read_pickle('data_cache/panel.pkl')\nout, cols = m.add_feature(p)\nprint('SIGNAL_NAME', m.SIGNAL_NAME)\nprint('new cols:', cols)\nprint('shape in/out:', p.shape, out.sh

<details><summary>thinking</summary>


</details>

**researcher:** Smoke test passes. Summary of iteration 1:

**Signal: `mom_12_1` — 12-1 month cross-sectional price momentum** (two columns: raw `mom_12_1` and its within-date cross-sectional rank `mom_12_1_xs_rank`).

**Verification:**
- ✅ Contract satisfied: `SIGNAL_NAME`, `HYPOTHESIS`, `add_feature(panel) → (df, [cols])`.
- ✅ Columns populated — 60,360 / 66,408 rows (90.9%). The ~9% NaN are exactly the first 252 trading days per ticker, where lookback history doesn't yet exist. Not fabricated/filled — left as genuine unknowns.
- ✅ **Point-in-time safe**: the window is `price[t-21] / price[t-252] - 1` — it ends 21 trading days *before* the current bar, so it cannot see the current price or the forward return. Manual per-ticker check reproduced the value exactly. The cross-sectional rank uses only same-date values.
- ✅ Uses only `adj_close` (split/dividend-adjusted) — never touched `label`, `forward_return`, or `split` to build the feature.

**Honest read on strength:** raw train correlation with label is ~0.001 (rank ~0.011) — modest, as expected for a single behavioral anomaly on a small 24-name large-cap universe. Critically, it is *not* suspiciously high, which is the reassuring sign there's no lookahead leak. Whether this clears a real significance bar is for the deterministic judge to decide — I do not score it myself.

**Design choices worth noting for the next iteration:**
- Deliberately skipped the most recent 21 days to avoid contaminating momentum with the opposite short-term-reversal effect.
- The 21-day skip aligns with the 21-day forward label horizon.
- If the judge flags this as a plain momentum-factor proxy (likely overlap with a momentum factor in any regression), the next iteration should pivot to something more orthogonal — e.g. a fundamentals-based or reversal/volatility signal — rather than re-tuning momentum windows.

The proposal is complete and stops here per the hard boundaries.

