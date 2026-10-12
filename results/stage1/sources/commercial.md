# Commercial map data (TomTom / HERE / Google) - licence and cost reference only

| Field | Finding |
|---|---|
| What it holds | Proprietary global road networks with speed limits (incl. time/vehicle-dependent), and on enterprise tiers truck attributes (height/width/weight restrictions), access restrictions and real-time traffic. |
| Speed-limit content | Explicit values via per-request APIs: **Google** Roads API Speed Limits; **HERE** Map Attributes API (pre-compiled map content incl. speed limits; also truck restrictions); **TomTom** Snap to Roads (road attributes along a snapped trace; speed-limit field not confirmed here). |
| Restrictions content | HERE/TomTom truck attributes (height/width/weight) on paid tiers; Google: none for this use. |
| Access / closure content | Traffic/incident APIs (real-time, online). No green-lane/PROW legality. |
| Geographic coverage | GB (global). |
| Access method | Online REST per request. Bulk/offline map data (TomTom MultiNet, HERE map content) only under enterprise licences with unpublished prices. |
| Auth | Paid API key / contract. |
| Rate limits | Per plan. TomTom Snap to Roads: up to 5,000 points / 100 km per request on Freemium and Pay-as-you-grow. |
| Licence | Proprietary. Google Maps Platform terms prohibit pre-fetching, caching or storing content outside the service (narrow exceptions, e.g. 30-day geocode caching), which rules out an offline SD-card tile set. Google Speed Limits is only available to customers with an **Asset Tracking** licence. HERE/TomTom offline storage requires an enterprise data licence. |
| Freshness | Vendor-managed, typically weekly-monthly map releases. |
| Volume | n/a (per request). |
| Format / CRS | JSON over HTTPS, WGS84. |
| Agreement with OSM | Not measured: no free access, and licence terms forbid storing results for comparison or offline use. |

**Indicative cost** (as published / reported, Oct 2026 search; confirm with vendors):
- Google Roads API Speed Limits: USD 0.02 per element (0-100k/month), 0.016 (100k-500k); requires an Asset Tracking licence (third-party report: ~USD 10,000/year).
- HERE Map Attributes API: 2,500 transactions/month free, then USD 5.50 per 1,000 (2.5k-200k), falling to 1.10 per 1,000 at high volume.
- TomTom Snap to Roads: USD 2.50 per 1,000 requests.

A device sampling every 5 s for 2 h/day would make ~1,400 calls/day (~42,000/month), i.e. roughly USD 100
(TomTom) / 220 (HERE) / 840 (Google, before the licence fee) per month per vehicle at these rates - and still needs a live data connection.

## Verdict
**Reject (reference point only).** The commercial APIs are online, per-call, and their terms
forbid caching the results for an offline SD-card dataset; bulk offline licences are
enterprise contracts with unpublished pricing, out of scope for a one-off gauge. They show
what "good" looks like (truck restrictions, conditional limits), but the project's open
stack (OSM + D-TRO + official layers) is the only legally and financially viable route.

## Sources
- https://developers.google.com/maps/documentation/roads/speed-limits (Asset Tracking licence requirement)
- https://developers.google.cn/maps/documentation/roads/usage-and-billing?hl=en (Speed Limits per-element pricing)
- https://developers.google.com/maps/solutions/asset-tracking/asset-tracking-plan
- https://blog.afi.io/blog/how-to-get-the-speed-limit-in-google-maps/ (third-party ~USD 10k/year estimate)
- https://cloud.google.com/maps-platform/terms/maps-service-terms/index-20240522 (caching restrictions)
- https://www.here.com/pricing/supplemental-pricing (Map Attributes API tiers)
- https://developer.here.com/pricing
- https://developer.tomtom.com/pricing (Snap to Roads USD 2.50 per 1,000)
- https://docs.tomtom.com/knowledgebase/apis/faq/snap-to-roads-api-faq/what-are-the-limitations-of-the-snap-to-roads-api
