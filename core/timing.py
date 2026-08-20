"""Wall-clock phase timing, printed to stdout only — added to diagnose where
a daily pipeline run's wall-clock time actually goes (network fetches vs. the
LLM call vs. price downloads), not surfaced anywhere in the UI.

Only meaningful with unbuffered stdout (see PYTHONUNBUFFERED in
.github/workflows/daily-candidates.yml) — otherwise Python block-buffers
print() when it isn't attached to a TTY, and lines can land in a GitHub
Actions log wildly out of true chronological order.
"""
from __future__ import annotations

import contextlib
import time


@contextlib.contextmanager
def timed(label: str):
    start = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] starting: {label}", flush=True)
    try:
        yield
    finally:
        elapsed = time.time() - start
        print(f"[{time.strftime('%H:%M:%S')}] finished: {label} ({elapsed:.1f}s)", flush=True)
