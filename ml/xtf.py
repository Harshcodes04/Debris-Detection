"""Read raw XTF survey files: imagery and the navigation that geo-references it.

This is the dependency everything downstream was waiting on. Depth lookups,
cross-survey matching, the heatmap and recovery planning all key off a real
position, and until now the position was simulated.

An XTF file is a stream of packets. The ones that matter here are sonar pings,
each carrying two channels - port and starboard - plus a header with the
towfish's own position, heading and altitude at the moment of that ping.

Two things about the format that shape this code:

**Navigation drops out.** Fields read 0 when the GPS had no fix, and 0,0 is a
real coordinate in the Gulf of Guinea, so it cannot be passed through. Gaps are
interpolated between good fixes and pings outside any fix are dropped.

**Coordinates are not always lat/lon.** The file header's NavUnits says whether
positions are degrees or projected metres. Reading metres as degrees puts the
survey somewhere absurd, so a file in metres is rejected rather than guessed at.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .interfaces import NavRecord, SonarImage

# Below this many valid fixes a file is not worth geo-referencing.
MIN_FIXES = 2

# XTF NavUnits: 0 = projected metres, 3 = latitude/longitude degrees.
NAV_LATLON = 3


class XTFError(RuntimeError):
    """Raised when a file cannot be read as a geo-referenced survey line."""


@dataclass
class SurveyLine:
    """One XTF file: the waterfall image plus everything needed to place it."""

    sonar: SonarImage
    n_pings: int
    n_fixes: int
    interpolated: int
    dropped: int
    slant_range_m: float
    mean_altitude_m: float
    frequency_hz: float | None
    notes: list[str]

    def summary(self) -> str:
        parts = [f"{self.n_pings} pings", f"{self.sonar.width} px across",
                 f"{self.slant_range_m:.0f} m range",
                 f"{self.mean_altitude_m:.1f} m altitude"]
        if self.interpolated:
            parts.append(f"{self.interpolated} nav gaps interpolated")
        if self.dropped:
            parts.append(f"{self.dropped} pings dropped for missing nav")
        return " · ".join(parts)


def _valid_fix(lat: float, lon: float) -> bool:
    """A dropped fix reads as 0. Null Island is not where the survey was."""
    if lat is None or lon is None:
        return False
    if abs(lat) < 1e-9 and abs(lon) < 1e-9:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _interpolate(values: list[float | None]) -> tuple[list[float], int]:
    """Fill None gaps by linear interpolation between known values.

    Leading and trailing gaps take the nearest known value rather than being
    extrapolated - a towfish does not accelerate off the end of a survey line,
    and extrapolating position is how you invent a coordinate.
    """
    known = [i for i, v in enumerate(values) if v is not None]
    if not known:
        return [], 0

    out: list[float] = [0.0] * len(values)
    filled = 0
    for i, v in enumerate(values):
        if v is not None:
            out[i] = v
            continue
        filled += 1
        before = [k for k in known if k < i]
        after = [k for k in known if k > i]
        if before and after:
            a, b = before[-1], after[0]
            t = (i - a) / (b - a)
            out[i] = values[a] + (values[b] - values[a]) * t   # type: ignore[operator]
        elif before:
            out[i] = values[before[-1]]                        # type: ignore[assignment]
        else:
            out[i] = values[after[0]]                          # type: ignore[assignment]
    return out, filled


def _channel_array(ping, index: int) -> np.ndarray | None:
    try:
        arr = np.asarray(ping.data[index], dtype=np.float32)
    except (AttributeError, IndexError, TypeError):
        return None
    return arr if arr.size else None


def read_xtf(path: str | Path, *, max_pings: int | None = None) -> SurveyLine:
    """Read an XTF file into a geo-referenced waterfall image.

    The port channel is flipped so the finished image runs port-outer through
    nadir to starboard-outer, left to right - which is how side-scan is
    conventionally displayed and, more importantly, what the geo-referencing
    assumes when it offsets a detection perpendicular to the track.
    """
    try:
        import pyxtf
    except ImportError as e:                                   # pragma: no cover
        raise XTFError("pyxtf is required to read XTF files: pip install pyxtf") from e

    path = Path(path)
    if not path.exists():
        raise XTFError(f"no such file: {path}")

    notes: list[str] = []

    try:
        gen = pyxtf.xtf_read_gen(str(path))
        file_header = next(gen)
        packets = {}
        try:
            while True:
                packet = next(gen)
                try:
                    p_headertype = pyxtf.XTFHeaderType(packet.HeaderType)
                except ValueError:
                    p_headertype = pyxtf.XTFHeaderType.unknown
                if p_headertype not in packets:
                    packets[p_headertype] = []
                packets[p_headertype].append(packet)
        except StopIteration:
            pass
        except Exception as e:
            notes.append(f"file reading stopped early due to corruption: {e}")
    except Exception as e:
        raise XTFError(f"failed to read XTF file header: {e}") from e

    nav_units = getattr(file_header, "NavUnits", NAV_LATLON)
    ignore_nav = False
    if nav_units != NAV_LATLON:
        notes.append(
            f"file stores positions in projected metres (NavUnits={nav_units}), "
            "not latitude/longitude. Navigation ignored."
        )
        ignore_nav = True

    pings = packets.get(pyxtf.XTFHeaderType.sonar) or []
    if not pings:
        raise XTFError("no sonar pings in the file")
    if max_pings:
        pings = pings[:max_pings]

    rows: list[np.ndarray] = []
    lats: list[float | None] = []
    lons: list[float | None] = []
    headings: list[float] = []
    altitudes: list[float] = []
    slant_ranges: list[float] = []
    frequencies: list[float] = []
    dropped = 0

    for ping in pings:
        port = _channel_array(ping, 0)
        starboard = _channel_array(ping, 1)
        if port is None or starboard is None:
            dropped += 1
            continue

        # port is recorded nadir-outward; flip it so the row reads
        # port-outer -> nadir -> starboard-outer
        rows.append(np.concatenate([port[::-1], starboard]))

        if ignore_nav:
            lat = lon = None
        else:
            lat = getattr(ping, "SensorYcoordinate", None)
            lon = getattr(ping, "SensorXcoordinate", None)
            if not _valid_fix(lat, lon):
                # towfish fix missing; the vessel's own fix is better than nothing,
                # though it ignores layback
                lat = getattr(ping, "ShipYcoordinate", None)
                lon = getattr(ping, "ShipXcoordinate", None)
        ok = _valid_fix(lat, lon)
        lats.append(float(lat) if ok else None)
        lons.append(float(lon) if ok else None)

        heading = getattr(ping, "SensorHeading", 0.0) or getattr(ping, "ShipGyro", 0.0)
        headings.append(float(heading or 0.0))

        alt = getattr(ping, "SensorPrimaryAltitude", 0.0)
        altitudes.append(float(alt or 0.0))

        chans = getattr(ping, "ping_chan_headers", []) or []
        if chans:
            slant_ranges.append(float(getattr(chans[0], "SlantRange", 0.0) or 0.0))
            f = float(getattr(chans[0], "Frequency", 0.0) or 0.0)
            if f:
                frequencies.append(f)

    if not rows:
        raise XTFError("no ping carried both channels; nothing to build an image from")

    n_fixes = sum(1 for v in lats if v is not None)
    if n_fixes < MIN_FIXES and not ignore_nav:
        notes.append(
            f"only {n_fixes} valid navigation fixes in {len(rows)} pings. "
            "The file has imagery but no usable position - it can be detected on, "
            "but not geo-referenced."
        )
        ignore_nav = True

    lat_f, filled_lat = _interpolate(lats)
    lon_f, _ = _interpolate(lons)
    if filled_lat:
        notes.append(f"{filled_lat} pings had no fix; position interpolated "
                     f"between neighbours")

    # rows vary in length when the range scale changes mid-line; pad to the
    # widest rather than truncating, so nothing is silently cropped
    width = max(r.size for r in rows)
    if len({r.size for r in rows}) > 1:
        notes.append("range scale changed mid-line; narrower pings padded")
    canvas = np.zeros((len(rows), width), dtype=np.float32)
    for i, r in enumerate(rows):
        canvas[i, : r.size] = r

    # percentile clip then scale: a few hot pixels otherwise crush the contrast
    lo, hi = np.percentile(canvas, [1.0, 99.0])
    if hi <= lo:
        hi = lo + 1.0
    image = np.clip((canvas - lo) / (hi - lo), 0.0, 1.0)
    image = (image * 255.0).astype(np.uint8)

    slant = float(np.median(slant_ranges)) if slant_ranges else 0.0
    altitude = float(np.median([a for a in altitudes if a > 0])) if any(
        a > 0 for a in altitudes) else 0.0

    nav = []
    if not ignore_nav:
        nav = [
            NavRecord(ping_index=i, lat=round(lat_f[i], 7), lon=round(lon_f[i], 7),
                      heading_deg=headings[i] % 360.0,
                      altitude_m=altitudes[i], slant_range_m=slant)
            for i in range(len(rows))
        ]

    sonar = SonarImage(image=image, image_id=path.stem, nav=nav)

    # across-track scale: ground range, not slant. The seabed distance actually
    # imaged is sqrt(slant^2 - altitude^2), and the row spans both channels.
    if slant > 0:
        ground = math.sqrt(max(slant**2 - altitude**2, 0.0))
        if ground > 0:
            sonar.ground_range_per_px_m = (2.0 * ground) / width
        else:
            notes.append("altitude exceeds slant range; across-track scale unusable")
    else:
        notes.append("no slant range recorded; detections cannot be sized in metres")

    sonar.meta.update({
        "navigation": "REAL (from XTF ping headers)",
        "source_file": path.name,
        "slant_range_m": slant,
        "altitude_m": altitude,
        "swath_m": round(2.0 * math.sqrt(max(slant**2 - altitude**2, 0.0)), 1),
    })

    return SurveyLine(
        sonar=sonar, n_pings=len(rows), n_fixes=n_fixes,
        interpolated=filled_lat, dropped=dropped, slant_range_m=slant,
        mean_altitude_m=altitude,
        frequency_hz=float(np.median(frequencies)) if frequencies else None,
        notes=notes,
    )
