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


# --- Task 9c: extra formats, plausibility bounds, placeholders ---

from slg.restrictions import PLACEHOLDERS, is_placeholder


@pytest.mark.parametrize("raw, expected", [
    ("6' 6\"", 1.981), ("6’6”", 1.981), ("6′6″", 1.981), ("6’6’’", 1.981),
    ("2,1", 2.1), ("2,1 m", 2.1), ("190 cm", 1.9), ("190cm", 1.9),
    ("2.1 metres", 2.1), ("2.1 meters", 2.1), ("2.1 metre", 2.1), ("2.1metres", 2.1),
    ("1.0", 1.0), ("10", 10.0),
    # Plausibility bounds: 1.0-10.0 m; inches must be < 12.
    ("3000", None), ("0", None), ("0.9", None), ("10.5", None), ("6'13\"", None), ("6'12\"", None),
    ("50 cm", None), ("40'", None),
])
def test_parse_length_m_extra(raw, expected):
    got = parse_length_m(raw)
    assert (got is None and expected is None) or got == pytest.approx(expected, abs=0.001)


@pytest.mark.parametrize("raw, expected", [
    ("7,5", 7.5), ("7,5 t", 7.5), ("7.5 tonnes", 7.5), ("7.5 tonne", 7.5), ("10 tons", 10.0),
    ("3 ton", 3.0), ("18 cwt", 0.914), ("18cwt", 0.914),
    ("0.5", 0.5), ("60", 60.0),
    # Plausibility bounds: 0.5-60 t.
    ("0", None), ("0.4", None), ("61", None), ("3000", None), ("100 kg", None),
])
def test_parse_weight_t_extra(raw, expected):
    got = parse_weight_t(raw)
    assert (got is None and expected is None) or got == pytest.approx(expected, abs=0.001)


@pytest.mark.parametrize("raw, expected", [
    ("default", True), ("below_default", True), ("none", True), ("no_sign", True),
    ("no_indications", True), ("unsigned", True), (" Default ", True),
    ("2.1", False), ("tall", False), ("", False), (None, False),
])
def test_is_placeholder(raw, expected):
    assert is_placeholder(raw) is expected


def test_placeholders_set():
    assert PLACEHOLDERS == {"default", "below_default", "none", "no_sign", "no_indications", "unsigned"}
