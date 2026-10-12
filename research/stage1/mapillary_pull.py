"""Stage 1: Mapillary speed signs per area and agreement with OSM.

Run: .venv/Scripts/python research/stage1/mapillary_pull.py
Needs MAPILLARY_TOKEN in .env; exits cleanly without it.

Signs are snapped (within 20 m) to public-road ways only: service and track ways
are excluded from the snap set because speed signs belong to public roads and a
sign beside a road must not be matched to a nearby driveway or track.
"""
import pandas as pd
from shapely import wkt as shapely_wkt
from shapely.geometry import Point

from slg.agreement import compare, snap_to_ways, to_bng
from slg.areas import AREAS
from slg.coverage import annotate
from slg.mapillary import fetch_features, sign_mph, token
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "mapillary"
EXCLUDED_HIGHWAYS = ("service", "track")
SNAP_M = 20


def main():
    tok = token()
    if not tok:
        print("No MAPILLARY_TOKEN in .env - skipping.")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    summary, raw_counts, disagreements = [], [], []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            continue
        feats, failed_cells = fetch_features(area.bbox, tok)
        raw_counts += [{"area": area.name, "object_value": f["object_value"]} for f in feats]
        signs = [(f, sign_mph(f["object_value"])) for f in feats]
        signs = [(f, mph) for f, mph in signs if mph is not None]
        all_ways = annotate(pd.read_parquet(cache))
        excluded = all_ways["highway"].isin(EXCLUDED_HIGHWAYS)
        ways = all_ways[~excluded].reset_index(drop=True)
        lines = [to_bng(shapely_wkt.loads(w)) for w in ways["wkt"]]
        pts = [to_bng(Point(*f["geometry"]["coordinates"])) for f, _ in signs]
        pairs = snap_to_ways(pts, lines, max_m=SNAP_M)
        rows = []
        for si, wi, d in pairs:
            w = ways.iloc[wi]
            osm_mph = None if pd.isna(w["ms_mph"]) else int(w["ms_mph"])
            rows.append({"osm_kind": w["ms_kind"], "osm_mph": osm_mph, "src_mph": signs[si][1]})
            if osm_mph is not None and osm_mph != signs[si][1]:
                disagreements.append({"area": area.name, "way_id": int(w["way_id"]),
                                      "osm": w["maxspeed"], "sign_mph": signs[si][1],
                                      "dist_m": d, "feature_id": signs[si][0]["id"],
                                      "last_seen": signs[si][0].get("last_seen_at")})
        summary.append({"area": area.name, "failed_cells": failed_cells,
                        "ways_excluded_service_track": int(excluded.sum()),
                        "speed_features": len(feats), "max_speed_signs": len(signs),
                        "snapped": len(pairs), **compare(rows)})
        print(summary[-1])
    pd.DataFrame(summary).to_csv(OUT / "agreement_by_area.csv", index=False)
    pd.DataFrame(raw_counts).value_counts().to_csv(OUT / "object_value_counts.csv")
    pd.DataFrame(disagreements).to_csv(OUT / "disagreements.csv", index=False)


if __name__ == "__main__":
    main()
