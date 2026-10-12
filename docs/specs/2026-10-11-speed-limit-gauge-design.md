# Speed Limit Gauge — design

Date: 2026-10-11
Status: approved in brainstorming, pending written-spec review
Companion document: `Speed Limit Estimator Plan.md` (the investigation brief; this spec fixes the platform and the decisions it left open)

## 1. Goal

A round dashboard gauge for a Land Rover Defender (Td5, Hard Top) that shows the most likely legal speed limit at the current position, styled as a UK speed-limit roundel. The estimator is developed by running the investigation plan in full (stages 1–6) before the firmware is built.

## 2. Hardware

Waveshare ESP32-S3-Touch-AMOLED-1.75, GPS variant ("-G"). Arrives approx. 2026-10-18; nothing can be flashed until then.

| Item | Detail |
|---|---|
| MCU | ESP32-S3R8, 240 MHz dual-core, 512 KB SRAM |
| Memory | 8 MB PSRAM, 16 MB flash |
| Display | 1.75" 466×466 round AMOLED, CO5300 over QSPI |
| Touch | CST9217 (product page) or FT3168 (wiki) — confirm on arrival |
| GPS | Quectel LC76G on the shared I2C bus (SDA GPIO15, SCL GPIO14), addresses 0x50 (write) / 0x54 (read); reset via TCA9554 P7; UART to GPIO17/18 only if R15/R16 fitted (NC by default). **V_BCKP → R33 (0 Ω) → VCC-RTC = AXP2101 RTCLDO**, which stays alive from the LiPo when the main rails are off, so ephemeris/time/position survive power-off (hot/warm start) |
| Other | QMI8658 IMU, PCF85063 RTC, AXP2101 PMIC, TCA9554 IO expander |
| Storage | microSD (TF) slot — confirmed on schematic. GPIO1 CMD/MOSI, GPIO2 CLK, GPIO3 D0/MISO, GPIO41 D3/CS; Waveshare BSP mounts it as 1-bit SDMMC. No clash with I2C (14/15), display QSPI (4–7, 38, 12, 39) or touch (11, 40) |
| Battery | LiPo on the AXP2101 (J1, MX1.25) — user is fitting one. Board thermistor RP4 (10 kΩ) on the AXP2101 TS pin allows temperature-limited charging |
| Toolchain | esp32 Arduino core 3.1.0, LVGL 8.4.0, SensorLib 0.3.1, XPowersLib 0.2.6 |

## 3. Decisions

| Topic | Decision |
|---|---|
| Scope | Run the plan as written (stages 1–6 with `results/` evidence), then build firmware |
| Implementation split | Python for research/data pipeline (stages 1, 2, 3 bake-off, 5 tile builder); portable C++17 for the device estimator (`core/`), also built on PC for replay and Stage 6 evaluation |
| Repo | Standalone git repo in this folder (nested inside the home-directory repo, like RoboMower). Local only; push only when asked |
| Default vehicle class | Car / dual-purpose. Rationale: Defender Hard Top is 4WD with unladen weight ≤ 2,040 kg, so it meets the dual-purpose definition (C&U Regs 1986 reg. 3) despite N1 tax class |
| Vehicle modes | Car 60/70/70, Commercial (goods ≤ 7.5 t) 50/60/70, Trailer 50/60/60 (single / dual / motorway). Modes change only national-limit defaults, never posted limits |
| Test traces | Synthetic + public OSM traces now; user records real drives (GPX) during the week of 2026-10-11 |
| WiFi | Compiled-in credential list (WiFiMulti): user's phone hotspot, car-radio hotspot when SSID/password are found. No home WiFi: the device is unpowered when parked, so all updates happen over the cellular hotspot while driving |
| Data | Offline-first: full-GB base on microSD; OSM + D-TRO changes delivered as small pre-conflated patch files from static hosting. Device is self-updating; the SD card is loaded from the PC once at install and is not a routine update path (behind the dash) |
| Write safety | SD writes only when GPS speed > 35 mph sustained ~10 s with a valid fix (ignition-off is implausible then); downloads staged in PSRAM until then. Atomic write-then-rename kept as a second layer (cranking brown-outs, connector faults) |
| Firmware | OTA over the hotspot into the spare app slot, activated at next power-on (never reboots while driving), with rollback on failed boot |

