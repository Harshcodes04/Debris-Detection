"""The seams between Akshat (pipeline) and Priyanshu (sonar processing).

Akshat owns the *shape* of these functions; Priyanshu owns the *implementation*.
Everything here has a working reference stub so the end-to-end pipeline runs
today, before any sonar-specific code exists. Priyanshu replaces the stubs
in ml/preprocessing/ and ml/postprocess/ without touching this file's signatures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np


@dataclass
class NavRecord:
    """Navigation attached to one ping (one image row)."""

    ping_index: int
    lat: float
    lon: float
    heading_deg: float      # 0 = north, clockwise
    altitude_m: float       # towfish height above seabed
    slant_range_m: float    # max slant range of the channel


@dataclass
class SonarImage:
    """A preprocessed, ground-range-corrected waterfall image, uint8, HxW."""

    image: np.ndarray
    image_id: str
    nav: list[NavRecord] = field(default_factory=list)
    ground_range_per_px_m: float = 0.0   # across-track metres per pixel; 0 = unknown
    along_track_per_px_m: float = 0.0    # metres per row
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def width(self) -> int:
        return int(self.image.shape[1])


@dataclass
class Tile:
    """One 640x640 crop, with the offset needed to map boxes back."""

    image: np.ndarray
    x_offset: int
    y_offset: int
    source_image_id: str


class Preprocessor(Protocol):
    """Priyanshu implements this in ml/preprocessing/. Steps A3 of the plan."""

    def load(self, file_path: str) -> SonarImage: ...

    def tile(self, sonar: SonarImage, size: int, overlap: float) -> list[Tile]: ...


class PostProcessor(Protocol):
    """Priyanshu implements this in ml/postprocess/. Steps A7 of the plan."""

    def stitch(
        self, tile_detections: list[tuple[Tile, list[dict]]], iou_threshold: float
    ) -> list[dict]: ...

    def georeference(self, detections: list[dict], sonar: SonarImage) -> list[dict]: ...


# --------------------------------------------------------------------------
# Reference implementations. Correct but naive; good enough to run the whole
# pipeline and to unit-test the contract. Replaced by the real sonar code.
# --------------------------------------------------------------------------

class ReferencePreprocessor:
    def load(self, file_path: str) -> SonarImage:
        from pathlib import Path

        path = Path(file_path)
        if path.suffix.lower() in {".xtf", ".jsf", ".segy", ".sgy"}:
            raise NotImplementedError(
                "Raw sonar reading is Priyanshu's read_xtf() (step A3.1). "
                "Point the pipeline at a preprocessed PNG/JPG until it lands."
            )
        from PIL import Image

        arr = np.array(Image.open(path).convert("L"), dtype=np.uint8)
        return SonarImage(image=arr, image_id=path.stem)

    def tile(self, sonar: SonarImage, size: int, overlap: float) -> list[Tile]:
        step = max(1, int(size * (1.0 - overlap)))
        tiles: list[Tile] = []
        h, w = sonar.height, sonar.width
        ys = list(range(0, max(1, h - size + 1), step)) or [0]
        xs = list(range(0, max(1, w - size + 1), step)) or [0]
        if ys[-1] + size < h:
            ys.append(h - size)
        if xs[-1] + size < w:
            xs.append(w - size)
        for y in ys:
            for x in xs:
                crop = sonar.image[y : y + size, x : x + size]
                if crop.shape != (size, size):
                    pad = np.zeros((size, size), dtype=np.uint8)
                    pad[: crop.shape[0], : crop.shape[1]] = crop
                    crop = pad
                tiles.append(
                    Tile(image=crop, x_offset=int(x), y_offset=int(y),
                         source_image_id=sonar.image_id)
                )
        return tiles


class ReferencePostProcessor:
    def stitch(
        self, tile_detections: list[tuple[Tile, list[dict]]], iou_threshold: float = 0.5
    ) -> list[dict]:
        boxes: list[dict] = []
        for tile, dets in tile_detections:
            for d in dets:
                x, y, w, h = d["bbox"]
                boxes.append(
                    {**d, "bbox": [x + tile.x_offset, y + tile.y_offset, w, h]}
                )
        return _nms(boxes, iou_threshold)

    def georeference(self, detections: list[dict], sonar: SonarImage) -> list[dict]:
        if not sonar.nav or sonar.ground_range_per_px_m <= 0:
            return detections  # no navigation in the file: lat/lon stay None

        centre_x = sonar.width / 2.0
        out = []
        for d in detections:
            x, y, w, h = d["bbox"]
            row = int(min(max(y + h / 2.0, 0), sonar.height - 1))
            nav = _nearest_nav(sonar.nav, row)
            across_px = (x + w / 2.0) - centre_x           # +starboard, -port
            across_m = across_px * sonar.ground_range_per_px_m
            lat, lon = offset_latlon(nav.lat, nav.lon, nav.heading_deg + 90.0, across_m)
            size_m = w * sonar.ground_range_per_px_m
            out.append({**d, "lat": lat, "lon": lon, "size_m": round(size_m, 2),
                        "frame_index": row})
        return out


def offset_latlon(lat: float, lon: float, bearing_deg: float, distance_m: float
                  ) -> tuple[float, float]:
    """Move `distance_m` from (lat, lon) along `bearing_deg`. Negative distance
    reverses the bearing. Flat-earth approximation: fine at survey scale."""
    r_earth = 6_378_137.0
    brg = math.radians(bearing_deg)
    dn = distance_m * math.cos(brg)
    de = distance_m * math.sin(brg)
    dlat = dn / r_earth
    dlon = de / (r_earth * math.cos(math.radians(lat)))
    return (round(lat + math.degrees(dlat), 7), round(lon + math.degrees(dlon), 7))


def _nearest_nav(nav: list[NavRecord], row: int) -> NavRecord:
    return min(nav, key=lambda n: abs(n.ping_index - row))


def _iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _nms(boxes: list[dict], iou_threshold: float) -> list[dict]:
    kept: list[dict] = []
    for box in sorted(boxes, key=lambda d: d["confidence"], reverse=True):
        if all(
            box["class"] != k["class"] or _iou(box["bbox"], k["bbox"]) < iou_threshold
            for k in kept
        ):
            kept.append(box)
    return kept
