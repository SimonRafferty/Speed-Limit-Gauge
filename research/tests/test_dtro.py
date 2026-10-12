import collections

import pytest

from slg.dtro import (PROHIBITION_TYPES, DtroClient, order_nature, parse_ewkt,
                      prohibition_provisions, restriction_provisions, speed_provisions)

RECORD_V5 = {
    "id": "abc",
    "schemaVersion": "5.0.0",
    "data": {"source": {"provision": [
        {"reference": "P1", "actionType": "new",
         "regulation": [{"regulationType": "speedLimitValueBased", "isDynamic": False,
                         "speedLimitValueBased": {"mphValue": 20, "type": "maximumSpeedLimit",
                                                  "nature": "permanent"}}],
         "regulatedPlace": [{"linearGeometry": {
             "linestring": "SRID=27700;LINESTRING(444284 333253, 444300 333260)"}}]},
        {"reference": "P2", "actionType": "new",
         "regulation": [{"regulationType": "kerbsideLimitedWaiting"}],
         "regulatedPlace": []},
        {"reference": "P3", "actionType": "new",
         "regulation": [{"regulationType": "speedLimitProfileBased",
                         "speedLimitProfileBased": {"type": "nationalSpeedLimitSingleCarriageway"}}],
         "regulatedPlace": [{"polygon": {"polygon": "SRID=27700;POLYGON((0 0, 1 0, 1 1, 0 0))"}}]},
    ]}},
}

RECORD_V3 = {
    "id": "old", "schemaVersion": "3.3.0",
    "data": {"source": {"provision": [
        {"reference": "Q1", "regulation": [{"generalRegulation": {"regulationType": "speedLimitValueBased"},
                                            "speedLimitValueBased": {"mphValue": 30, "type": "maximumSpeedLimit"}}],
         "regulatedPlace": []},
    ]}},
}


def test_speed_provisions_v5():
    out = speed_provisions(RECORD_V5)
    assert [p["provision_ref"] for p in out] == ["P1", "P3"]
    assert out[0]["mph"] == 20 and out[0]["limit_type"] == "maximumSpeedLimit"
    assert out[0]["geometries"] == ["SRID=27700;LINESTRING(444284 333253, 444300 333260)"]
    assert out[1]["mph"] is None and out[1]["limit_type"] == "nationalSpeedLimitSingleCarriageway"
    assert out[1]["geometries"][0].startswith("SRID=27700;POLYGON")


def test_speed_provisions_pre_v5():
    out = speed_provisions(RECORD_V3)
    assert out[0]["mph"] == 30 and out[0]["schema_version"] == "3.3.0"


class _Resp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


class _Session:
    def __init__(self):
        self.posts = 0
        self.gets = []
    def post(self, url, auth, data, timeout):
        self.posts += 1
        assert url == "https://dtro-integration.dft.gov.uk/v1/oauth-generator"
        assert auth == ("id", "secret") and data == {"grant_type": "client_credentials"}
        return _Resp({"access_token": "tok", "expires_in": "1799"})
    def get(self, url, headers, timeout):
        self.gets.append((url, headers["Authorization"]))
        return _Resp("https://storage.example/all.csv")


def test_client_caches_token_and_gets_all_url():
    s = _Session()
    c = DtroClient("id", "secret", env="integration", session=s)
    assert c.all_records_url() == "https://storage.example/all.csv"
    c.all_records_url()
    assert s.posts == 1
    assert s.gets[0] == ("https://dtro-integration.dft.gov.uk/v1/dtros/all", "Bearer tok")


# Shapes seen in the production /dtros/all dump (schema 3.5.x / 4.0.0): speed
# regulations carry no regulationType at all, only the speedLimit* object, and
# "regulation" may be a single object instead of a list.
RECORD_DUMP = {
    "id": "d1", "schemaVersion": "4.0.0",
    "data": {"source": {"provision": [
        {"reference": "T1", "actionType": "fullAmendment",
         "regulation": {"isDynamic": True,
                        "speedLimitValueBased": {"type": "maximumSpeedLimit", "nature": "temporary",
                                                 "mphValue": 50}},
         "regulatedPlace": [{"linearGeometry": {"linestring": "SRID=27700;LINESTRING(1 1, 2 2)"}}]},
        {"reference": "T2", "regulation": {"generalRegulation": {"regulationType": "miscRoadClosure"}},
         "regulatedPlace": []},
    ]}},
}


