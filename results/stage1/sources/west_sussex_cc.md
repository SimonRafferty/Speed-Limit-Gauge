# West Sussex County Council open data

Covers four of our test areas (Crawley, Horsham, Midhurst/Downs, A27 Chichester-Worthing)
and most of the M23/A23 corridor.

| Field | Finding |
|---|---|
| What it holds | The council "Data store" (OGL) offers potholes and claims, gender pay gap, Transparency Code datasets, commercial/residential land data and links to statistics sites - **no highways network, speed-limit, TRO or restriction datasets**. Separately: a **TRO map browser** (current and historical waiting/parking orders, PDFs); a lorry route network map; TRO consultations and notices (PDF plans, e.g. Southwater/Horsham, Harting 20/30/40 mph orders); and the **public rights of way data** (shapefile, OGL v3), which the council supplies to rowmaps.com. |
| Speed-limit content | None as data. The TRO map browser itself warns that "experimental, temporary or moving TROs, such as speed limits or banned manoeuvres, may not be shown". Speed orders exist only as PDFs/notices. West Sussex (an English traffic authority) should be submitting new orders to D-TRO: in the dump, the Crawley and A27 areas had only temporary (roadworks) speed orders and no permanent ones (`dtro/agreement_by_area.csv`). |
| Restrictions content | Weight restrictions: request/enforcement pages and lorry route map only (no data). Height/width: none found. |
| Access / closure content | PROW network with status Footpath / Bridleway / Restricted Byway / BOAT (via rowmaps; see `rights_of_way.md`). Temporary closures: D-TRO has 56-405 temporary road-closure provisions per West Sussex test area (`dtro/prohibition_counts_by_area.csv`). |
| Geographic coverage | West Sussex. |
| Access method | Web pages / PDF; PROW shapefile by request (redistributed by rowmaps.com). No API, WFS or GIS download found for highways data. |
| Auth | None. |
| Rate limits | n/a |
| Licence | Data store and PROW data: OGL v3 (attribution to West Sussex County Council). TRO PDFs: council copyright. |
| Freshness | PROW shapefile dated 17 Sep 2024 (rowmaps). TRO PDFs updated as orders are made. |
| Volume | PROW (rowmaps GeoJSON, whole county): footpaths 4.9 MB, bridleways 2.0 MB, restricted byways 205 kB, BOATs 30 kB. |
| Format / CRS | PDF; PROW: ESRI Shapefile (BNG), GeoJSON (WGS84) via rowmaps. |
| Agreement with OSM | Speed limits: not measured - no speed-limit data published. PROW: see [`rights_of_way_agreement.csv`](rights_of_way_agreement.csv). |

## Verdict
**Reject for speed limits and restrictions; use its PROW data via `rights_of_way`.**
West Sussex publishes nothing machine-readable on speed limits, height/width/weight
restrictions or TROs beyond PDFs and a parking-only map browser. Its future traffic orders
will arrive through D-TRO, which is the right channel to watch. The council's OGL rights of
way data is useful and is covered in the rights-of-way card.

## Sources
- https://www.westsussex.gov.uk/about-the-council/information-and-data/data-store
- https://www.westsussex.gov.uk/roads-and-travel/traffic-regulation-orders/about-tros/view-tro-restrictions-by-map
- https://www.westsussex.gov.uk/roads-and-travel/traffic-management
- https://www.horsham.gov.uk/planning/planning-applications/speed-limit-changes
- https://westsussex.moderngov.co.uk/documents/s21098/080420tro1a.pdf (example TRO plan PDF)
- https://barry.rowmaps.com/datasets/WS/ (PROW shapefile, OGL v3, 17 Sep 2024)
- https://www.westsussex.gov.uk/land-waste-and-housing/public-paths-and-the-countryside/public-rights-of-way/the-definitive-map-and-statement/
