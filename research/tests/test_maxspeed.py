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