## 4. Architecture

```
Speed Limit Gauge/
├─ Speed Limit Estimator Plan.md
├─ docs/specs/                      this design
├─ data/            (git-ignored)   GB OSM .pbf, D-TRO pulls, intermediates
├─ traces/                          user GPX, public and synthetic trace sets
├─ research/        (Python)        stages 1, 2, 3, 5
├─ core/            (C++17)         tile reader, matcher, fusion, update()
│   └─ tests/                       unit tests + Python↔C++ parity
├─ tools/replay/                    PC CLI: replay GPX, print estimate per fix (links core/)
├─ results/<stage>/                 data, scripts, numbers, plots, notes.md per stage
└─ firmware/        (after board)   Arduino sketch: GPS, UI, cache; uses core/ unchanged
```

Data flow:

```
OSM GB extract, D-TRO, other sources
        → research/ pipeline (Stage 2 inference: P(limit) per way and direction)
        → tile builder (Stage 5): versioned compact binary tiles
        → full-GB base tiles on microSD + patch overlay (PSRAM working cache)
GPS fix + vehicle mode → core::update() → {limit | unknown, P(20..70), basis, road, data age}
```

Boundaries:

- **Tile format is the Python↔C++ contract.** Versioned. Holds way geometry, node connectivity (needed for topological candidate survival), road form, P(limit) per direction, flags for conditional/variable limits, tile version and build date.
- **Vehicle mode is an input to `update()`, not baked into tiles.** Tiles store road form (single carriageway / dual / motorway / restricted-lit / country); the core maps road form + mode → national limit.
- **`core/` has no Arduino, filesystem or network dependencies.** Tile bytes arrive via a small reader interface (file on PC; LittleFS/flash or TF on device).

`update()` output, per the plan's Interface section: most likely limit in mph or unknown; probability for 20/30/40/50/60/70; basis (explicitly tagged, traffic order, inferred, held); matched road name/ref; age of data used.

## 5. Investigation (plan stages 1–4)

### Test areas

| Condition | Area |
|---|---|
| Dense urban | Central London (Camden/Islington); central Manchester |
| Suburban | Crawley; Horsham |
| Rural lanes | South Downs / Midhurst, West Sussex |
| Motorway / trunk | M23/A23 Crawley–Brighton; A27 Chichester–Worthing; an M25 section |
| Wales | Cardiff (20 mph default since Sept 2023, including later reversions to 30); rural Powys |
| Scotland | Edinburgh; A9 north of Perth |

### Stage 1 — sources

Assess OSM (primary), D-TRO (documentation and data model until credentials appear in `.env`, then API), Mapillary traffic-sign detections (free token), National Highways (motorway/trunk, variable limits), OS Open Roads (road form/classification), Welsh and Scottish 20 mph datasets, local-authority open data, and anything else found. Per source: coverage by road class and length, freshness, access method, rate limits, licence, bytes per km. Where sources overlap: agreement rate and causes of disagreement.

### Stage 2 — inference

Hide known limits on tagged OSM ways and predict them. Compare: statutory rules from tags; continuity with connected ways; built-up density (buildings/landuse within ~100 m); gradient-boosted model over all attributes; combinations. Deliver confusion matrices per method and road class, calibration plots, and a tagged-vs-untagged bias analysis with re-weighted scores. Output: P(limit) per way and direction.

### Stage 3 — map matching

Baseline: candidate table with topological survival (same way, or shares a node with a previous survivor). Compare with HMM/Viterbi (Newson–Krumm style) and a lightweight particle filter. Trace set: synthetic routed drives with a noise model (Gaussian, multipath bursts, dropouts, tunnels); public OSM GPS traces; user recordings. Hard cases are scripted explicitly: slip-road diverge, parallel service roads, stacked roads/flyovers, roundabouts, tunnels, cold start, limit change mid-way. Metrics: correct-road rate, time and distance to resolve after a diverge, behaviour across way splits.

### Stage 4 — combined estimator (C++)

Fuse match probabilities with per-way limit distributions. Handle `:forward`/`:backward`, `:conditional` and `:variable`. Implement hold / converge / timeout-to-unknown. Tune under the asymmetric cost: reading too high is the costly failure. Parity test against the Python reference on all traces.

