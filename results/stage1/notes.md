# Stage 1 notes: data sources for the speed-limit gauge

**Data licences:** OSM-derived results © OpenStreetMap contributors (ODbL). D-TRO, DataMapWales (Welsh Government) and West Sussex County Council rights-of-way data (via rowmaps.com) contain public sector information licensed under the Open Government Licence v3.0.

Written 2026-10-12 at the end of Stage 1. Every number below is copied or summed from a
committed results file (path given with each table); nothing is estimated. "Test areas" are
the 12 areas in spec §5. Per-area tables count a way in every area it falls in; country,
class and condition rollups count each way once.

**Short version.** OSM is the backbone and is good on main roads (98 % of motorway, trunk
and primary km carry a usable limit) but weak on English residential and unclassified roads
and on Welsh unclassified roads, which is where Stage 2 inference has to work. Live Overpass
queries are not viable; everything must be pre-built on the PC. D-TRO works and has a change
feed, but in today's test areas it adds almost nothing for permanent limits; its value is
temporary limits, closures and weight bans. Height data is mostly OSM, and car-park barriers
dominate it. Rights-of-way data from rowmaps conflates cleanly onto OSM tracks. Mapillary is
waiting for a token.

---

## 1. What was tried

All work ran on 2026-10-11 (spec and plan) and 2026-10-12 (code, data pulls, results), on
branch `stage1-sources`. Python package `research/slg/`, scripts in `research/stage1/`.

| Source | How | Script | Data date | Results |
|---|---|---|---|---|
| OSM (Geofabrik extracts) | 7 `.osm.pbf` extracts; drivable ways + tracks per test area cached as parquet | `osm_coverage.py` | downloaded 2026-10-12 08:38-08:41 UTC | `osm/` |
| OSM restrictions | `maxheight`/`maxwidth`/`maxweight` on ways and barrier nodes | `osm_restrictions.py` | same extracts | `restrictions/` |
| OSM access / tracks | red/yellow-X legality per way | `osm_access.py` | same extracts | `access/` |
| Overpass API (public) | live query per area, bytes and latency | `overpass_probe.py` | 2026-10-12 | `overpass/` |
| D-TRO (DfT) | production API, OAuth; bulk CSV dump + `/events` probe | `dtro_pull.py` | dump of 2026-09-06 | `dtro/`, `sources/dtro.md` |
| Wales 30 mph layer | DataMapWales WFS, Cardiff + Powys bboxes | `source_samples.py` | fetched 2026-10-12 | `sources/wales_20mph*` |
| Rights of way | rowmaps.com West Sussex GeoJSON | `source_samples.py` | council data 2024-09-17 | `sources/rights_of_way*` |
| Mapillary | traffic-sign map features | `mapillary_pull.py` | **not run: no token** | `sources/mapillary.md` |
| Desk research | National Highways, OS Open Roads, Scotland 20 mph, West Sussex CC, commercial APIs | - | 2026-10-12 | `sources/*.md` |

Tests: `.venv/Scripts/python -m pytest -q` → **240 passed** (2026-10-12).

---

## 2. OSM speed-limit coverage

"Usable" = a `maxspeed` the parser turns into a definite UK limit. "Any tag" = any `maxspeed`
value at all. The two differ by less than 0.1 percentage point in every class except service
(5.85 % vs 5.78 % in England), so only one column is shown.
Source: `osm/coverage_by_country_class.csv`.

**% of km with a usable limit**

| Class | England | Wales | Scotland | All (km) |
|---|---|---|---|---|
| motorway | 98.4 | - | - | 98.4 (89) |
| trunk | 98.5 | 91.5 | 100 | 97.5 (680) |
| primary | 98.0 | 95.7 | 100 | 98.2 (687) |
| secondary | 89.5 | 78.6 | 100 | 90.3 (416) |
| tertiary | 67.8 | 71.9 | 97.4 | 75.3 (906) |
| residential | **41.8** | 76.6 | 94.5 | 52.7 (3,644) |
| unclassified | **39.2** | **15.4** | 72.2 | 36.1 (1,170) |
| service | 5.8 | 6.4 | 6.2 | 6.0 (3,619) |
| track | 0.5 | 0.0 | 0.0 | 0.2 (2,565) |
| **Public roads (excl. service, track)** | **57.4** | **59.3** | **93.4** | **63.6** (7,592) |

