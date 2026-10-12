# Speed-Limit-Gauge

A round dashboard gauge for a Land Rover Defender that shows the current UK speed limit, styled as a UK speed-limit roundel.

- **Hardware:** Waveshare ESP32-S3-Touch-AMOLED-1.75 (GPS variant, LC76G), with a microSD card and a LiPo cell. [Waveshare repo and schematic](https://github.com/waveshareteam/ESP32-S3-Touch-AMOLED-1.75)
- **Data:** OpenStreetMap `maxspeed` plus DfT D-TRO traffic orders, with statutory-default inference where no limit is recorded. A full-GB base sits on the SD card and is kept current by small patches downloaded over a phone hotspot.

## Status

Research phase. Nothing is flashable yet.

## Layout

| Path | Contents |
|---|---|
| `Speed Limit Estimator Plan.md` | Investigation brief |
| `docs/specs/` | Design spec |
| `docs/superpowers/plans/` | Implementation plan per stage |
| `research/` | Python research and data pipeline (from Stage 1) |
| `results/<stage>/` | Measured results and notes per stage |

## Data licences

OpenStreetMap data © OpenStreetMap contributors, ODbL. D-TRO data under the Open Government Licence.
