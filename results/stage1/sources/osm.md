# OpenStreetMap (Geofabrik extracts / Overpass)

Summary of what Stage 1 measured (Tasks 7-10); no new research. Figures come from
`results/stage1/osm/`, `results/stage1/overpass/`, `results/stage1/restrictions/` and
`results/stage1/access/` (12 test areas, extracts downloaded 2026-10-12).

| Field | Finding |
|---|---|
| What it holds | Full road network (all classes incl. track, service), with `maxspeed` (+ `maxspeed:type`, `:conditional`, `:variable`, `zone:maxspeed`), `maxheight`/`maxwidth`/`maxweight` (way and barrier/bridge nodes), `access`/`motor_vehicle`/`motorcar`/`vehicle` (+ `:conditional`), `designation`/`prow_ref` for rights of way, `lit`, `dual_carriageway`, `junction`, `ref`. |
| Speed-limit content | Explicit values (mph) plus national-limit kinds (`GB:nsl_single`, `GB:nsl_dual`, `GB:motorway`, `GB:nsl_restricted`, `GB:zone20`). Usable limit on **63.6 %** of non-service/non-track km in the test areas: England 57.4 %, Wales 59.3 %, Scotland 93.4 % (`coverage_by_country_class.csv`). By class: motorway/trunk/primary ~92-100 %; secondary 79-100 %; tertiary 68-97 %; residential **42 % England**, 77 % Wales, 94 % Scotland; unclassified **15 % Wales**, 39 % England, 72 % Scotland; track 0-0.5 %. By condition (all classes): urban 63 %, suburban 33 %, rural 17 %, motorway_trunk areas 30 % (dragged down by service/track km; `coverage_by_condition.csv`). Only ~1 % of tagged ways carry `source:maxspeed`. |
| Restrictions content | Height: 816 way `maxheight` tags (481 parse to a number - the rest are placeholders such as `default`/`below_default`/`none`) and 126 node tags (117 parsed); 193 heights < 2.3 m, 66 widths < 2.0 m, 47 weights < 3.5 t across the 12 areas (`osm_restrictions_by_area.csv`, `unparsed_values.csv`). `maxheight:physical` is rare (4 nodes, 8 ways). |
| Access / closure content | Motor legality classified per way (`slg.access.motor_legality`): prohibited (red X), permission (yellow X), conditional, allowed, unknown. Tracks are mostly **untagged** for motor access: e.g. A9 area 1,102 of 1,169 track km unknown; Powys 225 of 388; Midhurst 82 of 236 (`access_by_area.csv`). `designation` present on only a minority of tracks (Midhurst 94 of 236 km; Powys 110 of 388 km; Scotland only `core_path`). Time-conditional bans (school streets etc.) exist as `motor_vehicle:conditional` (`conditional_values.csv`). Temporary closures/roadworks are not in OSM. |
| Geographic coverage | GB (and world). |
| Access method | Bulk download (Geofabrik `.osm.pbf` per county/country, daily); minutely/daily replication diffs from planet.openstreetmap.org for patches. Live Overpass API was **unreliable**: 4 of the 5 recorded requests to overpass-api.de returned 504 (`overpass/probe.csv`), so not usable from a device or as a build dependency without a private instance. |
| Auth | None. |
| Rate limits | Geofabrik: none stated for normal use. Public Overpass: slot-limited, 504s observed. |
| Licence | ODbL 1.0 (attribution + share-alike on derived databases). |
| Freshness | Edits flow to Geofabrik extracts within ~1 day. Median age of the last edit to tagged ways: trunk 426 d, primary 422 d, unclassified 426 d, tertiary 486 d, secondary 510 d, residential 714 d, motorway 1,011 d; 38-68 % of tagged ways edited in the last 2 years (`freshness_by_class.csv`). Age of edit is not age of verification. |
| Volume | Extracts: West Sussex 49.6 MB, Surrey 43.2 MB, East Sussex 21.8 MB, Greater London 129.5 MB, Greater Manchester 51.5 MB, Wales 149.0 MB, Scotland 327.3 MB (`extracts.csv`; whole-object PBF, far larger than the road subset). Overpass road JSON for London Camden/Islington: 9.9 MB for 870 km = **~11.4 kB/km** (`probe.csv`), an upper bound for raw road geometry + tags. |
| Format / CRS | PBF (protobuf), WGS84 lon/lat. |
| Agreement with OSM | n/a (reference). Other sources are scored against it: D-TRO (`dtro/agreement_by_area.csv`), Wales 30 mph layer (`wales_20mph_agreement.csv`), West Sussex rights of way (`rights_of_way_agreement.csv`). |

## Verdict
**Primary.** OSM is the only open source with GB-wide geometry, explicit speed limits,
dimension restrictions and motor-access tags in one model, under a licence that permits
a derived offline tile set and incremental patches (replication diffs). Its weaknesses are
known and measurable: residential/unclassified limits in England and Wales are often
untagged (must be inferred - Stage 2), track access is largely untagged (needs rights-of-way
data for the red/yellow X), and some height tags are placeholders rather than values. Build
from Geofabrik extracts / planet diffs, never from the public Overpass endpoint.

## Sources
- Stage 1 results: `results/stage1/osm/*.csv`, `results/stage1/overpass/README.md` + `probe.csv`,
  `results/stage1/restrictions/*.csv`, `results/stage1/access/*.csv`.
- https://download.geofabrik.de/europe/united-kingdom.html
- https://opendatacommons.org/licenses/odbl/1-0/
- https://wiki.openstreetmap.org/wiki/Key:maxspeed , https://wiki.openstreetmap.org/wiki/Planet.osm/diffs
