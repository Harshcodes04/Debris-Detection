"""Survey navigation: the ping-by-ping track that turns pixels into coordinates.

A side-scan image on its own has no geography. Every pixel becomes a real
position only when paired with the towfish navigation recorded alongside it:
where the fish was, which way it was pointing, how high above the seabed, and
how far the sonar was ranging.

Real surveys carry this in the sonar file's ping headers (XTF, JSF, SEGY).
`from_xtf` is the production path and belongs to the preprocessing track.

`synthetic_track` exists so the geotagging and reporting components can be
exercised, demonstrated and tested before raw survey files are available.
Anything it produces is SIMULATED and every report built on it says so.
"""

from __future__ import annotations

import math

from .interfaces import NavRecord, SonarImage

# Default demo line: a north-easterly run in the Arabian Sea off the Karnataka
# coast, roughly 20 km west of Mangaluru. Chosen because it is a plausible
# Indian survey area, not because any real survey happened here.
DEMO_ORIGIN = (12.9231, 74.6012)
KNOTS_TO_MS = 0.514444


def synthetic_track(
    n_pings: int,
    *,
    origin: tuple[float, float] = DEMO_ORIGIN,
    heading_deg: float = 45.0,
    speed_knots: float = 4.0,
    ping_rate_hz: float = 10.0,
    altitude_m: float = 12.0,
    slant_range_m: float = 75.0,
    turn_rate_deg_per_ping: float = 0.0,
) -> list[NavRecord]:
    """Build a straight (or gently turning) survey line, one record per ping.

    Defaults are typical for a shallow-water debris survey: 4 knots, 10 pings
    per second, 12 m altitude, 75 m range per channel giving a 150 m swath.
    """
    lat, lon = origin
    heading = heading_deg
    along_track_m = speed_knots * KNOTS_TO_MS / ping_rate_hz   # metres per ping

    r_earth = 6_378_137.0
    records: list[NavRecord] = []
    for i in range(n_pings):
        records.append(
            NavRecord(
                ping_index=i,
                lat=round(lat, 7),
                lon=round(lon, 7),
                heading_deg=heading % 360.0,
                altitude_m=altitude_m,
                slant_range_m=slant_range_m,
            )
        )
        # advance along the track
        brg = math.radians(heading)
        dlat = (along_track_m * math.cos(brg)) / r_earth
        dlon = (along_track_m * math.sin(brg)) / (r_earth * math.cos(math.radians(lat)))
        lat += math.degrees(dlat)
        lon += math.degrees(dlon)
        heading += turn_rate_deg_per_ping

    return records


def attach_track(sonar: SonarImage, **kwargs) -> SonarImage:
    """Give an image a simulated track and the scale factors geotagging needs.

    One ping per image row. Across-track scale comes from the swath: the image
    spans port range + starboard range, so metres-per-pixel is the full swath
    divided by image width. Along-track scale comes from speed and ping rate.
    """
    nav = synthetic_track(sonar.height, **kwargs)
    slant_range_m = nav[0].slant_range_m
    altitude_m = nav[0].altitude_m

    # ground range, not slant range: the seabed distance actually imaged
    ground_range_m = math.sqrt(max(slant_range_m**2 - altitude_m**2, 0.0))
    swath_m = 2.0 * ground_range_m

    speed = kwargs.get("speed_knots", 4.0)
    rate = kwargs.get("ping_rate_hz", 10.0)

    sonar.nav = nav
    sonar.ground_range_per_px_m = swath_m / sonar.width
    sonar.along_track_per_px_m = speed * KNOTS_TO_MS / rate
    sonar.meta["navigation"] = "SIMULATED"
    sonar.meta["swath_m"] = round(swath_m, 1)
    sonar.meta["altitude_m"] = altitude_m
    sonar.meta["slant_range_m"] = slant_range_m
    return sonar


def from_xtf(path: str) -> list[NavRecord]:
    """Read real navigation from a raw sonar file. Preprocessing track owns this."""
    raise NotImplementedError(
        "Real navigation comes from XTF/JSF ping headers via pyxtf - "
        "preprocessing step A3.1. Until then use synthetic_track()."
    )