def test_speed_provisions_without_regulation_type_and_dict_regulation():
    out = speed_provisions(RECORD_DUMP)
    assert [p["provision_ref"] for p in out] == ["T1"]
    assert out[0]["regulation_type"] == "speedLimitValueBased"
    assert out[0]["mph"] == 50 and out[0]["nature"] == "temporary"


def test_parse_ewkt_strips_srid_and_accepts_linear_kinds():
    g, why = parse_ewkt("SRID=27700;LINESTRING(0 0, 10 0)")
    assert why == "ok" and g.length == 10
    g, why = parse_ewkt("SRID=27700;MULTILINESTRING((0 0, 1 0),(2 0, 3 0))")
    assert why == "ok" and g.geom_type == "MultiLineString"
    g, why = parse_ewkt("SRID=27700;POLYGON((0 0, 1 0, 1 1, 0 0))")
    assert why == "ok" and g.area == 0.5


def test_parse_ewkt_rejects_points_other_srids_and_garbage():
    assert parse_ewkt("SRID=27700;POINT(1 1)") == (None, "kind_POINT")
    assert parse_ewkt("SRID=4326;LINESTRING(0 0, 1 1)") == (None, "not_27700")
    assert parse_ewkt("SRID=27700;LINESTRING(0 0, x)") == (None, "unparsable")


def test_parse_ewkt_split_rings_become_multipolygon():
    # Production shape: separate rings each written unclosed, and the last piece ends
    # on a stray copy of the polygon's very first vertex.
    stats = collections.Counter()
    g, why = parse_ewkt("SRID=27700;POLYGON((0 0, 10 0, 10 10, 0 10),"
                        "(100 100, 120 100, 120 120, 100 120, 0 0))", stats)
    assert why == "repaired_split_ring"
    assert g.geom_type == "MultiPolygon" and len(g.geoms) == 2
    assert sorted(p.area for p in g.geoms) == [100, 400]
    assert stats == {"pieces_kept": 2}


def test_parse_ewkt_split_rings_drops_degenerate_pieces():
    stats = collections.Counter()
    g, why = parse_ewkt("SRID=27700;POLYGON((0 0, 10 0, 10 10, 0 10),(50 50, 60 60, 0 0))", stats)
    assert why == "repaired_split_ring" and g.geom_type == "MultiPolygon" and len(g.geoms) == 1
    assert stats == {"pieces_kept": 1, "pieces_dropped": 1}


RECORD_RESTRICT = {
    "id": "r1", "schemaVersion": "5.0.0",
    "data": {"source": {"provision": [
        {"reference": "H1", "actionType": "new",
         "regulation": [{"regulationType": "dimensionMaximumHeightStructural",
                         "condition": [{"vehicleCharacteristics": {
                             "maximumHeightCharacteristic": {"vehicleHeight": 2.1}}}]}],
         "regulatedPlace": [{"linearGeometry": {"linestring": "SRID=27700;LINESTRING(1 1, 2 2)"}}]},
        {"reference": "W1", "actionType": "new",
         "regulation": [{"regulationType": "dimensionMaximumWeightStructural",
                         "condition": [{"vehicleCharacteristics": {
                             "maximumGrossWeightCharacteristic": {"grossVehicleWeight": 3.0,
                                                                  "typeOfWeight": "maximum"}}}]}],
         "regulatedPlace": []},
        {"reference": "S1", "regulation": [{"regulationType": "speedLimitValueBased"}], "regulatedPlace": []},
    ]}},
}


def test_restriction_provisions():
    out = restriction_provisions(RECORD_RESTRICT)
    assert [p["provision_ref"] for p in out] == ["H1", "W1"]
    assert out[0]["height_m"] == 2.1 and out[0]["weight_t"] is None
    assert out[0]["geometries"] == ["SRID=27700;LINESTRING(1 1, 2 2)"]
    assert out[1]["weight_t"] == 3.0 and out[1]["type_of_weight"] == "maximum"


