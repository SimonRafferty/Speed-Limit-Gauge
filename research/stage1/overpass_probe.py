"""Stage 1: time three live Overpass queries (urban, suburban, rural).

Run: .venv/Scripts/python research/stage1/overpass_probe.py

A failed probe is recorded in probe.csv (error column) rather than aborting.
"""
import time

import pandas as pd

from slg.areas import AREAS
from slg.overpass import probe
from slg.paths import RESULTS

PROBE_AREAS = ("london_camden_islington", "horsham", "midhurst_downs")


def main():
    out = RESULTS / "stage1" / "overpass"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, area in enumerate(a for a in AREAS if a.name in PROBE_AREAS):
        if i:
            time.sleep(10)
        try:
            res = probe(area.bbox)
        except Exception as exc:  # record the failure as a finding
            res = {"error": f"{type(exc).__name__}: {exc}"}
        res["area"] = area.name
        rows.append(res)
        print(res)
    pd.DataFrame(rows).to_csv(out / "probe.csv", index=False)


if __name__ == "__main__":
    main()
