"""Pure helpers of the research/stage1/osm_restrictions.py script."""
import math

import pandas as pd
import pytest

from stage1.osm_restrictions import node_location, parsed


def test_node_location_three_states():
    ids = pd.Series([1, 2, 3, 4])
    got = node_location(ids, drivable={1, 4}, any_way={1, 2, 4})
    assert list(got) == ["on_drivable", "on_other_way", "on_no_way", "on_drivable"]


def test_parsed_effective_is_min_of_signed_and_physical_skipping_nan():
    df = pd.DataFrame({
        "maxheight":          ["2.3", None,  "2.0", "default", None],
        "maxheight:physical": ["2.1", "1.9", None,  None,      None],
        "maxwidth":           ["2.0", None,  None,  None,      None],
    })
    out = parsed(df)
    assert list(out["maxheight_m"].fillna(-1)) == [2.3, -1, 2.0, -1, -1]
    assert out["eff_height_m"].tolist()[:3] == pytest.approx([2.1, 1.9, 2.0])
    assert math.isnan(out["eff_height_m"].iloc[3]) and math.isnan(out["eff_height_m"].iloc[4])
    # Width has no :physical column here: effective = signed.
    assert out["eff_width_m"].iloc[0] == pytest.approx(2.0)
    assert out["eff_width_m"].iloc[1:].isna().all()


def test_parsed_without_any_length_columns():
    out = parsed(pd.DataFrame({"maxweight": ["7.5", "18 cwt"]}))
    assert out["maxweight_t"].tolist() == pytest.approx([7.5, 0.914])
    assert out["eff_height_m"].isna().all() and out["eff_width_m"].isna().all()
