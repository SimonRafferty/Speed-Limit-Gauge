# National Highways (England strategic road network)

| Field | Finding |
|---|---|
| What it holds | Data about England's Strategic Road Network (SRN: motorways and most trunk A-roads) via the Digital Lab developer portal APIs, the NTIS DATEX II service, and an ArcGIS open-data portal. Developer-portal APIs: **Road & Lane Closures v2** (planned + unplanned, DATEX II), **Speed Managed Areas v1** (temporary speed limits from planned works and unplanned events, as set on Variable Signs and Signals), **Digital VMS v1** (text on variable message signs), **Road Limits & Features v1** (network features; field-level content not public without signing in), plus a **Diversion Routes** spatial dataset (incl. points of interest such as width restrictions). NTIS DATEX II push service: incidents, journey times, speeds, flows, VMS and **matrix signal settings** (the lane signals that display smart-motorway variable mandatory limits). |
| Speed-limit content | Temporary limits: explicit values (Speed Managed Areas; 0 mph = management ended, `validityStatus` suspended). Smart-motorway variable limits: only as matrix-signal aspects in NTIS (real-time; needs a connected client - not usable on an offline device, and no open archive found). **Permanent limits: no current open dataset.** The public "Network Model" (Feb 2025, OGL) states "speed limit and smart motorway information has been removed pending data validation". The only permanent-limit file found is the superseded 2016 "SRN permanent speed limit start and end points" on data.gov.uk. |
| Restrictions content | Road Limits & Features is the likely home of height/width/weight data for the SRN, but contents are behind the portal sign-in (not verified). Diversion Routes lists width restrictions on diversions. Network Model has lane counts and widths. |
| Access / closure content | Road & Lane Closures v2: planned and (since Mar 2025) unplanned closures, but only where VSS are actually set; lane detail missing elsewhere. |
| Geographic coverage | England SRN only (~4,500 miles); no local roads, no Wales/Scotland (Traffic Wales / Traffic Scotland are separate). |
| Access method | REST APIs (developer.data.nationalhighways.co.uk, subscription key); NTIS: DATEX II push subscription; Open Data Portal (opendata.nationalhighways.co.uk): ArcGIS feature services / downloads. |
| Auth | Free registration + per-API subscription key (accounts deactivated after 12 months unused). NTIS: free but approval against an Acceptable Use and Operational Policy. |
| Rate limits | Developer APIs: **10 calls per key per minute**. |
| Licence | Network Model: OGL v3. Developer APIs: "Terms & Conditions" (licence not named on the FAQ; not verified as OGL). NTIS: Acceptable Use Policy, free of charge. |
| Freshness | Closures v1 was daily; v2 "greater cadence". SMA/closures near-real-time. NTIS pushes within 1 minute of roadside collection. Network Model last updated 2025-02-11. |
| Volume | Not measured (needs a key). SRN-only, small relative to OSM. |
| Format / CRS | DATEX II XML/JSON (closures, NTIS); GeoJSON/ArcGIS feature services (portal). |
| Agreement with OSM | Not measured: no openly downloadable permanent speed-limit layer exists (Network Model removed limits); the live APIs need a subscription key and cover temporary limits only. OSM already has a usable limit on 98-100 % of motorway/trunk km in our areas (`osm/coverage_by_country_class.csv`). |

## Verdict
**Secondary for temporary limits/closures on the SRN; reject as a permanent-limit source.**
OSM already covers motorway/trunk limits well, and National Highways publishes no current
permanent-limit or smart-motorway-limit layer. The free Speed Managed Areas and Road & Lane
Closures APIs are worth a Stage 5 look as a patch feed for roadworks limits and closures on
motorways (complementing D-TRO, which is local-authority-led). Variable mandatory limits on
smart motorways are real-time signal states only; an offline gauge cannot show them and
should show "variable" (OSM `maxspeed:variable` / `maxspeed=signals`) instead. Worth signing
up for a key to inspect Road Limits & Features for height/width/weight on the SRN.

## Sources
- https://developer.data.nationalhighways.co.uk/ (product list)
- https://developer.data.nationalhighways.co.uk/faq (API scope, 10 calls/min, SMA semantics, registration)
- https://ckan.publishing.service.gov.uk/dataset/network-model-public (speed limits removed; OGL)
- https://www.data.gov.uk/dataset/strategic-road-network-permanent-speed-limit-start-and-end-points (2016, superseded)
- https://nationalhighways.co.uk/our-work/digital-data-and-technology/open-data-services/ , https://opendata.nationalhighways.co.uk/
- https://www.trafficengland.com/services-info (NTIS DATEX II: matrix signal settings, free subject to AUP)
- https://www.gov.uk/government/publications/m20-variable-speed-limit-data (FOI, historical VSL data)
