"""Spherical-earth distance helpers (lon/lat in degrees, results in metres)."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6371008.8


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def line_length_m(coords: list[tuple[float, float]]) -> float:
    return sum(haversine_m(*a, *b) for a, b in zip(coords, coords[1:]))
