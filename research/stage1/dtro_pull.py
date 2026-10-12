"""Stage 1: pull all D-TROs, extract speed, restriction and prohibition provisions,
compare speeds with OSM.

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

from slg.agreement import compare, match_orders_to_ways, to_bng
from slg.areas import AREAS
from slg.coverage import annotate
from slg.dtro import (NOT_IN_FORCE_NATURES, dump_date, ended, from_env, not_started, order_in_force, parse_ewkt,
                      prohibition_provisions, restriction_provisions, speed_provisions)
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "dtro"
RAW = DATA / "stage1" / "dtro_all.csv"
# Ways the speed comparison ignores: private/service access and tracks rarely carry a
# maxspeed tag and are not what a speed-limit order is about.
EXCLUDED_HIGHWAYS = ("service", "track")


def download_all(client) -> str | None:
    """Save the full dump to RAW; returns the file's Last-Modified header."""
    url = client.all_records_url()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    part = RAW.with_name(RAW.name + ".part")  # an interrupted download never replaces RAW
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        last_modified = r.headers.get("Last-Modified")
    part.replace(RAW)
    return last_modified


def _payload_column(row: dict) -> str | None:
    """Column holding the JSON body: 'Data' if present, else the first JSON object
    mentioning "provision" (fallback in case the undocumented layout changes)."""
    if "Data" in row:
        return "Data"
    for k, v in row.items():
        if v and v.lstrip().startswith("{") and '"provision"' in v:
            return k
    return None


