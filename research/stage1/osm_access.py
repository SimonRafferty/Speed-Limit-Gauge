"""Stage 1: tracks and motor-vehicle legality (red X) per test area (spec 7.1a).

Run (after osm_coverage.py has cached the ways):
    .venv/Scripts/python research/stage1/osm_access.py

Per-area tables use every row (overlapping areas count in each); conditional_values.csv
de-duplicates by way_id so a way in two areas counts once.
"""
import pandas as pd

from slg.access import KEYS, motor_legality
from slg.areas import AREAS
from slg.coverage import annotate
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "access"
LEGALITY = ("prohibited", "permission", "conditional", "allowed", "unknown")
CONDITIONAL_KEYS = tuple(k + ":conditional" for k in KEYS)


def grouped(df: pd.DataFrame, area: str, col: str) -> pd.DataFrame:
    """ways and km per value of `col`, for tracks and for all classes."""
    parts = []
    for scope, sub in (("track", df[df["road_class"] == "track"]), ("all", df)):
        g = (sub.assign(km=sub["length_m"] / 1000, **{col: sub[col].fillna("(none)")})
                .groupby(col).agg(ways=("way_id", "count"), km=("km", "sum")).reset_index())
        g.insert(0, "scope", scope)
        g.insert(0, "area", area)
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary, legality, designation, frames = [], [], [], []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            print("missing", cache)
            continue
        df = annotate(pd.read_parquet(cache))
        df["legality"] = [motor_legality(r) for r in df.to_dict("records")]
        frames.append(df)
        tracks = df[df["road_class"] == "track"]
        track_km = tracks["length_m"].sum() / 1000
        row = {"area": area.name, "country": area.country, "condition": area.condition,
               "track_ways": len(tracks), "track_km": round(float(track_km), 2),
               "track_pct_km_tagged": round(100 * tracks.loc[tracks["tagged"], "length_m"].sum()
                                            / 1000 / track_km, 1) if track_km else None,
               "track_pct_km_usable": round(100 * tracks.loc[tracks["usable"], "length_m"].sum()
                                            / 1000 / track_km, 1) if track_km else None}
        for scope, sub in (("track", tracks), ("all", df)):
            for cls in LEGALITY:
                m = sub["legality"] == cls
                row[f"{scope}_{cls}_km"] = round(float(sub.loc[m, "length_m"].sum()) / 1000, 2)
                row[f"{scope}_{cls}_ways"] = int(m.sum())
        summary.append(row)
        legality.append(grouped(df, area.name, "legality"))
        designation.append(grouped(df, area.name, "designation"))
        print({k: row[k] for k in ("area", "track_km", "track_pct_km_usable",
                                   "track_prohibited_km", "track_permission_km")})

    pd.DataFrame(summary).to_csv(OUT / "access_by_area.csv", index=False)
    pd.concat(legality, ignore_index=True).round({"km": 2}).to_csv(OUT / "legality_by_area.csv", index=False)
    pd.concat(designation, ignore_index=True).round({"km": 2}).to_csv(OUT / "designation_by_area.csv", index=False)

    # Every distinct :conditional value, to size the time-rule parser needed later.
    uniq = pd.concat(frames, ignore_index=True).drop_duplicates("way_id")
    cond = (uniq.melt(id_vars=["way_id", "highway", "length_m"], value_vars=list(CONDITIONAL_KEYS),
                      var_name="key", value_name="value")
                .dropna(subset=["value"]))
    (cond.assign(km=cond["length_m"] / 1000, track=cond["highway"] == "track")
         .groupby(["key", "value"])
         .agg(ways=("way_id", "count"), track_ways=("track", "sum"), km=("km", "sum"))
         .reset_index().sort_values("ways", ascending=False).round({"km": 2})
         .to_csv(OUT / "conditional_values.csv", index=False))
    print("written", OUT)


if __name__ == "__main__":
    main()
