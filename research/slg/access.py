"""Classify a way's legality for motor vehicles from its OSM access tags (spec 7.1a).

Result is one of:
  prohibited  - an explicit "no" for motor vehicles on the deciding key (red X)
  permission  - legal only with permission: private, destination ("except for access")...,
                or a footpath/bridleway/restricted-byway designation with no access value
                (often a private drive or estate road driven with lawful authority) (yellow X)
  conditional - a time/condition rule (`*:conditional`) decides; needs evaluating at drive time
  allowed     - lawful for anyone (yes / designated / permissive)
  unknown     - nothing relevant (an ordinary public road) or an ambiguous value

Legality is computed for a PRIVATE CAR. `goods`/`hgv` (and `maxweight:goods` etc.) are not
consulted: Commercial-mode handling, where a van is `goods` and those keys take precedence
over `motor_vehicle`, is Stage 4 work.

Deliberately simple: a semicolon list counts only when every part falls in the same class;
direction-specific keys (`:forward`/`:backward`) are not interpreted.
"""

# Most specific first: a value here overrides any value on a key after it.
KEYS = ("motorcar", "motor_vehicle", "vehicle", "access")

PROHIBITED_VALUES = frozenset({"no"})
# Lawful only for the owner or with permission / a lawful purpose (yellow X).
PERMISSION_VALUES = frozenset({
    "private", "permit", "destination", "customers", "delivery", "agricultural", "forestry",
})
# Lawful for anyone (no X). "discouraged" is legal, merely advised against.
ALLOWED_VALUES = frozenset({"yes", "designated", "permissive", "discouraged"})

# Public rights of way that give no public motor-vehicle right. Alone, they mean
# "permission" (yellow X), not "prohibited": the landowner and those with lawful
# authority may still drive them.
NO_MOTOR_DESIGNATIONS = frozenset({"restricted_byway", "public_bridleway", "public_footpath"})
ALL_TRAFFIC_DESIGNATIONS = frozenset({"byway_open_to_all_traffic"})


def _value(tags: dict, key: str) -> str | None:
    """Normalised tag value, or None for missing / NaN / empty (pandas rows carry NaN)."""
    v = tags.get(key)
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v or None


def _classify(value: str) -> str:
    """Class of one value; a semicolon list only when all its parts agree."""
    if ";" in value:
        classes = {_classify(part.strip()) for part in value.split(";") if part.strip()}
        return classes.pop() if len(classes) == 1 else "unknown"
    if value in PROHIBITED_VALUES:
        return "prohibited"
    if value in PERMISSION_VALUES:
        return "permission"
    if value in ALLOWED_VALUES:
        return "allowed"
    return "unknown"


def motor_legality(tags: dict) -> str:
    """'prohibited' / 'permission' / 'conditional' / 'allowed' / 'unknown' for motor vehicles."""
    deciding = next((k for k in KEYS if _value(tags, k) is not None), None)

    # A conditional rule on the deciding key, or on anything more specific, governs.
    # With no plain key at all, a conditional on any key governs.
    scope = KEYS[:KEYS.index(deciding) + 1] if deciding else KEYS
    if any(_value(tags, k + ":conditional") is not None for k in scope):
        return "conditional"

    # An explicit, recognised value on the most specific key decides, even over a
    # footpath/bridleway designation (e.g. a public footpath along a private track:
    # lawful for the owner and those with permission).
    result = _classify(_value(tags, deciding)) if deciding else "unknown"
    if result != "unknown":
        return result

    designation = _value(tags, "designation")
    if designation in NO_MOTOR_DESIGNATIONS:
        return "permission"
    if deciding is None and designation in ALL_TRAFFIC_DESIGNATIONS:
        return "allowed"
    return "unknown"
