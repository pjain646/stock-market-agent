# Researcher session — iteration 2

<details><summary>thinking</summary>


</details>

**researcher:** I'll start by loading the research methodology skill, then explore the data.

- tool `Skill`: {"skill": "research-methodology"}

- tool `Bash`: {"command": "cd \"$(pwd)\" && ls && echo \"---\" && ls research-methodology/scripts/ 2>/dev/null && echo \"---panel---\" && python -c \"\nimport pandas as pd\np = pd.read_pickle('data_cache/panel.pkl')\nprint(p.shape)\nprint(p.columns.tolist())\nprint(p.head())\nprint(p['ticker'].nunique(), 'tickers')\nprint(p['ticker'].unique())\nprint(p['date'].min(), p['date'].max())\nprint(p['industry'].value_

<details><summary>thinking</summary>


</details>

- tool `Read`: {"file_path": "/home/runner/work/stock-market-agent/stock-market-agent/research-methodology/scripts/data.py"}

<details><summary>thinking</summary>


</details>

**researcher:** Now let me explore the earnings data, since I'm considering a post-earnings-announcement drift (PEAD) signal — orthogonal to the momentum I tried in iteration 1, with a strong, well-documented economic mechanism.

- tool `Bash`: {"command": "cd \"$(pwd)\" && python -c \"\nimport sys\nsys.path.insert(0, 'research-methodology/scripts')\nfrom data import fetch_earnings\nimport pandas as pd\npd.set_option('display.width', 200)\ntk = ['AAPL','JPM','LLY','NVDA','WFC','MS']\ne = fetch_earnings(tk)\nprint('shape', e.shape)\nprint(e.columns.tolist())\nfor t in tk:\n    sub = e[e.ticker==t]\n    print(t, 'rows', len(sub), 'date ran

<details><summary>thinking</summary>


</details>

**researcher:** Earnings data is available (EPS actual/estimated/surprise) with full history, and `date` is the announcement date. This supports a **post-earnings-announcement drift (PEAD)** signal — one of the most robust, well-documented anomalies, and cleanly orthogonal to the price momentum I tried last iteration. Let me build it.

- tool `Bash`: {"command": "cd \"$(pwd)\" && mkdir -p proposals/iteration_2"}

<details><summary>thinking</summary>


</details>

- tool `Write`: {"file_path": "/home/runner/work/stock-market-agent/stock-market-agent/proposals/iteration_2/feature.py", "content": "\"\"\"Iteration 2 signal: Post-Earnings-Announcement Drift (PEAD).\n\nEconomic rationale\n------------------\nWhen a company reports EPS that beats (or misses) the consensus estimate, its\nprice does NOT fully re-rate on the announcement day. Investors under-react to\nthe earnings 

- tool `Bash`: {"command": "cd \"$(pwd)\" && python -c \"\nimport pandas as pd, numpy as np\nimport importlib.util\nspec = importlib.util.spec_from_file_location('feat','proposals/iteration_2/feature.py')\nm = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\npanel = pd.read_pickle('data_cache/panel.pkl')\nprint('SIGNAL', m.SIGNAL_NAME)\nout, cols = m.add_feature(panel)\nprint('new cols', cols)\

<details><summary>thinking</summary>


</details>

**researcher:** Datetime unit mismatch. Let me normalize both to `datetime64[ns]`.

- tool `Edit`: {"replace_all": false, "file_path": "/home/runner/work/stock-market-agent/stock-market-agent/proposals/iteration_2/feature.py", "old_string": "    earnings = earnings.dropna(subset=[\"eps_surprise\", \"date\"]).copy()\n    earnings[\"date\"] = pd.to_datetime(earnings[\"date\"])", "new_string": "    earnings = earnings.dropna(subset=[\"eps_surprise\", \"date\"]).copy()\n    earnings[\"date\"] = pd.

- tool `Edit`: {"replace_all": false, "file_path": "/home/runner/work/stock-market-agent/stock-market-agent/proposals/iteration_2/feature.py", "old_string": "    panel = panel.copy()\n    panel[\"date\"] = pd.to_datetime(panel[\"date\"])", "new_string": "    panel = panel.copy()\n    panel[\"date\"] = pd.to_datetime(panel[\"date\"]).astype(\"datetime64[ns]\")"}

- tool `Bash`: {"command": "cd \"$(pwd)\" && python -c \"\nimport pandas as pd, numpy as np\nimport importlib.util\nspec = importlib.util.spec_from_file_location('feat','proposals/iteration_2/feature.py')\nm = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\npanel = pd.read_pickle('data_cache/panel.pkl')\nout, cols = m.add_feature(panel)\nprint('new cols', cols, '| shape', out.shape, 'orig', pa

<details><summary>thinking</summary>


</details>

**researcher:** The feature works and passes the smoke test. Summary of what I built:

## Iteration 2 signal: `pead_earnings_surprise` (Post-Earnings-Announcement Drift)

**Hypothesis / economic rationale:** Investors under-react to earnings surprises, so a stock keeps drifting in the direction of its most recent EPS surprise for weeks after the report (the classic PEAD anomaly, Bernard & Thomas 1989). A 21-trading-day horizon sits inside the documented drift window. This is a discrete *fundamental-event* catalyst — deliberately **orthogonal to the price momentum** I tried in iteration 1 (which the judge scored −0.016 on logistic, exhausted as a plain factor).

**Features (one family, shared rationale):**
- `pead_sue` — standardized unexpected earnings (surprise ÷ rolling std of the 8 *prior* surprises, winsorized to ±4), valid only while the last report is fresh (≤63 calendar days), else 0 = "no catalyst / neutral."
- `pead_sue_decayed` — same SUE weighted by `exp(−days_since / 21)`, so recent surprises dominate and the signal fades smoothly.

**Point-in-time discipline:**
- `merge_asof(..., direction="backward", allow_exact_matches=False)` attaches only reports announced *strictly before* the row's date — a report on day *t* isn't used until *t+1*, conservative regardless of pre-open/post-close timing.
- The SUE denominator uses `shift(1)` so it never includes the current report.
- No use of `label`/`forward_return`/`split`.

**Smoke test (train+val, no scoring):** returns both columns, fully populated (0 NaN, 66% rows carry a fresh surprise). Directionally correct — mean label is **0.593 for positive SUE vs 0.553 for negative SUE** (base rate 0.596), so positive surprises predict higher up-probability as the hypothesis requires. Coverage is balanced across splits (~65–69%).

I'm stopping here — the deterministic judge will score it and record the verdict for the next iteration.