def test_restriction_provisions_dump_shape():
    # Production shape: pre-v5 generalRegulation, single-object regulation,
    # values nested under conditionSet[].conditions[].
    rec = {"id": "r2", "schemaVersion": "3.5.1", "data": {"source": {"provision": [
        {"reference": "X1", "regulation": {
            "generalRegulation": {"regulationType": "dimensionMaximumWidth"},
            "conditionSet": [{"operator": "and", "conditions": [
                {"timeValidity": {"start": "2016-02-29T00:00:00"}},
                {"vehicleCharacteristics": {"maximumWidthCharacteristic": {"vehicleWidth": 2}}}]}]},
         "regulatedPlace": []}]}}}
    out = restriction_provisions(rec)
    assert len(out) == 1 and out[0]["width_m"] == 2 and out[0]["height_m"] is None


RECORD_PROHIBIT = {
    "id": "p1", "schemaVersion": "3.5.1",
    "data": {"source": {"provision": [
        # Temporary full road closure (dump shape: generalRegulation, single-object regulation).
        {"reference": "C1", "orderReportingPoint": "ttroTtmoByNotice", "regulation": {
            "isDynamic": True,
            "generalRegulation": {"regulationType": "miscRoadClosure"},
            "condition": [{"timeValidity": {
                "start": "2026-06-23T09:48:11", "end": "2026-06-25T18:00:00",
                "validPeriod": [{"startOfPeriod": "2026-06-23T09:48:11"}]}}]},
         "regulatedPlace": [{"linearGeometry": {"linestring": "SRID=27700;LINESTRING(1 1, 2 2)"}}]},
        # Permanent weight-class ban except for access: a vehicle-class ban, not a closure.
        {"reference": "A1", "orderReportingPoint": "permanentNoticeOfMaking", "regulation": [{
            "isDynamic": False,
            "generalRegulation": {"regulationType": "movementOrderProhibitedAccess"},
            "conditionSet": [{"operator": "and", "conditions": [
                {"timeValidity": {"start": "2016-02-29T00:00:00"}},
                {"vehicleCharacteristics": {"maximumGrossWeightCharacteristic": {
                    "grossVehicleWeight": 3.5}}},
                {"accessCondition": {"accessConditionType": ["accessOnly"]}}]}]}],
         "regulatedPlace": []},
        # v5 shape, seasonal motor-vehicle ban with a recurring period.
        {"reference": "M1", "orderReportingPoint": "permanentAmendment", "regulation": [{
            "regulationType": "motorVehiclesProhibited",
            "condition": [{"timeValidity": {"start": "2020-10-01T00:00:00", "validPeriod": [
                {"recurringDayWeekMonthPeriod": [{"applicableMonth": ["october"]}]}]}}]}],
         "regulatedPlace": []},
        # Not a prohibition.
        {"reference": "K1", "regulation": [{"generalRegulation": {"regulationType": "kerbsideNoWaiting"}}],
         "regulatedPlace": []},
    ]}},
}


def test_prohibition_types():
    for t in ("motorVehiclesProhibited", "movementOrderProhibitedAccess", "miscRoadClosure",
              "miscPROWClosure", "bannedMovementNoEntry"):
        assert t in PROHIBITION_TYPES
    assert "kerbsideNoWaiting" not in PROHIBITION_TYPES


def test_prohibition_provisions():
    out = prohibition_provisions(RECORD_PROHIBIT)
    assert [p["provision_ref"] for p in out] == ["C1", "A1", "M1"]
    c, a, m = out
    assert c["dtro_id"] == "p1" and c["regulation_type"] == "miscRoadClosure"
    assert c["nature"] == "temporary" and c["is_dynamic"] is True
    assert c["start"] == "2026-06-23T09:48:11" and c["end"] == "2026-06-25T18:00:00"
    assert c["has_vehicle_condition"] is False and c["has_access_condition"] is False
    assert c["has_recurring_period"] is False
    assert c["geometries"] == ["SRID=27700;LINESTRING(1 1, 2 2)"]
    assert a["regulation_type"] == "movementOrderProhibitedAccess"
    assert a["nature"] == "permanent" and a["start"] == "2016-02-29T00:00:00" and a["end"] is None
    assert a["has_vehicle_condition"] is True and a["has_access_condition"] is True
    assert m["regulation_type"] == "motorVehiclesProhibited" and m["has_recurring_period"] is True
    assert m["nature"] == "permanent"


