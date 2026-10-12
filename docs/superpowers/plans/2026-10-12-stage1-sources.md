# Stage 1 — Project Scaffolding and Source Characterisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up the Python research environment and produce `results/stage1/`: measured coverage, freshness, access, licence and volume for each speed-limit source over the test areas, plus agreement where sources overlap.

**Architecture:** A small Python package `slg` (speed limit gauge) under `research/` holds pure, unit-tested functions: maxspeed parsing, geometry, area definitions, OSM way extraction, coverage aggregation, source clients and an agreement matcher. Thin scripts under `research/stage1/` call those functions and write CSV, PNG and markdown into `results/stage1/`. Network calls are injected (`session=`) so tests never touch the network.

**Tech Stack:** Python 3.13, pyosmium 4.3, shapely 2.2, pyproj 3.8, pandas 3, pyarrow, matplotlib, requests, python-dotenv, pytest 9.

**Spec:** `docs/specs/2026-10-11-speed-limit-gauge-design.md` §5 (Stage 1) and the plan brief `Speed Limit Estimator Plan.md`.

**Conventions:**
- All commands run from the repo root in Git Bash (Windows).
- Python is always `.venv/Scripts/python` (the repo venv).
- `data/` is git-ignored (large downloads). `results/` is committed.
- Each stage's results folder ends with a `notes.md`: what was tried, what happened, failed avenues included.

---

## File structure

| File | Responsibility |
|---|---|
| `research/requirements.txt` | Pinned Python dependencies |
| `pytest.ini` | Test discovery and import path |
| `research/slg/__init__.py` | Package marker |
| `research/slg/paths.py` | Repo-relative `ROOT`, `DATA`, `RESULTS` |
| `research/slg/areas.py` | `Area` dataclass and the `AREAS` test-area list |
| `research/slg/maxspeed.py` | `parse_maxspeed()` — OSM maxspeed string → kind + mph |
| `research/slg/geo.py` | Haversine and polyline length |
| `research/slg/osm_extract.py` | Geofabrik download and pyosmium way extraction for an area |
| `research/slg/coverage.py` | Annotate ways; coverage, kind and freshness tables |
| `research/slg/overpass.py` | Overpass query builder and latency/bytes probe |
| `research/slg/dtro.py` | D-TRO OAuth client and speed-provision parser |
| `research/slg/mapillary.py` | Mapillary map-feature fetch and speed-sign parsing |
| `research/slg/agreement.py` | Snap point/line limits from another source onto OSM ways and score agreement |
| `research/stage1/osm_coverage.py` | Script: OSM coverage and freshness for all areas |
| `research/stage1/overpass_probe.py` | Script: live-query latency and bytes per km |
| `research/stage1/dtro_pull.py` | Script: D-TRO bulk download, speed provisions, agreement with OSM |
| `research/stage1/mapillary_pull.py` | Script: Mapillary speed signs, agreement with OSM |
| `research/tests/test_*.py` | One test module per `slg` module |
| `results/stage1/...` | Outputs, source cards and `notes.md` |

---

### Task 1: Python environment and package skeleton

**Files:**
- Create: `research/requirements.txt`, `pytest.ini`, `research/slg/__init__.py`, `research/slg/paths.py`, `research/tests/test_paths.py`

- [ ] **Step 1: Write requirements and pytest config**

`research/requirements.txt`:
```
osmium==4.3.1
shapely==2.2.0
pyproj==3.8.0
pandas==3.0.6
pyarrow
matplotlib==3.11.2
requests==2.34.2
python-dotenv==1.2.4
pytest==9.1.1
```

`pytest.ini`:
```ini
[pytest]
testpaths = research/tests
pythonpath = research
```

`research/slg/__init__.py`:
```python
"""Speed Limit Gauge research package."""
```

- [ ] **Step 2: Create the venv and install**

Run:
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -q -r research/requirements.txt && .venv/Scripts/python -c "import osmium, shapely, pyproj, pandas, pyarrow; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Write the failing test**

`research/tests/test_paths.py`:
```python
from slg.paths import ROOT, DATA, RESULTS


def test_root_is_repo_root():
    assert (ROOT / "Speed Limit Estimator Plan.md").exists()
    assert DATA == ROOT / "data"
    assert RESULTS == ROOT / "results"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest research/tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.paths'`

- [ ] **Step 5: Implement**

`research/slg/paths.py`:
```python
"""Repo-relative paths. research/slg/paths.py -> parents[2] is the repo root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest research/tests/test_paths.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add research/requirements.txt pytest.ini research/slg research/tests
git commit -m "chore: research python env and slg package skeleton"
```

---

### Task 2: OSM maxspeed parser

UK OSM conventions: explicit values carry a unit (`30 mph`). A bare number means km/h by OSM's global default, but in GB it is almost always a mapper error for mph, so it is classed `ambiguous` rather than converted. National-limit values (`GB:nsl_single` etc.) have no fixed mph because the number depends on vehicle class; the parser returns the kind only.

**Files:**
- Create: `research/slg/maxspeed.py`, `research/tests/test_maxspeed.py`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_maxspeed.py`:
```python
import math

import pytest

from slg.maxspeed import Parsed, parse_maxspeed


@pytest.mark.parametrize("raw, expected", [
    ("30 mph", Parsed("explicit", 30)),
    ("30mph", Parsed("explicit", 30)),
    (" 20 MPH ", Parsed("explicit", 20)),
    ("48 km/h", Parsed("explicit", 30)),
    ("64 kmh", Parsed("explicit", 40)),
    ("GB:nsl_single", Parsed("nsl_single")),
    ("GB:nsl_dual", Parsed("nsl_dual")),
    ("GB:motorway", Parsed("motorway")),
    ("national", Parsed("national")),
    ("signals", Parsed("variable")),
    ("variable", Parsed("variable")),
    ("30", Parsed("ambiguous")),
    ("30 mph;40 mph", Parsed("multi")),
    ("none", Parsed("none")),
    ("fast", Parsed("unparsed")),
    (None, Parsed("absent")),
    ("", Parsed("absent")),
    (math.nan, Parsed("absent")),
])
def test_parse_maxspeed(raw, expected):
    assert parse_maxspeed(raw) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_maxspeed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.maxspeed'`

- [ ] **Step 3: Implement**

