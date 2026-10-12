# Mapillary (detected traffic signs)

Stage 1 has a ready pull (`research/stage1/mapillary_pull.py`, `research/slg/mapillary.py`)
but **no `MAPILLARY_TOKEN` in `.env`**, so nothing has been measured yet.

| Field | Finding |
|---|---|
| What it holds | Crowd-sourced street-level imagery plus machine-detected "map features": point positions of traffic signs (`object_value` e.g. `regulatory--maximum-speed-limit-30--g1`) with `first_seen_at` / `last_seen_at`, `aligned_direction`, contributing images. |
| Speed-limit content | Signs (points), not road segments: a speed-limit sign gives a value at a location and a facing direction; the extent must be inferred by snapping to OSM ways (pull script: nearest public-road way within 20 m, service/track excluded). Also detects height/width/weight signs, no-entry and "no motor vehicles" signs (other `regulatory--*` values), useful to flag OSM gaps on restrictions and access. |
| Geographic coverage | GB, but density depends on where contributors have driven; rural lanes and byways are thin. |
| Access method | REST (Graph API `https://graph.mapillary.com/map_features`, `bbox` + `object_values` filters, max 2,000 results per call, bbox area < 0.01 deg^2) and vector tiles (`traffic_sign` layer at z14). |
| Auth | Free client token (register an app at mapillary.com/dashboard/developers). **Needed: a client token in `.env` as `MAPILLARY_TOKEN`.** |
| Rate limits | Documented: entity API 60,000/min per app, search 10,000/min per app, tiles 50,000/day. |
| Licence | Imagery CC BY-SA 4.0; the API docs give no explicit licence for derived map-feature data (only "(c) Mapillary" attribution and Meta's terms of use). OSM has a permission to derive data from Mapillary; reuse in a redistributed product needs checking against the terms before using it for anything beyond validation. |
| Freshness | Per-feature `last_seen_at`; depends on recapture. Many UK signs are seen once. |
| Volume | Not measured. Points only (~100-200 bytes per feature in JSON). |
| Format / CRS | JSON / GeoJSON points, WGS84; MVT tiles. |
| Agreement with OSM | Not measured: no Mapillary client token yet. The script writes `results/stage1/mapillary/agreement_by_area.csv` when one is added. |

Note for when it runs: `fetch_features` requests 0.05 deg cells (0.0025 deg^2, inside the
0.01 deg^2 cap) with `limit=2000`, filters the speed-limit sign classes server-side
(`object_values`, all `--g1`..`--g5` variants), and splits any cell that returns exactly
2,000 features into 4 and re-queries, up to 3 levels, counting any still-full cell as
truncated (fixed in 0c028a6 / 19797cf after review; earlier the
filter was client-side and dense cells could be silently truncated).

## Verdict
**Validation only.** Detected signs are the best open, independent check on OSM speed
values and on restriction/access signs, and "last seen" dates help find stale OSM tags. But
they are points with no extent, detection errors and uneven coverage, and the licence for
redistributing derived features is unclear, so they should drive review lists (and OSM
fixes), not be shipped as a data layer. Get a free client token to measure agreement.

## Sources
- `research/stage1/mapillary_pull.py`, `research/slg/mapillary.py`.
- https://www.mapillary.com/developer/api-documentation (rate limits, map_features fields/filters, traffic_sign tiles)
- https://blog.mapillary.com/update/2021/06/23/getting-started-with-the-new-mapillary-api-v4.html (client token)
- https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data (CC BY-SA 4.0 imagery; page returned 403 to the fetcher, content via search snippets)
- https://wiki.openstreetmap.org/wiki/Mapillary (special permission for OSM-derived edits)
- https://web-archive.nli.org.il/National_Library/20160526010038mp_/https://mapillary.com/legal (2016 commercial terms: derived data for internal use; may be outdated after the 2020 Meta acquisition)
