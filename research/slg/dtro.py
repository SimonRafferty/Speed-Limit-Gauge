"""DfT D-TRO consumer client (OAuth2 client credentials) and speed-limit parser."""
import collections
import os
import re
import time

import requests
import shapely
from dotenv import load_dotenv

from slg.paths import ROOT

BASES = {
    "integration": "https://dtro-integration.dft.gov.uk/v1",
    "production": "https://dtro.dft.gov.uk/v1",
}
SPEED_TYPES = ("speedLimitValueBased", "speedLimitProfileBased")
# Geometry kinds that can describe a stretch of road; points (allowed pre-v5) cannot.
LINEAR_KINDS = ("LINESTRING", "MULTILINESTRING", "POLYGON", "MULTIPOLYGON")
_RING = re.compile(r"\(([^()]*)\)")


class DtroClient:
    def __init__(self, client_id: str, client_secret: str, env: str = "integration", session=requests):
        self.base = BASES[env]
        self._auth = (client_id, client_secret)
        self._session = session
        self._token = None
        self._expires = 0.0

    def token(self) -> str:
        # Refresh a minute early so a long download never starts with a dying token.
        if self._token is None or time.time() > self._expires - 60:
            r = self._session.post(f"{self.base}/oauth-generator", auth=self._auth,
                                   data={"grant_type": "client_credentials"}, timeout=30)
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._expires = time.time() + float(body.get("expires_in", 1799))
        return self._token

    def _get(self, path: str):
        r = self._session.get(f"{self.base}{path}",
                              headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
        r.raise_for_status()
        return r.json()

    def all_records_url(self) -> str:
        """Signed URL (valid 60 min) to a CSV of every published D-TRO."""
        return self._get("/dtros/all")

    def get(self, dtro_id: str) -> dict:
        return self._get(f"/dtros/{dtro_id}")


def from_env(session=requests) -> DtroClient | None:
    load_dotenv(ROOT / ".env")
    cid, secret = os.getenv("DTRO_CLIENT_ID"), os.getenv("DTRO_CLIENT_SECRET")
    if not cid or not secret:
        return None
    return DtroClient(cid, secret, os.getenv("DTRO_ENV", "integration"), session)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _as_list(obj) -> list:
    """The dump stores some arrays as a single object; normalise to a list of dicts."""
    items = obj if isinstance(obj, list) else [obj] if obj else []
    return [o for o in items if isinstance(o, dict)]


def _regulations(record: dict):
    """Yield (provision, regulation, regulation_type) for every regulation in a record.

    The type is read from regulationType (v5), generalRegulation.regulationType
    (pre-v5) or, failing both, inferred from a top-level speedLimit* object: the
    production dump (schema 3.5/4.0) stores speed regulations with no
    regulationType at all.
    """
    source = record.get("data", {}).get("source", {})
    for prov in _as_list(source.get("provision")):
        for reg in _as_list(prov.get("regulation")):
            general = reg.get("generalRegulation")
            rtype = reg.get("regulationType") or (
                general.get("regulationType") if isinstance(general, dict) else None)
            if not rtype:
                rtype = next((t for t in SPEED_TYPES if isinstance(reg.get(t), dict)), None)
            yield prov, reg, rtype


def speed_provisions(record: dict) -> list[dict]:
    """One row per speed-limit regulation in a D-TRO record (schema v3, v4 and v5 shapes)."""
    out = []
    for prov, reg, rtype in _regulations(record):
        if rtype not in SPEED_TYPES:
            continue
        detail = reg.get(rtype, {})
        out.append({
            "dtro_id": record.get("id"),
            "schema_version": record.get("schemaVersion"),
            "provision_ref": prov.get("reference"),
            "action": prov.get("actionType"),
            "regulation_type": rtype,
            "limit_type": detail.get("type"),
            "mph": detail.get("mphValue"),
            "nature": detail.get("nature"),
            "is_dynamic": reg.get("isDynamic"),
            **_time_validity(reg),
            "geometries": [s for s in _strings(prov.get("regulatedPlace", []))
                           if s.startswith("SRID=")],
        })
    return out


def _try_wkt(body: str):
    try:
        g = shapely.from_wkt(body)
    except shapely.errors.ShapelyError:
        return None
    return None if g is None or g.is_empty else g


def _split_ring_polygons(body: str, stats) -> list:
    """Polygons from a POLYGON body whose rings were published unclosed.

    Production shape: several separate rings, each written without its closing
    vertex, and the last ring ending on a stray copy of the first ring's start.
    Junctions between consecutive pieces are hundreds of metres to km apart, so the
    pieces are distinct rings: each is closed onto its own start. Pieces with fewer
    than 3 distinct points are dropped.
    """
    pieces = [[c.strip() for c in r.split(",") if c.strip()] for r in _RING.findall(body)]
    if len(pieces) > 1 and len(pieces[-1]) > 1 and pieces[-1][-1] == pieces[0][0]:
        pieces[-1] = pieces[-1][:-1]
    polys = []
    for piece in pieces:
        distinct = list(dict.fromkeys(piece))
        g = _try_wkt(f"POLYGON(({', '.join(piece + [piece[0]])}))") if len(distinct) >= 3 else None
        if g is None:
            stats["pieces_dropped"] += 1
        else:
            stats["pieces_kept"] += 1
            polys.append(g)
    return polys


def parse_ewkt(ewkt: str, stats=None):
    """D-TRO EWKT (BNG) -> (shapely geometry or None, reason).

    reason is "ok", "repaired_split_ring", "not_27700", "kind_<KIND>" (e.g. points,
    which cannot describe a stretch of road) or "unparsable". A POLYGON whose rings
    were published unclosed (see _split_ring_polygons) becomes a MultiPolygon of the
    closed rings; stats (a Counter, optional) receives pieces_kept / pieces_dropped.
    The result is not made valid: make_valid takes seconds on 30k-vertex zone
    polygons, and point-in-polygon and distance queries do not need it.
    """
    stats = collections.Counter() if stats is None else stats
    srid, _, body = ewkt.partition(";")
    if srid.strip().upper() != "SRID=27700":
        return None, "not_27700"
    kind = body.lstrip().split("(", 1)[0].strip().upper()
    if kind not in LINEAR_KINDS:
        return None, f"kind_{kind or 'unknown'}"
    g = _try_wkt(body)
    if g is not None:
        return g, "ok"
    if kind == "POLYGON":
        polys = _split_ring_polygons(body, stats)
        if polys:
            return shapely.MultiPolygon(polys), "repaired_split_ring"
    return None, "unparsable"


RESTRICTION_TYPES = (
    "dimensionMaximumHeightStructural", "dimensionMaximumHeightWithTRO",
    "dimensionMaximumWidth", "dimensionMaximumLength",
    "dimensionMaximumWeightEnvironmental", "dimensionMaximumWeightStructural",
)
# characteristic object -> (value key, output column)
_CHARACTERISTICS = {
    "maximumHeightCharacteristic": ("vehicleHeight", "height_m"),
    "maximumWidthCharacteristic": ("vehicleWidth", "width_m"),
    "maximumLengthCharacteristic": ("vehicleLength", "length_m"),
    "maximumGrossWeightCharacteristic": ("grossVehicleWeight", "weight_t"),
}


def _walk_dicts(obj):
    """Every dict nested anywhere in obj, depth first."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v)


def _limit_values(reg: dict) -> dict:
    """First stated value of each characteristic. typeOfWeight is taken from the same
    maximumGrossWeightCharacteristic object as the weight it qualifies."""
    out = {col: None for _, col in _CHARACTERISTICS.values()} | {"type_of_weight": None}
    for d in _walk_dicts(reg):
        for name, (key, col) in _CHARACTERISTICS.items():
            ch = d.get(name)
            if out[col] is None and isinstance(ch, dict) and ch.get(key) is not None:
                out[col] = ch[key]
                if col == "weight_t":
                    out["type_of_weight"] = ch.get("typeOfWeight")
    return out


def _time_validity(reg: dict) -> dict:
    tv = _find(reg, "timeValidity")
    tv = tv if isinstance(tv, dict) else {}
    return {"start": tv.get("start"), "end": tv.get("end")}


def _conditions(reg: dict) -> dict:
    """Condition-tree facts that decide whether a restriction applies to a vehicle.

    A negated condition is an exemption ("except loading and unloading"); its text is
    the negated condition's access/vehicle types joined with ';'.
    """
    operator, negated, exemptions = None, False, []
    for d in _walk_dicts(reg):
        if operator is None and isinstance(d.get("operator"), str):
            operator = d["operator"]
        if d.get("negate") is True:
            negated = True
            for k in ("accessConditionType", "vehicleType", "vehicleUsage", "permitType"):
                v = _find(d, k)
                exemptions += v if isinstance(v, list) else [v] if v else []
    return {"operator": operator, "has_negated_condition": negated,
            "has_exemption": negated, "exemption": ";".join(map(str, exemptions)) or None}


def restriction_provisions(record: dict) -> list[dict]:
    """One row per height/width/length/weight regulation in a D-TRO record, with the
    order nature, time validity and condition facts that decide applicability."""
    out = []
    for prov, reg, rtype in _regulations(record):
        if rtype not in RESTRICTION_TYPES:
            continue
        out.append({
            "dtro_id": record.get("id"),
            "schema_version": record.get("schemaVersion"),
            "provision_ref": prov.get("reference"),
            "action": prov.get("actionType"),
            "regulation_type": rtype,
            **_limit_values(reg),
            "nature": order_nature(prov, reg),
            "is_dynamic": reg.get("isDynamic"),
            **_time_validity(reg),
            **_conditions(reg),
            "geometries": [s for s in _strings(prov.get("regulatedPlace", []))
                           if s.startswith("SRID=")],
        })
    return out


# Orders that close a road (or a movement along it) to motor vehicles: red X sources (spec 7.1a).
# publicRightOfWayClosure is not in the published spec list but appears in the production
# dump alongside miscPROWClosure with the same meaning, so it is counted too.
PROHIBITION_TYPES = (
    "motorVehiclesProhibited", "movementOrderProhibitedAccess", "miscRoadClosure",
    "miscPROWClosure", "bannedMovementNoEntry", "publicRightOfWayClosure",
)


def order_nature(provision: dict, regulation: dict) -> str:
    """'temporary' / 'experimental' / 'permanent' / 'unknown' for a provision.

    The production dump has no explicit nature on non-speed regulations; the provision's
    orderReportingPoint says which kind of order it is (ttroTtmo* = temporary order or
    notice, specialEvent* = event order, permanent* / experimentalMakingPermanent).
    """
    orp = provision.get("orderReportingPoint") or ""
    if orp.startswith(("ttro", "specialEvent")):
        return "temporary"
    if orp == "experimentalMakingPermanent" or orp.startswith("permanent"):
        return "permanent"
    if orp.startswith("experimental"):
        return "experimental"
    if regulation.get("isDynamic") is True or regulation.get("temporaryRegulation"):
        return "temporary"
    return "unknown"


def _find(obj, key):
    """First value stored under `key` anywhere in obj (depth first), else None."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            if (found := _find(v, key)) is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            if (found := _find(v, key)) is not None:
                return found
    return None


def _has_recurring(obj) -> bool:
    return any(_find(obj, k) is not None for k in (
        "recurringDayWeekMonthPeriod", "recurringTimePeriodOfDay", "recurringSpecialDay"))


def prohibition_provisions(record: dict) -> list[dict]:
    """One row per prohibition / closure regulation in a D-TRO record.

    has_vehicle_condition marks a vehicle-class ban (e.g. over 3.5 t), not a full closure;
    has_access_condition marks "except for access" style exemptions.
    """
    out = []
    for prov, reg, rtype in _regulations(record):
        if rtype not in PROHIBITION_TYPES:
            continue
        tv = _find(reg, "timeValidity")
        tv = tv if isinstance(tv, dict) else {}
        out.append({
            "dtro_id": record.get("id"),
            "schema_version": record.get("schemaVersion"),
            "provision_ref": prov.get("reference"),
            "action": prov.get("actionType"),
            "regulation_type": rtype,
            "order_reporting_point": prov.get("orderReportingPoint"),
            "nature": order_nature(prov, reg),
            "is_dynamic": reg.get("isDynamic"),
            "start": tv.get("start"),
            "end": tv.get("end"),
            "has_recurring_period": _has_recurring(reg),
            "has_vehicle_condition": _find(reg, "vehicleCharacteristics") is not None,
            "has_access_condition": _find(reg, "accessCondition") is not None,
            "geometries": [s for s in _strings(prov.get("regulatedPlace", []))
                           if s.startswith("SRID=")],
        })
    return out