`research/slg/maxspeed.py`:
```python
"""Parse OSM `maxspeed` values as used in Great Britain.

kind values:
  explicit    - a numeric limit with a unit; mph is set
  nsl_single  - GB:nsl_single (national limit, single carriageway)
  nsl_dual    - GB:nsl_dual
  motorway    - GB:motorway
  national    - national limit without carriageway type
  variable    - signals / variable (smart motorway, VMS)
  ambiguous   - bare number; km/h by OSM default but usually meant as mph in GB
  multi       - several values separated by ';'
  none        - 'none' (not a legal UK value)
  unparsed    - anything else
  absent      - no value
"""
import re
from dataclasses import dataclass

STANDARD_MPH = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70)
KMH_PER_MPH = 1.609344

_NATIONAL = {
    "gb:nsl_single": "nsl_single",
    "gb:nsl_dual": "nsl_dual",
    "gb:motorway": "motorway",
    "gb:national": "national",
    "national": "national",
}
_MPH = re.compile(r"^(\d+(?:\.\d+)?)\s*mph$")
_KMH = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:km/h|kmh|kph)$")
_BARE = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class Parsed:
    kind: str
    mph: int | None = None


def snap_mph(mph: float) -> int:
    """Snap a converted value to the nearest standard UK limit if within 1.5 mph."""
    nearest = min(STANDARD_MPH, key=lambda s: abs(s - mph))
    return nearest if abs(nearest - mph) <= 1.5 else round(mph)


def parse_maxspeed(raw) -> Parsed:
    if not isinstance(raw, str) or not raw.strip():
        return Parsed("absent")
    v = raw.strip().lower()
    if ";" in v:
        return Parsed("multi")
    if v in _NATIONAL:
        return Parsed(_NATIONAL[v])
    if v in ("signals", "variable"):
        return Parsed("variable")
    if v == "none":
        return Parsed("none")
    if m := _MPH.match(v):
        return Parsed("explicit", round(float(m[1])))
    if m := _KMH.match(v):
        return Parsed("explicit", snap_mph(float(m[1]) / KMH_PER_MPH))
    if _BARE.match(v):
        return Parsed("ambiguous")
    return Parsed("unparsed")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_maxspeed.py -v`
Expected: 18 passed

- [ ] **Step 5: Commit**

```bash
git add research/slg/maxspeed.py research/tests/test_maxspeed.py
git commit -m "feat(stage1): GB OSM maxspeed parser"
```

---

### Task 3: Geometry helpers

**Files:**
- Create: `research/slg/geo.py`, `research/tests/test_geo.py`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_geo.py`:
```python
import pytest

from slg.geo import haversine_m, line_length_m


def test_one_degree_latitude():
    assert haversine_m(0.0, 51.0, 0.0, 52.0) == pytest.approx(111195, abs=5)


def test_line_length_sums_segments():
    coords = [(0.0, 51.0), (0.0, 51.001), (0.0, 51.002)]
    assert line_length_m(coords) == pytest.approx(2 * 111.195, abs=0.1)


def test_line_length_single_point_is_zero():
    assert line_length_m([(0.0, 51.0)]) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_geo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.geo'`

- [ ] **Step 3: Implement**

`research/slg/geo.py`:
```python
"""Spherical-earth distance helpers (lon/lat in degrees, results in metres)."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6371008.8


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def line_length_m(coords: list[tuple[float, float]]) -> float:
    return sum(haversine_m(*a, *b) for a, b in zip(coords, coords[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_geo.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add research/slg/geo.py research/tests/test_geo.py
git commit -m "feat(stage1): haversine and polyline length"
```

---

### Task 4: Test areas

Each area names the Geofabrik extract(s) that cover it. Boxes that straddle county extracts (M23/A23 into Brighton) list several regions; ways are de-duplicated by id later.

**Files:**
- Create: `research/slg/areas.py`, `research/tests/test_areas.py`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_areas.py`:
```python
from slg.areas import AREAS, Area

GB = (-8.7, 49.8, 1.8, 60.9)


def test_names_unique():
    names = [a.name for a in AREAS]
    assert len(names) == len(set(names))


def test_bboxes_valid_and_in_gb():
    for a in AREAS:
        w, s, e, n = a.bbox
        assert w < e and s < n, a.name
        assert GB[0] <= w and e <= GB[2] and GB[1] <= s and n <= GB[3], a.name


def test_plan_conditions_covered():
    conditions = {a.condition for a in AREAS}
    assert {"urban", "suburban", "rural", "motorway_trunk"} <= conditions
    countries = {a.country for a in AREAS}
    assert {"england", "wales", "scotland"} <= countries
    assert any("west-sussex" in r for a in AREAS for r in a.regions)


