"""Overpass API probe: latency and bytes per km for a live maxspeed query."""
import time

import requests

from slg.geo import line_length_m
from slg.osm_extract import DRIVABLE

ENDPOINT = "https://overpass-api.de/api/interpreter"


def build_query(bbox: tuple[float, float, float, float]) -> str:
    w, s, e, n = bbox
    highways = "|".join(sorted(DRIVABLE))
    return (f'[out:json][timeout:60];'
            f'way["highway"~"^({highways})$"]({s},{w},{n},{e});'
            f'out tags geom;')


def km_in_response(resp: dict) -> float:
    total = 0.0
    for el in resp.get("elements", []):
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        total += line_length_m(coords)
    return total / 1000


def probe(bbox, session=requests) -> dict:
    t0 = time.perf_counter()
    r = session.post(ENDPOINT, data={"data": build_query(bbox)}, timeout=90,
                     headers={"User-Agent": "speed-limit-gauge-research/0.1"})
    seconds = time.perf_counter() - t0
    r.raise_for_status()
    body = r.content
    km = km_in_response(r.json())
    return {"bytes": len(body), "seconds": round(seconds, 2), "km": round(km, 1),
            "ways": len(r.json().get("elements", [])),
            "bytes_per_km": round(len(body) / km) if km else None}
