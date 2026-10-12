import pytest

from slg.areas import Area
from slg.osm_extract import (download_extract, drivable_node_ids, restriction_nodes_in_area,
                             way_node_ids, ways_in_area)

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


NODES_XML = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
 <node id="1" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.000" lon="-0.300">
  <tag k="barrier" v="height_restrictor"/><tag k="maxheight" v="2.0"/>
 </node>
 <node id="2" version="1" timestamp="2024-01-01T00:00:00Z" lat="52.000" lon="-0.300">
  <tag k="maxheight" v="2.0"/>
 </node>
 <node id="3" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.001" lon="-0.300">
  <tag k="barrier" v="gate"/>
 </node>
</osm>
"""


def test_restriction_nodes_in_area(tmp_path):
    f = tmp_path / "n.osm"
    f.write_text(NODES_XML, encoding="utf-8")
    rows = restriction_nodes_in_area(f, AREA)
    assert [r["node_id"] for r in rows] == [1]
    assert rows[0]["barrier"] == "height_restrictor" and rows[0]["maxheight"] == "2.0"
    assert rows[0]["lon"] == pytest.approx(-0.3) and rows[0]["area"] == "t"


DRIVABLE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
 <node id="1" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.000" lon="-0.300"/>
 <node id="2" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.001" lon="-0.300"/>
 <node id="5" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.002" lon="-0.300"/>
 <node id="6" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.003" lon="-0.300"/>
 <way id="10" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/>
 </way>
 <way id="11" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="5"/><nd ref="6"/><tag k="highway" v="footway"/>
 </way>
</osm>
"""


def test_drivable_node_ids_excludes_footway_only_nodes(tmp_path):
    f = tmp_path / "d.osm"
    f.write_text(DRIVABLE_XML, encoding="utf-8")
    assert drivable_node_ids(f, AREA) == {1, 2}


ANYWAY_XML = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
 <node id="1" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.000" lon="-0.300"/>
 <node id="2" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.001" lon="-0.300"/>
 <node id="5" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.002" lon="-0.300"/>
 <node id="6" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.003" lon="-0.300"/>
 <node id="7" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.004" lon="-0.300"/>
 <node id="8" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.005" lon="-0.300"/>
 <node id="9" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.006" lon="-0.300"/>
 <node id="20" version="1" timestamp="2024-01-01T00:00:00Z" lat="52.000" lon="-0.300"/>
 <node id="21" version="1" timestamp="2024-01-01T00:00:00Z" lat="52.001" lon="-0.300"/>
 <way id="10" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/>
 </way>
 <way id="11" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="5"/><nd ref="6"/><tag k="highway" v="footway"/>
 </way>
 <way id="12" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="7"/><nd ref="8"/><tag k="building" v="yes"/>
 </way>
 <way id="13" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="20"/><nd ref="21"/><tag k="highway" v="footway"/>
 </way>
</osm>
"""


def test_way_node_ids_includes_every_way_touching_area(tmp_path):
    f = tmp_path / "a.osm"
    f.write_text(ANYWAY_XML, encoding="utf-8")
    # Node 9 is on no way; way 13 lies outside the area.
    assert way_node_ids(f, AREA) == {1, 2, 5, 6, 7, 8}
    assert drivable_node_ids(f, AREA) == {1, 2}


TRACK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
 <node id="1" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.000" lon="-0.300"/>
 <node id="2" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.001" lon="-0.300"/>
 <way id="30" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="1"/><nd ref="2"/><tag k="highway" v="track"/>
  <tag k="designation" v="byway_open_to_all_traffic"/><tag k="prow_ref" v="Horsham 123"/>
  <tag k="motor_vehicle:conditional" v="no @ (Oct-Apr)"/><tag k="tracktype" v="grade3"/>
  <tag k="surface" v="gravel"/><tag k="access" v="yes"/><tag k="motor_vehicle" v="yes"/>
  <tag k="motorcar" v="yes"/><tag k="vehicle" v="yes"/>
 </way>
</osm>
"""


def test_ways_in_area_includes_tracks_and_access_tags(tmp_path):
    f = tmp_path / "t.osm"
    f.write_text(TRACK_XML, encoding="utf-8")
    rows = ways_in_area(f, AREA)
    assert [r["way_id"] for r in rows] == [30]
    r = rows[0]
    assert r["highway"] == "track"
    assert r["designation"] == "byway_open_to_all_traffic" and r["prow_ref"] == "Horsham 123"
    assert r["motor_vehicle:conditional"] == "no @ (Oct-Apr)"
    assert r["tracktype"] == "grade3" and r["surface"] == "gravel"
    for k in ("access", "motor_vehicle", "motorcar", "vehicle"):
        assert r[k] == "yes"
    for k in ("motorcar:conditional", "vehicle:conditional", "access:conditional"):
        assert k in r and r[k] is None


def test_tag_keys_include_service_goods_hgv():
    from slg.osm_extract import TAG_KEYS
    for k in ("service", "goods", "hgv"):
        assert k in TAG_KEYS


SERVICE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
 <node id="1" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.000" lon="-0.300"/>
 <node id="2" version="1" timestamp="2024-01-01T00:00:00Z" lat="51.001" lon="-0.300"/>
 <way id="40" version="1" timestamp="2025-06-01T12:00:00Z">
  <nd ref="1"/><nd ref="2"/><tag k="highway" v="service"/><tag k="service" v="driveway"/>
  <tag k="access" v="private"/>
 </way>
</osm>
"""


def test_ways_in_area_reads_service_subtag(tmp_path):
    f = tmp_path / "s.osm"
    f.write_text(SERVICE_XML, encoding="utf-8")
    (r,) = ways_in_area(f, AREA)
    assert r["service"] == "driveway" and r["access"] == "private"
