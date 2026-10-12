"""Overpass API probe: latency and bytes per km for a live query.

The query fetches ALL drivable ways in the bbox (geometry plus tags), not only
those with a maxspeed tag, so bytes_per_km is bytes per km of road.
"""
import time

import requests

from slg.geo import line_length_m
from slg.osm_extract import DRIVABLE

ENDPOINT = "https://overpass-api.de/api/interpreter"


def build_query(bbox: tuple[float, float, float, float]) -> str:
    """Overpass QL for all drivable ways in bbox.

    bbox is (west, south, east, north) as used throughout slg; Overpass itself
    wants (south, west, north, east), so the order is swapped here.
    """
    w, s, e, n = bbox
    highways = "|".join(sorted(DRIVABLE))
    return (f'[out:json][timeout:60];'
            f'way["highway"~"^({highways})$"]({s},{w},{n},{e});'
            f'out tags geom;')


def km_in_response(resp: dict) -> float:
    """Total length in km of all way geometries in a parsed Overpass response."""
    total = 0.0
    for el in resp.get("elements", []):
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        total += line_length_m(coords)
    return total / 1000


def probe(bbox, session=requests) -> dict:
    """POST the query for bbox; return bytes, seconds, km, ways and bytes_per_km.

    seconds covers the request only. Raises on HTTP errors (caller records them).
    """
    t0 = time.perf_counter()
    r = session.post(ENDPOINT, data={"data": build_query(bbox)}, timeout=90,
                     headers={"User-Agent": "speed-limit-gauge-research/0.1"})
    seconds = time.perf_counter() - t0
    r.raise_for_status()
    body = r.content
    data = r.json()
    km = km_in_response(data)
    return {"bytes": len(body), "seconds": round(seconds, 2), "km": round(km, 1),
            "ways": len(data.get("elements", [])),
            "bytes_per_km": round(len(body) / km) if km else None}