Scotland's test areas (Edinburgh, A9) are well tagged. In England the gap is in suburban
and rural areas: residential usable km is 9.8 % in Horsham, 17.4 % on the A27 area and
27.5 % in Midhurst, against 97.9 % in London Camden/Islington (`osm/coverage_by_area_class.csv`).
By area condition, including service and tracks: urban 62.9 %, suburban 33.3 %,
rural 16.8 %, motorway/trunk areas 30.2 % (`osm/coverage_by_condition.csv`; tracks drag the
last two down, see `access/README.md`).

**How national limits are tagged.** No way in the test areas uses the national-limit form
`maxspeed=GB:nsl_single` (the parser's `nsl_*` / `national` kinds are 0 km in
`osm/kind_km_by_class.csv`). Mappers write the car figure as a number, e.g. `maxspeed=60 mph`,
and put the meaning in `maxspeed:type` (`osm/maxspeed_type_counts.csv`, way rows):

| `maxspeed:type` | ways |
|---|---|
| sign | 1,202 |
| GB:nsl_single | 1,179 |
| GB:zone20 | 996 |
| GB:nsl_dual | 678 |
| GB:nsl_restricted (+ GB-WLS:nsl_restricted) | 296 + 14 |
| GB:motorway | 188 |
| construction | 96 |

This matters for Commercial and Trailer modes: a `60 mph` way with `maxspeed:type=GB:nsl_single`
is a national limit (50 mph for those modes), not a posted 60. Stages 2 and 4 must read
`maxspeed:type`, not just `maxspeed`. A `60 mph` tag with no type is ambiguous; signed 60 mph
limits are rare (D-TRO has 6 permanent 60 mph provisions in all of England).

**Odd values** are rare: 17 way rows out of 39,633 tagged rows (`osm/odd_values.csv`):
`12 mph` ×6 (non-standard, London service roads) and bare numbers 5, 8, 15, 20, 30 (no unit;
km/h by OSM rule, mph by intent). They total 1.4 km "ambiguous" + 1.3 km "non-standard"
(`osm/kind_km_by_class.csv`). The parser shows no limit for either.

Provenance tags are thin: `source:maxspeed` is set on 375 way rows, about 1 % of tagged ways
(`osm/source_maxspeed_counts.csv`).

---

## 3. Freshness

Median age of the last edit to tagged ways, and share edited in the last 2 years
(`osm/freshness_by_class.csv`):

| Class | Tagged ways | Median age (days) | Edited < 2 years |
|---|---|---|---|
| trunk | 3,949 | 426 | 68 % |
| unclassified | 3,454 | 426 | 67 % |
| primary | 6,092 | 422 | 65 % |
| tertiary | 4,248 | 486 | 62 % |
| secondary | 2,470 | 510 | 60 % |
| residential | 15,117 | 714 | 51 % |
| service | 3,579 | 968 | 41 % |
| motorway | 264 | 1,011 | 38 % |
| track | 14 | 1,886 | 21 % |

**Caveat:** this is the way's timestamp, i.e. the last edit of any kind (geometry, name,
surface), not when `maxspeed` was last changed or checked. A way can be recently edited
with a stale limit, or old and still right. Old motorways are probably fine; old residential
limits in Wales (default 20 since Sept 2023) are the risk.

---

## 4. Live-query cost (Overpass)

`overpass/probe.csv`, `overpass/README.md`:

| Area | Result | Bytes | Seconds | km | Bytes/km |
|---|---|---|---|---|---|
| London Camden/Islington | OK | 9,918,951 | 1.94 | 869.5 | **11,407** |
| Horsham (2 tries) | 504 Gateway Timeout | - | - | - | - |
| Midhurst (2 tries) | 504 Gateway Timeout | - | - | - | - |

4 of the 5 recorded requests to the public `overpass-api.de` failed with 504, and the
failures were not linked to query size (Horsham's bbox is smaller than London's). **Live
Overpass is not viable** for the device or as a build dependency. The 11.4 kB/km figure is
raw JSON for road geometry plus all tags: an upper bound, not a tile size.

---

## 5. Restrictions (height / width / weight)

