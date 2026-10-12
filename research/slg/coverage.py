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


def annotate(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["road_class"] = out["highway"].map(ROAD_CLASS)
    parsed = out["maxspeed"].map(parse_maxspeed)
    out["ms_kind"] = parsed.map(lambda p: p.kind)
    out["ms_mph"] = parsed.map(lambda p: p.mph).astype("Int64")
    directional = out["maxspeed:forward"].notna() | out["maxspeed:backward"].notna()
    out["tagged"] = (out["ms_kind"] != "absent") | directional
    return out


def coverage_by_class(df: pd.DataFrame, by: tuple[str, ...] = ("road_class",)) -> pd.DataFrame:
    g = df.assign(
        km=df["length_m"] / 1000,
        km_tagged=df["length_m"].where(df["tagged"], 0.0) / 1000,
    )
    t = (g.groupby(list(by), dropna=False)
          .agg(ways=("way_id", "count"), ways_tagged=("tagged", "sum"),
               km=("km", "sum"), km_tagged=("km_tagged", "sum"))
          .reset_index())
    t["pct_km_tagged"] = 100 * t["km_tagged"] / t["km"]
    t["pct_ways_tagged"] = 100 * t["ways_tagged"] / t["ways"]
    return t


def kind_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """km of road per road_class x maxspeed kind."""
    return df.pivot_table(index="road_class", columns="ms_kind", values="length_m",
                          aggfunc="sum", fill_value=0.0) / 1000


def freshness(df: pd.DataFrame, now) -> pd.DataFrame:
    t = df[df["tagged"] & df["timestamp"].notna()].copy()
    t["age_days"] = (now - pd.to_datetime(t["timestamp"], utc=True)).dt.days
    return (t.groupby("road_class")
             .agg(tagged_ways_with_ts=("age_days", "count"),
                  median_age_days=("age_days", "median"),
                  pct_edited_2y=("age_days", lambda a: 100 * (a <= 730).mean()))
             .reset_index())
