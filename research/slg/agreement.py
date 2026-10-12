"""Snap another source's limits onto OSM ways and score agreement."""
import shapely
from pyproj import Transformer
from shapely import STRtree

_TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)

NATIONAL_KINDS = ("nsl_single", "nsl_dual", "motorway", "national")


def to_bng(geom):
    """WGS84 lon/lat geometry (or array of geometries) -> British National Grid metres."""
    return shapely.transform(geom, _TO_BNG.transform, interleaved=False)


def snap_to_ways(features, ways, max_m: float,
                 all_matches: bool = False) -> list[tuple[int, int, float]]:
    """For each feature, the nearest way within max_m: (feature_idx, way_idx, distance_m).

    All geometries must already be in a metric CRS (BNG). Features with no way
    within max_m are omitted. With all_matches=True every way tied for nearest
    is returned (e.g. a point inside two overlapping polygons); results are
    sorted by feature_idx then way_idx.
    """
    if len(features) == 0 or len(ways) == 0:
        return []
    tree = STRtree(ways)
    idx, dist = tree.query_nearest(features, max_distance=max_m, return_distance=True,
                                   all_matches=all_matches)
    pairs = [(int(f), int(w), round(float(d), 2)) for (f, w), d in zip(idx.T, dist)]
    return sorted(pairs, key=lambda p: (p[0], p[1]))


def compare(rows: list[dict]) -> dict:
    """Score a source's limits against OSM. rows: osm_kind, osm_mph (or None), src_mph.

    Counters (every row falls in exactly one except n):
    - n: total rows.
    - agree / osm_higher / osm_lower: OSM has a usable numeric limit and it
      equals / exceeds / is below the source's.
    - osm_untagged: osm_kind == "absent" (no maxspeed tag at all).
    - osm_unusable: tagged but no single numeric mph (variable, multi, none,
      nonstandard, unparsed, ambiguous...) and not a national-limit kind.
    - national_consistent / national_conflict: OSM uses a national-limit kind
      (nsl_single, nsl_dual, motorway, national). These have no fixed mph, so
      the source limit is judged against the lowest national limit any vehicle
      class can have there: src_mph >= 50 is consistent; below 50 is a conflict
      (OSM implies a higher limit for every vehicle class).
    """
    c = {"n": 0, "agree": 0, "osm_higher": 0, "osm_lower": 0, "osm_untagged": 0,
         "osm_unusable": 0, "national_consistent": 0, "national_conflict": 0}
    for r in rows:
        c["n"] += 1
        if r["osm_kind"] in NATIONAL_KINDS:
            c["national_consistent" if r["src_mph"] >= 50 else "national_conflict"] += 1
        elif r["osm_kind"] == "absent":
            c["osm_untagged"] += 1
        elif r["osm_mph"] is None:
            c["osm_unusable"] += 1
        elif r["osm_mph"] == r["src_mph"]:
            c["agree"] += 1
        elif r["osm_mph"] > r["src_mph"]:
            c["osm_higher"] += 1
        else:
            c["osm_lower"] += 1
    return c


_AREAL = ("Polygon", "MultiPolygon")


def match_orders_to_ways(ways, orders, mphs, buffer_m: float = 10,
                         min_fraction: float = 0.5) -> dict[int, int]:
    """Assign order speed limits to ways: {way_idx: mph}. All geometries in BNG metres.

    - Area orders (Polygon / MultiPolygon, e.g. 20 mph zones): a way matches only if
      its midpoint lies inside the order (distance 0).
    - Linear orders: a way matches only if at least min_fraction of its length lies
      within buffer_m of the order, so a road merely crossing or touching the order
      does not inherit its limit.
    Where several orders match a way the lowest mph is kept (conservative: never show
    a higher limit than an order says).
    """
    ways = list(ways)
    if not ways or not len(orders):
        return {}
    best: dict[int, int] = {}

    def keep(w: int, mph) -> None:
        best[w] = min(best.get(w, mph), mph)

    areal = [i for i, g in enumerate(orders) if g.geom_type in _AREAL]
    linear = [i for i, g in enumerate(orders) if g.geom_type not in _AREAL]
    if areal:
        mids = shapely.line_interpolate_point(ways, 0.5, normalized=True)
        tree = STRtree([orders[i] for i in areal])
        for i in areal:
            shapely.prepare(orders[i])  # zone polygons can have 30k vertices
        # Candidate pairs by bounding box, then an exact point-in-polygon test.
        m_idx, o_idx = tree.query(mids)
        for m, o in zip(m_idx, o_idx):
            order = orders[areal[o]]
            if shapely.intersects(order, mids[m]):
                keep(int(m), mphs[areal[o]])
    if linear:
        buffers = [orders[i].buffer(buffer_m) for i in linear]
        tree = STRtree(ways)
        for b, buf in enumerate(buffers):
            shapely.prepare(buf)
            for w in tree.query(buf, predicate="intersects"):
                way = ways[w]
                if way.length > 0 and way.intersection(buf).length >= min_fraction * way.length:
                    keep(int(w), mphs[linear[b]])
    return best
