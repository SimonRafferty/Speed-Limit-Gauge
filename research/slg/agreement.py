"""Snap another source's limits onto OSM ways and score agreement."""
from pyproj import Transformer
from shapely import STRtree
from shapely.ops import transform

_TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)


def to_bng(geom):
    """WGS84 lon/lat geometry -> British National Grid metres."""
    return transform(_TO_BNG.transform, geom)


def snap_to_ways(features, ways, max_m: float) -> list[tuple[int, int, float]]:
    """For each feature, the nearest way within max_m: (feature_idx, way_idx, distance_m).

    All geometries must already be in a metric CRS (BNG).
    """
    tree = STRtree(ways)
    idx, dist = tree.query_nearest(features, max_distance=max_m, return_distance=True,
                                   all_matches=False)
    return [(int(f), int(w), round(float(d), 2)) for (f, w), d in zip(idx.T, dist)]


def compare(rows: list[dict]) -> dict:
    """rows: osm_kind, osm_mph (or None), src_mph. National-limit OSM kinds are
    counted separately because their mph depends on vehicle class."""
    c = {"n": 0, "agree": 0, "osm_higher": 0, "osm_lower": 0, "osm_untagged": 0, "osm_national": 0}
    for r in rows:
        c["n"] += 1
        if r["osm_kind"] in ("nsl_single", "nsl_dual", "motorway", "national"):
            c["osm_national"] += 1
        elif r["osm_mph"] is None:
            c["osm_untagged"] += 1
        elif r["osm_mph"] == r["src_mph"]:
            c["agree"] += 1
        elif r["osm_mph"] > r["src_mph"]:
            c["osm_higher"] += 1
        else:
            c["osm_lower"] += 1
    return c
