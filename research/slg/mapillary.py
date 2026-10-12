"""Mapillary map-feature (traffic sign) fetch for speed-limit signs."""
import os
import re
import time

import requests
from dotenv import load_dotenv

from slg.paths import ROOT

ENDPOINT = "https://graph.mapillary.com/map_features"
_MAX = re.compile(r"^regulatory--maximum-speed-limit-(\d+)--")


def sign_mph(object_value: str) -> int | None:
    m = _MAX.match(object_value)
    return int(m[1]) if m else None


def chunk_bbox(bbox, step: float = 0.05) -> list[tuple[float, float, float, float]]:
    w, s, e, n = bbox
    cells = []
    lat = s
    while lat < n - 1e-9:
        lon = w
        while lon < e - 1e-9:
            cells.append((round(lon, 6), round(lat, 6),
                          round(min(lon + step, e), 6), round(min(lat + step, n), 6)))
            lon += step
        lat += step
    return cells


def token() -> str | None:
    load_dotenv(ROOT / ".env")
    return os.getenv("MAPILLARY_TOKEN")


def fetch_features(bbox, access_token: str, session=requests,
                   pause: float = 0.2) -> tuple[list[dict], int]:
    """Speed-related map features in bbox, fetched in 0.05 degree cells.

    Returns (features, failed_cells). A cell whose request errors (HTTP error,
    timeout, bad JSON) is counted and skipped rather than aborting the pull, so
    callers must report failed_cells: the result is incomplete when it is > 0.
    """
    feats, failed = [], 0
    for cell in chunk_bbox(bbox):
        try:
            r = session.get(ENDPOINT, timeout=60, params={
                "access_token": access_token,
                "fields": "id,object_value,geometry,first_seen_at,last_seen_at",
                "bbox": ",".join(str(v) for v in cell),
                "limit": 2000,
            })
            r.raise_for_status()
            data = r.json().get("data", [])
        except (requests.RequestException, ValueError):
            failed += 1
            continue
        feats += [f for f in data if "speed" in f.get("object_value", "")]
        time.sleep(pause)
    return feats, failed