### Ground truth

Stage 2 uses OSM-tagged ways as truth. For user recordings, build a hand-checked sample: Street View spot checks at limit transitions plus Mapillary detections, so Stage 6 measures accuracy rather than agreement with OSM.

## 6. Data delivery: offline base + online patches (plan stage 5)

Revised 2026-10-12 after the microSD slot was confirmed. The device is **offline-first**: it never needs a signal to work; connectivity is only used to receive updates.

Card in use (checked 2026-10-12): 16 GB, FAT32 (MBR), 8 KB clusters — FAT32 is what the ESP32 FatFs handles natively, so keep it (no exFAT). Tiles are stored in a small number of large pack files with an index, not one file per tile: fewer directory/FAT updates per write (less to corrupt), no 8 KB-cluster slack per tile, faster open/seek on the ESP32.

Storage: full-GB base tile set on microSD (expected 100–300 MB, to be measured; a high-endurance/industrial card is recommended for under-dash temperatures). 8 MB PSRAM holds the working set of tiles around the vehicle. Onboard flash holds firmware, NVS settings and the version manifest only.

Tiles: fixed grid, cell size chosen in Stage 5 from measured bytes per tile and read latency from SD (expected 2–5 km). Delta-encoded integer geometry, simplified to a tolerance Stage 3 shows is harmless to matching. Each way has a stable id so patches can address it.

Update pipeline (runs on the PC, later possibly a scheduled job; never on the device):

1. **Base build:** full GB from the Geofabrik GB extract → Stage 2 inference → tiles + manifest (base version, build date, per-tile hash).
2. **Patch build** on a regular cadence: OSM changes (Geofabrik daily `.osc` diffs) and D-TRO changes (incremental if the API supports it, else diff of successive bulk dumps) → conflated onto OSM ways on the PC → a small patch file of changed way records (add / replace / delete), numbered sequentially against a base version.
3. Publish base, patches and manifest on static hosting (e.g. GitHub Releases).

The device does not talk to D-TRO directly: conflating BNG geometries onto roads is heavy, and OAuth credentials do not belong on the device.

Device update behaviour (all over the cellular hotspot while driving; the device is unpowered when parked):

- Initial base: copied to the card from the PC once at install. After that the device maintains itself; the card is not routinely removed.
- When a connection is up: fetch the manifest; download missing patches in sequence; download individual replacement tiles where the manifest's per-tile hash differs (a base rebuild arrives as a trickle of changed tiles over many journeys). All downloads are resumable and survive dropouts.
- Downloads land in a PSRAM staging buffer. They are committed to SD only when GPS speed has exceeded 35 mph for ~10 s with a valid fix. A power-off before commit just loses the buffer; it is re-fetched next time.
- Patches are applied as an overlay on read (patch record wins over base record), and periodically merged into rewritten tiles.
- Every write goes to a new file and is renamed into place; the previous tile/patch is kept until the new one verifies (hash). This second layer covers what the speed gate cannot: cranking brown-outs and connector faults.
- Firmware OTA: downloaded in the background into the inactive app partition, marked for boot, takes effect at next power-on; ESP-IDF rollback reverts if the new image fails to confirm itself.
- LiPo hold-up (user is fitting one): covers cranking brown-outs and gives time to finish a write after ignition-off.

Ignition-off handling (required now that a LiPo is fitted, or the board would run until the cell is flat): the AXP2101 VBUS-removal interrupt (AXP_IRQ) triggers an orderly shutdown — finish or abandon the current SD write, unmount SD, display off, then AXP2101 power-off of the main rails. The LC76G keeps its state on V_BCKP (RTCLDO) for a hot/warm start next time. VBUS returning at ignition-on powers the board up. Charging is limited by temperature via the TS thermistor (under-dash heat). Confirm on the bench that RTCLDO stays up after AXP2101 power-off (measure at R33).

Stage 5 measures: GB base size, bytes per tile, SD read latency and write time per tile (on hardware), weekly `maxspeed` churn in OSM and D-TRO (to set patch cadence and expected patch size), bytes per update, and mobile data per month; plus the share of driving time above 35 mph on the user's traces (how much commit opportunity there is).