def test_contains():
    a = Area("t", "urban", "england", ("x",), (-1.0, 50.0, 0.0, 51.0))
    assert a.contains(-0.5, 50.5)
    assert not a.contains(0.5, 50.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_areas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.areas'`

- [ ] **Step 3: Implement**

`research/slg/areas.py`:
```python
"""Stage 1 test areas. bbox = (min_lon, min_lat, max_lon, max_lat), WGS84.

regions are Geofabrik paths under europe/united-kingdom/.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Area:
    name: str
    condition: str          # urban | suburban | rural | motorway_trunk
    country: str            # england | wales | scotland
    regions: tuple[str, ...]
    bbox: tuple[float, float, float, float]

    def contains(self, lon: float, lat: float) -> bool:
        w, s, e, n = self.bbox
        return w <= lon <= e and s <= lat <= n


AREAS: list[Area] = [
    Area("london_camden_islington", "urban", "england", ("england/greater-london",), (-0.19, 51.52, -0.08, 51.57)),
    Area("manchester_centre", "urban", "england", ("england/greater-manchester",), (-2.27, 53.46, -2.20, 53.50)),
    Area("crawley", "suburban", "england", ("england/west-sussex",), (-0.24, 51.08, -0.13, 51.14)),
    Area("horsham", "suburban", "england", ("england/west-sussex",), (-0.37, 51.04, -0.29, 51.09)),
    Area("midhurst_downs", "rural", "england", ("england/west-sussex",), (-0.80, 50.93, -0.62, 51.02)),
    Area("m23_a23_crawley_brighton", "motorway_trunk", "england",
         ("england/west-sussex", "england/east-sussex"), (-0.22, 50.84, -0.12, 51.10)),
    Area("a27_chichester_worthing", "motorway_trunk", "england", ("england/west-sussex",), (-0.80, 50.81, -0.36, 50.87)),
    Area("m25_surrey", "motorway_trunk", "england", ("england/surrey",), (-0.50, 51.29, -0.30, 51.35)),
    Area("cardiff", "urban", "wales", ("wales",), (-3.25, 51.45, -3.13, 51.52)),
    Area("powys_rural", "rural", "wales", ("wales",), (-3.55, 52.20, -3.25, 52.40)),
    Area("edinburgh", "urban", "scotland", ("scotland",), (-3.25, 55.92, -3.13, 55.97)),
    Area("a9_perth_pitlochry", "motorway_trunk", "scotland", ("scotland",), (-3.80, 56.40, -3.40, 56.72)),
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_areas.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add research/slg/areas.py research/tests/test_areas.py
git commit -m "feat(stage1): test area definitions"
```

---

### Task 5: OSM way extraction

Download sizes measured 2026-10-12: west-sussex 50 MB, east-sussex 22 MB, surrey 43 MB, greater-london 129 MB, greater-manchester 52 MB, wales 149 MB, scotland 327 MB (≈770 MB total).

pyosmium note: the location handler added by `with_locations()` sees every node regardless of filters, so filtering on the `highway` key is safe. The test below proves it.

**Files:**
- Create: `research/slg/osm_extract.py`, `research/tests/test_osm_extract.py`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_osm_extract.py`:
```python
import pytest

from slg.areas import Area
from slg.osm_extract import download_extract, ways_in_area

OSM_XML = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
 <node id="1" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.000" lon="-0.300"/>
 <node id="2" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.001" lon="-0.300"/>
 <node id="3" version="1" timestamp="2024-01-01T00:00:00Z" lat="52.000" lon="-0.300"/>
 <node id="4" version="1" timestamp="2024-01-01T00:00:00Z" lat="52.001" lon="-0.300"/>
 <way id="10" version="3" timestamp="2025-06-01T12:00:00Z">
  <nd ref="1"/><nd ref="2"/>
  <tag k="highway" v="residential"/><tag k="maxspeed" v="20 mph"/><tag k="lit" v="yes"/>
 </way>
 <way id="11" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="1"/><nd ref="2"/><tag k="highway" v="footway"/>
 </way>
 <way id="12" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="3"/><nd ref="4"/><tag k="highway" v="primary"/>
 </way>
</osm>
"""

AREA = Area("t", "urban", "england", ("x",), (-0.31, 50.99, -0.29, 51.01))


def test_ways_in_area_filters_and_measures(tmp_path):
    f = tmp_path / "t.osm"
    f.write_text(OSM_XML, encoding="utf-8")
    rows = ways_in_area(f, AREA)
    assert [r["way_id"] for r in rows] == [10]
    r = rows[0]
    assert r["highway"] == "residential"
    assert r["maxspeed"] == "20 mph"
    assert r["lit"] == "yes"
    assert r["version"] == 3
    assert r["length_m"] == pytest.approx(111.2, abs=0.2)
    assert r["timestamp"].year == 2025
    assert r["wkt"].startswith("LINESTRING")
    assert r["country"] == "england" and r["area"] == "t"


class _Resp:
    def __init__(self, chunks):
        self._chunks = chunks
    def raise_for_status(self):
        pass
    def iter_content(self, chunk_size):
        yield from self._chunks
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class _Session:
    def __init__(self):
        self.calls = 0
    def get(self, url, stream, timeout):
        self.calls += 1
        assert url.endswith("/england/west-sussex-latest.osm.pbf")
        return _Resp([b"ab", b"cd"])


def test_download_extract_writes_once(tmp_path):
    s = _Session()
    p = download_extract("england/west-sussex", dest_dir=tmp_path, session=s)
    assert p.read_bytes() == b"abcd"
    download_extract("england/west-sussex", dest_dir=tmp_path, session=s)
    assert s.calls == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_osm_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.osm_extract'`

- [ ] **Step 3: Implement**

`research/slg/osm_extract.py`:
```python
"""Download Geofabrik extracts and pull drivable ways for a test area."""
from pathlib import Path

import osmium
import requests
from shapely.geometry import LineString

from slg.areas import Area
from slg.geo import line_length_m
from slg.paths import DATA

GEOFABRIK = "https://download.geofabrik.de/europe/united-kingdom/{region}-latest.osm.pbf"

DRIVABLE = frozenset({
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "living_street", "service",
})

TAG_KEYS = (
    "highway", "maxspeed", "maxspeed:forward", "maxspeed:backward", "maxspeed:type",
    "maxspeed:conditional", "maxspeed:variable", "source:maxspeed", "zone:maxspeed",
    "lit", "oneway", "lanes", "dual_carriageway", "junction", "name", "ref",
)


def download_extract(region: str, dest_dir: Path = DATA / "osm", session=requests) -> Path:
    """Fetch a Geofabrik extract once; re-runs reuse the file on disk."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (region.replace("/", "_") + ".osm.pbf")
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    part = dest.with_suffix(".part")
    with session.get(GEOFABRIK.format(region=region), stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    part.replace(dest)
    return dest


def ways_in_area(pbf: Path, area: Area) -> list[dict]:
    """Drivable ways with at least one node inside the area bbox."""
    fp = (osmium.FileProcessor(str(pbf))
          .with_locations()
          .with_filter(osmium.filter.KeyFilter("highway")))
    rows = []
    for obj in fp:
        if not obj.is_way() or obj.tags.get("highway") not in DRIVABLE:
            continue
        coords = [(n.lon, n.lat) for n in obj.nodes if n.location.valid()]
        if len(coords) < 2 or not any(area.contains(lon, lat) for lon, lat in coords):
            continue
        ts = obj.timestamp
        row = {
            "way_id": obj.id,
            "area": area.name,
            "country": area.country,
            "length_m": line_length_m(coords),
            "version": obj.version,
            # Public extracts may strip metadata; an epoch timestamp means "unknown".
            "timestamp": ts if ts.year > 2000 else None,
            "wkt": LineString(coords).wkt,
            "first_node": obj.nodes[0].ref,
            "last_node": obj.nodes[-1].ref,
        }
        for k in TAG_KEYS:
            row[k] = obj.tags.get(k)
        rows.append(row)
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_osm_extract.py -v`
Expected: 2 passed. If `KeyFilter` drops node locations (test fails on way 10 missing), remove the `.with_filter(...)` line; the `is_way()`/`DRIVABLE` check already filters, just more slowly. Record which in `results/stage1/notes.md`.

- [ ] **Step 5: Commit**

```bash
git add research/slg/osm_extract.py research/tests/test_osm_extract.py
git commit -m "feat(stage1): Geofabrik download and drivable-way extraction"
```

---

### Task 6: Coverage, kind and freshness tables

Note for the notes file: a way's timestamp is its last edit of *anything*, not of `maxspeed`. It is an upper bound on the age of the speed tag's last review.

**Files:**
- Create: `research/slg/coverage.py`, `research/tests/test_coverage.py`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_coverage.py`:
```python
from datetime import datetime, timezone

import pandas as pd
import pytest

from slg.coverage import annotate, coverage_by_class, freshness, kind_breakdown


def _df():
    return pd.DataFrame({
        "way_id": [1, 2, 3, 4],
        "area": ["a", "a", "a", "a"],
        "highway": ["residential", "residential", "trunk", "trunk_link"],
        "maxspeed": ["20 mph", None, "GB:nsl_dual", None],
        "maxspeed:forward": [None, None, None, "50 mph"],
        "maxspeed:backward": [None, None, None, None],
        "length_m": [1000.0, 3000.0, 2000.0, 500.0],
        "timestamp": [
            datetime(2026, 1, 1, tzinfo=timezone.utc), None,
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        ],
    })


def test_annotate():
    a = annotate(_df())
    assert list(a["road_class"]) == ["residential", "residential", "trunk", "trunk"]
    assert list(a["ms_kind"]) == ["explicit", "absent", "nsl_dual", "absent"]
    assert list(a["tagged"]) == [True, False, True, True]


def test_coverage_by_class():
    t = coverage_by_class(annotate(_df())).set_index("road_class")
    assert t.loc["residential", "km"] == pytest.approx(4.0)
    assert t.loc["residential", "pct_km_tagged"] == pytest.approx(25.0)
    assert t.loc["residential", "pct_ways_tagged"] == pytest.approx(50.0)
    assert t.loc["trunk", "pct_km_tagged"] == pytest.approx(100.0)


def test_kind_breakdown():
    k = kind_breakdown(annotate(_df()))
    assert k.loc["residential", "explicit"] == pytest.approx(1.0)
    assert k.loc["residential", "absent"] == pytest.approx(3.0)


def test_freshness():
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    f = freshness(annotate(_df()), now).set_index("road_class")
    assert f.loc["trunk", "tagged_ways_with_ts"] == 2
    assert f.loc["trunk", "pct_edited_2y"] == pytest.approx(50.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_coverage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.coverage'`

- [ ] **Step 3: Implement**

`research/slg/coverage.py`:
```python
"""Coverage of speed-limit tagging by road class, by count and by length."""
import pandas as pd

from slg.maxspeed import parse_maxspeed

ROAD_CLASS = {
    "motorway": "motorway", "motorway_link": "motorway",
    "trunk": "trunk", "trunk_link": "trunk",
    "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary",
    "tertiary": "tertiary", "tertiary_link": "tertiary",
    "unclassified": "unclassified",
    "residential": "residential", "living_street": "residential",
    "service": "service",
}


def annotate(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["road_class"] = out["highway"].map(ROAD_CLASS)
    parsed = out["maxspeed"].map(parse_maxspeed)
    out["ms_kind"] = parsed.map(lambda p: p.kind)
    out["ms_mph"] = parsed.map(lambda p: p.mph).astype("Int64")
    directional = out["maxspeed:forward"].notna() | out["maxspeed:backward"].notna()
    out["tagged"] = (out["ms_kind"] != "absent") | directional
    return out


def coverage_by_class(df: pd.DataFrame, by: tuple[str, ...] = ("road_class",)) -> pd.DataFrame:
    g = df.assign(
        km=df["length_m"] / 1000,
        km_tagged=df["length_m"].where(df["tagged"], 0.0) / 1000,
    )
    t = (g.groupby(list(by), dropna=False)
          .agg(ways=("way_id", "count"), ways_tagged=("tagged", "sum"),
               km=("km", "sum"), km_tagged=("km_tagged", "sum"))
          .reset_index())
    t["pct_km_tagged"] = 100 * t["km_tagged"] / t["km"]
    t["pct_ways_tagged"] = 100 * t["ways_tagged"] / t["ways"]
    return t


def kind_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """km of road per road_class x maxspeed kind."""
    return df.pivot_table(index="road_class", columns="ms_kind", values="length_m",
                          aggfunc="sum", fill_value=0.0) / 1000


def freshness(df: pd.DataFrame, now) -> pd.DataFrame:
    t = df[df["tagged"] & df["timestamp"].notna()].copy()
    t["age_days"] = (now - pd.to_datetime(t["timestamp"], utc=True)).dt.days
    return (t.groupby("road_class")
             .agg(tagged_ways_with_ts=("age_days", "count"),
                  median_age_days=("age_days", "median"),
                  pct_edited_2y=("age_days", lambda a: 100 * (a <= 730).mean()))
             .reset_index())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_coverage.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add research/slg/coverage.py research/tests/test_coverage.py
git commit -m "feat(stage1): coverage, kind and freshness tables"
```

---

### Task 7: Run OSM coverage over all test areas

**Files:**
- Create: `research/stage1/osm_coverage.py`
- Output: `data/stage1/<area>_ways.parquet`, `results/stage1/osm/*.csv`, `results/stage1/osm/coverage_pct_km.png`

- [ ] **Step 1: Write the script**

`research/stage1/osm_coverage.py`:
```python
"""Stage 1: OSM maxspeed coverage and freshness for every test area.

Run: .venv/Scripts/python research/stage1/osm_coverage.py
"""
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from slg.areas import AREAS
from slg.coverage import annotate, coverage_by_class, freshness, kind_breakdown
from slg.osm_extract import download_extract, ways_in_area
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "osm"
WAYS = DATA / "stage1"


def area_ways(area) -> pd.DataFrame:
    cache = WAYS / f"{area.name}_ways.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows = []
    for region in area.regions:
        rows += ways_in_area(download_extract(region), area)
    df = pd.DataFrame(rows).drop_duplicates("way_id")
    WAYS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    frames = []
    for area in AREAS:
        df = annotate(area_ways(area))
        df["condition"] = area.condition
        frames.append(df)
        print(f"{area.name}: {len(df)} ways, {df['length_m'].sum() / 1000:.0f} km")
    ways = pd.concat(frames, ignore_index=True)

    coverage_by_class(ways, ("area", "road_class")).to_csv(OUT / "coverage_by_area_class.csv", index=False)
    coverage_by_class(ways, ("country", "road_class")).to_csv(OUT / "coverage_by_country_class.csv", index=False)
    coverage_by_class(ways, ("condition",)).to_csv(OUT / "coverage_by_condition.csv", index=False)
    kind_breakdown(ways).to_csv(OUT / "kind_km_by_class.csv")
    freshness(ways, now).to_csv(OUT / "freshness_by_class.csv", index=False)
    (ways[ways["ms_kind"].isin(["ambiguous", "unparsed", "none", "multi", "nonstandard"])]
        [["way_id", "area", "highway", "maxspeed"]]
        .to_csv(OUT / "odd_values.csv", index=False))
    ways["maxspeed:type"].value_counts(dropna=False).to_csv(OUT / "maxspeed_type_counts.csv")
    ways["source:maxspeed"].value_counts(dropna=False).to_csv(OUT / "source_maxspeed_counts.csv")

    pivot = coverage_by_class(ways, ("area", "road_class")).pivot(
        index="area", columns="road_class", values="pct_km_tagged")
    ax = pivot.plot.barh(figsize=(11, 8), width=0.85)
    ax.set_xlabel("% of km with maxspeed (any form)")
    ax.set_title("OSM maxspeed coverage by area and road class")
    plt.tight_layout()
    plt.savefig(OUT / "coverage_pct_km.png", dpi=110)
    print("written", OUT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it (downloads ≈770 MB on first run)**

Run: `.venv/Scripts/python research/stage1/osm_coverage.py`
Expected: one line per area like `crawley: 4123 ways, 512 km`, then `written ...results\stage1\osm`. Run in the background if the download is slow; re-runs reuse `data/`.

- [ ] **Step 3: Sanity-check the numbers**

Open `results/stage1/osm/coverage_by_area_class.csv`. Expected pattern from the brief: motorway near 100 %, trunk high, residential/unclassified much lower. If motorway coverage is under 90 %, inspect `odd_values.csv` and the `maxspeed_type_counts.csv` before trusting the run: a parse bug is likelier than a data gap.

- [ ] **Step 4: Commit**

```bash
git add research/stage1/osm_coverage.py results/stage1/osm
git commit -m "results(stage1): OSM coverage and freshness for test areas"
```

---

### Task 8: Overpass live-query probe

Measures what a live query costs, as input to the Stage 5 hosting decision. Three probes at most, 10 s apart, within the Overpass usage policy.

**Files:**
- Create: `research/slg/overpass.py`, `research/tests/test_overpass.py`, `research/stage1/overpass_probe.py`
- Output: `results/stage1/overpass/probe.csv`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_overpass.py`:
```python
import pytest

from slg.overpass import build_query, km_in_response


def test_build_query_uses_south_west_north_east_order():
    q = build_query((-0.37, 51.04, -0.29, 51.09))
    assert "(51.04,-0.37,51.09,-0.29)" in q
    assert "out tags geom" in q
    assert "motorway" in q and "residential" in q


def test_km_in_response():
    resp = {"elements": [
        {"type": "way", "geometry": [{"lat": 51.0, "lon": 0.0}, {"lat": 51.001, "lon": 0.0}]},
        {"type": "way", "geometry": [{"lat": 51.0, "lon": 0.0}, {"lat": 51.002, "lon": 0.0}]},
    ]}
    assert km_in_response(resp) == pytest.approx(0.3336, abs=0.001)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_overpass.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.overpass'`

- [ ] **Step 3: Implement the module**

`research/slg/overpass.py`:
```python
"""Overpass API probe: latency and bytes per km for a live maxspeed query."""
import time

import requests

from slg.geo import line_length_m
from slg.osm_extract import DRIVABLE

ENDPOINT = "https://overpass-api.de/api/interpreter"


def build_query(bbox: tuple[float, float, float, float]) -> str:
    w, s, e, n = bbox
    highways = "|".join(sorted(DRIVABLE))
    return (f'[out:json][timeout:60];'
            f'way["highway"~"^({highways})$"]({s},{w},{n},{e});'
            f'out tags geom;')


def km_in_response(resp: dict) -> float:
    total = 0.0
    for el in resp.get("elements", []):
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        total += line_length_m(coords)
    return total / 1000


def probe(bbox, session=requests) -> dict:
    t0 = time.perf_counter()
    r = session.post(ENDPOINT, data={"data": build_query(bbox)}, timeout=90,
                     headers={"User-Agent": "speed-limit-gauge-research/0.1"})
    seconds = time.perf_counter() - t0
    r.raise_for_status()
    body = r.content
    km = km_in_response(r.json())
    return {"bytes": len(body), "seconds": round(seconds, 2), "km": round(km, 1),
            "ways": len(r.json().get("elements", [])),
            "bytes_per_km": round(len(body) / km) if km else None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_overpass.py -v`
Expected: 2 passed

- [ ] **Step 5: Write and run the probe script**

`research/stage1/overpass_probe.py`:
```python
"""Stage 1: time three live Overpass queries (urban, suburban, rural).

Run: .venv/Scripts/python research/stage1/overpass_probe.py
"""
import time

import pandas as pd

from slg.areas import AREAS
from slg.overpass import probe
from slg.paths import RESULTS

PROBE_AREAS = ("london_camden_islington", "horsham", "midhurst_downs")


def main():
    out = RESULTS / "stage1" / "overpass"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, area in enumerate(a for a in AREAS if a.name in PROBE_AREAS):
        if i:
            time.sleep(10)
        res = probe(area.bbox)
        res["area"] = area.name
        rows.append(res)
        print(res)
    pd.DataFrame(rows).to_csv(out / "probe.csv", index=False)


if __name__ == "__main__":
    main()
```

Run: `.venv/Scripts/python research/stage1/overpass_probe.py`
Expected: three dict lines with `bytes_per_km` in the low tens of kB. A 429 or 504 is itself a finding: record it in notes, wait 5 minutes, retry once.

- [ ] **Step 6: Commit**

```bash
git add research/slg/overpass.py research/tests/test_overpass.py research/stage1/overpass_probe.py results/stage1/overpass
git commit -m "feat(stage1): Overpass latency and bytes-per-km probe"
```

---

### Task 9: Agreement matcher (shared by D-TRO, Mapillary and any later source)

Projects everything to British National Grid (EPSG:27700, metres) so distances are honest, then snaps each foreign limit to the nearest OSM way within a tolerance.

**Files:**
- Create: `research/slg/agreement.py`, `research/tests/test_agreement.py`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_agreement.py`:
```python
from shapely.geometry import LineString, Point

from slg.agreement import compare, snap_to_ways, to_bng


def test_to_bng_round_numbers():
    p = to_bng(Point(-0.1276, 51.5072))   # Trafalgar Square-ish
    assert 529000 < p.x < 531000 and 180000 < p.y < 181000


def test_snap_to_ways_respects_tolerance():
    ways = [LineString([(0, 0), (100, 0)]), LineString([(0, 50), (100, 50)])]
    feats = [Point(50, 5), Point(50, 30), Point(50, 48)]
    pairs = snap_to_ways(feats, ways, max_m=10)
    assert pairs == [(0, 0, 5.0), (2, 1, 2.0)]


def test_compare_counts():
    rows = [
        {"osm_kind": "explicit", "osm_mph": 30, "src_mph": 30},
        {"osm_kind": "explicit", "osm_mph": 40, "src_mph": 30},
        {"osm_kind": "explicit", "osm_mph": 20, "src_mph": 30},
        {"osm_kind": "absent", "osm_mph": None, "src_mph": 30},
        {"osm_kind": "nsl_single", "osm_mph": None, "src_mph": 60},
    ]
    c = compare(rows)
    assert c == {"n": 5, "agree": 1, "osm_higher": 1, "osm_lower": 1,
                 "osm_untagged": 1, "osm_national": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_agreement.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.agreement'`

- [ ] **Step 3: Implement**

`research/slg/agreement.py`:
```python
"""Snap another source's limits onto OSM ways and score agreement."""
from pyproj import Transformer
from shapely import STRtree
from shapely.ops import transform

_TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)


def to_bng(geom):
    """WGS84 lon/lat geometry -> British National Grid metres."""
    return transform(_TO_BNG.transform, geom)


def snap_to_ways(features, ways, max_m: float) -> list[tuple[int, int, float]]:
    """For each feature, the nearest way within max_m: (feature_idx, way_idx, distance_m).

    All geometries must already be in a metric CRS (BNG).
    """
    tree = STRtree(ways)
    idx, dist = tree.query_nearest(features, max_distance=max_m, return_distance=True,
                                   all_matches=False)
    return [(int(f), int(w), round(float(d), 2)) for (f, w), d in zip(idx.T, dist)]


def compare(rows: list[dict]) -> dict:
    """rows: osm_kind, osm_mph (or None), src_mph. National-limit OSM kinds are
    counted separately because their mph depends on vehicle class."""
    c = {"n": 0, "agree": 0, "osm_higher": 0, "osm_lower": 0, "osm_untagged": 0, "osm_national": 0}
    for r in rows:
        c["n"] += 1
        if r["osm_kind"] in ("nsl_single", "nsl_dual", "motorway", "national"):
            c["osm_national"] += 1
        elif r["osm_mph"] is None:
            c["osm_untagged"] += 1
        elif r["osm_mph"] == r["src_mph"]:
            c["agree"] += 1
        elif r["osm_mph"] > r["src_mph"]:
            c["osm_higher"] += 1
        else:
            c["osm_lower"] += 1
    return c
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_agreement.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add research/slg/agreement.py research/tests/test_agreement.py
git commit -m "feat(stage1): source-vs-OSM agreement matcher"
```

---

### Task 10: D-TRO client and speed-provision parser

API facts (from `github.com/pa-digital/dft-dtro-api-docs`, `api_quickstart.rst` and `a_tour_of_the_data_model.rst`):
- Bases: integration `https://dtro-integration.dft.gov.uk/v1`, production `https://dtro.dft.gov.uk/v1`.
- Token: `POST {base}/oauth-generator`, HTTP basic auth (client id, secret), form body `grant_type=client_credentials`; JSON response has `access_token` and `expires_in` (string, seconds, ~1799).
- `GET {base}/dtros/all` returns a JSON string: a signed URL to a CSV of all D-TROs, valid 60 minutes.
- `GET {base}/dtros/{id}` returns one record: `{"id", "schemaVersion", "data": {"source": {"provision": [...]}}}`.
- Schema v5+: `regulation.regulationType` is `speedLimitValueBased` (object `speedLimitValueBased` with `mphValue`, `nature`, `type` ∈ maximumSpeedLimit / minimumSpeedLimit / nationalSpeedLimitWellLitStreetDefault) or `speedLimitProfileBased` (object with `type` ∈ nationalSpeedLimitDualCarriageway / SingleCarriageway / Motorway / nationalSpeedLimit). Pre-v5 records put `regulationType` inside `generalRegulation`.
- Geometry strings are EWKT in BNG: `"SRID=27700;LINESTRING(...)"`; polygons are allowed for speed limits, points are not (v5).

Credentials are read from `.env` (`DTRO_CLIENT_ID`, `DTRO_CLIENT_SECRET`, `DTRO_ENV`). Approval is pending, so the script must exit cleanly without them.

**Files:**
- Create: `research/slg/dtro.py`, `research/tests/test_dtro.py`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_dtro.py`:
```python
from slg.dtro import DtroClient, speed_provisions

RECORD_V5 = {
    "id": "abc",
    "schemaVersion": "5.0.0",
    "data": {"source": {"provision": [
        {"reference": "P1", "actionType": "new",
         "regulation": [{"regulationType": "speedLimitValueBased", "isDynamic": False,
                         "speedLimitValueBased": {"mphValue": 20, "type": "maximumSpeedLimit",
                                                  "nature": "permanent"}}],
         "regulatedPlace": [{"linearGeometry": {
             "linestring": "SRID=27700;LINESTRING(444284 333253, 444300 333260)"}}]},
        {"reference": "P2", "actionType": "new",
         "regulation": [{"regulationType": "kerbsideLimitedWaiting"}],
         "regulatedPlace": []},
        {"reference": "P3", "actionType": "new",
         "regulation": [{"regulationType": "speedLimitProfileBased",
                         "speedLimitProfileBased": {"type": "nationalSpeedLimitSingleCarriageway"}}],
         "regulatedPlace": [{"polygon": {"polygon": "SRID=27700;POLYGON((0 0, 1 0, 1 1, 0 0))"}}]},
    ]}},
}

RECORD_V3 = {
    "id": "old", "schemaVersion": "3.3.0",
    "data": {"source": {"provision": [
        {"reference": "Q1", "regulation": [{"generalRegulation": {"regulationType": "speedLimitValueBased"},
                                            "speedLimitValueBased": {"mphValue": 30, "type": "maximumSpeedLimit"}}],
         "regulatedPlace": []},
    ]}},
}


def test_speed_provisions_v5():
    out = speed_provisions(RECORD_V5)
    assert [p["provision_ref"] for p in out] == ["P1", "P3"]
    assert out[0]["mph"] == 20 and out[0]["limit_type"] == "maximumSpeedLimit"
    assert out[0]["geometries"] == ["SRID=27700;LINESTRING(444284 333253, 444300 333260)"]
    assert out[1]["mph"] is None and out[1]["limit_type"] == "nationalSpeedLimitSingleCarriageway"
    assert out[1]["geometries"][0].startswith("SRID=27700;POLYGON")


def test_speed_provisions_pre_v5():
    out = speed_provisions(RECORD_V3)
    assert out[0]["mph"] == 30 and out[0]["schema_version"] == "3.3.0"


class _Resp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


class _Session:
    def __init__(self):
        self.posts = 0
        self.gets = []
    def post(self, url, auth, data, timeout):
        self.posts += 1
        assert url == "https://dtro-integration.dft.gov.uk/v1/oauth-generator"
        assert auth == ("id", "secret") and data == {"grant_type": "client_credentials"}
        return _Resp({"access_token": "tok", "expires_in": "1799"})
    def get(self, url, headers, timeout):
        self.gets.append((url, headers["Authorization"]))
        return _Resp("https://storage.example/all.csv")


def test_client_caches_token_and_gets_all_url():
    s = _Session()
    c = DtroClient("id", "secret", env="integration", session=s)
    assert c.all_records_url() == "https://storage.example/all.csv"
    c.all_records_url()
    assert s.posts == 1
    assert s.gets[0] == ("https://dtro-integration.dft.gov.uk/v1/dtros/all", "Bearer tok")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_dtro.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.dtro'`

- [ ] **Step 3: Implement**

`research/slg/dtro.py`:
```python
"""DfT D-TRO consumer client (OAuth2 client credentials) and speed-limit parser."""
import os
import time

import requests
from dotenv import load_dotenv

from slg.paths import ROOT

BASES = {
    "integration": "https://dtro-integration.dft.gov.uk/v1",
    "production": "https://dtro.dft.gov.uk/v1",
}
SPEED_TYPES = ("speedLimitValueBased", "speedLimitProfileBased")


class DtroClient:
    def __init__(self, client_id: str, client_secret: str, env: str = "integration", session=requests):
        self.base = BASES[env]
        self._auth = (client_id, client_secret)
        self._session = session
        self._token = None
        self._expires = 0.0

    def token(self) -> str:
        # Refresh a minute early so a long download never starts with a dying token.
        if self._token is None or time.time() > self._expires - 60:
            r = self._session.post(f"{self.base}/oauth-generator", auth=self._auth,
                                   data={"grant_type": "client_credentials"}, timeout=30)
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._expires = time.time() + float(body.get("expires_in", 1799))
        return self._token

    def _get(self, path: str):
        r = self._session.get(f"{self.base}{path}",
                              headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
        r.raise_for_status()
        return r.json()

    def all_records_url(self) -> str:
        """Signed URL (valid 60 min) to a CSV of every published D-TRO."""
        return self._get("/dtros/all")

    def get(self, dtro_id: str) -> dict:
        return self._get(f"/dtros/{dtro_id}")


def from_env(session=requests) -> DtroClient | None:
    load_dotenv(ROOT / ".env")
    cid, secret = os.getenv("DTRO_CLIENT_ID"), os.getenv("DTRO_CLIENT_SECRET")
    if not cid or not secret:
        return None
    return DtroClient(cid, secret, os.getenv("DTRO_ENV", "integration"), session)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def speed_provisions(record: dict) -> list[dict]:
    """One row per speed-limit regulation in a D-TRO record (schema v3 and v5 shapes)."""
    source = record.get("data", {}).get("source", {})
    out = []
    for prov in source.get("provision", []):
        for reg in prov.get("regulation", []):
            rtype = reg.get("regulationType") or reg.get("generalRegulation", {}).get("regulationType")
            if rtype not in SPEED_TYPES:
                continue
            detail = reg.get(rtype, {})
            out.append({
                "dtro_id": record.get("id"),
                "schema_version": record.get("schemaVersion"),
                "provision_ref": prov.get("reference"),
                "action": prov.get("actionType"),
                "regulation_type": rtype,
                "limit_type": detail.get("type"),
                "mph": detail.get("mphValue"),
                "nature": detail.get("nature"),
                "is_dynamic": reg.get("isDynamic"),
                "geometries": [s for s in _strings(prov.get("regulatedPlace", []))
                               if s.startswith("SRID=")],
            })
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_dtro.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add research/slg/dtro.py research/tests/test_dtro.py
git commit -m "feat(stage1): D-TRO OAuth client and speed-provision parser"
```

---

### Task 11: D-TRO pull and agreement script

The CSV layout of `/dtros/all` is not documented. The script saves the raw CSV, prints its columns, and locates the JSON payload column by content (the first column whose values parse as JSON objects containing `"provision"`).

**Files:**
- Create: `research/stage1/dtro_pull.py`
- Output: `data/stage1/dtro_all.csv`, `results/stage1/dtro/*.csv`

- [ ] **Step 1: Write the script**

`research/stage1/dtro_pull.py`:
```python
"""Stage 1: pull all D-TROs, extract speed provisions, compare with OSM.

Run: .venv/Scripts/python research/stage1/dtro_pull.py
Needs DTRO_CLIENT_ID / DTRO_CLIENT_SECRET in .env; exits cleanly without them.
"""
import csv
import json
import sys

import pandas as pd
import requests
from shapely import wkt as shapely_wkt

from slg.agreement import compare, snap_to_ways, to_bng
from slg.areas import AREAS
from slg.coverage import annotate
from slg.dtro import from_env, speed_provisions
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "dtro"
RAW = DATA / "stage1" / "dtro_all.csv"


def download_all(client) -> None:
    url = client.all_records_url()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(RAW, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def records():
    csv.field_size_limit(sys.maxsize if sys.maxsize < 2**31 else 2**31 - 1)
    with open(RAW, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        print("columns:", reader.fieldnames)
        for row in reader:
            for value in row.values():
                if value and value.lstrip().startswith("{") and '"provision"' in value:
                    rec = json.loads(value)
                    rec.setdefault("id", row.get("id") or row.get("Id"))
                    yield rec
                    break


def main():
    client = from_env()
    if client is None:
        print("No D-TRO credentials in .env yet - skipping (documentation-only assessment).")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    download_all(client)
    n_records, provs = 0, []
    for rec in records():
        n_records += 1
        provs += speed_provisions(rec)
    df = pd.DataFrame(provs)
    print(f"{n_records} D-TRO records, {len(df)} speed provisions")
    pd.DataFrame([{"records": n_records, "speed_provisions": len(df),
                   "raw_bytes": RAW.stat().st_size}]).to_csv(OUT / "volume.csv", index=False)
    if df.empty:
        return
    df.drop(columns="geometries").to_csv(OUT / "speed_provisions.csv", index=False)
    df.groupby(["regulation_type", "limit_type"], dropna=False).size().to_csv(OUT / "type_counts.csv")

    # Agreement: midpoint of each OSM way vs D-TRO geometries within 15 m.
    geoms, mphs = [], []
    for _, p in df.iterrows():
        for g in p["geometries"]:
            geoms.append(shapely_wkt.loads(g.split(";", 1)[1]))
            mphs.append(p["mph"])
    results = []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            continue
        ways = annotate(pd.read_parquet(cache))
        mids = [to_bng(shapely_wkt.loads(w)).interpolate(0.5, normalized=True) for w in ways["wkt"]]
        pairs = snap_to_ways(mids, geoms, max_m=15)
        rows = [{"osm_kind": ways.iloc[i]["ms_kind"],
                 "osm_mph": None if pd.isna(ways.iloc[i]["ms_mph"]) else int(ways.iloc[i]["ms_mph"]),
                 "src_mph": mphs[g]} for i, g, _ in pairs if mphs[g] is not None]
        results.append({"area": area.name, **compare(rows)})
    pd.DataFrame(results).to_csv(OUT / "agreement_by_area.csv", index=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python research/stage1/dtro_pull.py`
Expected now: `No D-TRO credentials in .env yet - skipping (documentation-only assessment).`
Expected once credentials exist: `columns: [...]`, then `N D-TRO records, M speed provisions`. If `M` is 0 but `N` is not, open `data/stage1/dtro_all.csv`, find where the payload lives, and fix `records()` before going on. Note: integration holds test data only; real coverage needs `DTRO_ENV=production`.

- [ ] **Step 3: Commit**

```bash
git add research/stage1/dtro_pull.py
git add results/stage1/dtro 2>/dev/null; git commit -m "feat(stage1): D-TRO bulk pull and OSM agreement"
```

---

### Task 12: Mapillary speed-sign detections

Mapillary map features are de-duplicated sign positions derived from street-level imagery. Endpoint: `https://graph.mapillary.com/map_features` with `access_token`, `fields=id,object_value,geometry,first_seen_at,last_seen_at`, `bbox=minlon,minlat,maxlon,maxlat`, `limit`. The API rejects large boxes, so the area is chunked into 0.05° cells. Speed values are parsed from `object_value` (e.g. `regulatory--maximum-speed-limit-30--g1`); every speed-related value is kept raw so unexpected sign classes (national-limit, end-of-limit) show up in the counts.

Needs `MAPILLARY_TOKEN` in `.env` (free client token from mapillary.com/dashboard/developers). Without it the script exits cleanly.

**Files:**
- Create: `research/slg/mapillary.py`, `research/tests/test_mapillary.py`, `research/stage1/mapillary_pull.py`
- Output: `results/stage1/mapillary/*.csv`

- [ ] **Step 1: Write the failing tests**

`research/tests/test_mapillary.py`:
```python
from slg.mapillary import chunk_bbox, sign_mph


def test_sign_mph():
    assert sign_mph("regulatory--maximum-speed-limit-30--g1") == 30
    assert sign_mph("regulatory--maximum-speed-limit-20--g3") == 20
    assert sign_mph("regulatory--end-of-maximum-speed-limit-30--g1") is None
    assert sign_mph("regulatory--no-entry--g1") is None


def test_chunk_bbox_covers_area():
    cells = chunk_bbox((-0.37, 51.04, -0.29, 51.09), step=0.05)
    assert len(cells) == 2 * 1
    assert cells[0][:2] == (-0.37, 51.04)
    assert max(c[2] for c in cells) == -0.29 and max(c[3] for c in cells) == 51.09
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest research/tests/test_mapillary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slg.mapillary'`

- [ ] **Step 3: Implement the module**

`research/slg/mapillary.py`:
```python
"""Mapillary map-feature (traffic sign) fetch for speed-limit signs."""
import os
import re
import time

import requests
from dotenv import load_dotenv

from slg.paths import ROOT

ENDPOINT = "https://graph.mapillary.com/map_features"
_MAX = re.compile(r"^regulatory--maximum-speed-limit-(\d+)--")


def sign_mph(object_value: str) -> int | None:
    m = _MAX.match(object_value)
    return int(m[1]) if m else None


def chunk_bbox(bbox, step: float = 0.05) -> list[tuple[float, float, float, float]]:
    w, s, e, n = bbox
    cells = []
    lat = s
    while lat < n - 1e-9:
        lon = w
        while lon < e - 1e-9:
            cells.append((round(lon, 6), round(lat, 6),
                          round(min(lon + step, e), 6), round(min(lat + step, n), 6)))
            lon += step
        lat += step
    return cells


def token() -> str | None:
    load_dotenv(ROOT / ".env")
    return os.getenv("MAPILLARY_TOKEN")


def fetch_features(bbox, access_token: str, session=requests) -> list[dict]:
    feats = []
    for cell in chunk_bbox(bbox):
        r = session.get(ENDPOINT, timeout=60, params={
            "access_token": access_token,
            "fields": "id,object_value,geometry,first_seen_at,last_seen_at",
            "bbox": ",".join(str(v) for v in cell),
            "limit": 2000,
        })
        r.raise_for_status()
        feats += [f for f in r.json().get("data", []) if "speed" in f.get("object_value", "")]
        time.sleep(0.2)
    return feats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest research/tests/test_mapillary.py -v`
Expected: 2 passed

- [ ] **Step 5: Write the pull script**

`research/stage1/mapillary_pull.py`:
```python
"""Stage 1: Mapillary speed signs per area and agreement with OSM.

Run: .venv/Scripts/python research/stage1/mapillary_pull.py
"""
import pandas as pd
from shapely import wkt as shapely_wkt
from shapely.geometry import Point

from slg.agreement import compare, snap_to_ways, to_bng
from slg.areas import AREAS
from slg.coverage import annotate
from slg.mapillary import fetch_features, sign_mph, token
from slg.paths import DATA, RESULTS

OUT = RESULTS / "stage1" / "mapillary"


def main():
    tok = token()
    if not tok:
        print("No MAPILLARY_TOKEN in .env - skipping.")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    summary, raw_counts, disagreements = [], [], []
    for area in AREAS:
        cache = DATA / "stage1" / f"{area.name}_ways.parquet"
        if not cache.exists():
            continue
        feats = fetch_features(area.bbox, tok)
        raw_counts += [{"area": area.name, "object_value": f["object_value"]} for f in feats]
        signs = [(f, sign_mph(f["object_value"])) for f in feats]
        signs = [(f, mph) for f, mph in signs if mph is not None]
        ways = annotate(pd.read_parquet(cache))
        lines = [to_bng(shapely_wkt.loads(w)) for w in ways["wkt"]]
        pts = [to_bng(Point(*f["geometry"]["coordinates"])) for f, _ in signs]
        pairs = snap_to_ways(pts, lines, max_m=20)
        rows = []
        for si, wi, d in pairs:
            w = ways.iloc[wi]
            osm_mph = None if pd.isna(w["ms_mph"]) else int(w["ms_mph"])
            rows.append({"osm_kind": w["ms_kind"], "osm_mph": osm_mph, "src_mph": signs[si][1]})
            if osm_mph is not None and osm_mph != signs[si][1]:
                disagreements.append({"area": area.name, "way_id": int(w["way_id"]),
                                      "osm": w["maxspeed"], "sign_mph": signs[si][1],
                                      "dist_m": d, "feature_id": signs[si][0]["id"],
                                      "last_seen": signs[si][0].get("last_seen_at")})
        summary.append({"area": area.name, "speed_features": len(feats),
                        "max_speed_signs": len(signs), "snapped": len(pairs), **compare(rows)})
        print(summary[-1])
    pd.DataFrame(summary).to_csv(OUT / "agreement_by_area.csv", index=False)
    pd.DataFrame(raw_counts).value_counts().to_csv(OUT / "object_value_counts.csv")
    pd.DataFrame(disagreements).to_csv(OUT / "disagreements.csv", index=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run it**

Run: `.venv/Scripts/python research/stage1/mapillary_pull.py`
Expected without a token: `No MAPILLARY_TOKEN in .env - skipping.` With a token: one summary dict per area. Then hand-check 10 rows of `disagreements.csv` in the Mapillary web viewer (`https://www.mapillary.com/app/?focus=map&mapFeatureKey=<feature_id>`) and classify each as OSM wrong / sign snapped to the wrong road / sign misread / sign since changed. Record the tally in notes.

- [ ] **Step 7: Commit**

```bash
git add research/slg/mapillary.py research/tests/test_mapillary.py research/stage1/mapillary_pull.py
git add results/stage1/mapillary 2>/dev/null; git commit -m "feat(stage1): Mapillary speed-sign pull and OSM agreement"
```

---

### Task 13: Source cards for the remaining candidates

Desk research, one card per source, in `results/stage1/sources/<source>.md`. Use WebSearch/WebFetch. Where a source is openly downloadable and carries speed limits, download a sample for one test area into `data/stage1/<source>/` and run it through `slg.agreement` the same way as Tasks 11–12 (point or line geometry → `to_bng` if WGS84 → `snap_to_ways` → `compare`), saving `agreement.csv` beside the card.

Sources: `osm` (summarise Tasks 7–8), `dtro` (docs-based until credentials arrive; must answer: is there an incremental / changed-since query, or only the full `/dtros/all` dump? how big is the dump? — this sets the patch-build design in Stage 5), `mapillary`, `national_highways` (motorway/trunk limits, variable/smart-motorway data), `os_open_roads` (form of way: dual carriageway, slip, roundabout — input for Stage 2, not limits), `wales_20mph` (DataMapWales default-20 layer and post-2024 reversions), `scotland_20mph` (Transport Scotland / council layers), `west_sussex_cc` (council open data), `commercial` (TomTom/HERE/Google: licence and cost only, as a reference point).

**Files:**
- Create: `results/stage1/sources/<source>.md` × 9

- [ ] **Step 1: Write each card using this template**

```markdown
# <Source name>

| Field | Finding |
|---|---|
| What it holds | |
| Speed-limit content | explicit values / road form only / signs / none |
| Geographic coverage | GB / England / Wales / Scotland / single authority |
| Access method | bulk download / REST API / tiles / none |
| Auth | none / free key / paid |
| Rate limits | |
| Licence | e.g. ODbL, OGL v3, CC-BY-SA, proprietary |
| Freshness | update cadence, last update seen |
| Volume | bytes per km or total size, measured where possible |
| Format / CRS | |
| Agreement with OSM | link to agreement.csv or "not measured: <reason>" |

## Verdict
Use as primary / secondary / validation only / reject — one paragraph why.

## Sources
- links used
```

- [ ] **Step 2: Commit**

```bash
git add results/stage1/sources
git commit -m "results(stage1): source cards"
```

---

### Task 14: Stage 1 notes and wrap-up

**Files:**
- Create: `results/stage1/notes.md`

- [ ] **Step 1: Run the full test suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 42 passed.

- [ ] **Step 2: Write `results/stage1/notes.md`**

Sections, all filled from measured outputs (no estimates presented as measurements):
1. What was tried: list of sources and scripts run, with dates.
2. OSM coverage: table of % km tagged by road class (overall and per country), from `coverage_by_country_class.csv`; the share that is national-limit form vs explicit mph; odd-value rate.
3. Freshness: median age and % edited within 2 years by class; the caveat that way timestamp ≠ maxspeed edit time.
4. Live-query cost: Overpass latency and bytes/km from `probe.csv`.
5. Agreement: D-TRO and Mapillary tables (or "pending credentials/token"), with the hand-checked disagreement tally.
6. Failed avenues: anything that did not work and why.
7. Implications for Stage 2 (which road classes need inference most, by km) and Stage 5 (bytes/km baseline; how OSM and D-TRO changes can be picked up incrementally for the offline-base + patch design).
8. Footprint notes: none on device yet; record extract sizes and per-area parquet sizes.

- [ ] **Step 3: Commit**

```bash
git add results/stage1/notes.md
git commit -m "results(stage1): notes and findings"
```

- [ ] **Step 4: Hand over to Stage 2 planning**

Stage 2 (inference) is planned in a separate document after reading `results/stage1/notes.md`, because its method list depends on which tags Stage 1 found to be well populated.
