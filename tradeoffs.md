# Trade-offs

Decisions made for practical reasons, with a real cost accepted knowingly. Not a full design log — just the calls worth remembering *why* we made.

## Caching

Three places we've added caching so far, so we stop re-downloading data every day that we already have:

1. **Prices** (`candidates/price_cache.parquet`) — instead of re-fetching 12 years of price history for 169 tickers every day, we only grab what's new since the last run. Since prices can get quietly revised (dividends/splits), we also do a full refetch every other Monday to catch up on anything that changed.
2. **Insider transactions** (`candidates/insider_transactions_cache.parquet`) — instead of re-downloading and re-parsing every Form 4 filing every day, we only fetch filings we haven't seen before (tracked by each filing's unique ID). No periodic refresh needed here, because filings never change once they're filed.
3. **Fundamentals** (`candidates/fundamentals_cache.parquet`) — instead of re-pulling every ticker's full financial history every day, we serve it from cache and only refetch a ticker every other Monday (same cadence as prices). Companies only file new numbers ~4 times a year (quarterly), so checking every 2 weeks is already far more often than needed, not less.

## Price cache: parquet over pickle (2026-08-18)

We use the pickle data type for the research panel cache (`data_cache/panel.pkl`) because it's only ever saved and read on the same local machine — you just want the fastest data type, and pickle is fast.

But we use the parquet data type for the live price cache (`candidates/price_cache.parquet`) because we need a data type that can be easily read and understood across many different versions. This is because this cache gets uploaded to GitHub and read every day as part of the workflow — so if a different version of pandas (or anything else) comes along, it can still easily read the cache without struggling, the way pickle would.