@pytest.mark.parametrize("orp, dynamic, expected", [
    ("ttroTtmoByNotice", False, "temporary"), ("ttroTtmoNoticeOfIntention", False, "temporary"),
    ("specialEventOrderNoticeOfMaking", False, "temporary"),
    ("experimentalNoticeOfMaking", False, "experimental"),
    ("experimentalMakingPermanent", False, "permanent"),
    ("permanentNoticeOfMaking", False, "permanent"), ("permanentAmendment", False, "permanent"),
    ("troOnRoadActiveStatus", False, "unknown"), (None, False, "unknown"),
    (None, True, "temporary"),
])
def test_order_nature(orp, dynamic, expected):
    assert order_nature({"orderReportingPoint": orp}, {"isDynamic": dynamic}) == expected


def test_speed_provisions_carry_time_validity():
    rec = {"id": "t", "schemaVersion": "3.5.1", "data": {"source": {"provision": [
        {"reference": "T", "regulation": {
            "condition": [{"timeValidity": {"start": "2025-10-20T20:00:00", "end": "2025-10-24T03:00:00"}}],
            "speedLimitValueBased": {"type": "maximumSpeedLimit", "nature": "temporary", "mphValue": 50}},
         "regulatedPlace": []}]}}}
    (p,) = speed_provisions(rec)
    assert p["start"] == "2025-10-20T20:00:00" and p["end"] == "2025-10-24T03:00:00"


RECORD_RESTRICT_CONDITIONS = {"id": "r3", "schemaVersion": "3.5.1", "data": {"source": {"provision": [
    {"reference": "L1", "orderReportingPoint": "permanentNoticeOfMaking", "regulation": {
        "isDynamic": False,
        "generalRegulation": {"regulationType": "dimensionMaximumWeightStructural"},
        "conditionSet": [{"operator": "and", "conditions": [
            {"timeValidity": {"start": "2016-02-29T00:00:00"}},
            # typeOfWeight must come from the same characteristic as the weight it qualifies
            {"vehicleCharacteristics": {"maximumGrossWeightCharacteristic": {"typeOfWeight": "laden"}}},
            {"vehicleCharacteristics": {"maximumGrossWeightCharacteristic": {
                "typeOfWeight": "maximumPermitted", "grossVehicleWeight": 1.5}}},
            {"negate": True, "accessCondition": {"accessConditionType": ["loadingAndUnloading"]}}]}]},
     "regulatedPlace": []},
    {"reference": "T1", "orderReportingPoint": "ttroTtmoByNotice", "regulation": {
        "isDynamic": True,
        "generalRegulation": {"regulationType": "dimensionMaximumWidth"},
        "condition": {"timeValidity": {"start": "2026-09-01T00:00:00", "end": "2026-11-03T23:59:00"}}},
     "regulatedPlace": []},
]}}}


def test_restriction_provisions_carry_applicability_conditions():
    w, t = restriction_provisions(RECORD_RESTRICT_CONDITIONS)
    assert w["weight_t"] == 1.5 and w["type_of_weight"] == "maximumPermitted"
    assert w["nature"] == "permanent" and w["start"] == "2016-02-29T00:00:00" and w["end"] is None
    assert w["operator"] == "and" and w["has_negated_condition"] is True
    assert w["has_exemption"] is True and w["exemption"] == "loadingAndUnloading"
    assert t["nature"] == "temporary" and t["end"] == "2026-11-03T23:59:00"
    assert t["has_exemption"] is False and t["exemption"] is None and t["operator"] is None
