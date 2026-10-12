# OS Open Roads (Ordnance Survey)

| Field | Finding |
|---|---|
| What it holds | Generalised (1:25,000) link-and-node network of GB roads: `RoadLink`, `RoadNode`, `MotorwayJunction`. Link attributes include `roadClassification` (Motorway, A Road, B Road, Classified Unnumbered, Unclassified, Not Classified, Unknown), `roadFunction` (Motorway, A Road, B Road, Minor Road, Local Road, Local Access Road, Restricted Local Access Road, Secondary Access Road), `formOfWay`, `trunkRoad`, `primaryRoute`, `roadNumber`, name, length, `loop`, start/end nodes. |
| Speed-limit content | **Road form only.** `formOfWay` values: Single Carriageway, Dual Carriageway, Slip Road, Roundabout, Collapsed Dual Carriageway, Guided Busway, Shared Use Carriageway. Dual vs single carriageway drives the national limit (60 vs 70 mph for cars; lower for vans/towing) where OSM only says `GB:nsl_*` or nothing. No speed values. |
| Restrictions content | None. OS states that one-way, width and height restrictions are not in Open Roads (they are in the premium OS MasterMap Highways Network RAMI, which has height/width/length/weight restrictions and average speeds but is licensed - free only to public-sector PSGA members). |
| Access / closure content | None (no access rights, no rights of way; OS paths are a separate product). |
| Geographic coverage | Great Britain. |
| Access method | Bulk download from OS Data Hub / OS Downloads API (no key needed for open products). |
| Auth | None. |
| Rate limits | None relevant (single national files). |
| Licence | Open Government Licence v3 (OS OpenData); attribution "Contains OS data (c) Crown copyright and database right <year>". |
| Freshness | Every six months (April and October). |
| Volume | Zipped national files: GeoPackage ~973 MB (3 layers); Shapefile ~566 MB (up to 156 files in 100 km tiles); GML ~568 MB; vector tiles ~1.3 GB MBTiles. |
| Format / CRS | GeoPackage / Shapefile / GML 3.2.1 / MBTiles; British National Grid (EPSG:27700). |
| Agreement with OSM | Not measured: carries no speed-limit or restriction values, so there is nothing to score with `slg.agreement`. Its role is to supply `formOfWay` (dual carriageway / slip / roundabout) to Stage 2 by conflating links to OSM ways; the national ~1 GB download was not justified for Stage 1. |

## Verdict
**Secondary (Stage 2 input, not limits).** Open Roads is the authoritative open source for
carriageway form and road classification across GB. OSM's `dual_carriageway`/separate-way
modelling and `junction=roundabout` cover much of this, but Open Roads gives a consistent,
OGL-licensed second opinion to decide `nsl_single` vs `nsl_dual` where OSM is untagged, and
road classification (A/B/C/unclassified) for the default-limit inference. OS itself says it
is not suitable for in-vehicle navigation (generalised geometry), so it should be conflated
onto OSM geometry, not shipped as geometry. Twice-yearly releases are enough for road form.

## Sources
- https://docs.os.uk/os-downloads/products/transport-network-portfolio/os-open-roads (overview, update frequency, unsuitability caveats, restrictions not included)
- https://docs.os.uk/os-downloads/products/transport-network-portfolio/os-open-roads/os-open-roads-overview/coverage-and-file-sizes.md
- https://docs.os.uk/os-downloads/products/transport-network-portfolio/os-open-roads/os-open-roads-technical-specification/code-lists-and-enumerations/formofwayvalue.md
- https://www.ordnancesurvey.co.uk/documents/product-support/tech-spec/os-open-roads-technical-specification.pdf (OGL v3, attribution)
- https://docs.os.uk/os-downloads/networks/os-mastermap-highways-network-fundamentals/os-mastermap-highways-network-code-lists/restrictiontypevalue (RAMI restriction types)