### OSM

12 test areas, summed per area (`restrictions/osm_restrictions_by_area.csv`, `restrictions/unparsed_values.csv`):

| Tag | Way tags | Parsed | Node tags | Parsed |
|---|---|---|---|---|
| maxheight | 816 | 481 | 126 | 117 |
| maxheight:physical | 8 | 8 | 4 | 4 |
| maxwidth | 91 | 91 | 46 | 46 |
| maxwidth:physical | 1 | 1 | 220 | 204 |
| maxweight | 313 | 313 | 5 | 5 |
| maxweightrating | 11 | 11 | 5 | 5 |
| maxweight:hgv | 0 | - | 0 | - |

- **Placeholders, not failures.** All 335 unparsed way `maxheight` values and the 9 unparsed
  node ones are placeholders: `default` 222, `below_default` 104, `none` 18. They mean "no
  sign / not measured" and never warn (spec §7.1).
- **Real rejections:** 16 node `maxwidth:physical` values fell outside the 1-10 m bounds:
  bollard gaps of 0.5-0.9 m (true, but not a road width), plus `0` and `20`.
- **Drivable-only filter.** Of 399 restriction nodes, 184 sit on drivable ways, 209 on other
  ways (footpaths, cycleways) and 6 on no way (`restrictions/osm_restriction_nodes.csv`).
  Only the 184 can warn.
- **Car-park cluster.** Of the 107 drivable nodes with an effective height, 81 are in
  1.8-2.2 m (`restrictions/node_height_histogram.csv`); 47 of the 107 are
  `barrier=height_restrictor`. These are mostly car-park barriers, and the default 2.20 m
  vehicle height is at or above every one of them. 23 drivable nodes are above 2.2 m and 3
  are at or below 1.8 m.
- Summed over areas: 193 heights < 2.3 m, 66 widths < 2.0 m, 47 weights < 3.5 t.
- `maxheight:physical` (measured clearance) is rare: 8 ways and 4 nodes, all in Horsham.

### D-TRO

355 dimension provisions in the whole of England; **only 17 state a value**
(`dtro/restriction_counts.csv`):

| Type | Provisions | With value | In force at dump |
|---|---|---|---|
| Weight (structural) | 186 | 13 | 109 |
| Height (structural) | 84 | 0 | 73 |
| Width | 81 | 4 | 74 |
| Length | 4 | 0 | 2 |

Values: weights 3.5 t ×11, 1.5 t (except loading), 7.5 t; widths 1.8, 2.0 ×2, 2.1 m. A larger
weight source is the 1,313 `movementOrderProhibitedAccess` regulations with a gross-weight
condition (HGV bans, mostly 3.5 / 7.5 t; one-off survey, `dtro/README.md`). For height and
width, OSM is the only usable source.

---

## 6. Access, tracks, red X and yellow X

Classifier `slg.access.motor_legality`, private-car view (`access/README.md`). Summed over the
12 areas (overlaps count twice; `access/legality_by_area.csv`):

| | Red X km | Yellow X km | Conditional km | Allowed km | Unknown km |
|---|---|---|---|---|---|
| All classes | 110 | 2,100 | 33 | 239 | 11,477 |
| Tracks only | 69 | 775 | 0 | 86 | 1,688 |

- **Designation alone is a yellow X.** In the first pass a footpath / bridleway / restricted
  byway designation with no access tag was a red X, and that was 308 of 419 red-X km. Many such
  ways are private drives or farm lanes the owner may drive, so the user decided (2026-10-12)
  they are yellow X. Yellow X now comes 1,786 km from access tags and 314 km from
  designation alone (`access/permission_by_class_service.csv`).
- **Yellow X by class:** service 1,059 km, track 775 km, residential 200 km,
  unclassified 64 km (same file). Because driveways and car-park aisles are so common, the
  yellow X is a small badge when a limit is known.
- **Tracks** have almost no speed tags (0-0.6 % of km, London 12.5 % of 6.8 km) and most have
  no motor-access tag: the A9 area has 1,102 of 1,169 track km "unknown"
  (`access/access_by_area.csv`). By spec §7.1a tracks use the national limit for the mode.
