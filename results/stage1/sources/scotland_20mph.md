# Scotland 20 mph (Transport Scotland / councils)

| Field | Finding |
|---|---|
| What it holds | Scotland has no default-20 law; the National Strategy for 20 mph aims to put "all appropriate roads in built-up areas" at 20 mph via council orders (target end-2025, **missed**). Implementation is council by council (Edinburgh citywide network 2016-2018; Dundee; Aberdeen ~700 roads; Aberdeenshire, Fife, Perth & Kinross, Highland, West Dunbartonshire; Glasgow ~3,700 streets in six phases to autumn 2026; Dumfries & Galloway schemes into 2026/27) plus Transport Scotland trunk-road schemes in villages (e.g. A76 Kirkconnell 20 Mar 2026). Many towns are on **temporary / experimental orders that expire in 2027**. |
| Speed-limit content | No national spatial dataset found. Transport Scotland told an FOI (2021) it holds speed-limit information only for the trunk road network; local limits sit with 32 councils as TRO documents and maps. No Spatial Hub (Improvement Service) speed-limit layer found. |
| Restrictions content | None found. |
| Access / closure content | None found (Scottish access rights / core paths are a separate regime; see `rights_of_way.md`). |
| Geographic coverage | Scotland; in practice per council. |
| Access method | None for data: council TRO PDFs and web maps; FOI/EIR. |
| Auth | n/a |
| Rate limits | n/a |
| Licence | n/a (no dataset). Council TRO documents are Crown/council copyright. |
| Freshness | High churn 2024-2027: phased rollouts, and temporary orders up for review/renewal in 2027. |
| Volume | n/a |
| Format / CRS | PDF orders and maps. |
| Agreement with OSM | Not measured: no downloadable dataset. OSM coverage in the Scottish test areas is already the best in GB: usable limit on 94 % of residential km, 72 % unclassified, 100 % trunk (`osm/coverage_by_country_class.csv`). |

## Verdict
**Reject as a data source (monitor).** There is no open Scottish speed-limit layer, and the
20 mph rollout is spread across council TROs, many temporary. OSM is the source for Scotland
and is already well tagged in our test areas; the risk is staleness during the 2025-2027
rollout (Glasgow, Highland, D&G phases, expiring temporary orders), so Stage 5 should
prioritise OSM-diff freshness and Mapillary sign checks in Scottish towns rather than look
for an official layer. Re-check Spatial Hub and Transport Scotland once the strategy
completes.

## Sources
- https://www.gov.scot/publications/foi-202100234414 (Transport Scotland holds speed-limit info for trunk roads only)
- https://www.gov.scot/publications/foi-202600509732/ (national 20 mph roll-out programme FOI)
- https://www.dumfriesandgalloway.gov.uk/news/2026/councillors-consider-next-phase-20mph-programme-progress-continues-across-region (temporary orders expiring 2027)
- https://www.scottishdailyexpress.co.uk/news/scottish-news/glasgow-start-implementation-20mph-speed-36497454.amp (Glasgow ~3,700 streets)
- https://www.gov.scot/publications/foi-202500484568/ (20 mph trunk routes programme 2025)
- https://www.highland.gov.uk/download/meetings/id/82406/item_12_early_adoption_of_20mph_speed_limits_in_highland_update
- https://www.edinburgh.gov.uk/downloads/file/32217/evaluation-of-the-20mph-speed-limit-roll-out-three-years-post-implementation
- https://www.pkc.gov.uk/article/24638/Elected-Member-Briefing-Local-roll-out-of-20mph-national-strategy
