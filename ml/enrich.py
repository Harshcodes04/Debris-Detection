"""Context for a detection: how deep, how far, what lives there.

A detection on its own says an object exists. A recovery operation needs to
know whether it is worth going to get: how deep it sits, how far it is from
port, and whether it threatens anything. This module attaches that.

Everything here is a LOOKUP against open data, not a prediction. Depth comes
from the GEBCO grid, biodiversity from OBIS. Nothing is inferred from the sonar
image, because none of it can be.

    GEBCO 2020 bathymetry   via OpenTopoData    no key
    OBIS occurrence records via api.obis.org    no key

Both are network calls, so every function degrades to None rather than raising -
a demo without wifi still runs, it just reports less.

IMPORTANT: this is only meaningful with REAL navigation. Enriching a simulated
coordinate produces confident-looking facts about a place that has nothing to
do with the image. `enrich_detection` refuses unless told the navigation is
real, so that mistake has to be made deliberately.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any

TIMEOUT = 15
_DEPTH_CACHE: dict[tuple, float | None] = {}
_SPECIES_CACHE: dict[tuple, dict | None] = {}

# Nearest ports to the demo survey area. A real deployment reads these from a
# port database; three is enough to show the mechanism.
PORTS = {
    "New Mangalore": (12.9200, 74.8000),
    "Malpe": (13.3500, 74.7000),
    "Karwar": (14.8000, 74.1000),
}


def _get_json(url: str) -> Any | None:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None      # offline, rate-limited, service down - all the same here


def water_depth_m(lat: float, lon: float) -> float | None:
    """Seabed depth in metres from the GEBCO 2020 grid. None if unavailable.

    GEBCO is a global grid at ~450 m resolution, so this is the depth of the
    area, not of the exact object. Good enough to decide whether a site is
    diveable; not a substitute for a survey.
    """
    key = (round(lat, 4), round(lon, 4))
    if key in _DEPTH_CACHE:
        return _DEPTH_CACHE[key]

    data = _get_json(
        f"https://api.opentopodata.org/v1/gebco2020?locations={lat},{lon}")
    depth = None
    if data and data.get("status") == "OK" and data.get("results"):
        elevation = data["results"][0].get("elevation")
        if elevation is not None and elevation < 0:
            depth = abs(float(elevation))   # elevation is negative below sea level
    _DEPTH_CACHE[key] = depth
    return depth


def biodiversity(lat: float, lon: float, radius_km: float = 5.0) -> dict | None:
    """Species and record counts near a point, from OBIS.

    A count is a crude proxy for ecological sensitivity - it partly measures
    how well surveyed an area is rather than how rich it is. Useful for
    ranking sites against each other, not as an absolute measure.
    """
    key = (round(lat, 3), round(lon, 3), radius_km)
    if key in _SPECIES_CACHE:
        return _SPECIES_CACHE[key]

    d = radius_km / 111.0        # degrees per km, near enough at this latitude
    poly = (f"POLYGON(({lon-d} {lat-d},{lon+d} {lat-d},{lon+d} {lat+d},"
            f"{lon-d} {lat+d},{lon-d} {lat-d}))")
    data = _get_json("https://api.obis.org/v3/statistics?geometry="
                     + urllib.parse.quote(poly))
    out = None
    if data:
        out = {
            "species": data.get("species"),
            "records": data.get("records"),
            "datasets": data.get("datasets"),
            "radius_km": radius_km,
        }
    _SPECIES_CACHE[key] = out
    return out


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two lat/lon points, kilometres."""
    r = 6371.0088
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def nearest_port(lat: float, lon: float, speed_knots: float = 8.0) -> dict:
    """Closest port, straight-line distance and transit time.

    Straight line over water - it ignores coastline, traffic separation and
    weather, so treat it as a lower bound on transit rather than a plan.
    """
    name, coords = min(PORTS.items(), key=lambda kv: haversine_km((lat, lon), kv[1]))
    km = haversine_km((lat, lon), coords)
    hours = km / (speed_knots * 1.852)     # knots -> km/h
    return {
        "port": name,
        "distance_km": round(km, 2),
        "transit_hours": round(hours, 2),
        "assumed_speed_knots": speed_knots,
        "note": "straight-line distance; ignores coastline and traffic routing",
    }


@dataclass
class Context:
    depth_m: float | None
    diveable: bool | None          # within ~30 m recreational/commercial dive limit
    biodiversity: dict | None
    nearest_port: dict | None
    sources: list[str]


def enrich_detection(lat: float | None, lon: float | None, *,
                     navigation_is_real: bool,
                     speed_knots: float = 8.0) -> Context | None:
    """Attach depth, biodiversity and port distance to one detection.

    `navigation_is_real` is not a formality. Every value here is derived purely
    from the coordinate, so a simulated coordinate yields a real depth for a
    place the sonar never saw. Refusing is the only honest default.
    """
    if lat is None or lon is None:
        return None
    if not navigation_is_real:
        return None

    depth = water_depth_m(lat, lon)
    return Context(
        depth_m=depth,
        diveable=(depth is not None and depth <= 30.0),
        biodiversity=biodiversity(lat, lon),
        nearest_port=nearest_port(lat, lon, speed_knots),
        sources=["GEBCO 2020 via OpenTopoData", "OBIS api.obis.org"],
    )


def to_dict(ctx: Context | None) -> dict | None:
    return asdict(ctx) if ctx else None