- **Conditional rules** (`access/conditional_values.csv`): 58 distinct values on 241 way rows,
  33 km. By count they are mostly **school streets**: 32 values / 145 way rows are a weekday
  morning-plus-afternoon window such as `no @ (Mo-Fr 08:30-09:30,15:00-16:00; SH off)`. By km
  they are not: two dated one-off event closures (2024 and 2025) account for 11.7 km, and
  one weekend closure for 4.4 km. Keys: `motor_vehicle:conditional` 50, `vehicle:conditional` 5,
  `access:conditional` 3. **No track carries a conditional rule**, and there are no
  seasonal green-lane closures in the test areas. The only seasonal rule is one
  `destination @ (Apr 01-Sep 30: ... -sunset)` on a 0.11 km non-track way.
- **Rights of way (rowmaps, West Sussex).** Restricted-byway and BOAT lines lie within 10 m
  of an OSM way for 86-100 % of their length (`sources/rights_of_way_osm_coverage.csv`), so
  they conflate cleanly. Vehicle-relevant classes (RB + BOAT) are about 0.24 MB of GeoJSON
  per county. See §7 for agreement.

---

## 7. Agreement with OSM

### D-TRO speed orders (`dtro/agreement_by_area.csv`)

Three subsets: `all` = every order in the dump, including long-expired roadworks
(historical); `permanent`; `in_force` = inside its start/end window at the dump date
(2026-09-06 02:01 BST). Ways matched (agree / OSM higher / OSM lower / OSM untagged):

| Area | all | permanent | in force |
|---|---|---|---|
| Manchester centre | 47 (10 / 1 / 8 / 28) | 28 (2 / 1 / 0 / 25) | 47 (10 / 1 / 8 / 28) |
| Crawley | 19 (4 / 14 / 0 / 1) | 0 | 8 (3 / 4 / 0 / 1) |
| A27 Chichester-Worthing | 13 (0 / 7 / 0 / 6) | 0 | 3 (0 / 3 / 0 / 0) |
| M23/A23 | 5 (0 / 3 / 0 / 2) | 0 | 0 |
| Other 8 areas | 0 | 0 | 0 |

D-TRO adds almost nothing for permanent limits in the test areas today. "OSM higher" in
Crawley and on the A27 is temporary roadworks limits that OSM rightly does not carry.
England only.

### Wales 30 mph layer (`sources/wales_20mph_agreement.csv`)

| Area | Ways matched | Agree | OSM higher | OSM lower | OSM untagged | Agree where tagged |
|---|---|---|---|---|---|---|
| Cardiff | 497 | 372 | 20 | 23 | 82 | 90 % |
| Powys rural | 38 | 36 | 0 | 2 | 0 | 95 % |

It fills 82 untagged Cardiff ways. The layer has no dates, so it may lag the 2025 reversions.

### Rights of way vs OSM legality (`sources/rights_of_way_agreement.csv`, re-run 2026-10-12 with the current classifier)

| Council status | km matched | Yellow X | Red X | No X (allowed) |
|---|---|---|---|---|
| Restricted byway | 29.6 | 21.5 | 5.4 | 2.7 |
| BOAT | 1.7 | - | 1.1 | 0.55 |
| Footpath / bridleway | 189.4 | 173.5 | 10.5 | 5.4 |

The 2.7 km of restricted byway tagged `motorcar=yes`/`access=yes` (Midhurst) and the 1.1 km
BOAT tagged `motor_vehicle=no` (A27) are where OSM and the council disagree. Council data
can't tell a TRO from an OSM error.

### Mapillary

**Pending:** no `MAPILLARY_TOKEN` in `.env`. The pull is ready
(`research/stage1/mapillary_pull.py`) and writes `results/stage1/mapillary/agreement_by_area.csv`.

---

## 8. Failed avenues and corrections made during review

