# OSM tracks and motor-vehicle legality: Stage 1 findings

Script: `research/stage1/osm_access.py` (run after `osm_coverage.py` has cached the ways).
Classifier: `research/slg/access.py` `motor_legality(tags)`. Spec §7.1a.

## Classes

`motor_legality` gives one class per OSM way. **It is computed for a private car.**

| Class | Display | Rule |
|---|---|---|
| `prohibited` | red X | explicit `no` on the deciding key (most specific of `motorcar` > `motor_vehicle` > `vehicle` > `access`) |
| `permission` | yellow X | deciding key is `private`, `permit`, `destination`, `customers`, `delivery`, `agricultural` or `forestry`; **or** a `public_footpath` / `public_bridleway` / `restricted_byway` designation with no recognised access value |
| `conditional` | evaluate at drive time | a `*:conditional` on the deciding key or a more specific one (time rules: school streets, bus gates, seasonal TROs) |
| `allowed` | no X | `yes`, `designated`, `permissive`, `discouraged`, or `byway_open_to_all_traffic` with no access value |
| `unknown` | no X | nothing relevant (an ordinary public road), or an ambiguous value |

Details:
- An explicit, recognised access value overrides a designation. For example, a footpath with `access=private` is `permission` and a footpath with `motor_vehicle=no` is `prohibited`.
- A semicolon list counts only when all its parts are in the same class (`agricultural;forestry` is `permission`, `private;yes` is `unknown`).
- **Designation alone is a yellow X, not a red one** (user decision 2026-10-12). A first pass classed it as a red X; 308 of 419 red-X km came from a designation with no access tag. Those ways are often private drives, estate roads or farm lanes that carry a public footpath and that the owner and anyone with lawful authority may drive.
- **Yellow X is a small badge** at the edge of the dial when a speed limit is known (the numeral stays). It is full-size only where no limit is known, because private car parks, drives and except-for-access streets are common. The red X always replaces the numeral.
- **Commercial mode is not handled here.** `goods` and `hgv` are extracted but not consulted; for a van, `goods` takes precedence over `motor_vehicle`. That is Stage 4 work.
- D-TRO orders (closures, prohibitions) are a separate red-X source; see `../dtro/`.

## Files

| File | Content |
|---|---|
| `access_by_area.csv` | per area: track km and ways, % track km with tagged / usable maxspeed, km and ways per class for tracks and all classes |
| `legality_by_area.csv` | long form of the class counts (`scope` = track / all) |
| `designation_by_area.csv` | km and ways per `designation` value, tracks and all classes |
| `permission_by_class_service.csv` | yellow-X km by `highway`, `service=*` value and basis (`access_tag` or `designation_only`) |
| `conditional_values.csv` | every distinct `*:conditional` value with way counts (de-duplicated across areas), to size the time-rule parser |

## Headline numbers (12 test areas, per-area rows summed, overlaps count twice)

| | Red X km | Yellow X km | Conditional km | Allowed km | Unknown km |
|---|---|---|---|---|---|
| All classes | 110 | 2,100 | 33 | 239 | 11,477 |
| Tracks | 69 | 775 | 0 | 86 | 1,688 |

- **Yellow X mostly comes from access tags.** 1,786 km is from access tags and 314 km from a designation alone. By highway class it is mostly `service` (1,059 km: driveways, parking aisles), then `track` (775 km), then `residential` (200 km).
- **Tracks have almost no speed tagging** (0–0.6 % of km usable, except London at 12.5 % of 6.8 km). Tracks use the national limit for the mode (spec §7.1a).
- **No track in any test area carries a `:conditional` rule.** The 58 distinct conditional values are almost all school-street windows, for example `no @ (Mo-Fr 08:30-09:30,15:00-16:00; SH off)`. There are no seasonal green-lane TROs in these areas.

## Coverage headline drop caused by tracks

Adding `highway=track` to the drivable set (Task 9c) put about 2,560 km (de-duplicated) of mostly untagged track into the denominator. The per-area, per-class tables for the other classes are unchanged, but the condition rollups (`../osm/coverage_by_condition.csv`, % of km with a usable limit) dropped:

| Condition | Before tracks | With tracks |
|---|---|---|
| motorway_trunk | 39.5 % | 30.2 % |
| rural | 26.3 % | 16.8 % |
| suburban | 36.2 % | 33.3 % |
| urban | 63.8 % | 62.9 % |

When comparing with earlier figures, quote the per-class numbers or exclude tracks. The device does not need tagging on tracks, because it applies the national limit there.
