"""Stage 1: OSM height/width/weight restriction coverage per test area.

Run: .venv/Scripts/python research/stage1/osm_restrictions.py
"""
import pandas as pd

from slg.areas import AREAS
from slg.osm_extract import (RESTRICTION_KEYS, download_extract, drivable_node_ids,
                            restriction_nodes_in_area, way_node_ids)
from slg.paths import DATA, RESULTS
from slg.restrictions import is_placeholder, parse_length_m, parse_weight_t

OUT = RESULTS / "stage1" / "restrictions"
LENGTH_KEYS = ("maxheight", "maxheight:physical", "maxwidth", "maxwidth:physical")
WEIGHT_KEYS = ("maxweight", "maxweightrating", "maxweight:hgv")
NODE_LOCATIONS = ("on_drivable", "on_other_way", "on_no_way")


def parsed(df: pd.DataFrame) -> pd.DataFrame:
    """Add <key>_m / <key>_t numeric columns for every restriction key present, plus the
    effective height/width: the lower of the signed and the physical value (NaN skipped)."""
    out = df.copy()
    for k in LENGTH_KEYS:
        if k in out:
            out[k + "_m"] = out[k].map(parse_length_m).astype(float)
    for k in WEIGHT_KEYS:
        if k in out:
            out[k + "_t"] = out[k].map(parse_weight_t).astype(float)
    for dim in ("height", "width"):
        cols = [c for c in (f"max{dim}_m", f"max{dim}:physical_m") if c in out]
        out[f"eff_{dim}_m"] = out[cols].min(axis=1) if cols else float("nan")
    return out


def node_location(node_ids: pd.Series, drivable: set[int], any_way: set[int]) -> pd.Series:
    """Where a restriction node sits: on a drivable way, on some other way (footway,
    cycleway, building...), or on no way at all (free-standing point)."""
    return node_ids.map(lambda n: "on_drivable" if n in drivable
                        else "on_other_way" if n in any_way else "on_no_way")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary, points, unparsed = [], [], []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            print("missing", cache)
            continue
        ways = parsed(pd.read_parquet(cache))
        nodes, drivable, any_way = [], set(), set()
        for region in area.regions:
            pbf = download_extract(region)
            nodes += restriction_nodes_in_area(pbf, area)
            drivable |= drivable_node_ids(pbf, area)
            any_way |= way_node_ids(pbf, area)
        nodes = parsed(pd.DataFrame(nodes).drop_duplicates("node_id")) if nodes else pd.DataFrame()
        if not nodes.empty:
            # Barriers on footways/cycleways/bollard gaps are not on a road a car can use.
            nodes["location"] = node_location(nodes["node_id"], drivable, any_way)
            nodes["on_drivable"] = nodes["location"] == "on_drivable"
        points.append(nodes)
        row = {"area": area.name, "country": area.country}
        for loc in NODE_LOCATIONS:
            row[f"nodes_{loc}"] = 0 if nodes.empty else int((nodes["location"] == loc).sum())
        for kind, df in (("way", ways), ("node", nodes)):
            for k in RESTRICTION_KEYS:
                if df.empty or k not in df:
                    continue
                col = k + ("_t" if k in WEIGHT_KEYS else "_m")
                present, ok = df[k].notna(), df[col].notna()
                row[f"{kind}_{k}_n"] = int(present.sum())
                row[f"{kind}_{k}_parsed"] = int((present & ok).sum())
                if kind == "node":
                    on_road = df["on_drivable"]
                    row[f"node_{k}_n_drivable"] = int((present & on_road).sum())
                    row[f"node_{k}_parsed_drivable"] = int((present & ok & on_road).sum())
                unparsed += [{"area": area.name, "kind": kind, "key": k, "value": v,
                              "placeholder": is_placeholder(v)}
                             for v in df.loc[present & ~ok, k]]
        # What would trip the default profile (2.2 m high, 1.79 m wide, 3.0 t)?
        # Heights/widths flagged with a ~0.1-0.2 m margin, using effective (min of signed, physical).
        road_nodes = nodes[nodes["on_drivable"]] if not nodes.empty else nodes

        def pooled(col):
            parts = [s for s in (ways.get(col), road_nodes.get(col)) if s is not None]
            return pd.concat(parts) if parts else pd.Series(dtype=float)

        w = ways.get("maxweight_t", pd.Series(dtype=float))
        row["heights_below_2_3m"] = int((pooled("eff_height_m") < 2.3).sum())
        row["widths_below_2_0m"] = int((pooled("eff_width_m") < 2.0).sum())
        row["weights_below_3_5t"] = int((w < 3.5).sum())
        summary.append(row)
        print(row)
    by_area = pd.DataFrame(summary)
    counts = [c for c in by_area if c not in ("area", "country")]
    # An area with no nodes of a key leaves the column missing: that is a count of 0.
    by_area[counts] = by_area[counts].fillna(0).astype(int)
    by_area.to_csv(OUT / "osm_restrictions_by_area.csv", index=False)
    # Areas overlap, so pool unique nodes only (per-area rows above stay per-area).
    found = [p for p in points if not p.empty]
    pts = (pd.concat(found, ignore_index=True).drop_duplicates("node_id") if found
           else pd.DataFrame(columns=["node_id", "location", "on_drivable"]))
    pts.to_csv(OUT / "osm_restriction_nodes.csv", index=False)
    pd.DataFrame(unparsed, columns=["area", "kind", "key", "value", "placeholder"]).value_counts() \
        .to_csv(OUT / "unparsed_values.csv")
    if "eff_height_m" in pts:
        bins = [0, 1.8, 2.0, 2.1, 2.2, 2.3, 2.5, 3.0, 4.0, 5.0, 10]
        pd.cut(pts.loc[pts["on_drivable"], "eff_height_m"].dropna(), bins).value_counts().sort_index() \
            .to_csv(OUT / "node_height_histogram.csv")


if __name__ == "__main__":
    main()
