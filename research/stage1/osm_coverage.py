"""Stage 1: OSM maxspeed coverage and freshness for every test area.

Run: .venv/Scripts/python research/stage1/osm_coverage.py

Per-area tables use every row (overlapping areas count in each). Country and
condition rollups de-duplicate by way_id so a way in two areas counts once.
"""
from datetime import datetime, timezone
from importlib.metadata import version

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from slg.areas import AREAS
from slg.coverage import annotate, coverage_by_class, freshness, kind_breakdown
from slg.osm_extract import download_extract, ways_in_area
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "osm"
WAYS = DATA / "stage1"


def area_ways(area) -> pd.DataFrame:
    cache = WAYS / f"{area.name}_ways.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows = []
    for region in area.regions:
        rows += ways_in_area(download_extract(region), area)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("way_id")
    WAYS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def write_extract_provenance(regions) -> None:
    """Record which Geofabrik extracts the numbers came from."""
    rows = []
    for region in sorted(regions):
        p = download_extract(region)  # already on disk, so no download
        st = p.stat()
        rows.append({"region": region, "file": p.name, "bytes": st.st_size,
                     "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                     "osmium": version("osmium"), "pandas": pd.__version__})
    pd.DataFrame(rows).to_csv(OUT / "extracts.csv", index=False)


def plot_pivot(ways, value, xlabel, title, fname) -> None:
    pivot = coverage_by_class(ways, ("area", "road_class")).pivot(
        index="area", columns="road_class", values=value)
    ax = pivot.plot.barh(figsize=(11, 8), width=0.85)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(OUT / fname, dpi=110)
    plt.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    frames, regions = [], set()
    for area in AREAS:
        raw = area_ways(area)
        if raw.empty:
            print(f"WARNING: {area.name} yielded no ways; skipped")
            continue
        df = annotate(raw)
        df["condition"] = area.condition
        frames.append(df)
        regions.update(area.regions)
        print(f"{area.name}: {len(df)} ways, {df['length_m'].sum() / 1000:.0f} km")
    ways = pd.concat(frames, ignore_index=True)
    uniq = ways.drop_duplicates("way_id")  # for rollups across overlapping areas
    print(f"overlap: {len(ways) - len(uniq)} duplicate way rows removed from rollups")

    coverage_by_class(ways, ("area", "road_class")).to_csv(OUT / "coverage_by_area_class.csv", index=False)
    coverage_by_class(uniq, ("country", "road_class")).to_csv(OUT / "coverage_by_country_class.csv", index=False)
    coverage_by_class(uniq, ("condition",)).to_csv(OUT / "coverage_by_condition.csv", index=False)
    kind_breakdown(uniq).to_csv(OUT / "kind_km_by_class.csv")
    freshness(uniq, now).to_csv(OUT / "freshness_by_class.csv", index=False)
    (ways[ways["ms_kind"].isin(["ambiguous", "unparsed", "none", "multi", "nonstandard"])]
        [["way_id", "area", "highway", "maxspeed"]]
        .to_csv(OUT / "odd_values.csv", index=False))
    ways["maxspeed:type"].value_counts(dropna=False).to_csv(OUT / "maxspeed_type_counts.csv")
    ways["source:maxspeed"].value_counts(dropna=False).to_csv(OUT / "source_maxspeed_counts.csv")
    write_extract_provenance(regions)

    plot_pivot(ways, "pct_km_usable", "% of km with a usable maxspeed limit",
               "OSM maxspeed coverage (usable limits) by area and road class", "coverage_pct_km.png")
    plot_pivot(ways, "pct_km_tagged", "% of km with any maxspeed tag",
               "OSM maxspeed coverage (any maxspeed tag) by area and road class", "coverage_pct_km_any.png")
    print("written", OUT)


if __name__ == "__main__":
    main()
