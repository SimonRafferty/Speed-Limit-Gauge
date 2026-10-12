from shapely.geometry import LineString, Point, box

from slg.agreement import compare, snap_to_ways, to_bng


def test_to_bng_round_numbers():
    p = to_bng(Point(-0.1276, 51.5072))   # Trafalgar Square-ish
    assert 529000 < p.x < 531000 and 180000 < p.y < 181000


def test_snap_to_ways_respects_tolerance():
    ways = [LineString([(0, 0), (100, 0)]), LineString([(0, 50), (100, 50)])]
    feats = [Point(50, 5), Point(50, 30), Point(50, 48)]
    pairs = snap_to_ways(feats, ways, max_m=10)
    assert pairs == [(0, 0, 5.0), (2, 1, 2.0)]


def test_to_bng_accepts_single_geometry_and_no_warning():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        line = to_bng(LineString([(-0.1276, 51.5072), (-0.1270, 51.5075)]))
    assert 529000 < line.coords[0][0] < 531000


def test_snap_all_matches_returns_ties():
    ways = [box(0, 0, 10, 10), box(5, 5, 15, 15)]
    feats = [Point(7, 7)]
    assert snap_to_ways(feats, ways, max_m=5, all_matches=True) == [(0, 0, 0.0), (0, 1, 0.0)]
    assert len(snap_to_ways(feats, ways, max_m=5)) == 1


def test_snap_empty_inputs():
    ways = [LineString([(0, 0), (100, 0)])]
    assert snap_to_ways([], ways, max_m=10) == []
    assert snap_to_ways([Point(1, 1)], [], max_m=10) == []
    assert snap_to_ways([], ways, max_m=10, all_matches=True) == []
    assert snap_to_ways([Point(1, 1)], [], max_m=10, all_matches=True) == []


def test_compare_counts():
    rows = [
        {"osm_kind": "explicit", "osm_mph": 30, "src_mph": 30},
        {"osm_kind": "explicit", "osm_mph": 40, "src_mph": 30},
        {"osm_kind": "explicit", "osm_mph": 20, "src_mph": 30},
        {"osm_kind": "absent", "osm_mph": None, "src_mph": 30},
        {"osm_kind": "nsl_single", "osm_mph": None, "src_mph": 60},
        {"osm_kind": "nsl_dual", "osm_mph": None, "src_mph": 30},
        {"osm_kind": "motorway", "osm_mph": None, "src_mph": 70},
        {"osm_kind": "national", "osm_mph": None, "src_mph": 40},
        {"osm_kind": "variable", "osm_mph": None, "src_mph": 40},
        {"osm_kind": "unparsed", "osm_mph": None, "src_mph": 30},
    ]
    c = compare(rows)
    assert c == {"n": 10, "agree": 1, "osm_higher": 1, "osm_lower": 1,
                 "osm_untagged": 1, "osm_unusable": 2,
                 "national_consistent": 2, "national_conflict": 2}
