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
