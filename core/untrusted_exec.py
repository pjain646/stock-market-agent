"""Guard rails around running researcher-written feature code.

feature.py is LLM-authored, partly from external data (SEC/FMP/FRED/Alpha
Vantage responses) the model reads while researching — so it's untrusted by
construction. `secrets_hidden()` hides live API credentials from os.environ
for the duration of any call into that code (module import and add_feature()
itself), so it can't read and exfiltrate them even if it tried.
"""
from __future__ import annotations

import contextlib
import os

SECRET_ENV_VARS = (
    "ANTHROPIC_API_KEY", "FMP_API_KEY", "FRED_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
)


@contextlib.contextmanager
def secrets_hidden():
    saved_env = {key: os.environ.pop(key) for key in SECRET_ENV_VARS if key in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved_env)
