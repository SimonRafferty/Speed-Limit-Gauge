"""Stage 1: pull all D-TROs, extract speed provisions, compare with OSM.

Run: .venv/Scripts/python research/stage1/dtro_pull.py [--cached]
Needs DTRO_CLIENT_ID / DTRO_CLIENT_SECRET in .env; exits cleanly without them.
--cached reuses data/stage1/dtro_all.csv instead of downloading it again (~540 MB).

/dtros/all CSV layout (observed 2026-10-12, undocumented): UTF-8 with BOM,
columns Id, SchemaVersion, Created, LastUpdated (MM/DD/YYYY HH:MM:SS), Data.
Data is the record's JSON body ({"source": {...}}) without the id/schemaVersion
wrapper that GET /dtros/{id} returns, so records() rebuilds that wrapper.
"""
import collections
import csv
import json
import sys
from datetime import datetime

import pandas as pd
import requests
import shapely

from slg.agreement import compare, snap_to_ways, to_bng
from slg.areas import AREAS
from slg.coverage import annotate
from slg.dtro import from_env, parse_ewkt, speed_provisions
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "dtro"
RAW = DATA / "stage1" / "dtro_all.csv"
SNAP_M = 15


def download_all(client) -> str | None:
    """Save the full dump to RAW; returns the file's Last-Modified header."""
    url = client.all_records_url()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(RAW, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        return r.headers.get("Last-Modified")


def _payload_column(row: dict) -> str | None:
    """Column holding the JSON body: 'Data' if present, else the first JSON object
    mentioning "provision" (fallback in case the undocumented layout changes)."""
    if "Data" in row:
        return "Data"
    for k, v in row.items():
        if v and v.lstrip().startswith("{") and '"provision"' in v:
            return k
    return None


def records():
    """Yield {"id", "schemaVersion", "created", "lastUpdated", "data"} per D-TRO row."""
    csv.field_size_limit(sys.maxsize if sys.maxsize < 2**31 else 2**31 - 1)
    with open(RAW, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        print("columns:", reader.fieldnames)
        col = None
        for row in reader:
            col = col or _payload_column(row)
            if col is None or not row.get(col):
                continue
            yield {"id": row.get("Id") or row.get("id"),
                   "schemaVersion": row.get("SchemaVersion") or row.get("schemaVersion"),
                   "created": row.get("Created"), "lastUpdated": row.get("LastUpdated"),
                   "data": json.loads(row[col])}


def _ts(s: str | None):
    try:
        return datetime.strptime(s, "%m/%d/%Y %H:%M:%S")
    except (TypeError, ValueError):
        return None


def agreement(df: pd.DataFrame, subset: str, outcomes: collections.Counter) -> list[dict]:
    """Snap each OSM way's midpoint to D-TRO maximum-speed geometries within SNAP_M.

    Only provisions with a numeric mph and limit_type maximumSpeedLimit are used.
    Where several D-TRO geometries tie for nearest, the lowest mph is kept
    (conservative: the device should never show a higher limit than an order says).
    """
    cand = df[df["mph"].notna() & (df["limit_type"] == "maximumSpeedLimit")]
    geoms, mphs = [], []
    for _, p in cand.iterrows():
        for s in p["geometries"]:
            g, why = parse_ewkt(s)
            outcomes[why] += 1
            if g is not None:
                geoms.append(g)
                mphs.append(int(p["mph"]))
    results = []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            continue
        ways = annotate(pd.read_parquet(cache))
        lines = to_bng(shapely.from_wkt(ways["wkt"].to_numpy()))
        mids = shapely.line_interpolate_point(lines, 0.5, normalized=True)
        best = {}  # way index -> lowest tied D-TRO mph
        for i, g, _ in snap_to_ways(mids, geoms, max_m=SNAP_M, all_matches=True):
            best[i] = min(best.get(i, mphs[g]), mphs[g])
        kinds, osm_mph = ways["ms_kind"].to_numpy(), ways["ms_mph"].to_numpy()
        rows = [{"osm_kind": kinds[i],
                 "osm_mph": None if pd.isna(osm_mph[i]) else int(osm_mph[i]),
                 "src_mph": m} for i, m in best.items()]
        results.append({"area": area.name, "subset": subset, "osm_ways": len(ways),
                        "dtro_geoms": len(geoms), **compare(rows)})
    return results


def main():
    client = from_env()
    if client is None:
        print("No D-TRO credentials in .env yet - skipping (documentation-only assessment).")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    last_modified = None
    if "--cached" in sys.argv and RAW.exists():
        print("using cached", RAW)
    else:
        last_modified = download_all(client)
    n_records, provs = 0, []
    versions, updated = collections.Counter(), []
    for rec in records():
        n_records += 1
        versions[rec["schemaVersion"]] += 1
        updated.append(_ts(rec["lastUpdated"]))
        provs += speed_provisions(rec)
    df = pd.DataFrame(provs)
    updated = [u for u in updated if u]
    print(f"{n_records} D-TRO records, {len(df)} speed provisions")
    pd.Series(versions, name="records").rename_axis("schema_version").sort_index() \
        .to_csv(OUT / "schema_versions.csv")
    pd.DataFrame([{"records": n_records, "speed_provisions": len(df),
                   "speed_dtros": df["dtro_id"].nunique() if not df.empty else 0,
                   "raw_bytes": RAW.stat().st_size, "dump_last_modified": last_modified,
                   "min_last_updated": min(updated, default=None),
                   "max_last_updated": max(updated, default=None)}]) \
        .to_csv(OUT / "volume.csv", index=False)
    if df.empty:
        return
    df.drop(columns="geometries").to_csv(OUT / "speed_provisions.csv", index=False)
    df.groupby(["regulation_type", "limit_type", "nature"], dropna=False).size() \
        .rename("provisions").to_csv(OUT / "type_counts.csv")

    # Agreement over all maximum-speed provisions, then permanent ones only
    # (temporary orders - roadworks, events - are expected to differ from OSM).
    outcomes = collections.Counter()
    results = agreement(df, "all", outcomes)
    results += agreement(df[df["nature"] == "permanent"], "permanent", collections.Counter())
    pd.DataFrame(results).to_csv(OUT / "agreement_by_area.csv", index=False)
    pd.Series(outcomes, name="geometries", dtype="int64").rename_axis("parse_outcome") \
        .sort_index().to_csv(OUT / "geometry_parse.csv")
    print("maximum-speed geometry parse outcomes:", dict(outcomes))


if __name__ == "__main__":
    main()
