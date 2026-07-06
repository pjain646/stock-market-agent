# Researcher session — iteration 2

<details><summary>thinking</summary>


</details>

**researcher:** I'll start by loading the research methodology skill, then explore the data.

- tool `Skill`: {"skill": "research-methodology"}

- tool `Bash`: {"command": "cd \"$(ls -d */ 2>/dev/null | grep -i research 2>/dev/null || echo .)\"; find . -maxdepth 3 -name panel.pkl 2>/dev/null; echo \"---\"; ls proposals/ 2>/dev/null; echo \"---scripts---\"; find . -path ./node_modules -prune -o -name data.py -print 2>/dev/null | head"}

<details><summary>thinking</summary>


</details>

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; find . -name panel.pkl 2>/dev/null; echo \"---prop---\"; ls -R proposals 2>/dev/null | head -40; echo \"---data.py loc---\"; find . -name data.py 2>/dev/null | grep -v node_modules"}

**researcher:** Let me explore the panel and the data fetchers.

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; python3 -c \"\nimport pandas as pd\np=pd.read_pickle('data_cache/panel.pkl')\nprint(p.shape)\nprint(p.dtypes)\nprint(p['date'].min(), p['date'].max())\nprint('tickers', p['ticker'].nunique())\nprint(p['split'].value_counts())\nprint('industries', p['industry'].nunique())\nprint(p.head())\nprint('label rate', p['label'].mean())\n\"

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; sed -n '1,60p' research-methodology/scripts/data.py | grep -n \"def \\|return\\|columns\" | head -50"}

<details><summary>thinking</summary>


</details>

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; grep -n \"^def \\|-> pd\" research-methodology/scripts/data.py"}

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; python3 -c \"\nimport pandas as pd\np=pd.read_pickle('data_cache/panel.pkl')\nprint(sorted(p['ticker'].unique()))\nprint(p.groupby('industry')['ticker'].nunique())\n\""}

<details><summary>thinking</summary>


</details>

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; sed -n '362,560p' research-methodology/scripts/data.py"}

<details><summary>thinking</summary>


</details>

**researcher:** Let me test the analyst grades fetcher for coverage over our panel window.

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; timeout 280 python3 -c \"\nimport sys; sys.path.insert(0,'research-methodology/scripts')\nfrom data import fetch_analyst_grades\nimport pandas as pd\ntks=['AAPL','ABBV','AMGN','AMZN','AVGO','AXP','BAC','BMY','C','CRM','GILD','GOOGL','GS','JNJ','JPM','LLY','META','MRK','MS','MSFT','NVDA','PFE','SCHW','WFC']\ng=fetch_analyst_grades(

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; python3 -c \"\nimport sys; sys.path.insert(0,'research-methodology/scripts')\nfrom data import fetch_analyst_grades\nimport pandas as pd\ntks=['AAPL','ABBV','AMGN','AMZN','AVGO','AXP','BAC','BMY','C','CRM','GILD','GOOGL','GS','JNJ','JPM','LLY','META','MRK','MS','MSFT','NVDA','PFE','SCHW','WFC']\ng=fetch_analyst_grades(tks)\nprint(

<details><summary>thinking</summary>


</details>

**researcher:** Grades endpoint is paywalled. Let me test earnings (PEAD has strong economic rationale and an Alpha Vantage fallback).

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; python3 -c \"\nimport sys; sys.path.insert(0,'research-methodology/scripts')\nfrom data import fetch_earnings\nimport pandas as pd\ntks=['AAPL','ABBV','AMGN','AMZN','AVGO','AXP','BAC','BMY','C','CRM','GILD','GOOGL','GS','JNJ','JPM','LLY','META','MRK','MS','MSFT','NVDA','PFE','SCHW','WFC']\ne=fetch_earnings(tks)\nprint(e.shape)\npr

<details><summary>thinking</summary>


</details>

**researcher:** Earnings data covers all 24 tickers well. I'll build a **PEAD (post-earnings-announcement drift)** signal — a well-documented anomaly with a clear mechanism distinct from my prior price-only signals. Let me write it.

- tool `Write`: {"file_path": "~/stock-research-agent/proposals/iteration_2/feature.py", "content": "\"\"\"Iteration 2 signal: post-earnings-announcement drift (PEAD).\n\nEconomic mechanism: investors systematically UNDER-react to earnings news.\nAfter a positive earnings surprise, prices drift up (and after a negative\nsurprise, drift down) for several weeks as the information is slowly a

- tool `Bash`: {"command": "cd \"~/stock-research-agent\"; python3 -c \"\nimport pandas as pd, sys\nsys.path.insert(0,'proposals/iteration_2')\nfrom feature import add_feature, SIGNAL_NAME\np=pd.read_pickle('data_cache/panel.pkl')\nout,cols=add_feature(p)\nprint('cols',cols, 'shape',out.shape)\ns=out[cols[0]]\nprint('nonzero frac', (s!=0).mean(), 'nan', s.isna().sum())\nprint(s.describe()

<details><summary>thinking</summary>


</details>

**researcher:** The feature works correctly. Smoke test passes:

- **Column populated:** `pead_sue_decayed`, no NaNs, 95% of rows nonzero (the ~5% zeros are early history before 4 prior surprises exist to standardize).
- **Directional sanity (train only):** a mild but monotone gradient across SUE quintiles (up-rate 0.594 → 0.601 → 0.601 → 0.611 → 0.610), consistent with the PEAD mechanism — higher standardized surprise → higher next-21-day up-rate.

## Summary

**Signal proposed:** `pead_sue_decayed` — post-earnings-announcement drift.

**Economic rationale:** Investors under-react to earnings news, so prices keep drifting in the direction of the latest earnings surprise for roughly a quarter. I measure this as a **standardized unexpected earnings (SUE)** score — the most recent EPS surprise scaled by the stock's *own trailing volatility of surprises* — then linearly decay it over a 90-day drift window.

**Why this is a fresh bet:** Iterations 0 (momentum) and 1 (mean-reversion) both mined price paths and failed. This uses an orthogonal, fundamental information source (earnings surprises via `fetch_earnings`), which is the classic driver of the PEAD anomaly.

**Point-in-time discipline:**
- SUE normalization uses only *prior* surprises (`shift(1).expanding`) — no lookahead in the scaling.
- `merge_asof` with `allow_exact_matches=False` attaches only announcements *strictly before* each row's date, so a same-day announcement (typically released after close) isn't treated as actionable until the next open.
- SUE clipped to ±8 to blunt single-print outliers.

I've written `proposals/iteration_2/feature.py` and confirmed it returns the new column, populated. Per the boundaries, I'm not scoring it — leaving the verdict to the deterministic judge.

