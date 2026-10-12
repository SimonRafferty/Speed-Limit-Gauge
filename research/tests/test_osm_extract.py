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
