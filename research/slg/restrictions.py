"""Parse OSM height/width (metres) and weight (tonnes) restriction values, GB conventions.

Unparseable values and sentinels ('default', 'none', ...) return None; callers count them
separately so data-quality numbers stay honest.
"""
import re

FEET_M = 0.3048
INCH_M = 0.0254

_METRES = re.compile(r"^(\d+(?:\.\d+)?)\s*m?$")
_FEET_INCHES = re.compile(r"""^(\d+)\s*(?:'|ft)\s*(?:(\d+(?:\.\d+)?)\s*(?:"|''|in)?)?$""")
_TONNES = re.compile(r"^(\d+(?:\.\d+)?)\s*t?$")
_KG = re.compile(r"^(\d+(?:\.\d+)?)\s*kg$")


def parse_length_m(raw) -> float | None:
    if not isinstance(raw, str):
        return None
    v = raw.strip().lower()
    if m := _METRES.match(v):
        return float(m[1])
    if m := _FEET_INCHES.match(v):
        return round(int(m[1]) * FEET_M + float(m[2] or 0) * INCH_M, 3)
    return None


def parse_weight_t(raw) -> float | None:
    if not isinstance(raw, str):
        return None
    v = raw.strip().lower()
    if m := _TONNES.match(v):
        return float(m[1])
    if m := _KG.match(v):
        return float(m[1]) / 1000
    return None
