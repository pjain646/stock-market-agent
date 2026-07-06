
import pandas as pd

SIGNAL_NAME = "dryrun_momentum_21d"
HYPOTHESIS = "Dry-run plumbing test: 21d momentum as a placeholder signal."

def add_feature(panel):
    frames = []
    for _t, g in panel.sort_values("date").groupby("ticker", sort=False):
        g = g.copy()
        g["dryrun_momentum_21d"] = g["adj_close"].pct_change(21)
        frames.append(g)
    out = pd.concat(frames).reset_index(drop=True)
    return out, ["dryrun_momentum_21d"]
