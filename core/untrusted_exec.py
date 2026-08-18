"""Guard rails around running researcher-written feature code.

feature.py is LLM-authored, partly from external data (SEC/FMP/FRED/Alpha
Vantage responses) the model reads while researching — so it's untrusted by
construction. `secrets_hidden()` hides live API credentials from os.environ
for the duration of any call into that code (module import and add_feature()
itself), so it can't read and exfiltrate them even if it tried.

Scoped to ANTHROPIC_API_KEY only. The data-source keys (FMP/FRED/Alpha
Vantage/Finnhub) authenticate the exact free-tier data access spec §6
explicitly grants feature code — stripping them didn't add real protection
(they're low-value, low-limit credentials) and it broke legitimate live
re-fetches a proven signal's feature code needs at candidate-ranking time
(e.g. proposals/iteration_37/feature.py calling fetch_macro_series). What
actually matters to keep out of reach is ANTHROPIC_API_KEY — misuse of that
one has real billing consequences.
"""
from __future__ import annotations

import contextlib
import os

SECRET_ENV_VARS = (
    "ANTHROPIC_API_KEY",
)


@contextlib.contextmanager
def secrets_hidden():
    saved_env = {key: os.environ.pop(key) for key in SECRET_ENV_VARS if key in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved_env)
