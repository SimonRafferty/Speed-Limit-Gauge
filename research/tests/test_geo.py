import pytest

from slg.geo import haversine_m, line_length_m


def test_one_degree_latitude():
    assert haversine_m(0.0, 51.0, 0.0, 52.0) == pytest.approx(111195, abs=5)


def test_line_length_sums_segments():
    coords = [(0.0, 51.0), (0.0, 51.001), (0.0, 51.002)]
    assert line_length_m(coords) == pytest.approx(2 * 111.195, abs=0.1)


def test_line_length_single_point_is_zero():
    assert line_length_m([(0.0, 51.0)]) == 0.0
