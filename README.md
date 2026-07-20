# Self-Improving Market Research Agent

An AI agent that works like an automated quant researcher. **Claude Opus proposes
market signals and writes the code to compute them; a deterministic statistical
judge scores them honestly out-of-sample; a journal remembers everything** — so
each iteration builds on the last. The LLM researches; it never predicts and it
never grades its own work.

## How the loop works

```
┌─────────────┐   reads    ┌──────────┐
│   JOURNAL   │──────────▶ │RESEARCHER│  Claude Opus, governed by the
│  (sqlite)   │            │  (LLM)   │  research-methodology skill
└─────────────┘            └────┬─────┘
      ▲                         │ writes a BUNDLE of 2-3 orthogonal
      │ verdict +               │ factors as point-in-time feature code
      │ reflection              │ (proposals/iteration_N/), scored together
      │                    ┌────▼─────┐ as one combined model
      └────────────────────│  JUDGE   │  fixed models (LR + RF + boosted trees),
                           │ (Python) │  purged walk-forward, scored vs base rate;
                           └──────────┘  the LLM cannot influence the score
```

At the end of a research run, a sealed **holdout** (the newest 20% of history)
opens exactly once. If the best signal still beats the base rate there, it
passes **Gate 1**.

**Why bundles, not single signals:** the first campaign's best single signal
(validation +0.0521) failed Gate 1 on the sealed holdout (-0.0118). Picking
the best of N single-signal tries is a noisy max-order-statistic — it finds
validation-split artifacts, not real edges. Testing 2-3 deliberately
orthogonal factors together as one model each iteration is the fix; the
universe was also expanded from 24 to ~166 liquid names across 11 sectors to
raise the effective sample size behind every score.

## Repo map

| Path | What it is |
|---|---|
| `run_phase_c_loop.py` | **The main entry point** — the research loop orchestrator (the only file that knows the Claude Agent SDK exists) |
| `dashboard.py` | Streamlit dashboard: signals, predictions, experiment detail, holdout verdicts, run controls, glossary |
| `core/` | Domain core, harness-independent: labeling, splits, purged evaluator, feature pipeline, journal |
| `research-methodology/` | The Claude skill governing the researcher, with the bundled point-in-time data fetchers (`scripts/data.py`: SEC EDGAR, FMP, Alpha Vantage, FRED, Form 4) |
| `proposals/` | One folder per iteration: the researcher's `feature.py`, session transcript, and the exact out-of-sample rows behind its score |
| `journal.db` | The journal (SQLite): every hypothesis, verdict, reflection, cost |
| `run_phase_a_demo.py` | No-LLM smoke test of the whole data layer: fetch → features → label → split → score |
| `.github/workflows/research-run.yml` | Remote research runs via GitHub Actions ("Run workflow" button) |

## Setup — get your own bot running

### 1. Install

```bash
git clone <this repo> && cd <repo>
pip install -r requirements.txt
```

