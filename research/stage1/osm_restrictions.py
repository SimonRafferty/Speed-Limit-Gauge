"""Stage 1: OSM height/width/weight restriction coverage per test area.

Run: .venv/Scripts/python research/stage1/osm_restrictions.py
"""
import pandas as pd

from slg.areas import AREAS
from slg.osm_extract import RESTRICTION_KEYS, download_extract, restriction_nodes_in_area
from slg.paths import DATA, RESULTS
from slg.restrictions import parse_length_m, parse_weight_t

OUT = RESULTS / "stage1" / "restrictions"
LENGTH_KEYS = ("maxheight", "maxheight:physical", "maxwidth", "maxwidth:physical")
WEIGHT_KEYS = ("maxweight", "maxweightrating", "maxweight:hgv")


def parsed(df: pd.DataFrame) -> pd.DataFrame:
    """Add <key>_m / <key>_t numeric columns for every restriction key present."""
    out = df.copy()
    for k in LENGTH_KEYS:
        if k in out:
            out[k + "_m"] = out[k].map(parse_length_m)
    for k in WEIGHT_KEYS:
        if k in out:
            out[k + "_t"] = out[k].map(parse_weight_t)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary, points, unparsed = [], [], []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            print("missing", cache)
            continue
        ways = parsed(pd.read_parquet(cache))
        nodes = []
        for region in area.regions:
            nodes += restriction_nodes_in_area(download_extract(region), area)
        nodes = parsed(pd.DataFrame(nodes).drop_duplicates("node_id")) if nodes else pd.DataFrame()
        points.append(nodes)
        row = {"area": area.name, "country": area.country}
        for kind, df in (("way", ways), ("node", nodes)):
            for k in RESTRICTION_KEYS:
                if df.empty or k not in df:
                    continue
                col = k + ("_t" if k in WEIGHT_KEYS else "_m")
                present, ok = df[k].notna(), df[col].notna()
                row[f"{kind}_{k}_n"] = int(present.sum())
                row[f"{kind}_{k}_parsed"] = int((present & ok).sum())
                unparsed += [{"area": area.name, "kind": kind, "key": k, "value": v}
                             for v in df.loc[present & ~ok, k]]
        # What would trip the default profile (2.2 m, 3.0 t)? Heights flagged with a 0.1 m margin.
        heights = [s for s in (ways.get("maxheight_m"), nodes.get("maxheight_m")) if s is not None]
        h = pd.concat(heights) if heights else pd.Series(dtype=float)
        w = ways.get("maxweight_t", pd.Series(dtype=float))
        row["heights_below_2_3m"] = int((h < 2.3).sum())
        row["weights_below_3_5t"] = int((w < 3.5).sum())
        summary.append(row)
        print(row)
    pd.DataFrame(summary).to_csv(OUT / "osm_restrictions_by_area.csv", index=False)
    pts = pd.concat([p for p in points if not p.empty], ignore_index=True)
    pts.to_csv(OUT / "osm_restriction_nodes.csv", index=False)
    pd.DataFrame(unparsed, columns=["area", "kind", "key", "value"]).value_counts() \
        .to_csv(OUT / "unparsed_values.csv")
    if "maxheight_m" in pts:
        bins = [0, 1.8, 2.0, 2.1, 2.2, 2.3, 2.5, 3.0, 4.0, 5.0, 10]
        pd.cut(pts["maxheight_m"].dropna(), bins).value_counts().sort_index() \
            .to_csv(OUT / "node_height_histogram.csv")


if __name__ == "__main__":
    main()
