# D-TRO (DfT Digital Traffic Regulation Orders) — Stage 1 findings

Pulled 2026-10-12 from **production** (`https://dtro.dft.gov.uk/v1`) with an approved
consumer application. Script: `research/stage1/dtro_pull.py` (`--cached` reuses the raw file).

## Access

- OAuth2 client credentials: `POST /v1/oauth-generator` (basic auth, `grant_type=client_credentials`),
  token valid 30 min. Integration and production need separate applications; our
  credentials are production-only.
- Bulk: `GET /v1/dtros/all` returns a signed Google Cloud Storage URL (valid 60 min) to a CSV.
- Single record: `GET /v1/dtros/{id}`.
- Search: `POST /v1/search` (`page`, `pageSize`, `queries[]`) — works; returns summaries
  (troName, publicationTime, regulationType[], regulationStart/End, id), not geometry.
- Rate limit observed: Apigee spike arrest **120 requests/minute**
  (`429 policies.ratelimit.SpikeArrestViolation`, no `Retry-After` header). No other
  rate-limit headers are returned. No OpenAPI/Swagger document is exposed
  (`/swagger`, `/openapi.json`, `/api-docs` all rejected by the gateway's OAS validator).
- `GET /v1/schemas/versions` and `GET /v1/schemas` (464 KB, JSON Schemas for every version) work.

## Dump size and layout

| | |
|---|---|
| Object | `dtro-prod-records/dtros_20260906_010013.csv` |
| Size | 537,483,749 bytes (~513 MiB), downloads in ~15 s |
| Last-Modified | Sun, 06 Sep 2026 01:01:46 GMT — **5 weeks old** on 2026-10-12 |
| Records | 146,202 (unique Ids) |
| Record LastUpdated range | 2024-10-18 → 2026-09-05 23:50 |

The snapshot is not regenerated daily: the URL served on 2026-10-12 still pointed at the
6 Sep file. How often it is rebuilt is undocumented.

Layout (undocumented): UTF-8 with BOM; columns `Id, SchemaVersion, Created, LastUpdated, Data`;
timestamps `MM/DD/YYYY HH:MM:SS`; `Data` is the record body (`{"source": {...}}`, plus
`consultation` on 132 records) **without** the `id`/`schemaVersion` wrapper `GET /dtros/{id}` uses.
Records do carry `Created` and `LastUpdated` timestamps.

Schema versions seen (`schema_versions.csv`): 3.5.1 (107,407), 4.0.0 (35,612), 3.5.0 (2,631),
3.4.0 (541), a handful of 3.2.x/3.3.0/3.4.1. **No v5 records.**

## Data-shape surprises (parser fixes)

- Speed regulations carry **no `regulationType`** (neither top-level nor `generalRegulation`);
  they are only identifiable by a `speedLimitValueBased` / `speedLimitProfileBased` object on the
  regulation. Consequently `/events` and `/search` summaries list `regulationType: []` for them,
  so speed orders cannot be filtered server-side by type.
- `regulation` is a single object rather than a list in ~47k provisions (`condition` likewise in v4).
- 1,699 maximum-speed POLYGON geometries fail to parse because every ring is written
  **unclosed**, and the last ring ends on a stray copy of the polygon's very first vertex
  (`POLYGON((a … ),( … ),( … a))`). The pieces are separate rings, not fragments of one: the
  gaps between consecutive pieces are hundreds of metres to ~11 km. `parse_ewkt` drops the stray
  closing vertex, closes each piece onto its own start and returns a MultiPolygon
  (`repaired_split_ring`); pieces with fewer than 3 distinct points are dropped. On this dump:
  10,782 rings kept, 0 dropped (`geometry_parse.csv`). Results are not passed through
  `make_valid` (seconds per 30k-vertex zone polygon; point-in-polygon does not need it).
- 218 speed geometries are POINTs (allowed pre-v5), unusable for matching a road; skipped.

## Speed provisions (`type_counts.csv`, `speed_provisions.csv`)

5,229 speed provisions in 3,127 D-TROs (2.4 % of the dump's ~215k provisions; 2 % of D-TROs).

| regulation | type | nature | provisions |
|---|---|---|---|
| speedLimitValueBased | maximumSpeedLimit | permanent | 2,768 |
| speedLimitValueBased | maximumSpeedLimit | temporary | 2,273 |
| speedLimitValueBased | nationalSpeedLimitWellLitStreetDefault | permanent | 112 |
| speedLimitProfileBased | nationalSpeedLimit | — | 76 |

Maximum-speed mph values: permanent 20 (197), 30 (1,573), 40 (667), 50 (325), 60 (6);
temporary 10 (336), 20 (277), 30 (852), 40 (762), 50 (46). No minimum-speed provisions.

## Agreement with OSM (`agreement_by_area.csv`)

Method (`slg.agreement.match_orders_to_ways`, scored by `slg.agreement.compare`), using
provisions with a numeric mph and type `maximumSpeedLimit`:
- area orders (20 mph zones etc.): a way matches only if its midpoint is **inside** the polygon;
- linear orders: a way matches only if **at least 50 % of its length** lies within 10 m of the order;
- several matching orders: the **lowest** mph is kept (conservative);
- `highway=service` and `highway=track` ways are excluded (`excluded_ways` column);
- a way tagged only `maxspeed:forward/backward` counts as `osm_unusable`, not `osm_untagged`
  (`compare` only sees one mph per way, so directional values are not compared).

Subsets: `all` is **historical** — every order in the dump, including roadworks limits long
expired; `permanent` keeps permanent orders only; `in_force` keeps orders whose timeValidity
covers the dump date (2026-09-06T01:01:46, from Last-Modified): start ≤ date and no end or
end ≥ date. The window is applied to permanent orders too (287 permanent speed provisions carry
an end date), and temporary orders without any timeValidity are excluded.

| area | subset | matched ways | agree | OSM higher | OSM lower | OSM untagged |
|---|---|---|---|---|---|---|
| manchester_centre | all | 47 | 10 | 1 | 8 | 28 |
| manchester_centre | permanent | 28 | 2 | 1 | 0 | 25 |
| manchester_centre | in_force | 47 | 10 | 1 | 8 | 28 |
| crawley | all | 19 | 4 | 14 | 0 | 1 |
| crawley | permanent | 0 | | | | |
| crawley | in_force | 8 | 3 | 4 | 0 | 1 |
| a27_chichester_worthing | all | 13 | 0 | 7 | 0 | 6 |
| a27_chichester_worthing | permanent | 0 | | | | |
| a27_chichester_worthing | in_force | 3 | 0 | 3 | 0 | 0 |
| m23_a23_crawley_brighton | all | 5 | 0 | 3 | 0 | 2 |
| m23_a23_crawley_brighton | in_force | 0 | | | | |

All other areas (London Camden/Islington, Horsham, Midhurst, M25 Surrey, Cardiff, Powys,
Edinburgh, A9) match **nothing** in any subset. Only Manchester has permanent-order matches, and
most of those are ways OSM leaves untagged. "OSM higher" in Crawley and on the A27 is from
temporary (roadworks) limits that were in force on the dump date. D-TRO coverage of our test
areas is therefore negligible today; it is England-only (Wales may adopt; Scotland/NI not in scope).

## Height, width and weight orders (`restriction_counts.csv`, `restriction_provisions.csv`)

355 dimension provisions; only 17 state a **limit value**. Nature is from the provision's
`orderReportingPoint` (`order_nature`), not `isDynamic`; "ended" is relative to the dump date.
Each row also carries start/end, the condition-set `operator`, and `has_exemption` / `exemption`
for negated conditions (e.g. `loadingAndUnloading` = "except for loading").

| type | n | with value | temporary | permanent | ended | with exemption | min |
|---|---|---|---|---|---|---|---|
| dimensionMaximumWeightStructural | 186 | 13 | 131 | 55 | 67 | 1 | 1.5 t |
| dimensionMaximumHeightStructural | 84 | 0 | 14 | 70 | 10 | 0 | — |
| dimensionMaximumWidth | 81 | 4 | 14 | 67 | 6 | 0 | 1.8 m |
| dimensionMaximumLength | 4 | 0 | 2 | 2 | 2 | 0 | — |

Weight values: 3.5 t ×11, 1.5 t (except loading), 7.5 t (`typeOfWeight: maximumPermitted`, read from the same characteristic as the weight); widths 1.8, 2.0 ×2, 2.1 m.
No `dimensionMaximumHeightWithTRO` or `dimensionMaximumWeightEnvironmental` at all.
Separately (one-off survey, not in the script): 1,313 `movementOrderProhibitedAccess` regulations
carry a `grossVehicleWeight` condition (HGV access bans, mostly 3.5 t / 7.5 t) — a larger
weight source than the dimension orders, but they are not dimension types.

## Incremental / changed-since options

Yes — **`POST /v1/events`** is a change feed (not described in the public quickstart):
body `{"page", "pageSize" (1–50), "since", "to"}` (`to` required). Each event has
`id`, `eventType` (`create` / `update` / `delete`), `eventTime`, `publicationTime`, `troName`,
`regulationType[]`, `regulationStart/End[]` and `_links.self` (`/dtros/{id}`); `totalCount` is
returned as -1, so the window must be paged to the end. Volume: 108 events on Sunday 2026-10-11;
over 7,178 events (5,750 distinct D-TROs; 2,858 create / 4,220 update / 100 delete) in the week
2026-10-05→11 before the 120/min limit stopped paging. Keeping a mirror current therefore means:
bulk CSV once, then `/events` since the CSV's `max LastUpdated`, then `GET /dtros/{id}` per
changed id — on the order of 1,000 calls/day at 120/min (~10 min/day). Because speed orders have
empty `regulationType` in events, they cannot be pre-filtered; every changed record must be fetched.
`/search` also accepts a `publicationTime` query but returns summaries only.

## Licence

D-TRO data is licensed under the **Open Government Licence v3.0** (stated in the service's
`terms_and_conditions.rst`, section 7). Attribution where none is given: "Contains public sector
information licensed under the Open Government Licence v3.0." Portal content itself is Crown
Copyright and not for reuse without consent.

## Sources

- `github.com/pa-digital/dft-dtro-api-docs` (`content/api_quickstart.rst`, `terms_and_conditions.rst`,
  `upversioning.rst`, FAQ 2-6, 4-26) — fetched 2026-10-12.
- Live production API probes, 2026-10-12.
