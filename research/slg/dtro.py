"""DfT D-TRO consumer client (OAuth2 client credentials) and speed-limit parser."""
import collections
import os
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import shapely
from dotenv import load_dotenv

from slg.paths import ROOT
from slg.restrictions import LENGTH_RANGE_M, WEIGHT_RANGE_T

BASES = {
    "integration": "https://dtro-integration.dft.gov.uk/v1",
    "production": "https://dtro.dft.gov.uk/v1",
}
SPEED_TYPES = ("speedLimitValueBased", "speedLimitProfileBased")
# Geometry kinds that can describe a stretch of road; points (allowed pre-v5) cannot.
LINEAR_KINDS = ("LINESTRING", "MULTILINESTRING", "POLYGON", "MULTIPOLYGON")
_RING = re.compile(r"\(([^()]*)\)")


class DtroClient:
    def __init__(self, client_id: str, client_secret: str, env: str = "production", session=requests):
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
    return DtroClient(cid, secret, os.getenv("DTRO_ENV", "production"), session)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _place_geometries(prov: dict) -> list[str]:
    """EWKT strings of a provision's regulated places, excluding diversion routes
    (the signed alternative route is not where the regulation applies)."""
    return [s for place in _as_list(prov.get("regulatedPlace"))
            if place.get("type") != "diversionRoute"
            for s in _strings(place) if s.startswith("SRID=")]


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
            # From orderReportingPoint: flags revoked / proposed orders the speed
            # object's own nature (permanent / temporary) cannot express.
            "order_nature": order_nature(prov, reg),
            "is_dynamic": reg.get("isDynamic"),
            **_time_validity(reg),
            "geometries": _place_geometries(prov),
        })
    return out


def _try_wkt(body: str):
    try:
        g = shapely.from_wkt(body)
    except shapely.errors.ShapelyError:
        return None
    return None if g is None or g.is_empty else g


def _split_ring_polygons(body: str, stats):
    """Polygon / MultiPolygon from a POLYGON body whose rings were all published unclosed.

    Production shape: POLYGON((outer),(hole),...) with every ring written without its
    closing vertex and the last ring ending on a stray copy of the outer ring's first
    vertex. Each piece is closed onto its own start. A piece inside an earlier shell is
    a hole of that shell; a piece outside every shell starts a new part. Pieces with
    fewer than 3 distinct points are dropped. stats gets shell_with_holes / multipart /
    single_ring and pieces_dropped (always present, possibly 0).
    """
    pieces = [[c.strip() for c in r.split(",") if c.strip()] for r in _RING.findall(body)]
    if len(pieces) > 1 and len(pieces[-1]) > 1 and pieces[-1][-1] == pieces[0][0]:
        pieces[-1] = pieces[-1][:-1]
    rings, dropped = [], 0
    for piece in pieces:
        g = None
        if len(set(piece)) >= 3:
            g = _try_wkt(f"POLYGON(({', '.join(piece + [piece[0]])}))")
        if g is None:
            dropped += 1
        else:
            rings.append(g)
    stats["pieces_dropped"] += dropped
    if not rings:
        return None
    shells: list[list] = []  # [shell polygon, [hole rings]]
    for ring in rings:
        probe = ring.representative_point()
        owner = next((sh for sh in shells if sh[0].contains(probe)), None)
        if owner is None:
            shapely.prepare(ring)
            shells.append([ring, []])
        else:
            owner[1].append(ring.exterior.coords)
    polys = [shapely.Polygon(sh.exterior.coords, holes) for sh, holes in shells]
    if len(polys) > 1:
        stats["multipart"] += 1
        return shapely.MultiPolygon(polys)
    stats["shell_with_holes" if shells[0][1] else "single_ring"] += 1
    return polys[0]


