import pytest

from slg.restrictions import parse_length_m, parse_weight_t


@pytest.mark.parametrize("raw, expected", [
    ("2.1", 2.1), ("2.1 m", 2.1), ("2.1m", 2.1),
    ("6'6\"", 1.981), ("6'6''", 1.981), ("7'", 2.134), ("13'9\"", 4.191), ("6 ft 6 in", 1.981),
    ("default", None), ("none", None), ("below_default", None), ("", None), (None, None),
    ("tall", None),
])
def test_parse_length_m(raw, expected):
    got = parse_length_m(raw)
    assert (got is None and expected is None) or got == pytest.approx(expected, abs=0.001)


@pytest.mark.parametrize("raw, expected", [
    ("3", 3.0), ("3 t", 3.0), ("7.5", 7.5), ("7.5t", 7.5), ("7500 kg", 7.5),
    ("none", None), (None, None), ("heavy", None),
])
def test_parse_weight_t(raw, expected):
    got = parse_weight_t(raw)
    assert (got is None and expected is None) or got == pytest.approx(expected)
