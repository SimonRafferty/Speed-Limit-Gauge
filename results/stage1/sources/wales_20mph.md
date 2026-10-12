# Wales default-20 mph data (DataMapWales)

| Field | Finding |
|---|---|
| What it holds | Welsh Government layers for the default 20 mph limit on restricted roads (in force 17 Sep 2023). On the DataMapWales GeoServer: **`geonode:_30mph_roads_in_wales`** - "a combination of exemptions to the 20mph restricted road speed and existing 30mph roads (as determined by Traffic Regulation Order)", supplied by the 22 highway authorities; `geonode:20mph_la_mask_2` / `_20mph_ha_boundaries_lwm` (authority masks); `national_20mph_restricted` ("Roads that will become 20mph by virtue of legislation", WMS only, published 2022-10-24); map 3342 "Exception roads by Order / 20mph by Order roads". |
| Speed-limit content | Explicit by implication: polygons where the limit is 30 mph inside the default-20 regime. **Geometry is buffered** ("because of inaccuracies within the data, a buffer has been applied"), so features are MultiPolygons around roads, not centre-lines. Attributes are only `id`/`uuid` - no road name, order reference or date. Does not show part-time 20 mph limits. The complementary 20 mph restricted-roads layer is WMS (image) only. |
| Restrictions content | None. |
| Access / closure content | None. (DataMapWales separately hosts at least one council PROW network - Monmouthshire 2024-08-20 - see `rights_of_way.md`.) |
| Geographic coverage | Wales (all 22 authorities). |
| Access method | OGC WFS (GeoServer `https://datamap.gov.wales/geoserver/ows`, `typeNames=geonode:_30mph_roads_in_wales`, GeoJSON/CSV/GML/Shapefile outputs) and WMS; the catalogue page lists file downloads as "not yet available" but the WFS works. |
| Auth | None. |
| Rate limits | None observed (3 requests). |
| Licence | **OGL v3** per the layer's ISO metadata ("Open Government Licence for Public Sector Information"). The portal page shows copyright "Not applicable", and an OSM forum reply claimed it is Crown Copyright / not open; the formal metadata is the better evidence, but confirm with data@gov.wales before redistribution. |
| Freshness | Metadata publication date 2023-09-14; "will continue to be updated as changes are made by Highway Authorities". No per-feature dates, so changes cannot be detected except by re-downloading and diffing. Post-review reversions: revised Welsh Government guidance (July 2024 review, 2025 assessments) led councils to revert roads to 30 mph (e.g. Cardiff 4 of 192 re-assessed roads, Wrexham 52 sections, Swansea 17, Carmarthenshire 11, Bridgend 3 more; Neath Port Talbot none). Each reversion needs a TRO and new signs first; whether these are reflected in the layer is not stated and could not be confirmed. |
| Volume | Whole layer: **1,273 features, 12.5 MB GeoJSON** (BNG). Cardiff bbox 17 features / 345 kB; Powys test bbox 13 features / 60 kB. |
| Format / CRS | GeoJSON / GML / CSV / Shapefile via WFS; native EPSG:27700. |
| Agreement with OSM | [`wales_20mph_agreement.csv`](wales_20mph_agreement.csv) (`research/stage1/source_samples.py`). A non-service/track OSM way is assigned 30 mph if its midpoint is inside a polygon. **Cardiff:** 497 ways matched - 372 agree, 20 OSM higher, 23 OSM lower (OSM says 20), 82 untagged -> **90 % agreement where OSM is tagged**. **Powys rural:** 38 ways - 36 agree, 2 OSM lower -> 95 %. |

## Verdict
**Secondary (Wales), for the 30 mph exceptions.** It is the official, openly licensed
record of which Welsh restricted roads stayed at 30 mph, it is small (12.5 MB for all of
Wales), and it agrees with OSM on ~90-95 % of tagged ways, so it is a good gap-filler for
the 82 untagged Cardiff ways and a check on the 43 that disagree. Combined with the legal
default (restricted road = a system of street lighting with lamps not more than 200 yards apart, unless an order says otherwise -> 20 mph), it lets the
build set 20 vs 30 mph on Welsh urban roads that OSM leaves untagged. Limitations: buffered
polygons need conflation by midpoint, no dates or order references, and it may lag the
2025 reversions - so OSM (where tagged and recently edited) should win on conflicts, and the
layer should be re-diffed on each build.

## Sources
- https://datamap.gov.wales/geoserver/ows?service=WFS&version=2.0.0&request=GetCapabilities (layer list; fetched 2026-10-12)
- https://datamap.gov.wales/showmetadata/xsl/5519 (30mph roads in Wales: description, OGL v3, 2023-09-14)
- https://datamap.gov.wales/layers/geonode:national_20mph_restricted/metadata_detail
- https://datamap.gov.wales/maps/3342 , https://datamap.gov.wales/layers/geonode:20mph_la_mask_2/metadata_detail
- https://www.gov.wales/roads-affected-changes-speed-limit-restricted-roads-user-guide
- https://community.openstreetmap.org/t/uk-updating-wales-speed-limit-changes-for-maxspeed/126130 (licence doubt)
- https://www.itv.com/news/wales/2025-03-07/the-roads-going-back-to-30mph-in-cardiff
- https://news.wrexham.gov.uk/?p=75756 , https://swanseabaynews.com/neath-port-talbot-rules-out-more-20mph-zones-reverting-to-30mph-after-review/
