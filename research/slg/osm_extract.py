"""Download Geofabrik extracts and pull drivable ways for a test area."""
from pathlib import Path

import osmium
import requests
from shapely.geometry import LineString

from slg.areas import Area
from slg.geo import line_length_m
from slg.paths import DATA

GEOFABRIK = "https://download.geofabrik.de/europe/united-kingdom/{region}-latest.osm.pbf"

DRIVABLE = frozenset({
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "living_street", "service",
})

TAG_KEYS = (
    "highway", "maxspeed", "maxspeed:forward", "maxspeed:backward", "maxspeed:type",
    "maxspeed:conditional", "maxspeed:variable", "source:maxspeed", "zone:maxspeed",
    "lit", "oneway", "lanes", "dual_carriageway", "junction", "name", "ref",
    "maxheight", "maxheight:physical", "maxwidth", "maxwidth:physical",
    "maxweight", "maxweightrating", "maxweight:hgv", "maxweight:goods",
    "hgv", "goods", "bridge", "tunnel", "covered",
)

RESTRICTION_KEYS = ("maxheight", "maxheight:physical", "maxwidth", "maxwidth:physical",
                    "maxweight", "maxweightrating", "maxweight:hgv")


def download_extract(region: str, dest_dir: Path = DATA / "osm", session=requests) -> Path:
    """Fetch a Geofabrik extract once; re-runs reuse the file on disk."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (region.replace("/", "_") + ".osm.pbf")
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    part = dest.with_suffix(".part")
    with session.get(GEOFABRIK.format(region=region), stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    part.replace(dest)
    return dest


def _drivable_ways(pbf: Path, area: Area):
    """Yield (way, coords) for drivable ways with at least one node inside the area bbox."""
    fp = (osmium.FileProcessor(str(pbf))
          .with_locations()
          .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
          .with_filter(osmium.filter.KeyFilter("highway")))
    for obj in fp:
        if not obj.is_way() or obj.tags.get("highway") not in DRIVABLE:
            continue
        coords = [(n.lon, n.lat) for n in obj.nodes if n.location.valid()]
        if len(coords) < 2 or not any(area.contains(lon, lat) for lon, lat in coords):
            continue
        yield obj, coords


def drivable_node_ids(pbf: Path, area: Area) -> set[int]:
    """Node refs of every drivable way touching the area (used to drop footway/cycle barriers)."""
    return {n.ref for obj, _ in _drivable_ways(pbf, area) for n in obj.nodes}


def ways_in_area(pbf: Path, area: Area) -> list[dict]:
    """Drivable ways with at least one node inside the area bbox."""
    rows = []
    for obj, coords in _drivable_ways(pbf, area):
        ts = obj.timestamp
        row = {
            "way_id": obj.id,
            "area": area.name,
            "country": area.country,
            "length_m": line_length_m(coords),
            "version": obj.version,
            # Public extracts may strip metadata; an epoch timestamp means "unknown".
            "timestamp": ts if ts.year > 2000 else None,
            "wkt": LineString(coords).wkt,
            "first_node": obj.nodes[0].ref,
            "last_node": obj.nodes[-1].ref,
        }
        for k in TAG_KEYS:
            row[k] = obj.tags.get(k)
        rows.append(row)
    return rows


def restriction_nodes_in_area(pbf: Path, area: Area) -> list[dict]:
    """Nodes carrying a height/width/weight restriction inside the area bbox (e.g. car-park barriers)."""
    fp = (osmium.FileProcessor(str(pbf))
          .with_filter(osmium.filter.EntityFilter(osmium.osm.NODE))
          .with_filter(osmium.filter.KeyFilter(*RESTRICTION_KEYS)))
    rows = []
    for n in fp:
        if not n.location.valid() or not area.contains(n.location.lon, n.location.lat):
            continue
        row = {"node_id": n.id, "area": area.name, "country": area.country,
               "lon": n.location.lon, "lat": n.location.lat, "barrier": n.tags.get("barrier")}
        for k in RESTRICTION_KEYS:
            row[k] = n.tags.get(k)
        rows.append(row)
    return rows
