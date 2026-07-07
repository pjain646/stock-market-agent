# Researcher session — iteration 10

<details><summary>thinking</summary>


</details>

- tool `Skill`: {"skill": "research-methodology"}

- tool `Bash`: {"command": "cd \"$(pwd)\" && ls && echo \"---\" && ls research-methodology/scripts 2>/dev/null && echo \"---\" && ls proposals 2>/dev/null", "description": "List repo structure"}

<details><summary>thinking</summary>


</details>

- tool `Read`: {"file_path": "/home/runner/work/stock-market-agent/stock-market-agent/research-methodology/scripts/data.py"}

<details><summary>thinking</summary>


</details>

- tool `Bash`: {"command": "python -c \"\nimport pandas as pd\np = pd.read_pickle('data_cache/panel.pkl')\nprint(p.shape)\nprint(p.columns.tolist())\nprint(p['date'].min(), p['date'].max())\nprint('n tickers', p['ticker'].nunique())\nprint(p.groupby('industry')['ticker'].nunique())\nprint(p['split'].value_counts())\nprint(sorted(p['ticker'].unique()))\n\"", "description": "Inspect panel"}

<details><summary>thinking</summary>


</details>

- tool `Bash`: {"command": "cd \"$(pwd)\" && python -c \"\nimport sys; sys.path.insert(0,'research-methodology/scripts')\nfrom data import fetch_insider_transactions\ntickers=['AAPL','JPM','LLY','BAC','PFE','GS','WFC','MRK','C','MS','GILD','ABBV']\ndf=fetch_insider_transactions(tickers, max_form4_filings_per_ticker=40)\nprint(df.shape)\nprint(df['transaction_code'].value_counts(dropna=False))\nprint(df['filing_d

<details><summary>thinking</summary>


</details>

- tool `Bash`: {"command": "cd \"$(pwd)\" && python -c \"\nimport sys; sys.path.insert(0,'research-methodology/scripts')\nfrom data import fetch_analyst_grades\ndf=fetch_analyst_grades(['AAPL','JPM','LLY','BAC','PFE','GS','NVDA','MSFT'])\nprint(df.shape)\nprint(df['date'].min(), df['date'].max())\nprint(df['action'].value_counts())\nprint(df.groupby('ticker')['date'].agg(['min','max','count']))\n\" 2>&1 | tail -

<details><summary>thinking</summary>


</details>

**researcher:** Insider data only covers ~2025-2026 (no overlap with the 2014-2024 panel), and analyst grades are rate-limited on the free tier — both infeasible for this panel. Let me pivot to a well-covered, genuinely orthogonal axis. Let me quickly confirm my reasoning about the reversal pattern I've observed.

- tool `Bash`: {"command": "cd \"$(pwd)\" && python -c \"\nimport pandas as pd, numpy as np\np=pd.read_pickle('data_cache/panel.pkl').sort_values(['ticker','date'])\n# past 21d return per ticker\np['past21']=p.groupby('ticker')['adj_close'].transform(lambda s: s/s.shift(21)-1)\np['past5']=p.groupby('ticker')['adj_close'].transform(lambda s: s/s.shift(5)-1)\ntr=p[p['split']=='train'].dropna(subset=['past21','labe

<details><summary>thinking</summary>


</details>

**researcher:** Clear monotonic reversal gradient on train: lowest past-21d-return quintile has 63.9% up-rate vs 57.6% for the highest — a 6.3pp spread, monotone across all buckets. This confirms short-term reversal in this universe (consistent with my iter 1-2 observation that continuation inverts here), it's orthogonal to my 8 fundamental/vol signals, and mom_12_1 deliberately *excluded* this last-month window. Let me build it.

- tool `Write`: {"file_path": "/home/runner/work/stock-market-agent/stock-market-agent/proposals/iteration_10/feature.py", "content": "\"\"\"Iteration 10 \u2014 short-term reversal.\n\nA genuinely non-fundamental, orthogonal axis to the eight quality/capital-discipline\nand momentum/vol signals tried so far. Insider (Form 4) and analyst-grade data were\nexplored first but are infeasible here: the bundled Form 4 f

- tool `Bash`: {"command": "cd \"$(pwd)\" && python -c \"\nimport pandas as pd, sys\nsys.path.insert(0,'proposals/iteration_10')\nfrom feature import add_feature, SIGNAL_NAME, HYPOTHESIS\np=pd.read_pickle('data_cache/panel.pkl')\nout,cols=add_feature(p.copy())\nprint('SIGNAL', SIGNAL_NAME)\nprint('new cols', cols)\nprint(out[cols].describe().T[['count','mean','std','min','max']].round(4))\nprint('nan frac')\npri

**researcher:** The module works correctly. All four features are populated (NaN fraction <1%, only from the initial 21-day warmup per ticker), values are in sensible ranges, and the reversal direction holds on the untouched validation split too (str_rev_1m vs label correlation +0.0285, same sign as train — oversold names more likely to rise).

## Summary

**Iteration 10 signal: `short_term_reversal`**

**Why this, this time.** My iter-9 note directed me to add a genuinely orthogonal *non-fundamental* axis (insider buying or a volatility/trend regime flag) since eight fundamental/vol signals had all clustered at GBM +0.03…+0.05. I explored the two suggested data sources first and found both infeasible for this panel:
- **Form 4 insider data** — the bundled fetcher only returns the last ~1 year of filings (2025-08 → 2026-07); zero overlap with the 2014-2024 panel.
- **Analyst grades** — FMP free tier 429s (rate-limited), and history is thin.

So I pivoted to price-based **short-term reversal**, which uses fully-covered, split-adjusted prices and is genuinely orthogonal to everything I've built.

**Economic rationale.** Over ~1-month horizons, sharp price moves largely reflect temporary liquidity demand/overreaction that mean-reverts as liquidity providers get compensated (Jegadeesh 1990, Lehmann 1990). Crucially, this is grounded in my *own* prior evidence: iterations 1–2 showed continuation signals (momentum, PEAD) systematically *invert* in this large-cap universe. mom_12_1 deliberately *excluded* the last month, so this window was never tested. A pre-check on train showed a clean monotone gradient (63.9% up-rate for the most-oversold quintile → 57.6% for the most-overbought), and the direction replicated on the untouched validation split.

**Features (4):** `str_rev_1m` (negated 21-day return), `str_rev_1w` (negated 5-day), `str_rev_1m_volnorm` (vol-normalized "stretch" — the overreaction magnitude relative to the stock's own volatility, which ties in the regime-conditioning idea), and `str_rev_1m_ind_rank` (within-industry cross-sectional rank). All point-in-time safe — every value uses only prices up to the row's own date. Handing off to the judge.

