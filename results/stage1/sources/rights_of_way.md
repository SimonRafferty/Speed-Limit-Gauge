# Rights of way and green lanes (definitive maps, rowmaps, TrailWise2, TRF, GLASS/LARA, seasonal TROs)

What the gauge needs on green lanes: is a motor vehicle **legally allowed now** (BOAT,
vehicular UCR), **prohibited** (footpath, bridleway, restricted byway, or a TRO - red X), or
**allowed only with permission** (private rights - yellow X)?

| Field | Finding |
|---|---|
| What it holds | **Council definitive map data** (England & Wales): legal status of each public right of way - Footpath, Bridleway, Restricted Byway (RB: no mechanically propelled vehicles), Byway Open to All Traffic (BOAT). **rowmaps.com** (Barry Cornelius) republishes the councils' openly licensed extracts, normalised, as KML/GPX/CSV/GeoJSON. **Unclassified county roads (UCRs)** are not on definitive maps but on councils' List of Streets (shown as ORPA on OS maps). **TrailWise2** (Green Lane Association, GLASS) records BOATs and UCRs with status icons and user condition reports. **TRF Green Road Map**: public web map of where motorcycles may legally ride, enhanced for members. **LARA** (Land Access & Recreation Association): advocacy body; no dataset found. **Seasonal / permanent TROs on byways** are council orders (PDF notices); D-TRO carries only 20 PROW closure provisions so far. |
| Speed-limit content | None. |
| Restrictions content | None (width limits on lanes are rarely recorded; TrailWise2 condition notes are free text). |
| Access / closure content | Explicit legal status for public rights (the core of the red/yellow X). Not included: private vehicular rights, TROs (seasonal closures e.g. 1 Oct/Nov-30 Apr, often **exempting solo motorcycles** - so the X is vehicle-class dependent), temporary closures. UCR vehicular status is not in definitive-map data. Scotland has no definitive maps; access rights under the Land Reform (Scotland) Act 2003 exclude motor vehicles, and core-path data adds nothing on vehicular rights. |
| Geographic coverage | rowmaps: **149 authorities in England and Wales** with open data; missing 16 (several Outer London boroughs, Hartlepool, Luton, North Tyneside, Stoke-on-Trent, Southend-on-Sea, Isles of Scilly); Inner London has no definitive map. TrailWise2 / TRF: England and Wales. Scotland: n/a. |
| Access method | rowmaps: static file downloads per authority (`/datasets/<code>/` original, `/jsons/<code>/` GeoJSON). Councils: varied (shapefile/MapInfo by request, some WFS e.g. DataMapWales hosts Monmouthshire). TrailWise2: members-only web app, no export stated. TRF map: web only ("tracks are not available to download as the network is in a constant state of change"). TROs: council PDF notices; D-TRO for new English orders. |
| Auth | rowmaps/council: none. TrailWise2: Green Lane Association membership. TRF enhanced map: TRF membership. |
| Rate limits | None (static files). |
| Licence | Per authority; rowmaps only includes authorities that released under an open licence (OGL v3 or OS OpenData terms), attribution to each council required. Councils stress the data is "an interpretation of the Definitive Map", not the legal record, and may lag recent orders. TrailWise2 / TRF: proprietary, member use only. |
| Freshness | Per authority; rowmaps requests updates roughly annually (West Sussex shapefile 17 Sep 2024; Wrexham 15 Jan 2025). Site stamped 2025-09-17. Seasonal TROs change yearly; temporary closures (e.g. Suffolk byways closed until Feb 2027) are not in any dataset. |
| Volume | West Sussex (GeoJSON, whole county): footpaths 4.9 MB, bridleways 2.0 MB, restricted byways 205 kB, BOATs 30 kB - vehicle-relevant classes (RB + BOAT) are ~0.24 MB per county. |
| Format / CRS | Shapefile / MapInfo / GML (BNG) from councils; KML/GPX/CSV/GeoJSON (WGS84) from rowmaps; status in a coded `Description` field (`Fo`/`Br`/`Re`/`BO`). |
| Agreement with OSM | [`rights_of_way_agreement.csv`](rights_of_way_agreement.csv), [`rights_of_way_osm_coverage.csv`](rights_of_way_osm_coverage.csv) (`research/stage1/source_samples.py`; West Sussex rowmaps GeoJSON vs cached OSM drivable+track ways in the 5 West Sussex areas; an OSM way takes a PROW's status if >= 50 % of it lies within 10 m; most restrictive wins). Results below. |

**Sample results (West Sussex, rowmaps data of 17 Sep 2024 vs OSM 2026-10-12):**
- **Geometry:** 86-100 % of RB/BOAT length lies within 10 m of an OSM drivable/track way
  (Midhurst RB 31.3 of 33.9 km = 92 %; A27 RB 7.1 of 8.3 km = 86 %; BOATs 100 %), so
  conflation onto OSM ways works.
- **Restricted byways -> OSM legality:** 29.6 km of OSM ways matched; **24.4 km (82 %)
  prohibited** (red X) - all of these carry `designation=restricted_byway`; 2.5 km
  `permission` (`motor_vehicle=private`, correct for private rights); **2.7 km `allowed`**
  (Midhurst: tracks tagged `motorcar=yes`/`access=yes` despite RB designation - OSM tagging
  errors or private-access lanes mis-tagged; they would wrongly show no X).
- **BOATs:** 1.7 km matched. Horsham 0.55 km `allowed` (`designation=byway_open_to_all_traffic`,
  agrees). A27 1.1 km `prohibited`: OSM `designation=public_byway` + `motor_vehicle=no` -
  either a TRO OSM knows about or an OSM error; council data cannot tell which.
- **Footpath/bridleway-matched ways:** 151 of 190 km prohibited, 33 km permission, 5.4 km
  allowed (mostly public roads or private drives that a path follows).
- OSM `designation` is missing on most tracks outside these PROW ways (e.g. Midhurst 141 of
  236 track km have none; `access/designation_by_area.csv`), which is where council data adds
  most.

## Verdict
**Primary for legal status on green lanes (England & Wales), with OSM as geometry.**
Council definitive-map extracts via rowmaps are open (OGL / OS OpenData), cover 149 of ~165
authorities, are tiny for the vehicle-relevant classes, and conflate cleanly onto OSM tracks.
They give the authoritative public status (BOAT vs RB/bridleway/footpath) that OSM lacks on
most tracks, and flag OSM contradictions (2.7 km of RB tagged allowed in one area). Gaps to
fill elsewhere: UCR vehicular status (List of Streets - not in this data; TrailWise2 has it but
is members-only and non-exportable, so validation only, by the user), and TROs/seasonal
closures (council notices now, D-TRO going forward; must be vehicle-class aware because
motorcycles are often exempt). TRF/LARA: reference only. Scotland: no equivalent - treat
off-road tracks as prohibited unless a public road.

## Sources
- https://barry.rowmaps.com/ (149 authorities, licence notes, update practice; stamped 2025-09-17)
- https://barry.rowmaps.com/missing/ (authorities without data)
- https://barry.rowmaps.com/datasets/WS/ , https://barry.rowmaps.com/jsons/WS/ (West Sussex, OGL v3, 17 Sep 2024)
- https://barry.rowmaps.com/datasets/WX/ (Wrexham, OGL v3, BOATs included)
- https://trailwise2.co.uk/ (TrailWise2, Green Lane Association, BOATs + UCRs, members only)
- https://www.trf.org.uk/conservation/green-road-map/ (TRF Green Road Map, not downloadable)
- https://laragb.org/blog/page/6 (LARA on seasonal TROs: 4-wheeled vehicles banned 1 Oct-30 Apr, motorcycles not)
- https://www.nottinghamshire.gov.uk/planning-and-environment/walking-cycling-and-rights-of-way/rights-of-way/news/byway-seasonal-closure-order-2019
- https://consult.nottinghamshire.gov.uk/traffic-regulation-orders/tro-8418-advert-flintham-boat-no-9-prohibiton-of-d/supporting_documents/8418-statement-of-reasonspdf (2025 seasonal BOAT order, solo motorcycles exempt)
- https://barnham-pc.gov.uk/home/consultation-proposal-to (Suffolk byways seasonal TRO consultation, closed until Feb 2027)
- `results/stage1/dtro/prohibition_counts.csv` (20 PROW closure provisions in D-TRO)
- `results/stage1/access/*.csv` (OSM designation/legality on tracks)
