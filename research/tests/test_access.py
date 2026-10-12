import math

import pytest

from slg.access import motor_legality


@pytest.mark.parametrize("tags, expected", [
    # Nothing relevant: an ordinary public road.
    ({}, "unknown"),
    ({"highway": "residential"}, "unknown"),
    # Plain "no" on any key prohibits.
    ({"access": "no"}, "prohibited"),
    ({"vehicle": "no"}, "prohibited"),
    ({"motor_vehicle": "no"}, "prohibited"),
    ({"motorcar": "no"}, "prohibited"),
    # Legal only with permission: yellow X.
    *[({"access": v}, "permission") for v in (
        "private", "permit", "destination", "customers", "delivery", "agricultural", "forestry")],
    ({"motor_vehicle": "private"}, "permission"),
    ({"motorcar": "destination"}, "permission"),
    # Allowed outright: no X.
    *[({"access": v}, "allowed") for v in ("yes", "designated", "permissive", "discouraged")],
    # Most specific key wins.
    ({"access": "no", "motor_vehicle": "yes"}, "allowed"),
    ({"access": "yes", "motor_vehicle": "no"}, "prohibited"),
    ({"motor_vehicle": "no", "motorcar": "yes"}, "allowed"),
    ({"motor_vehicle": "yes", "motorcar": "no"}, "prohibited"),
    ({"vehicle": "no", "motor_vehicle": "destination"}, "permission"),
    ({"access": "private", "motor_vehicle": "yes"}, "allowed"),
    ({"access": "yes", "motorcar": "private"}, "permission"),
    ({"access": "private", "vehicle": "no"}, "prohibited"),
    # Case and whitespace are tolerated.
    ({"motor_vehicle": " No "}, "prohibited"),
    # Unrecognised value on the deciding key is ambiguous.
    ({"motor_vehicle": "unknown"}, "unknown"),
    ({"access": "use_sidepath"}, "unknown"),
])
def test_keys_and_values(tags, expected):
    assert motor_legality(tags) == expected


@pytest.mark.parametrize("tags, expected", [
    # Conditional on the deciding key.
    ({"motor_vehicle": "yes", "motor_vehicle:conditional": "no @ (Oct-Apr)"}, "conditional"),
    # Conditional on a more specific key than the deciding one.
    ({"access": "yes", "motorcar:conditional": "no @ (Oct-Apr)"}, "conditional"),
    ({"vehicle": "no", "motor_vehicle:conditional": "yes @ (May-Sep)"}, "conditional"),
    # Conditional alone (no plain key at all).
    ({"motor_vehicle:conditional": "no @ (Oct-Apr)"}, "conditional"),
    ({"access:conditional": "no @ (Mo-Fr 08:30-09:30)"}, "conditional"),
    # Conditional on a LESS specific key is overridden by the more specific plain key.
    ({"motor_vehicle": "no", "access:conditional": "yes @ (Sa,Su)"}, "prohibited"),
    ({"motorcar": "yes", "vehicle:conditional": "no @ (Oct-Apr)"}, "allowed"),
])
def test_conditional(tags, expected):
    assert motor_legality(tags) == expected


@pytest.mark.parametrize("tags, expected", [
    # Rights of way that exclude motor vehicles.
    ({"designation": "restricted_byway"}, "prohibited"),
    ({"designation": "public_bridleway"}, "prohibited"),
    ({"designation": "public_footpath"}, "prohibited"),
    # Any explicit value on the four keys decides over the designation (spec 7.1a:
    # a public footpath over a private track is legal for those with permission).
    ({"designation": "public_footpath", "access": "private"}, "permission"),
    ({"designation": "public_bridleway", "access": "private"}, "permission"),
    ({"designation": "public_footpath", "access": "yes"}, "allowed"),
    ({"designation": "restricted_byway", "vehicle": "yes"}, "allowed"),
    ({"designation": "public_footpath", "access": "permissive"}, "allowed"),
    ({"designation": "public_footpath", "motor_vehicle": "private"}, "permission"),
    ({"designation": "restricted_byway", "motorcar": "destination"}, "permission"),
    ({"designation": "public_bridleway", "motor_vehicle": "no"}, "prohibited"),
    ({"designation": "public_footpath", "access": "private", "motor_vehicle": "no"}, "prohibited"),
    # An unrecognised value does not override the designation.
    ({"designation": "public_footpath", "access": "unknown"}, "prohibited"),
    # Byway open to all traffic.
    ({"designation": "byway_open_to_all_traffic"}, "allowed"),
    ({"designation": "byway_open_to_all_traffic", "motor_vehicle": "no"}, "prohibited"),
    ({"designation": "byway_open_to_all_traffic", "access": "no"}, "prohibited"),
    ({"designation": "byway_open_to_all_traffic", "access": "private"}, "permission"),
    ({"designation": "byway_open_to_all_traffic",
      "motor_vehicle:conditional": "no @ (Oct-Apr)"}, "conditional"),
    # Other designations say nothing about motor vehicles.
    ({"designation": "unclassified_county_road"}, "unknown"),
])
def test_designation(tags, expected):
    assert motor_legality(tags) == expected


def test_missing_values_from_pandas_are_ignored():
    tags = {"access": None, "motor_vehicle": math.nan, "motorcar": "", "vehicle": "no",
            "motor_vehicle:conditional": None, "designation": math.nan}
    assert motor_legality(tags) == "prohibited"
