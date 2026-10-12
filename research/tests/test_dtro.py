from slg.dtro import DtroClient, speed_provisions

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


from slg.dtro import parse_ewkt


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


def test_parse_ewkt_repairs_outer_ring_split_into_pieces():
    # Seen in production: one ring published as several unclosed pieces.
    g, why = parse_ewkt("SRID=27700;POLYGON((0 0, 10 0, 10 10),(0 10, 0 0))")
    assert why == "repaired_split_ring"
    assert g.geom_type == "Polygon" and g.area == 100


from slg.dtro import restriction_provisions

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
