"""Coverage of speed-limit tagging by road class, by count and by length."""
import pandas as pd

from slg.maxspeed import parse_maxspeed

ROAD_CLASS = {
    "motorway": "motorway", "motorway_link": "motorway",
    "trunk": "trunk", "trunk_link": "trunk",
    "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary",
    "tertiary": "tertiary", "tertiary_link": "tertiary",
    "unclassified": "unclassified",
    "residential": "residential", "living_street": "residential",
    "service": "service",
}

# Kinds that give a legal limit (or a national-limit form) a consumer can act on.
USABLE_KINDS = frozenset({"explicit", "nsl_single", "nsl_dual", "motorway", "national"})


def annotate(df: pd.DataFrame) -> pd.DataFrame:
    """Add road_class, ms_kind, ms_mph, tagged (any maxspeed or directional value
    present) and usable (a parsed legal limit or national-limit form)."""
    out = df.copy()
    out["road_class"] = out["highway"].map(ROAD_CLASS)
    parsed = out["maxspeed"].map(parse_maxspeed)
    out["ms_kind"] = parsed.map(lambda p: p.kind)
    out["ms_mph"] = parsed.map(lambda p: p.mph).astype("Int64")
    directional = out["maxspeed:forward"].notna() | out["maxspeed:backward"].notna()
    out["usable"] = out["ms_kind"].isin(USABLE_KINDS)
    out["tagged"] = (out["ms_kind"] != "absent") | directional
    return out


def coverage_by_class(df: pd.DataFrame, by: tuple[str, ...] = ("road_class",)) -> pd.DataFrame:
    """Ways and km per group, with % tagged and % usable by count and by length."""
    g = df.assign(
        km=df["length_m"] / 1000,
        km_tagged=df["length_m"].where(df["tagged"], 0.0) / 1000,
        km_usable=df["length_m"].where(df["usable"], 0.0) / 1000,
    )
    t = (g.groupby(list(by), dropna=False)
          .agg(ways=("way_id", "count"), ways_tagged=("tagged", "sum"),
               ways_usable=("usable", "sum"), km=("km", "sum"),
               km_tagged=("km_tagged", "sum"), km_usable=("km_usable", "sum"))
          .reset_index())
    t["pct_km_tagged"] = 100 * t["km_tagged"] / t["km"]
    t["pct_km_usable"] = 100 * t["km_usable"] / t["km"]
    t["pct_ways_tagged"] = 100 * t["ways_tagged"] / t["ways"]
    return t


def kind_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """km of road per road_class x maxspeed kind."""
    return df.pivot_table(index="road_class", columns="ms_kind", values="length_m",
                          aggfunc="sum", fill_value=0.0) / 1000


def freshness(df: pd.DataFrame, now) -> pd.DataFrame:
    """Age of tagged ways by class. The timestamp is the way's last edit of anything,
    not of maxspeed; `now` must be timezone-aware; classes with no timestamped
    tagged ways are omitted."""
    t = df[df["tagged"] & df["timestamp"].notna()].copy()
    t["age_days"] = (now - pd.to_datetime(t["timestamp"], utc=True)).dt.days
    return (t.groupby("road_class")
             .agg(tagged_ways_with_ts=("age_days", "count"),
                  median_age_days=("age_days", "median"),
                  pct_edited_2y=("age_days", lambda a: 100 * (a <= 730).mean()))
             .reset_index())
