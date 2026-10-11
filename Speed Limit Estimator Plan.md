# Speed limit estimator: investigation and build plan

## Goal

Build an algorithm that takes a stream of GPS fixes and returns the most likely legal speed limit at the current location on UK roads, using whatever information is available. It feeds a dashboard dial. The device has a GPS receiver and an internet connection that drops out, so data can come from online sources and be cached locally.

Integration with the dial hardware is out of scope. The target platform is undecided, so prototype in whatever gets results fastest, keep the core logic portable, and record memory and compute footprint as you go.

## Interface

Input, per fix: timestamp, latitude, longitude, speed, course, and horizontal accuracy where the receiver gives it.

Output, per fix:

- Most likely limit in mph, or "unknown"
- Probability for each plausible limit (20, 30, 40, 50, 60, 70)
- Basis: explicitly tagged, traffic order, inferred, or held from an earlier fix
- Matched road (name or ref) and the age of the data used

Vehicle class is a parameter, defaulting to car, because national speed limits differ by class.

## How to work

This is an investigation as much as a build. Pursue every avenue that looks promising, including ones not listed here, and use your own judgement about where to dig. Failed avenues are useful: keep them.

Store results at the end of each stage in `results/<stage>/` (data, scripts, numbers, plots, and a short notes file saying what was tried and what happened). Carry on to the next stage without waiting for review.

Prefer measured behaviour over reasoning about what should work. Where a choice can be settled by a test on real data, run the test.

## What is already known

**Sources**

- OpenStreetMap `maxspeed` is the main free source. Coverage is near complete on motorways and good on trunk roads, and thin on residential and unclassified roads. Related tags: `maxspeed:type`, `maxspeed:forward` / `backward`, `maxspeed:conditional`, `maxspeed:variable`, `lit`, `highway`, `oneway`, `lanes`.
- DfT D-TRO service: free, OGL, API, England, public beta. Registration is required; Si will put credentials in `.env`. Until then, work from the published documentation and data model at https://d-tro.dft.gov.uk.
- Other candidates to assess: Mapillary traffic sign detections, local authority open datasets, National Highways data, OS open products (for road form and classification), and anything else you find.

**Statutory defaults** (for roads with no explicit limit)

- Restricted roads (street lit): 30 mph in England and Scotland, 20 mph in Wales
- National limit for cars: 60 single carriageway, 70 dual carriageway and motorway
- Many limits exist by statute with no traffic order behind them, so order-based sources will never be complete on their own

**Matching approach to start from**

A candidate table: on each fix, list every road within the error radius; keep only candidates that persist across the last few fixes. It collapses to one road quickly.

Two refinements for OSM:

- OSM ways are split wherever a tag changes, so survival has to be topological: a candidate survives if it is the same way as, or shares a node with, a survivor from the previous fix.
- The dial needs the limit, not the road. If all surviving candidates carry the same limit, output it immediately. If they disagree, hold the previous value until they converge, with a timeout to "unknown".

**Cost of errors**

Showing a limit higher than the real one is the costly failure. Showing one that is too low, or "unknown", is cheap. Tune thresholds with that asymmetry.

## Stages

### 1. Characterise the sources

Pull each source for a set of test areas covering different conditions: dense urban, suburban, rural lanes, motorway and trunk corridors, and at least one area each in Wales and Scotland. Include West Sussex.

For each source, measure coverage by road class and by length, freshness, access method, rate limits, licence terms, and data volume per km of road. Where two sources cover the same road, measure how often they agree and look at why they disagree.

### 2. Infer limits where none is recorded

Find the best way to estimate the limit on a road with no explicit value. Calibrate empirically: take roads that do have a known limit, hide it, predict it from everything else, and score the prediction.

Approaches to compare include statutory rules from tags, continuity with connected and neighbouring roads, built-up density and land use around the road, and learned models over all available attributes. Try combinations.

Produce a confusion matrix per method and per road class. Check how far the tagged roads are representative of the untagged ones, since mappers tag some kinds of road more than others, and say what that does to the scores.

The output of this stage is a probability distribution over limits for any road, with calibration evidence.

### 3. Map matching

Implement the candidate table method above as the baseline. Compare it against other matchers (HMM/Viterbi and anything else worth trying) on the same traces.

Build a trace set from:

- Synthetic drives routed over the OSM graph with realistic noise models, including dropouts and multipath
- Public GPS traces from OpenStreetMap
- Any real recordings found in `traces/`

Make sure the set exercises the hard cases: slip road diverges, parallel service roads, stacked roads and flyovers, roundabouts, tunnels, cold start with no history, and a limit change part-way along a road.

Measure correct-road rate, time and distance to resolve after a diverge, and behaviour across way splits.

### 4. Combined estimator

Fuse the match uncertainty from stage 3 with the limit distribution from stages 1 and 2 into the output defined under Interface. Handle direction-specific, time-conditional and variable limits. Work out the hold, converge and "unknown" behaviour and tune it against the error costs above.

### 5. Online fetch and local cache

Design how data reaches the device: what is requested, when, from where, how much is fetched ahead along the direction of travel, how it is stored, how it is refreshed, and what happens with no signal at start-up and mid-journey.

Compare live queries against public APIs with pre-processed regional data hosted somewhere simple. Measure request latency, bytes per km driven, cache size for a typical home area and for all of Great Britain, and compliance with each source's usage policy.

### 6. End-to-end evaluation

Replay the full trace set through the whole system, including simulated signal loss. Report by road class and overall:

- Share of distance with the correct limit
- Share reading too high, too low, and "unknown"
- Distance travelled after a real limit change before the output follows

## Deliverables

- A library exposing a single update call matching the Interface section
- A command line tool that replays a GPX file and prints the estimate per fix
- The `results/` tree for every stage
- A final write-up covering what was tried, what worked, what failed and why, and the recommended design with its measured performance