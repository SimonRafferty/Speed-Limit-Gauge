import math

import pytest

from slg.maxspeed import Parsed, parse_maxspeed


@pytest.mark.parametrize("raw, expected", [
    ("30 mph", Parsed("explicit", 30)),
    ("30mph", Parsed("explicit", 30)),
    (" 20 MPH ", Parsed("explicit", 20)),
    ("48 km/h", Parsed("explicit", 30)),
    ("64 kmh", Parsed("explicit", 40)),
    ("35 mph", Parsed("explicit", 35)),
    ("0 mph", Parsed("nonstandard")),
    ("999 mph", Parsed("nonstandard")),
    ("65 mph", Parsed("nonstandard")),
    ("30.5 mph", Parsed("nonstandard")),
    ("100 km/h", Parsed("nonstandard")),
    ("60 km/h", Parsed("nonstandard")),
    ("UK:nsl_single", Parsed("nsl_single")),
    ("GB:nsl", Parsed("national")),
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
