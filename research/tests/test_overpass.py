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
