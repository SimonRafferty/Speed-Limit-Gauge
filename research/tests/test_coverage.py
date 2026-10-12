from datetime import datetime, timezone

import pandas as pd
import pytest

from slg.coverage import annotate, coverage_by_class, freshness, kind_breakdown


def _df():
    return pd.DataFrame({
        "way_id": [1, 2, 3, 4],
        "area": ["a", "a", "a", "a"],
        "highway": ["residential", "residential", "trunk", "trunk_link"],
        "maxspeed": ["20 mph", None, "GB:nsl_dual", None],
        "maxspeed:forward": [None, None, None, "50 mph"],
        "maxspeed:backward": [None, None, None, None],
        "length_m": [1000.0, 3000.0, 2000.0, 500.0],
        "timestamp": [
            datetime(2026, 1, 1, tzinfo=timezone.utc), None,
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        ],
    })


def test_annotate():
    a = annotate(_df())
    assert list(a["road_class"]) == ["residential", "residential", "trunk", "trunk"]
    assert list(a["ms_kind"]) == ["explicit", "absent", "nsl_dual", "absent"]
    assert list(a["tagged"]) == [True, False, True, True]


def test_coverage_by_class():
    t = coverage_by_class(annotate(_df())).set_index("road_class")
    assert t.loc["residential", "km"] == pytest.approx(4.0)
    assert t.loc["residential", "pct_km_tagged"] == pytest.approx(25.0)
    assert t.loc["residential", "pct_ways_tagged"] == pytest.approx(50.0)
    assert t.loc["trunk", "pct_km_tagged"] == pytest.approx(100.0)


def test_kind_breakdown():
    k = kind_breakdown(annotate(_df()))
    assert k.loc["residential", "explicit"] == pytest.approx(1.0)
    assert k.loc["residential", "absent"] == pytest.approx(3.0)


def test_freshness():
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    f = freshness(annotate(_df()), now).set_index("road_class")
    assert f.loc["trunk", "tagged_ways_with_ts"] == 2
    assert f.loc["trunk", "pct_edited_2y"] == pytest.approx(50.0)
