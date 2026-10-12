"""Stage 1 Task 13: agreement of two openly downloadable samples with OSM.

Run: .venv/Scripts/python research/stage1/source_samples.py

1. wales_20mph - DataMapWales `geonode:_30mph_roads_in_wales` (OGL v3, WFS). Buffered
   polygons of roads that stay at 30 mph under the Welsh default-20 regime (exceptions
   + existing 30 mph orders). Expected data:
       data/stage1/wales_20mph/<area>_30mph.geojson  (WFS GetFeature, EPSG:4326, area bbox)
   A way whose midpoint lies inside a polygon is assigned 30 mph
   (slg.agreement.match_orders_to_ways), then scored with slg.agreement.compare.
   Ways tagged highway=service/track are excluded, as in the D-TRO comparison.

2. rights_of_way - West Sussex public rights of way via rowmaps.com GeoJSON (OGL v3):
       data/stage1/rights_of_way/WS/mutated{1..4}.json  (Fo, Br, RB, BOAT)
   Not a speed source, so compare() does not apply. Instead each OSM way (drivable +
   track; the cache holds no path/bridleway ways) that has >= 50 % of its length
   within 10 m of a PROW line is given that PROW's status (the most restrictive if
   several), and we cross-tabulate it against OSM's designation and the red/yellow-X
   legality class from slg.access.motor_legality. Also: share of RB/BOAT length lying
   within 10 m of any cached OSM way.
"""
import json

import pandas as pd
import shapely
from shapely.geometry import shape

from slg.access import motor_legality
from slg.agreement import compare, match_orders_to_ways, to_bng
from slg.areas import AREAS
from slg.coverage import annotate
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "sources"
EXCLUDED_HIGHWAYS = ("service", "track")
# Lower code = more restrictive for motor vehicles (match_orders_to_ways keeps the minimum).
PROW_CODE = {"Fo": 1, "Br": 2, "Re": 3, "BO": 4}
PROW_NAME = {1: "footpath", 2: "bridleway", 3: "restricted_byway", 4: "boat"}
WS_AREAS = ("crawley", "horsham", "midhurst_downs", "m23_a23_crawley_brighton",
            "a27_chichester_worthing")


def load_ways(area: str) -> pd.DataFrame:
    return annotate(pd.read_parquet(DATA / "stage1" / f"{area}_ways.parquet"))


def wales_30mph() -> None:
    rows_out = []
    for area in ("cardiff", "powys_rural"):
        src = DATA / "stage1" / "wales_20mph" / f"{area}_30mph.geojson"
        feats = json.loads(src.read_text(encoding="utf-8"))["features"]
        polys = [to_bng(shape(f["geometry"])) for f in feats]
        all_ways = load_ways(area)
        excluded = all_ways["highway"].isin(EXCLUDED_HIGHWAYS)
        ways = all_ways[~excluded].reset_index(drop=True)
        lines = [to_bng(shapely.from_wkt(w)) for w in ways["wkt"]]
        best = match_orders_to_ways(lines, polys, [30] * len(polys))
        rows = []
        for wi, mph in best.items():
            w = ways.iloc[wi]
            osm_mph = None if pd.isna(w["ms_mph"]) else int(w["ms_mph"])
            rows.append({"osm_kind": w["ms_kind"], "osm_mph": osm_mph, "src_mph": mph})
        rows_out.append({"area": area, "src_polygons": len(polys),
                         "osm_ways": len(ways), "excluded_ways": int(excluded.sum()),
                         **compare(rows)})
        print(rows_out[-1])
    pd.DataFrame(rows_out).to_csv(OUT / "wales_20mph_agreement.csv", index=False)


def west_sussex_prow() -> None:
    lines, codes = [], []
    for i in range(1, 5):
        fc = json.loads((DATA / "stage1" / "rights_of_way" / "WS" / f"mutated{i}.json")
                        .read_text(encoding="utf-8"))
        for f in fc["features"]:
            code = PROW_CODE.get(f["properties"]["Description"].split("|", 1)[0])
            if code is None or f["geometry"] is None:
                continue
            lines.append(to_bng(shape(f["geometry"])))
            codes.append(code)
    tree = shapely.STRtree(lines)
    xtab, cover = [], []
    for area_name in WS_AREAS:
        area = next(a for a in AREAS if a.name == area_name)
        ways = load_ways(area_name).reset_index(drop=True)
        ways["legality"] = [motor_legality(r) for r in ways.to_dict("records")]
        geoms = [to_bng(shapely.from_wkt(w)) for w in ways["wkt"]]
        best = match_orders_to_ways(geoms, lines, codes)
        for wi, code in best.items():
            w = ways.iloc[wi]
            xtab.append({"area": area_name, "prow_status": PROW_NAME[code],
                         "osm_highway": w["highway"],
                         "osm_designation": w["designation"] or "(none)",
                         "osm_legality": w["legality"], "km": w["length_m"] / 1000})
        # Share of RB / BOAT length (clipped to the area bbox) near any cached OSM way.
        bbox = to_bng(shapely.box(*area.bbox))
        way_buf = shapely.union_all(shapely.buffer(geoms, 10))
        for code in (3, 4):
            idx = [i for i in tree.query(bbox) if codes[i] == code]
            if not idx:
                continue
            clipped = shapely.intersection(shapely.union_all([lines[i] for i in idx]), bbox)
            near = shapely.intersection(clipped, way_buf).length
            cover.append({"area": area_name, "prow_status": PROW_NAME[code],
                          "prow_km": round(clipped.length / 1000, 2),
                          "km_within_10m_of_osm_way": round(near / 1000, 2),
                          "pct": round(100 * near / clipped.length, 1) if clipped.length else None})
    x = (pd.DataFrame(xtab).groupby(["area", "prow_status", "osm_designation", "osm_legality"])
         .agg(ways=("km", "size"), km=("km", "sum")).round(2).reset_index())
    x.to_csv(OUT / "rights_of_way_agreement.csv", index=False)
    pd.DataFrame(cover).to_csv(OUT / "rights_of_way_osm_coverage.csv", index=False)
    print(x.groupby(["prow_status", "osm_legality"])["km"].sum().round(1))
    print(pd.DataFrame(cover))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wales_30mph()
    west_sussex_prow()


if __name__ == "__main__":
    main()
