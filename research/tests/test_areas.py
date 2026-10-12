from slg.areas import AREAS, Area

GB = (-8.7, 49.8, 1.8, 60.9)


def test_names_unique():
    names = [a.name for a in AREAS]
    assert len(names) == len(set(names))


def test_bboxes_valid_and_in_gb():
    for a in AREAS:
        w, s, e, n = a.bbox
        assert w < e and s < n, a.name
        assert GB[0] <= w and e <= GB[2] and GB[1] <= s and n <= GB[3], a.name


def test_plan_conditions_covered():
    conditions = {a.condition for a in AREAS}
    assert {"urban", "suburban", "rural", "motorway_trunk"} <= conditions
    countries = {a.country for a in AREAS}
    assert {"england", "wales", "scotland"} <= countries
    assert any("west-sussex" in r for a in AREAS for r in a.regions)


def test_contains():
    a = Area("t", "urban", "england", ("x",), (-1.0, 50.0, 0.0, 51.0))
    assert a.contains(-0.5, 50.5)
    assert not a.contains(0.5, 50.5)