Failure behaviour: no signal ever → base + last applied patches, with data age reported in the output. SD card missing or unreadable → every reading is "unknown" plus an SD-fault icon; never a guess.

## 7. Firmware and UI (after board arrives)

- LC76G over I2C at the highest supported rate (1–10 Hz, confirm on board). The I2C bus is shared with touch, IMU, RTC, IO expander, AXP2101 and codecs: choose one bus speed all devices support and check NMEA throughput at the chosen rate.
- Measure time to first fix after a power cycle with the LiPo fitted (expected hot/warm < 5 s) versus a cold start (26–35 s).
- `core::update()` in its own task; LVGL 8.4 UI.
- Task watchdog + `esp_reset_reason()` logging (user default for ESP32 firmware).
- LVGL: delete non-current screens on screen switch (Td5 display "many faces" lesson).

UI on 466×466 round AMOLED:

| State | Appearance |
|---|---|
| Known limit | Full-bleed red ring, white disc, bold black numeral (free font close to DfT Transport Medium) |
| National-limit road | The number for the current mode (e.g. 60/70, or 50/60 in Trailer mode) — not the NSL diagonal-bar sign |
| Overspeed | Disc turns JCB yellow (#FCB712, verify on panel) when GPS speed > limit + 2 mph sustained for 2 s; returns to white at or below the limit. Suppressed when basis is held or confidence is low |
| Unknown / uncertain | Red ring, white disc, a "?" in the same font, size and colour as the numeral (user decision 2026-10-12). Shown whenever the estimator outputs unknown, including when candidates disagree past the hold timeout or confidence is too low to commit |
| No GPS fix | "?" plus small satellite icon |
| SD card fault | "?" plus small SD-card icon |
| Mode pictogram | Small car / van / car+trailer below the numeral |

Interaction: vertical swipe cycles Car → Commercial → Trailer. Selected mode persisted in NVS.

### 7.1 Height, width and weight restriction warnings (added 2026-10-12)

The gauge warns when the road ahead has a height, width or weight restriction the current vehicle configuration exceeds.

- **Sources:** OSM `maxheight` / `maxwidth` / `maxweight` (+ `:physical`, `maxweightrating`, `maxweight:hgv`) on ways and on nodes (e.g. `barrier=height_restrictor` at car parks); D-TRO `dimensionMaximum*` orders (height structural / with TRO, width, length, weight environmental / structural). Measured in Stage 1 Tasks 9b and 11b.
- **Applicability:** weight limits that apply only to goods vehicles (OSM `maxweight:hgv`, D-TRO environmental weight limits, lorry-symbol signs) are checked only in Commercial mode; structural / all-vehicle limits in every mode.
- **Look-ahead:** check the matched way and its continuation in the direction of travel for roughly the next 300–500 m (tuned in Stage 4), so the warning comes before the restriction, not at it.
- **Warn only when certain (user decision 2026-10-12: false alarms make it annoying and ignored):**
  - *Data certainty:* only a numeric, parsed restriction value can warn. Placeholders (`default`, `below_default`, `none`, `no_sign`, `no_indications`, `unsigned`) and unparseable values never warn. Restrictions that don't apply to the current mode (e.g. goods-only weight limits outside Commercial mode) never warn.
  - *Match certainty:* warn only when the restriction lies on the confidently matched way or its single unambiguous continuation in the direction of travel. At a fork where only one branch carries the restriction, wait until the matcher has settled on that branch. Accepted trade-off: a warning may arrive just after a junction rather than before it.
- **Display:** flash the restriction roundel itself (UK height/width signs show feet-and-inches, weight signs tonnes), alternating with the speed limit, until the restriction is passed or the route diverges from it.

### 7.1a Tracks / green lanes and "not legal now" (added 2026-10-12)

- **Tracks are in scope:** `highway=track` (byways, green lanes, unsurfaced roads) is matched like any other road, for speed and for restriction warnings.
- **Speed on tracks:** the national single-carriageway limit for the current mode (Car 60, Commercial/Trailer 50) unless a lower limit is tagged or ordered. This is a deliberate user choice; it overrides the "?" behaviour for untagged tracks.
- **Red X — not legal to drive here now:** when the matched way is legally closed to motor vehicles at the current date/time, the dial shows a large red X (same footprint as the numeral) in place of the limit. Sources:
  - D-TRO orders: `motorVehiclesProhibited`, `movementOrderProhibitedAccess`, `miscRoadClosure`, `miscPROWClosure`, honouring their time validity (seasonal and temporary orders, evaluated against GPS date/time). `bannedMovementNoEntry` applies in its direction only.
  - OSM: `motor_vehicle`/`motorcar`/`vehicle`/`access` = `no` and their `:conditional` forms (evaluated now, e.g. seasonal green-lane TROs `motor_vehicle:conditional=no @ (Oct-Apr)`); rights-of-way designations that exclude motor vehicles (`restricted_byway`, `public_bridleway`, `public_footpath`).
  - Not a red X: `access=private` / `destination` / `permissive` (lawful with permission), and anything ambiguous or unparseable.
- Same certainty rule as restrictions: only a definite, currently-in-force prohibition on the confidently matched way shows the red X.
- Applies to any matched way, not only tracks (road closures, timed bus gates, school streets).

### 7.2 Vehicle profile and setup screens (added 2026-10-12)

Profile values (NVS, written only when changed):

| Setting | Default | Step | Shown as |
|---|---|---|---|
| Vehicle height | 2.20 m | 0.05 m | m and ft/in |
| Vehicle width (body, excluding mirrors, as UK width limits are measured) | 1.79 m | 0.05 m | m and ft/in |
| Vehicle gross weight | 3,000 kg | 100 kg | kg and t |
| Trailer height | 2.20 m | 0.05 m | m and ft/in |
| Trailer width | 1.79 m | 0.05 m | m and ft/in |
| Train weight (vehicle + trailer) | 6,500 kg | 100 kg | kg and t |

What each mode checks:

| Mode | Height | Width | Weight | Speed limits (single / dual / motorway) |
|---|---|---|---|---|
| Car | vehicle | vehicle | vehicle gross | 60 / 70 / 70 |
| Commercial | vehicle | vehicle | vehicle gross (also goods-only limits) | 50 / 60 / 70 |
| Trailer | max(vehicle, trailer) | max(vehicle, trailer) | train weight | 50 / 60 / 60 |

Setup interaction:

- **Enter:** long-press the dial (~2 s), only when stationary (GPS speed < ~3 mph); ignored otherwise.
- **Navigate:** one setting per screen; horizontal swipe between screens (vertical swipe remains mode change on the main dial only).
- **Adjust:** large on-screen ▲ / ▼ touch buttons; hold to auto-repeat with acceleration. Value drawn inside a red-ring roundel in the style of the matching sign.
- **Exit:** long-press again, or automatically after ~20 s without a touch or as soon as the vehicle moves (> ~3 mph). Always returns to the speed dial; changes saved to NVS on exit.
- Follow the Td5 display lesson: delete non-current LVGL screens when switching.

## 8. Error handling

- Corrupt tile (hash mismatch): fall back to the previous verified version if present, else that cell reads unknown; flagged for re-download when online.
- SD card missing/unreadable: unknown everywhere, SD-fault icon.
- Failed flash write: previous tile kept (atomic replace).
- GPS dropout: hold last limit, then unknown after timeout (timeout tuned in Stage 4).
- Low-confidence estimate: shown, but overspeed cue suppressed.

## 9. Testing

- Python: unit tests for inference rules and tile builder.
- C++ `core/`: unit tests on hand-built tiles (way splits, forward/backward limits, diverges) and Python↔C++ parity over all traces.
- Stage 6: end-to-end replay of the full trace set through the C++ build with simulated signal loss. Report by road class and overall: share of distance correct / too high / too low / unknown, and distance after a real limit change before the output follows.
- Bench (after arrival): GPX replay injected in place of live GPS on the device, before in-vehicle testing.

## 10. Open items to confirm on hardware

- Touch controller (CST9217 vs FT3168).
- LC76G I2C address, pins, maximum update rate.
- SD read latency per tile; RTCLDO staying up after AXP2101 power-off (R33); TTFF hot vs cold.
- JCB yellow appearance on AMOLED.
- Car-radio hotspot SSID/password, and whether it provides internet without a tethered phone.
