"""Parse OSM `maxspeed` values as used in Great Britain.

kind values:
  explicit    - a numeric limit with a unit; mph is set
  nsl_single  - GB:nsl_single (national limit, single carriageway)
  nsl_dual    - GB:nsl_dual
  motorway    - GB:motorway
  national    - national limit without carriageway type. Downstream code must
                treat it as the single-carriageway national limit (the lower
                value), never dual carriageway or motorway.
  nonstandard - numeric limit that is not a standard UK limit (likely a
                tagging error); mph is None
  variable    - signals / variable (smart motorway, VMS)
  ambiguous   - bare number; km/h by OSM default but usually meant as mph in GB
  multi       - several values separated by ';'
  none        - 'none' (not a legal UK value)
  unparsed    - anything else
  absent      - no value
"""
import re
from dataclasses import dataclass

STANDARD_MPH = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70)
KMH_PER_MPH = 1.609344

_NATIONAL = {
    "gb:nsl_single": "nsl_single",
    "gb:nsl_dual": "nsl_dual",
    "gb:motorway": "motorway",
    "gb:national": "national",
    "national": "national",
    "uk:nsl_single": "nsl_single",
    "uk:nsl_dual": "nsl_dual",
    "uk:motorway": "motorway",
    "uk:national": "national",
    "gb:nsl": "national",
}
_MPH = re.compile(r"^(\d+(?:\.\d+)?)\s*mph$")
_KMH = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:km/h|kmh|kph)$")
_BARE = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class Parsed:
    kind: str
    mph: int | None = None


def snap_mph(mph: float) -> int | None:
    """Nearest standard UK limit if within 1.5 mph, else None."""
    nearest = min(STANDARD_MPH, key=lambda s: abs(s - mph))
    return nearest if abs(nearest - mph) <= 1.5 else None


def _explicit_or_nonstandard(mph: int | None) -> Parsed:
    return Parsed("nonstandard") if mph is None else Parsed("explicit", mph)


def parse_maxspeed(raw) -> Parsed:
    if not isinstance(raw, str) or not raw.strip():
        return Parsed("absent")
    v = raw.strip().lower()
    if ";" in v:
        return Parsed("multi")
    if v in _NATIONAL:
        return Parsed(_NATIONAL[v])
    if v in ("signals", "variable"):
        return Parsed("variable")
    if v == "none":
        return Parsed("none")
    if m := _MPH.match(v):
        val = float(m[1])
        ok = val.is_integer() and int(val) in STANDARD_MPH
        return _explicit_or_nonstandard(int(val) if ok else None)
    if m := _KMH.match(v):
        return _explicit_or_nonstandard(snap_mph(float(m[1]) / KMH_PER_MPH))
    if _BARE.match(v):
        return Parsed("ambiguous")
    return Parsed("unparsed")