| What | Problem | Fix |
|---|---|---|
| Public Overpass | 4 of 5 requests returned 504 | Dropped as a live or build source; build from Geofabrik extracts and diffs |
| km/h parsing | The first parser rounded values that matched no UK limit: `100 km/h` became an explicit 62 mph, a limit that does not exist in the UK and is above the 60 mph the road probably has | Values not within 1.5 mph of a UK limit are now `nonstandard` (no limit shown) (5e2a44d) |
| D-TRO split-ring polygons | 1,699 zone polygons written with unclosed rings. First read as separate polygons (MultiPolygon) | They are a shell with holes (1,691) or multi-part (8); a way in a hole is outside the zone (c7f683d → b688dc6) |
| D-TRO speed orders | Carry no `regulationType`; `regulation` sometimes a single object | Identified by the speed object; cannot be filtered server-side or in `/events` (8a3d643) |
| D-TRO in-force test | Dump date in GMT vs order times in local time; revoked and proposed orders counted | Compare in Europe/London; revoked / proposed never in force (b688dc6) |
| D-TRO diversion routes | Counted as the order's place | Excluded (b688dc6) |
| Designation-only red X | 308 of 419 red-X km came from a designation with no access tag | Now yellow X (user decision; 8baa697). Rights-of-way agreement re-run with the new rule |
| Restriction nodes | Nodes on footpaths and duplicates from pooled extracts counted | Drivable ways only, deduplicated (311f7c2) |
| Mapillary fetch | Client-side filter could truncate dense cells at 2,000 features | Server-side sign filter and cell splitting (0c028a6, 19797cf); still unmeasured |
| Tracks in coverage | Adding `highway=track` cut the condition rollups (rural 26.3 % → 16.8 %) | Quote per-class figures; tracks use the national limit anyway (`access/README.md`) |

Rejected sources: commercial APIs (terms forbid offline caching), West Sussex CC (no
machine-readable orders), Scotland 20 mph (no national dataset). National Highways has no
open permanent-limit layer; its closure and speed-managed-area APIs are a possible Stage 5
feed for motorways. See `sources/*.md`.

---

## 9. Implications for later stages

### Stage 2 (inference)

Where the missing km are (public classes, km with no usable limit,
`osm/coverage_by_country_class.csv`):

| Country / class | Untagged km | Usable % |
|---|---|---|
| England residential | 1,590 | 41.8 |
| England unclassified | 352 | 39.2 |
| Wales unclassified | 344 | 15.4 |
| England tertiary | 192 | 67.8 |
| Wales residential | 107 | 76.6 |
| Scotland unclassified | 51 | 72.2 |

Service roads (England 2,158 km, Scotland 662, Wales 583 untagged) and tracks (Scotland 1,175,
England 964, Wales 421) are larger but different. Many service roads are private (yellow X).
Tracks take the national limit by rule, so they need legality data, not inference.

Inputs available: OSM `maxspeed:type`, `lit`, `dual_carriageway`, `junction` and road class;
OS Open Roads `formOfWay` (single / dual / slip / roundabout) to choose nsl_single vs nsl_dual;
the Wales 30 mph layer for Welsh restricted roads (default 20 unless listed). Untagged ways are
mostly residential and rural, so a model trained on tagged ways (urban-heavy) needs the
tagged-vs-untagged bias check in the spec.

### Stages 3 and 4 (matching and estimator)

- **Direction.** D-TRO no-entry orders carry a direction, and OSM has `maxspeed:forward/backward`.
  Stage 1 counts directional-only ways as unusable rather than comparing them; Stage 4 must
  handle them.
- **Time rules.** The conditional parser needs: weekday ranges, several windows per day,
  `SH off` / `PH`, dated one-off ranges (`2025 Jan 17 21:00-…`), date ranges
  (`2026-01-26-2026-06-04`), month ranges and `sunset`. Stale one-off events are still in OSM,
  so expired dates must evaluate to "not now". D-TRO recurring periods (`validPeriod`) and
  amendments/revocations (`actionType`) are not evaluated yet.
- **Time zone.** D-TRO times are Europe/London wall-clock time; GPS gives UTC. The device must
  convert with BST rules.
- **Vehicle modes.** National limits come from `maxspeed:type` plus road form. Goods-only
  weights (`maxweight:hgv`, D-TRO HGV bans) apply only in Commercial mode; `goods`/`hgv`
  access keys are extracted but not yet used.

### Stage 5 (data delivery)

- **D-TRO:** the bulk dump is 537 MB and was 5 weeks old when fetched (not rebuilt daily). The
  change feed `POST /v1/events` works: 108 events on Sunday 2026-10-11; over 7,178 events
  (5,750 D-TROs) in the week to 2026-10-11 before the 120 requests/min limit stopped paging.
  Keeping a mirror current is about 1,000 `GET /dtros/{id}` calls a day (~10 min/day).
  Speed orders can't be pre-filtered, so every changed record must be fetched.
