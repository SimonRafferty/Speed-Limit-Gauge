"""Parse OSM `maxspeed` values as used in Great Britain.

kind values:
  explicit    - a numeric limit with a unit; mph is set
  nsl_single  - GB:nsl_single (national limit, single carriageway)
  nsl_dual    - GB:nsl_dual
  motorway    - GB:motorway
  national    - national limit without carriageway type
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
}
_MPH = re.compile(r"^(\d+(?:\.\d+)?)\s*mph$")
_KMH = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:km/h|kmh|kph)$")
_BARE = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class Parsed:
    kind: str
    mph: int | None = None


def snap_mph(mph: float) -> int:
    """Snap a converted value to the nearest standard UK limit if within 1.5 mph."""
    nearest = min(STANDARD_MPH, key=lambda s: abs(s - mph))
    return nearest if abs(nearest - mph) <= 1.5 else round(mph)


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
        return Parsed("explicit", round(float(m[1])))
    if m := _KMH.match(v):
        return Parsed("explicit", snap_mph(float(m[1]) / KMH_PER_MPH))
    if _BARE.match(v):
        return Parsed("ambiguous")
    return Parsed("unparsed")
