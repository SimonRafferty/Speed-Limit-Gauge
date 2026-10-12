# D-TRO (DfT Digital Traffic Regulation Orders)

Summary of what Stage 1 measured with production credentials on 2026-10-12 (Tasks 11-12);
full detail in `results/stage1/dtro/README.md`. No new research.

| Field | Finding |
|---|---|
| What it holds | Digital versions of traffic regulation orders submitted by English traffic authorities: speed limits, dimension restrictions, prohibited access / no entry, road and PROW closures, with geometry and time validity. 146,202 records in the dump (schema 3.2.3-4.0.0; no v5). |
| Speed-limit content | Explicit values, but sparse: 5,229 speed provisions in 3,127 D-TROs (2 % of D-TROs). Permanent max-speed 2,768 (20 mph 197, 30 mph 1,573, 40 mph 667, 50 mph 325, 60 mph 6); temporary 2,273 (mostly roadworks 10-50 mph); 112 `nationalSpeedLimitWellLitStreetDefault`; 76 profile-based national limits. Speed regulations carry **no `regulationType`**, so they cannot be filtered server-side. Times are Europe/London local; "in force" = inside the start/end window at the dump date (recurring periods and amendments not yet evaluated). |
| Restrictions content | 355 dimension provisions, only **17 state a value** (weight 186 / 13 valued; height 84 / 0 valued; width 81 / 4 valued; length 4 / 0). A larger weight source is the 1,313 `movementOrderProhibitedAccess` regulations with a `grossVehicleWeight` condition (HGV bans, mostly 3.5 t / 7.5 t). |
| Access / closure content | 150,339 prohibition/closure provisions: 147,683 `miscRoadClosure` (almost all temporary street works; 84 % already ended at the dump date, 2,921 in force), 2,611 permanent `movementOrderProhibitedAccess` (2,060 with a vehicle condition, mostly weight-class bans, 1,505 of those "except for access"; 2,559 in force), 20 PROW closures (`miscPROWClosure`, `publicRightOfWayClosure`; 7 of them proposed), 8 no-entry. 146 provisions are proposed (notice of intention) and 1 revoked; neither is ever in force. In test areas (bbox, all natures): 52 (Midhurst) to 649 (Manchester) per area, none in London Camden/Islington, Wales or Scotland (`prohibition_counts.csv`, `prohibition_counts_by_area.csv`). This is the only open source of **temporary closures** in England. |
| Geographic coverage | England only (Wales may adopt; Scotland / NI out of scope). Patchy by authority: no matches at all in London Camden/Islington, Horsham, Midhurst, M25 Surrey; Wales/Scotland areas zero by design. |
| Access method | REST API (OAuth2 client credentials). Bulk: `GET /v1/dtros/all` -> signed GCS URL to a CSV. Single: `GET /v1/dtros/{id}`. Search: `POST /v1/search` (summaries only). **Change feed: `POST /v1/events`** (`since`/`to`, paged, create/update/delete). |
| Auth | Free; registered consumer application, separate for integration and production. |
| Rate limits | 120 requests/minute spike arrest (429, no `Retry-After`). |
| Licence | Open Government Licence v3.0 (service terms, section 7). |
| Freshness | Bulk dump **not regenerated daily**: the file served on 2026-10-12 was dated 2026-09-06 (5 weeks old); rebuild cadence undocumented. Events feed is live: 108 events on Sun 2026-10-11; >7,178 events (5,750 D-TROs) in the week 2026-10-05..11. |
| Volume | Dump 537,483,749 bytes (~513 MiB CSV), 146,202 records; downloads in ~15 s. Keeping current: bulk once, then `/events` since max `LastUpdated`, then `GET /dtros/{id}` per changed id, ~1,000 calls/day (~10 min/day at 120/min). |
| Format / CRS | CSV (UTF-8 BOM; `Id, SchemaVersion, Created, LastUpdated, Data` JSON); geometry as EWKT in EPSG:27700. 1,699 speed polygons are written with unclosed rings and need repair: 1,691 are a shell with holes, 8 are multi-part (`geometry_parse.csv`); 218 speed geometries are points (unusable). Diversion-route geometries are excluded. |
| Agreement with OSM | [`../dtro/agreement_by_area.csv`](../dtro/agreement_by_area.csv). Permanent orders match ways only in Manchester (28 ways: 2 agree, 1 OSM higher, 25 OSM untagged). In-force (incl. temporary) orders: Manchester 47 ways (10 agree, 1 higher, 8 lower, 28 untagged), Crawley 8 (3 agree, 4 higher), A27 3 (3 higher). OSM "higher" cases are temporary roadworks limits OSM rightly does not carry. |

## Verdict
**Secondary (England), for temporary limits, closures and access bans; not a speed-limit
backbone.** Coverage of permanent limits in our test areas is negligible today, dimension
orders rarely carry a value, and there is nothing for Wales or Scotland. But D-TRO is the
only open, licensed, machine-readable feed of temporary speed limits, road closures and
HGV/weight access bans, and it has a working change feed (`/events`) that fits the
patch-build design in Stage 5. Use it as an overlay on OSM (temporary limits and closures
win while in force) and re-measure coverage as authorities migrate; statutory D-TRO
submission will grow it.

## Sources
- `results/stage1/dtro/README.md` and CSVs in that folder; `research/stage1/dtro_pull.py`.
- https://github.com/pa-digital/dft-dtro-api-docs (api_quickstart.rst, terms_and_conditions.rst, FAQ) - fetched 2026-10-12.
- Live production API probes, 2026-10-12.
