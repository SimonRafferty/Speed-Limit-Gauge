"""Stage 1: time live Overpass queries (urban, suburban, rural).

Run: .venv/Scripts/python research/stage1/overpass_probe.py [--attempt N] [--areas a,b]

Each probe is APPENDED to results/stage1/overpass/probe.csv. A failed probe is
recorded (error column, seconds still filled) rather than aborting the script.
"""
import argparse
import csv
import time
from datetime import datetime, timezone

from slg.areas import AREAS
from slg.overpass import ENDPOINT, probe
from slg.paths import RESULTS

DEFAULT_AREAS = ("london_camden_islington", "horsham", "midhurst_downs")
COLUMNS = ["utc_time", "endpoint", "area", "attempt", "bytes", "seconds", "km",
           "ways", "bytes_per_km", "error"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--areas", default=",".join(DEFAULT_AREAS),
                    help="comma-separated area names")
    args = ap.parse_args()
    wanted = args.areas.split(",")

    out = RESULTS / "stage1" / "overpass"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "probe.csv"
    new_file = not path.exists()
    areas = [a for a in AREAS if a.name in wanted]
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new_file:
            w.writeheader()
        for i, area in enumerate(areas):
            if i:
                time.sleep(10)
            row = {"utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "endpoint": ENDPOINT, "area": area.name, "attempt": args.attempt}
            t0 = time.perf_counter()
            try:
                row.update(probe(area.bbox))
            except Exception as exc:  # record the failure as a finding
                row["seconds"] = round(time.perf_counter() - t0, 2)
                row["error"] = f"{type(exc).__name__}: {exc}"
            w.writerow(row)
            fh.flush()
            print(row)


if __name__ == "__main__":
    main()
