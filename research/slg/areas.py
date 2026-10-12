"""Stage 1 test areas. bbox = (min_lon, min_lat, max_lon, max_lat), WGS84.

regions are Geofabrik paths under europe/united-kingdom/.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Area:
    name: str
    condition: str          # urban | suburban | rural | motorway_trunk
    country: str            # england | wales | scotland
    regions: tuple[str, ...]
    bbox: tuple[float, float, float, float]

    def contains(self, lon: float, lat: float) -> bool:
        w, s, e, n = self.bbox
        return w <= lon <= e and s <= lat <= n


AREAS: list[Area] = [
    Area("london_camden_islington", "urban", "england", ("england/greater-london",), (-0.19, 51.52, -0.08, 51.57)),
    Area("manchester_centre", "urban", "england", ("england/greater-manchester",), (-2.27, 53.46, -2.20, 53.50)),
    Area("crawley", "suburban", "england", ("england/west-sussex",), (-0.24, 51.08, -0.13, 51.14)),
    Area("horsham", "suburban", "england", ("england/west-sussex",), (-0.37, 51.04, -0.29, 51.09)),
    Area("midhurst_downs", "rural", "england", ("england/west-sussex",), (-0.80, 50.93, -0.62, 51.02)),
    Area("m23_a23_crawley_brighton", "motorway_trunk", "england",
         ("england/west-sussex", "england/east-sussex"), (-0.22, 50.84, -0.12, 51.10)),
    Area("a27_chichester_worthing", "motorway_trunk", "england", ("england/west-sussex",), (-0.80, 50.81, -0.36, 50.87)),
    Area("m25_surrey", "motorway_trunk", "england", ("england/surrey",), (-0.50, 51.29, -0.30, 51.35)),
    Area("cardiff", "urban", "wales", ("wales",), (-3.25, 51.45, -3.13, 51.52)),
    Area("powys_rural", "rural", "wales", ("wales",), (-3.55, 52.20, -3.25, 52.40)),
    Area("edinburgh", "urban", "scotland", ("scotland",), (-3.25, 55.92, -3.13, 55.97)),
    Area("a9_perth_pitlochry", "motorway_trunk", "scotland", ("scotland",), (-3.80, 56.40, -3.40, 56.72)),
]
