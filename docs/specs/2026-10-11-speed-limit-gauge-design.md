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
| GPS | Quectel LC76G, read over I2C in Waveshare demo 09; pins/address in Waveshare "Mylibrary" pin-macro file — confirm on arrival |
| Other | QMI8658 IMU, PCF85063 RTC, AXP2101 PMIC, TCA9554 IO expander |
| Storage | microSD (TF) slot — confirmed on schematic 2026-10-12. Demo pins GPIO 41 (CS) / 1 (MOSI) / 3 (MISO) / 2 (SCK); check no clash with GPS I2C |
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
| WiFi | Compiled-in credential list (WiFiMulti): user's phone hotspot, home WiFi (updates while parked), car-radio hotspot when SSID/password are found |
| Data | Offline-first: full-GB base on microSD; OSM + D-TRO changes delivered as small pre-conflated patch files from static hosting |

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

Storage: full-GB base tile set on microSD (expected 100–300 MB, to be measured; a high-endurance/industrial card is recommended for under-dash temperatures). 8 MB PSRAM holds the working set of tiles around the vehicle. Onboard flash holds firmware, NVS settings and the version manifest only.

Tiles: fixed grid, cell size chosen in Stage 5 from measured bytes per tile and read latency from SD (expected 2–5 km). Delta-encoded integer geometry, simplified to a tolerance Stage 3 shows is harmless to matching. Each way has a stable id so patches can address it.

Update pipeline (runs on the PC, later possibly a scheduled job; never on the device):

1. **Base build:** full GB from the Geofabrik GB extract → Stage 2 inference → tiles + manifest (base version, build date, per-tile hash).
2. **Patch build** on a regular cadence: OSM changes (Geofabrik daily `.osc` diffs) and D-TRO changes (incremental if the API supports it, else diff of successive bulk dumps) → conflated onto OSM ways on the PC → a small patch file of changed way records (add / replace / delete), numbered sequentially against a base version.
3. Publish base, patches and manifest on static hosting (e.g. GitHub Releases).

The device does not talk to D-TRO directly: conflating BNG geometries onto roads is heavy, and OAuth credentials do not belong on the device.

Device update behaviour:

- On WiFi (home WiFi while parked, phone hotspot, car-radio hotspot): fetch the manifest; download any missing patches in sequence; occasionally download a new base when the manifest says the patch chain is too long.
- Patches are applied as an overlay on read (patch record wins over base record), and periodically merged into rewritten tiles.
- Every write goes to a new file and is renamed into place; the previous base/patch set is kept until the new one verifies (hash). Power loss at ignition-off can never leave a half-written tile in use. The base is otherwise read-only.

Stage 5 measures: GB base size, bytes per tile, SD read latency per tile (on hardware), weekly `maxspeed` churn in OSM and D-TRO (to set patch cadence and expected patch size), and bytes per update.

Failure behaviour: no signal ever → base + last applied patches, with data age reported in the output. SD card missing or unreadable → every reading is "unknown" plus an SD-fault icon; never a guess.

## 7. Firmware and UI (after board arrives)

- LC76G over I2C at the highest supported rate (1–10 Hz, confirm on board).
- `core::update()` in its own task; LVGL 8.4 UI.
- Task watchdog + `esp_reset_reason()` logging (user default for ESP32 firmware).
- LVGL: delete non-current screens on screen switch (Td5 display "many faces" lesson).

UI on 466×466 round AMOLED:

| State | Appearance |
|---|---|
| Known limit | Full-bleed red ring, white disc, bold black numeral (free font close to DfT Transport Medium) |
| National-limit road | The number for the current mode (e.g. 60/70, or 50/60 in Trailer mode) — not the NSL diagonal-bar sign |
| Overspeed | Disc turns JCB yellow (#FCB712, verify on panel) when GPS speed > limit + 2 mph sustained for 2 s; returns to white at or below the limit. Suppressed when basis is held or confidence is low |
| Unknown | Red ring, grey "– –" |
| No GPS fix | Unknown appearance plus small satellite icon |
| Mode pictogram | Small car / van / car+trailer below the numeral |

Interaction: vertical swipe cycles Car → Commercial → Trailer. Selected mode persisted in NVS.

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
- microSD pins vs GPS I2C pins (schematic); SD read latency per tile.
- JCB yellow appearance on AMOLED.
- Car-radio hotspot SSID/password, and whether it provides internet without a tethered phone.