- **OSM:** Geofabrik daily `.osc` diffs; churn not measured yet.
- **Rights of way:** rowmaps per-council files, about 0.24 MB per county for RB + BOAT
  (West Sussex: 7.1 MB for all four classes); councils update about yearly.
- **Wales layer:** 1,273 features, 12.5 MB, no per-feature dates; re-download and diff each build.
- **Bytes/km baseline:** Overpass raw JSON 11.4 kB/km; the research parquet (all tags plus WKT)
  is 0.6-2.0 kB/km (§10). The device tile format should be well below both.

---

## 10. Footprint and environment

Nothing is on the device yet. PC-side sizes:

| Item | Size |
|---|---|
| Geofabrik extracts (`osm/extracts.csv`) | West Sussex 49.6 MB, East Sussex 21.8 MB, Surrey 43.2 MB, Greater London 129.5 MB, Greater Manchester 51.5 MB, Wales 149.0 MB, Scotland 327.3 MB; total 772 MB |
| D-TRO dump (`data/stage1/dtro_all.csv`) | 537,483,749 bytes, 146,202 records |
| Wales 30 mph layer, all of Wales | 12.5 MB GeoJSON |
| West Sussex rights of way (4 files) | 7.1 MB GeoJSON |

Per-area way parquet (`data/stage1/*_ways.parquet`, measured 2026-10-12; km and ways from
`osm/coverage_by_area_class.csv`):

| Area | Ways | km | Parquet | Bytes/km |
|---|---|---|---|---|
| London Camden/Islington | 15,837 | 876 | 1.58 MB | 1,808 |
| Manchester centre | 11,279 | 602 | 1.11 MB | 1,849 |
| Crawley | 8,918 | 731 | 1.25 MB | 1,707 |
| Horsham | 4,046 | 373 | 0.74 MB | 1,991 |
| Midhurst / Downs | 1,969 | 525 | 0.32 MB | 615 |
| M23/A23 | 10,627 | 1,373 | 1.53 MB | 1,112 |
| A27 | 12,837 | 1,638 | 1.65 MB | 1,007 |
| M25 Surrey | 23,587 | 2,440 | 2.86 MB | 1,170 |
| Cardiff | 12,722 | 1,096 | 1.50 MB | 1,369 |
| Powys rural | 3,719 | 1,185 | 0.71 MB | 600 |
| Edinburgh | 9,189 | 732 | 1.15 MB | 1,573 |
| A9 Perth-Pitlochry | 8,737 | 2,389 | 1.56 MB | 653 |

Environment: Python 3.13.5, osmium 4.3.1, pandas 3.0.6 (both recorded in `osm/extracts.csv`),
shapely 2.2.0, pyproj 3.8.0, pyarrow 26.0.0, requests 2.34.2, pytest 9.1.1; Windows 10.

---

## 11. Open items for the user

1. **Mapillary token.** Register a free client token at mapillary.com/dashboard/developers
   and add `MAPILLARY_TOKEN=` to `.env`. Then run `research/stage1/mapillary_pull.py` to get
   the sign-vs-OSM agreement. The licence for redistributing derived features is unclear, so
   use it for validation only.
2. **Wales 30 mph layer licence.** The metadata says OGL v3, but an OSM forum post says Crown
   copyright. Confirm with data@gov.wales before shipping data derived from it.
3. **National Highways key** (optional). Needed to inspect Road Limits & Features (SRN
   height/width/weight) and the speed-managed-area feed.
4. **UCR vehicular status.** Not in rowmaps; councils' List of Streets or TrailWise2 (members
   only) would be needed. Decide whether Stage 5 should chase it.
5. **Scotland tracks.** There are no definitive maps; most A9-area tracks have no access tag.
   Decide whether untagged Scottish tracks show no X (current classifier) or an X; the
   rights-of-way card suggests treating them as prohibited unless a public road.
6. **D-TRO dump cadence.** The 6 Sep dump was still served on 12 Oct. Stage 5 should plan on
   `/events` and not on a fresh bulk dump.