def parse_ewkt(ewkt: str, stats=None):
    """D-TRO EWKT (BNG) -> (shapely geometry or None, reason).

    reason is "ok", "repaired_split_ring", "not_27700", "kind_<KIND>" (e.g. points,
    which cannot describe a stretch of road) or "unparsable". A POLYGON whose rings
    were published unclosed is rebuilt as shell(s) with holes (see _split_ring_polygons);
    stats (a Counter, optional) receives the rebuild outcome and pieces_dropped.
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
        g = _split_ring_polygons(body, stats)
        if g is not None:
            return g, "repaired_split_ring"
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


# Plausibility bounds as for OSM values (slg.restrictions); vehicle length goes higher.
_BOUNDS = {"height_m": LENGTH_RANGE_M, "width_m": LENGTH_RANGE_M,
           "length_m": (2.0, 30.0), "weight_t": WEIGHT_RANGE_T}


def _walk_dicts(obj, skip_negated: bool = False):
    """Every dict nested anywhere in obj, depth first. With skip_negated, subtrees of a
    negated condition (an exemption such as "except vehicles under 2 t") are skipped."""
    if isinstance(obj, dict):
        if skip_negated and obj.get("negate") is True:
            return
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v, skip_negated)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v, skip_negated)


def _limit_values(reg: dict) -> dict:
    """First stated value of each characteristic, outside exemption subtrees. typeOfWeight
    is taken from the same maximumGrossWeightCharacteristic object as its weight. Values
    outside _BOUNDS become None and are counted in out_of_range."""
    out = {col: None for _, col in _CHARACTERISTICS.values()} | {"type_of_weight": None}
    for d in _walk_dicts(reg, skip_negated=True):
        for name, (key, col) in _CHARACTERISTICS.items():
            ch = d.get(name)
            if out[col] is None and isinstance(ch, dict) and ch.get(key) is not None:
                out[col] = ch[key]
                if col == "weight_t":
                    out["type_of_weight"] = ch.get("typeOfWeight")
    out["out_of_range"] = 0
    for col, (lo, hi) in _BOUNDS.items():
        v = out[col]
        if v is not None and not (isinstance(v, (int, float)) and lo <= v <= hi):
            out[col] = None
            out["out_of_range"] += 1
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
    return {"operator": operator, "has_exemption": negated,
            "exemption": ";".join(map(str, exemptions)) or None}


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
            "geometries": _place_geometries(prov),
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
    """'temporary' / 'experimental' / 'permanent' / 'revoked' / 'proposed' / 'unknown'.

    The production dump has no explicit nature on non-speed regulations; the provision's
    orderReportingPoint says which kind of order it is (ttroTtmo* = temporary order or
    notice, specialEvent* = event order, permanent* / experimentalMakingPermanent).
    *Revocation revokes an order (not in force); *NoticeOfIntention is a proposal that
    has not been made yet. Neither should raise a warning.
    """
    orp = provision.get("orderReportingPoint") or ""
    if "Revocation" in orp:
        return "revoked"
    if "NoticeOfIntention" in orp:
        return "proposed"
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
            "direction": _direction(prov),
            "geometries": _place_geometries(prov),
        })
    return out


def _direction(prov: dict) -> str | None:
    """Direction of the regulated (non-diversion) linear place, e.g. startToEnd for a
    one-way no-entry, or None when not stated."""
    for place in _as_list(prov.get("regulatedPlace")):
        if place.get("type") != "diversionRoute":
            d = _find(place, "direction")
            if isinstance(d, str):
                return d
    return None


# --- time validity -----------------------------------------------------------------
# D-TRO times (timeValidity start/end) are Europe/London local wall-clock times, while the
# dump's Last-Modified header is GMT (one hour behind in BST), so the dump date is
# converted to Europe/London before comparing. Comparisons are on ISO strings.
# Not evaluated yet (Stage 4): recurring periods (validPeriod, days, times of day) and
# the provision actionType (amendments / revokes of earlier provisions).
LONDON = ZoneInfo("Europe/London")
NOT_IN_FORCE_NATURES = ("revoked", "proposed")


def dump_date(last_modified: str | None, fallback: datetime | None) -> str | None:
    """ISO Europe/London local time the dump describes: its Last-Modified header (GMT),
    else the newest record LastUpdated (taken as already local)."""
    if last_modified:
        try:
            when = parsedate_to_datetime(last_modified)
            return when.astimezone(LONDON).replace(tzinfo=None).isoformat()
        except (TypeError, ValueError):
            pass
    return fallback.replace(microsecond=0).isoformat() if fallback else None


def _iso(col) -> pd.Series:
    """Column of ISO strings (any dtype, all-NaN float included) as nullable strings."""
    return pd.Series(col, dtype="object").astype("string")


def _cmp(col, as_of: str, op: str, missing: bool) -> pd.Series:
    s = _iso(col)
    res = s < as_of if op == "<" else s > as_of
    return res.fillna(missing).astype(bool)  # missing value -> `missing`


def ended(end, as_of: str) -> pd.Series:
    """End strictly before as_of (an order ending exactly at as_of is still in force)."""
    return _cmp(end, as_of, "<", False)


def not_started(start, as_of: str) -> pd.Series:
    """Start strictly after as_of."""
    return _cmp(start, as_of, ">", False)


def in_force(start, end, as_of: str) -> pd.Series:
    """timeValidity covers as_of: start missing or <= as_of, end missing or >= as_of."""
    return ~not_started(start, as_of) & ~ended(end, as_of)


def order_in_force(df: pd.DataFrame, as_of: str) -> pd.Series:
    """Provisions (nature, start, end columns) in force at as_of: inside their time
    window, not revoked or proposed, and temporary orders must state a window."""
    s, e = _iso(df["start"]), _iso(df["end"])
    dated = (df["nature"] != "temporary").to_numpy() | s.notna().to_numpy() | e.notna().to_numpy()
    nature_ok = ~df["nature"].isin(NOT_IN_FORCE_NATURES).to_numpy()
    return pd.Series(in_force(s, e, as_of).to_numpy() & dated & nature_ok, index=df.index)
