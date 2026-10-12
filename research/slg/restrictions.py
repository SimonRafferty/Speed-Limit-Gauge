"""Parse OSM height/width (metres) and weight (tonnes) restriction values, GB conventions.

Unparseable, implausible and placeholder values ('default', 'none', ...) return None;
callers count them separately (see `is_placeholder`) so data-quality numbers stay honest.
"""
import re

FEET_M = 0.3048
INCH_M = 0.0254
CWT_T = 0.0508  # UK long hundredweight (112 lb) in tonnes

# Plausibility bounds. Anything outside is treated as a tagging error, not a restriction.
LENGTH_RANGE_M = (1.0, 10.0)
WEIGHT_RANGE_T = (0.5, 60.0)

# Sentinel values mappers use instead of a number; they must never trigger a warning.
PLACEHOLDERS = {"default", "below_default", "none", "no_sign", "no_indications", "unsigned"}

_NUM = r"(\d+(?:[.,]\d+)?)"
_METRES = re.compile(rf"^{_NUM}\s*(?:m|metres?|meters?)?$")
_CM = re.compile(rf"^{_NUM}\s*cm$")
_FEET_INCHES = re.compile(rf"""^(\d+)\s*(?:'|ft)\s*(?:{_NUM}\s*(?:"|''|in)?)?$""")
# A UK "ton" (long ton, 1.016 t) is close enough to a tonne for a sign value.
_TONNES = re.compile(rf"^{_NUM}\s*(?:t|tonnes?|tons?)?$")
_KG = re.compile(rf"^{_NUM}\s*kg$")
_CWT = re.compile(rf"^{_NUM}\s*cwt$")

# Curly quotes and primes mappers paste from word processors.
_QUOTES = str.maketrans({"’": "'", "‘": "'", "′": "'",
                         "”": '"', "“": '"', "″": '"'})


def _num(s: str) -> float:
    """Number with either decimal point or decimal comma."""
    return float(s.replace(",", "."))


def _normalise(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    return raw.strip().lower().translate(_QUOTES)


def _bounded(value: float, lo_hi: tuple[float, float]) -> float | None:
    lo, hi = lo_hi
    return value if lo <= value <= hi else None


def is_placeholder(raw) -> bool:
    """True for sentinel values like 'default' or 'none' (not a failure to parse, not a limit)."""
    v = _normalise(raw)
    return v is not None and v in PLACEHOLDERS


def parse_length_m(raw) -> float | None:
    v = _normalise(raw)
    if v is None:
        return None
    if m := _METRES.match(v):
        value = _num(m[1])
    elif m := _CM.match(v):
        value = _num(m[1]) / 100
    elif m := _FEET_INCHES.match(v):
        inches = _num(m[2]) if m[2] else 0.0
        if inches >= 12:
            return None
        value = round(int(m[1]) * FEET_M + inches * INCH_M, 3)
    else:
        return None
    return _bounded(value, LENGTH_RANGE_M)


def parse_weight_t(raw) -> float | None:
    v = _normalise(raw)
    if v is None:
        return None
    if m := _TONNES.match(v):
        value = _num(m[1])
    elif m := _KG.match(v):
        value = _num(m[1]) / 1000
    elif m := _CWT.match(v):
        value = round(_num(m[1]) * CWT_T, 3)
    else:
        return None
    return _bounded(value, WEIGHT_RANGE_T)
