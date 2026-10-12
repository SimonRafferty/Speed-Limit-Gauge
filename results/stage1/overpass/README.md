# Overpass probe notes

- `probe.csv` rows 1-3 are the first run of `overpass_probe.py`; rows 4-5 (attempt 2) are the single retry of the two failed areas, produced ad hoc about 5 minutes later. `utc_time` and `endpoint` were not recorded for these five rows (the script predates those columns); the endpoint was `https://overpass-api.de/api/interpreter`. Failed rows have no `seconds` (not measured at the time).
- 4 of 5 recorded requests to the public overpass-api.de returned 504 Gateway Timeout. This has no link to bbox size: Horsham's bbox is smaller than London's, which succeeded (about 10 MB in 1.9 s). A gateway timeout points to instance load or slot limits, not query size.
- Implication: a device cannot rely on the public live Overpass endpoint.
