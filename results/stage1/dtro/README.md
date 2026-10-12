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
  **unclosed**, and the last ring ends on a stray copy of the outer ring's first vertex
  (`POLYGON((a … ),( … ),( … a))`). They are ordinary shell-plus-holes polygons: the first
  ring is the outer boundary (largest in all 1,699) and the others are holes inside it (roads
  carved out of a 20 mph zone, for example). `parse_ewkt` drops the stray vertex and closes each
  ring onto its own start; a ring inside an earlier shell becomes a hole of that shell, a ring
  outside every shell starts a separate part (MultiPolygon). Rings with fewer than 3 distinct
  points are dropped. On this dump (`geometry_parse.csv`): **1,691 shell-with-holes, 8
  multi-part, 0 rings dropped**. A way whose midpoint is in a hole is not in the zone.
  Results are not passed through `make_valid` (seconds per 30k-vertex zone polygon;
  point-in-polygon does not need it). The agreement figures below did not change when holes
  were added: no test-area way midpoint falls in a hole.
- Diversion routes (`regulatedPlace.type = diversionRoute`) are excluded from every provision's
  geometries: the signed alternative route is not where the order applies.
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
covers the dump date: start ≤ date and no end or end ≥ date (equality counts as in force).
The window is applied to permanent orders too (287 permanent speed provisions carry an end
date); temporary orders without any timeValidity, and revoked or proposed orders, are excluded.

**Time zone.** D-TRO times are Europe/London local wall-clock times, while the dump's
Last-Modified header is GMT. The dump date is converted to local time before comparing:
Sun, 06 Sep 2026 01:01:46 GMT = **2026-09-06T02:01:46** BST. All in-force / ended /
not-yet-started logic lives in `slg.dtro` (`dump_date`, `in_force`, `ended`, `not_started`,
`order_in_force`). **Not evaluated yet (Stage 4):** recurring periods (`validPeriod` days and
times of day, e.g. school-time limits or seasonal closures) and the provision `actionType`
(amendments and revocations of earlier provisions), so "in force" means "inside its overall
start/end window".

**Order nature** (`order_nature`, from the provision's `orderReportingPoint`): `ttroTtmo*` and
`specialEvent*` = temporary, `permanent*` / `experimentalMakingPermanent` = permanent, other
`experimental*` = experimental, `*Revocation` = **revoked**, `*NoticeOfIntention` = **proposed**
(not made yet). Revoked and proposed orders are never in force and never red-X relevant. Speed
rows keep the speed object's own `nature` plus `order_nature`; no speed provision in this dump
is revoked or proposed.

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
`orderReportingPoint` (`order_nature`), not `isDynamic`; "ended" and "in force" are relative to
the dump date. Each row also carries start/end, the condition-set `operator`, and
`has_exemption` / `exemption` for negated conditions (e.g. `loadingAndUnloading` = "except for
loading"). Limit values inside a negated (exemption) condition are ignored, and values outside
the OSM plausibility bounds (height/width 1–10 m, length 2–30 m, weight 0.5–60 t) are set to
None and counted in `out_of_range` (0 on this dump).

| type | n | with value | temporary | permanent | ended | in force | with exemption | min |
|---|---|---|---|---|---|---|---|---|
| dimensionMaximumWeightStructural | 186 | 13 | 131 | 55 | 67 | 109 | 1 | 1.5 t |
| dimensionMaximumHeightStructural | 84 | 0 | 14 | 70 | 10 | 73 | 0 | — |
| dimensionMaximumWidth | 81 | 4 | 14 | 67 | 6 | 74 | 0 | 1.8 m |
| dimensionMaximumLength | 4 | 0 | 2 | 2 | 2 | 2 | 0 | — |

Weight values: 3.5 t ×11, 1.5 t (except loading), 7.5 t (`typeOfWeight: maximumPermitted`, read from the same characteristic as the weight); widths 1.8, 2.0 ×2, 2.1 m.
No `dimensionMaximumHeightWithTRO` or `dimensionMaximumWeightEnvironmental` at all.
Separately (one-off survey, not in the script): 1,313 `movementOrderProhibitedAccess` regulations
carry a `grossVehicleWeight` condition (HGV access bans, mostly 3.5 t / 7.5 t) — a larger
weight source than the dimension orders, but they are not dimension types.

## Prohibitions and closures (`prohibition_counts.csv`, `prohibition_counts_by_area.csv`)

Red-X sources: `motorVehiclesProhibited`, `movementOrderProhibitedAccess`, `miscRoadClosure`,
`miscPROWClosure`, `publicRightOfWayClosure`, `bannedMovementNoEntry`. 150,339 provisions,
counted by type, order nature and whether a vehicle condition makes it a class ban (e.g. over
3.5 t) rather than a full closure. `ended`, `not_yet_started` and `in_force_at_dump` are
relative to the dump date; `access_exempt` marks "except for access" conditions; `recurring`
marks provisions with recurring periods (not evaluated). Each row in the code also carries
`direction` (from the regulated place's linear geometry, e.g. `startToEnd` for a one-way
no-entry) when stated.

| nature | provisions | in force at dump |
|---|---|---|
| temporary | 147,312 | 2,921 |
| permanent | 2,612 | 2,560 |
| unknown (`troOnRoadActiveStatus`) | 267 | 1 |
| proposed | 146 | 0 |
| revoked | 1 | 0 |
| experimental | 1 | 1 |

Almost all are temporary street-works road closures (`miscRoadClosure`, 147,683), 84 % already
ended at the dump date. Permanent prohibitions are almost all `movementOrderProhibitedAccess` (2,611; 2,060
with a vehicle condition, mostly weight-class bans, 1,505 of those "except for access"). By test
area (bbox intersection, all natures): Manchester 649 (6 permanent, 12 proposed), A27 397,
M25 Surrey 306, M23/A23 194, Crawley 144, Horsham 58, Midhurst 52; none in London Camden/
Islington, Cardiff, Powys, Edinburgh or the A9.

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