You also need [Claude Code](https://claude.com/claude-code) installed and logged
in — the research loop drives it through the Claude Agent SDK, and local runs
bill your Claude plan (observed ≈ $0.55–0.65 per research iteration).

### 2. Data keys

The fetchers use free tiers. SEC EDGAR (fundamentals, insider Form 4) and
yfinance (prices) need **no key**. Get the other three (each takes ~2 minutes):

| Key | Used for | Where to get it |
|---|---|---|
| `FMP_API_KEY` | earnings surprises, analyst estimates/grades | financialmodelingprep.com (free, 250 calls/day) |
| `ALPHA_VANTAGE_API_KEY` | earnings fallback for tickers FMP's free tier blocks | alphavantage.co/support/#api-key (free, 25 calls/day) |
| `FRED_API_KEY` | macro series (rates, CPI, VIX...) | fred.stlouisfed.org → API key (free) |
| `SEC_CONTACT_EMAIL` | SEC EDGAR requires a contact email in the User-Agent (their fair-access policy) | your own email — no signup |

Put them in a `keys.local.json` at the repo root (gitignored — **never commit keys**):

```json
{"FMP_API_KEY": "...", "ALPHA_VANTAGE_API_KEY": "...", "FRED_API_KEY": "...",
 "SEC_CONTACT_EMAIL": "you@example.com"}
```

Environment variables with the same names also work. All responses are cached to
disk (`~/.cache/stock_research_*`), so re-runs cost zero API calls — the low
daily limits are fine in practice.

### 3. Verify the data layer (no LLM, free)

```bash
python3 run_phase_a_demo.py
```

Fetches everything, builds features, and scores them out-of-sample. If this
prints a metrics dict at the end, your data layer works.

### 4. Research

```bash
# watch the research
streamlit run dashboard.py

# send the researcher on a run (n iterations, hard $ cap per iteration)
python3 run_phase_c_loop.py --iterations 5 --budget-usd 5

# end of a research run: open the sealed holdout ONCE for the Gate 1 verdict
python3 run_phase_c_loop.py --final-verdict

# after local runs: publish results to the deployed dashboard
python3 run_phase_c_loop.py --iterations 5 --push
```

### 5. Deploy (optional)

- **Dashboard:** push this repo to GitHub → share.streamlit.io → New app →
  main file `dashboard.py`. Every push redeploys, so `--push` after a run
  updates the public dashboard.
- **Remote runs:** add repo secrets (Settings → Secrets → Actions):
  `ANTHROPIC_API_KEY` (required — CI can't use a Claude login, so remote runs
  bill API credits) plus the three data keys above. Then the Actions tab has a
  "research run" workflow you can fire from any browser or the GitHub mobile app;
  results push back and the dashboard refreshes.

## Recommended workflow (not in the repo, learned the hard way)

This repo is deliberately **only** functional code. Two working documents made
this project manageable and are strongly recommended — keep them *outside* the
repo (gitignored here):

- **A spec** (`market-research-agent-spec.md` locally): the source of truth for
  goals, constraints, and non-negotiables (the honesty rules started there).
  When a decision changes, change the spec — it's what keeps an agent-built
  project from drifting.
- **A scratchpad** (`scratchpad.md` locally): a running build log where every
  entry records *what* was decided and *why*. Sessions end and context is lost;
  the scratchpad is how the next session (or a future you) reconstructs the
  reasoning instead of re-deriving it.

## Honesty rules (non-negotiable, enforced in code)

- **Point-in-time everywhere:** fundamentals count from their SEC *filing* date;
  earnings from the report date; insider trades from the Form 4 filing date.
- **Out-of-sample only:** walk-forward evaluation with a 21-day purge gap so no
  training label overlaps the test window.
- **The holdout opens once**, and the code refuses to open it casually.
- **A weak result honestly reported is a success.** A huge score is treated as
  a probable leak, not a win.

**Current caveat:** the universe is 24 large caps that exist *today* —
survivorship bias makes every backtest here optimistic until a delisted-inclusive
universe is added. Results are research signals, not investment advice.

## Future ideas

**V2 — better research, better data**
- **Candidate combiner** (in progress): merge every proven signal into one
  learned-weight model → ranked per-stock P(up) in the "Stock predictions" tab.
- **Survivorship-free universe:** add delisted companies so backtests stop
  flattering themselves (the single biggest honesty upgrade; likely paid data).
- **More base-model-blind data:** FINRA short interest, 13F institutional
  holdings, timestamped news — data an LLM can't know from pretraining.
- **Live sentiment confirmation:** once the agent has a data-driven thesis,
  check credibility-weighted public sentiment (X/Reddit) as a forward-only
  confirmation layer — never backtested (no honest historical timestamps).
- **Chat interface:** ask the quant questions ("why is JPM ranked #2?") instead
  of reading the dashboard.

**V3 — from direction to trades**
- **Stage 2 — magnitude:** predict how *much* a stock moves, not just direction
  (gated on Gate 1 passing consistently).
- **Stage 3 — options:** translate direction + magnitude + volatility into
  option structures (gated on Stage 2).
- **Scale:** 500+ tickers, deeper per-industry models.
- **Own orchestration:** replace the Claude Agent SDK shell with a hand-built
  agent loop on the raw API (the clean seam in `run_phase_c_loop.py` exists for
  exactly this swap).
