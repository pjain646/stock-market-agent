# Trade-offs

Decisions made for practical reasons, with a real cost accepted knowingly. Not a full design log — just the calls worth remembering *why* we made.

## Price cache: parquet over pickle (2026-08-18)

We use the pickle data type for the research panel cache (`data_cache/panel.pkl`) because it's only ever saved and read on the same local machine — you just want the fastest data type, and pickle is fast.

But we use the parquet data type for the live price cache (`candidates/price_cache.parquet`) because we need a data type that can be easily read and understood across many different versions. This is because this cache gets uploaded to GitHub and read every day as part of the workflow — so if a different version of pandas (or anything else) comes along, it can still easily read the cache without struggling, the way pickle would.