def records(malformed: collections.Counter | None = None):
    """Yield {"id", "schemaVersion", "created", "lastUpdated", "data"} per D-TRO row.

    Rows with no payload or unparsable JSON are skipped and counted in malformed."""
    malformed = collections.Counter() if malformed is None else malformed
    csv.field_size_limit(sys.maxsize if sys.maxsize < 2**31 else 2**31 - 1)
    with open(RAW, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        print("columns:", reader.fieldnames)
        col = None
        for row in reader:
            col = col or _payload_column(row)
            if col is None or not row.get(col):
                malformed["no_payload"] += 1
                continue
            try:
                data = json.loads(row[col])
            except json.JSONDecodeError:
                malformed["bad_json"] += 1
                continue
            if not isinstance(data, dict):
                malformed["not_object"] += 1
                continue
            yield {"id": row.get("Id") or row.get("id"),
                   "schemaVersion": row.get("SchemaVersion") or row.get("schemaVersion"),
                   "created": row.get("Created"), "lastUpdated": row.get("LastUpdated"),
                   "data": data}


def _ts(s: str | None):
    try:
        return datetime.strptime(s, "%m/%d/%Y %H:%M:%S")
    except (TypeError, ValueError):
        return None


def load_orders(df: pd.DataFrame, outcomes: collections.Counter, pieces: collections.Counter):
    """Maximum-speed order geometries and mph (numeric mph, maximumSpeedLimit only)."""
    cand = df[df["mph"].notna() & (df["limit_type"] == "maximumSpeedLimit")]
    geoms, mphs = [], []
    for _, p in cand.iterrows():
        for s in p["geometries"]:
            g, why = parse_ewkt(s, pieces)
            outcomes[why] += 1
            if g is not None:
                geoms.append(g)
                mphs.append(int(p["mph"]))
    return geoms, mphs


def agreement(df: pd.DataFrame, subset: str, outcomes: collections.Counter,
              pieces: collections.Counter) -> list[dict]:
    """Per test area, OSM ways matched to D-TRO maximum-speed orders (see
    slg.agreement.match_orders_to_ways), scored by slg.agreement.compare.

    service and track ways are left out (counted in excluded_ways). A way with only
    maxspeed:forward/backward is passed as kind "directional_only", which compare
    counts as osm_unusable rather than osm_untagged.
    """
    geoms, mphs = load_orders(df, outcomes, pieces)
    results = []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            continue
        ways = annotate(pd.read_parquet(cache))
        excluded = ways["highway"].isin(EXCLUDED_HIGHWAYS)
        kept = ways[~excluded].reset_index(drop=True)
        lines = to_bng(shapely.from_wkt(kept["wkt"].to_numpy()))
        best = match_orders_to_ways(lines, geoms, mphs)
        kinds = kept["ms_kind"].where(~((kept["ms_kind"] == "absent") & kept["tagged"]),
                                      "directional_only").to_numpy()
        osm_mph = kept["ms_mph"].to_numpy()
        rows = [{"osm_kind": kinds[i],
                 "osm_mph": None if pd.isna(osm_mph[i]) else int(osm_mph[i]),
                 "src_mph": m} for i, m in best.items()]
        results.append({"area": area.name, "subset": subset, "osm_ways": len(kept),
                        "excluded_ways": int(excluded.sum()), "dtro_geoms": len(geoms),
                        **compare(rows)})
    return results


def _any_geometry(ewkt: str):
    """D-TRO EWKT (BNG) -> shapely geometry of any kind (points included), or None."""
    srid, _, body = ewkt.partition(";")
    if srid.strip().upper() != "SRID=27700":
        return None
    try:
        g = shapely.from_wkt(body)
    except shapely.errors.ShapelyError:
        return None
    return None if g is None or g.is_empty else g


def prohibition_area_counts(pdf: pd.DataFrame) -> pd.DataFrame:
    """Prohibition provisions with any geometry intersecting each test area's bbox."""
    names = [a.name for a in AREAS]
    tree = shapely.STRtree([to_bng(shapely.box(*a.bbox)) for a in AREAS])
    rows = []
    for _, p in pdf.iterrows():
        hit = set()
        for s in p["geometries"]:
            g = _any_geometry(s)
            if g is not None:
                hit.update(int(i) for i in tree.query(g, predicate="intersects"))
        rows += [{"area": names[i], "regulation_type": p["regulation_type"], "nature": p["nature"],
                  "has_vehicle_condition": p["has_vehicle_condition"]} for i in hit]
    cols = ["area", "regulation_type", "nature", "has_vehicle_condition"]
    return (pd.DataFrame(rows, columns=cols).value_counts().rename("provisions")
            .reset_index().sort_values(cols))


def write_prohibitions(pdf: pd.DataFrame, as_of: str) -> None:
    """Closure / prohibition orders (red X sources): counts by type and order nature.
    ended / not_yet_started / in_force_at_dump are relative to as_of (the dump date,
    Europe/London local ISO); revoked and proposed orders are never in force."""
    if pdf.empty:
        return
    flags = pdf.assign(
        has_end=pdf["end"].notna(),
        ended=ended(pdf["end"], as_of),
        not_yet_started=not_started(pdf["start"], as_of),
        in_force_at_dump=order_in_force(pdf, as_of),
        geometries_n=pdf["geometries"].map(len))
    flags.groupby(["regulation_type", "nature", "has_vehicle_condition"]).agg(
        provisions=("provision_ref", "count"), dtros=("dtro_id", "nunique"),
        with_end=("has_end", "sum"), ended=("ended", "sum"),
        not_yet_started=("not_yet_started", "sum"), in_force_at_dump=("in_force_at_dump", "sum"),
        recurring=("has_recurring_period", "sum"), access_exempt=("has_access_condition", "sum"),
        no_geometry=("geometries_n", lambda n: int((n == 0).sum())),
    ).reset_index().to_csv(OUT / "prohibition_counts.csv", index=False)
    prohibition_area_counts(pdf).to_csv(OUT / "prohibition_counts_by_area.csv", index=False)
    print(f"prohibition provisions: {len(pdf)}")


def main():
    client = from_env()
    if client is None:
        print("No D-TRO credentials in .env yet - skipping (documentation-only assessment).")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    last_modified = None
    if "--cached" in sys.argv and RAW.exists():
        print("using cached", RAW)
        # Keep the dump date recorded when the cached file was downloaded.
        if (OUT / "volume.csv").exists():
            prev = pd.read_csv(OUT / "volume.csv").get("dump_last_modified")
            if prev is not None and prev.notna().any():
                last_modified = prev.dropna().iloc[0]
    else:
        last_modified = download_all(client)
    n_records, provs, restrs, prohibs = 0, [], [], []
    malformed = collections.Counter()
    versions, updated = collections.Counter(), []
    for rec in records(malformed):
        n_records += 1
        versions[rec["schemaVersion"]] += 1
        updated.append(_ts(rec["lastUpdated"]))
        provs += speed_provisions(rec)
        restrs += restriction_provisions(rec)
        prohibs += prohibition_provisions(rec)
    df = pd.DataFrame(provs)
    rdf = pd.DataFrame(restrs)
    pdf = pd.DataFrame(prohibs)
    updated = [u for u in updated if u]
    as_of = dump_date(last_modified, max(updated, default=None))
    print(f"{n_records} D-TRO records, {len(df)} speed provisions, {len(rdf)} restriction provisions, "
          f"{len(pdf)} prohibition provisions")
    pd.Series(versions, name="records").rename_axis("schema_version").sort_index() \
        .to_csv(OUT / "schema_versions.csv")
    pd.DataFrame([{"records": n_records, "speed_provisions": len(df),
                   "speed_dtros": df["dtro_id"].nunique() if not df.empty else 0,
                   "restriction_provisions": len(rdf),
                   "prohibition_provisions": len(pdf),
                   "malformed_rows": sum(malformed.values()),
                   "raw_bytes": RAW.stat().st_size, "dump_last_modified": last_modified,
                   "min_last_updated": min(updated, default=None),
                   "max_last_updated": max(updated, default=None)}]) \
        .to_csv(OUT / "volume.csv", index=False)
    if not rdf.empty:
        rdf.drop(columns="geometries").to_csv(OUT / "restriction_provisions.csv", index=False)
        # Many dimension orders are temporary street-works orders with no limit value at
        # all, so count how many actually state one. Nature comes from the provision's
        # orderReportingPoint (order_nature), not isDynamic.
        values = rdf[["height_m", "width_m", "length_m", "weight_t"]].notna().any(axis=1)
        rdf.assign(has_value=values, temporary=rdf["nature"].eq("temporary"),
                   permanent=rdf["nature"].eq("permanent"),
                   ended=ended(rdf["end"], as_of or "9999"),
                   in_force_at_dump=order_in_force(rdf, as_of or "9999")).groupby("regulation_type").agg(
            n=("provision_ref", "count"),
            with_value=("has_value", "sum"), temporary=("temporary", "sum"),
            permanent=("permanent", "sum"), ended=("ended", "sum"),
            in_force_at_dump=("in_force_at_dump", "sum"),
            with_exemption=("has_exemption", "sum"), out_of_range=("out_of_range", "sum"),
            min_height_m=("height_m", "min"), min_width_m=("width_m", "min"),
            min_length_m=("length_m", "min"), min_weight_t=("weight_t", "min"),
        ).to_csv(OUT / "restriction_counts.csv")
        print(f"restriction provisions: {len(rdf)}")
    write_prohibitions(pdf, as_of or "9999")
    if df.empty:
        return
    df.drop(columns="geometries").to_csv(OUT / "speed_provisions.csv", index=False)
    df.groupby(["regulation_type", "limit_type", "nature"], dropna=False).size() \
        .rename("provisions").to_csv(OUT / "type_counts.csv")

    # Agreement subsets: "all" is historical (every order ever published, including
    # expired roadworks limits); "permanent" drops temporary orders; "in_force" keeps
    # orders whose timeValidity covers the dump date.
    outcomes, pieces = collections.Counter(), collections.Counter()
    results = agreement(df, "all", outcomes, pieces)
    results += agreement(df[df["nature"] == "permanent"], "permanent",
                         collections.Counter(), collections.Counter())
    if as_of:
        # Speed rows carry the speed object's own nature; revoked / proposed orders are
        # only visible in order_nature, so let those override it for the in-force test.
        sp = df.assign(nature=df["order_nature"].where(
            df["order_nature"].isin(NOT_IN_FORCE_NATURES), df["nature"]))
        results += agreement(df[order_in_force(sp, as_of)], "in_force",
                             collections.Counter(), collections.Counter())
    pd.DataFrame(results).to_csv(OUT / "agreement_by_area.csv", index=False)
    pd.Series({**outcomes, **pieces}, name="geometries", dtype="int64").rename_axis("parse_outcome") \
        .sort_index().to_csv(OUT / "geometry_parse.csv")
    print("dump date:", as_of, "| maximum-speed geometry parse outcomes:", dict(outcomes),
          "| split-ring pieces:", dict(pieces), "| malformed rows:", dict(malformed))


if __name__ == "__main__":
    main()
