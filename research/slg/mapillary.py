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


SPEED_VALUES = ",".join(
    f"regulatory--maximum-speed-limit-{n}--g1"
    for n in (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70))
LIMIT = 2000
MAX_DEPTH = 3


def _split(cell):
    w, s, e, n = cell
    mx, my = round((w + e) / 2, 6), round((s + n) / 2, 6)
    return [(w, s, mx, my), (mx, s, e, my), (w, my, mx, n), (mx, my, e, n)]


def fetch_features(bbox, access_token: str, session=requests,
                   pause: float = 0.2) -> tuple[list[dict], int, int]:
    """Speed-related map features in bbox, fetched in 0.05 degree cells.

    Returns (features, failed_cells, truncated_cells).
    - The request filters speed-limit sign classes server-side (object_values; only
      the common --g1 variants), and "speed" in object_value is still checked
      client-side as a fallback.
    - The API returns at most LIMIT features per request, so a cell that returns
      exactly LIMIT is split into 4 and re-queried, up to MAX_DEPTH levels. A cell
      still full at the deepest level is counted in truncated_cells (some signs
      are then missing).
    - A request that errors (HTTP error, timeout, bad JSON) is counted in
      failed_cells and skipped rather than aborting the pull; the result is then
      incomplete. Features are de-duplicated by id across overlapping sub-cells.
    """
    feats: dict[str, dict] = {}
    stats = {"failed": 0, "truncated": 0}

    def query(cell, depth):
        try:
            r = session.get(ENDPOINT, timeout=60, params={
                "access_token": access_token,
                "fields": "id,object_value,geometry,first_seen_at,last_seen_at",
                "bbox": ",".join(str(v) for v in cell),
                "object_values": SPEED_VALUES,
                "limit": LIMIT,
            })
            r.raise_for_status()
            data = r.json().get("data", [])
        except (requests.RequestException, ValueError):
            stats["failed"] += 1
            return
        time.sleep(pause)
        if len(data) >= LIMIT:
            if depth < MAX_DEPTH:
                for sub in _split(cell):
                    query(sub, depth + 1)
                return
            stats["truncated"] += 1
        for f in data:
            if "speed" in f.get("object_value", ""):
                feats[f["id"]] = f

    for cell in chunk_bbox(bbox):
        query(cell, 0)
    return list(feats.values()), stats["failed"], stats["truncated"]
