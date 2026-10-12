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
- 1,699 speed-limit polygons have their single outer ring split into several unclosed pieces
  (`POLYGON((a … ),( … a))`); joining the pieces end to end restores the ring
  (`repaired_split_ring` in `geometry_parse.csv`). Some are 30k-vertex area polygons (20 mph zones).
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

Method: midpoint of each OSM way in the test areas, nearest D-TRO maximum-speed geometry within
15 m (all tied nearest kept, lowest mph wins), scored by `slg.agreement.compare`.
Subset `all` uses every maximum-speed provision; `permanent` excludes temporary orders.

| area | subset | matched ways | agree | OSM higher | OSM lower | OSM untagged |
|---|---|---|---|---|---|---|
| manchester_centre | all | 156 | 20 | 2 | 27 | 107 |
| manchester_centre | permanent | 88 | 3 | 2 | 0 | 83 |
| crawley | all | 42 | 8 | 18 | 0 | 16 |
| a27_chichester_worthing | all | 32 | 0 | 8 | 1 | 23 |
| m23_a23_crawley_brighton | all | 7 | 0 | 3 | 0 | 4 |
| m25_surrey | all | 1 | 0 | 1 | 0 | 0 |

All other areas (London Camden/Islington, Horsham, Midhurst, Cardiff, Powys, Edinburgh, A9) match
**nothing**. Only Manchester has any permanent-order matches. The "OSM higher" cases on the
Sussex/Surrey roads are temporary (roadworks) limits. D-TRO coverage of our test areas is
therefore negligible today; it is England-only (Wales may adopt; Scotland/NI not in scope).

## Height, width and weight orders (`restriction_counts.csv`, `restriction_provisions.csv`)

355 dimension provisions; almost all are temporary street-works orders with **no limit value**:

| type | n | with value | dynamic (temporary) | min |
|---|---|---|---|---|
| dimensionMaximumWeightStructural | 186 | 13 | 131 | 1.5 t |
| dimensionMaximumHeightStructural | 84 | 0 | 14 | — |
| dimensionMaximumWidth | 81 | 4 | 14 | 1.8 m |
| dimensionMaximumLength | 4 | 0 | 2 | — |

Weight values: 3.5 t ×11, 1.5 t, 7.5 t (`typeOfWeight: maximumPermitted`); widths 1.8, 2.0 ×2, 2.1 m.
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
