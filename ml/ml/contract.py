"""Frozen ML -> backend contract for SIH PS57.

This module is the single source of truth for the shape of everything the ML
track hands to the backend. Harshit imports `validate_result` in his tests;
if his code passes and this module is unchanged, the integration cannot drift.

CONTRACT VERSION: 1.0.0  (frozen at model-contract-freeze checkpoint)
Any change here must be announced in the group BEFORE it is pushed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

CONTRACT_VERSION = "1.0.0"

# Frozen class list. Index == YOLO class id. Must match configs/data.yaml.
CLASSES: list[str] = [
    "tyre",
    "drum",
    "net",
    "plastic_debris",
    "wreck",
    "unidentified",
]

# Frozen preprocessing constants the backend must NOT re-implement, but which
# are documented here so a second inference host can reproduce our numbers.
INPUT_IMAGE_SIZE = 640          # square tile fed to the model
TILE_OVERLAP = 0.20             # 20% overlap between adjacent tiles
INPUT_CHANNELS = 3              # single-channel sonar is replicated to 3
PIXEL_SCALE = 1.0 / 255.0       # uint8 -> float
PIXEL_MEAN = [0.0, 0.0, 0.0]
PIXEL_STD = [1.0, 1.0, 1.0]

JOB_STATUSES = ("queued", "processing", "done", "failed")


@dataclass
class Detection:
    """One detected object in FULL-IMAGE pixel coordinates (not tile coords)."""

    cls: str                    # one of CLASSES
    confidence: float           # 0.0 - 1.0
    bbox: list[float]           # [x, y, w, h] top-left origin, full-image pixels
    lat: float | None = None    # WGS84; None when the file carries no navigation
    lon: float | None = None
    size_m: float | None = None  # along-track length estimate in metres
    frame_index: int | None = None  # ping/row index of the box centre

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["class"] = d.pop("cls")   # 'class' is a Python keyword, JSON uses it
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Detection":
        d = dict(d)
        d["cls"] = d.pop("class")
        return Detection(**d)


@dataclass
class InferenceResult:
    image_id: str
    width: int
    height: int
    processing_ms: int
    detections: list[Detection] = field(default_factory=list)
    overlay_path: str | None = None
    model_version: str = "unset"
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "width": self.width,
            "height": self.height,
            "processing_ms": self.processing_ms,
            "detections": [d.to_dict() for d in self.detections],
            "overlay_path": self.overlay_path,
            "model_version": self.model_version,
            "contract_version": self.contract_version,
        }


class ContractError(ValueError):
    """Raised when a payload does not satisfy the frozen schema."""


def validate_result(payload: dict[str, Any]) -> None:
    """Raise ContractError if `payload` is not a valid run_inference() result.

    Backend and ML both call this in their tests. It is intentionally strict:
    a silent shape change is what costs the team a day.
    """
    required = {
        "image_id": str,
        "width": int,
        "height": int,
        "processing_ms": int,
        "detections": list,
    }
    for key, typ in required.items():
        if key not in payload:
            raise ContractError(f"missing top-level key: {key!r}")
        if not isinstance(payload[key], typ):
            raise ContractError(
                f"{key!r} must be {typ.__name__}, got {type(payload[key]).__name__}"
            )

    if payload["width"] <= 0 or payload["height"] <= 0:
        raise ContractError("width and height must be positive")

    for i, det in enumerate(payload["detections"]):
        where = f"detections[{i}]"
        if not isinstance(det, dict):
            raise ContractError(f"{where} must be an object")
        for key in ("class", "confidence", "bbox"):
            if key not in det:
                raise ContractError(f"{where} missing key: {key!r}")
        if det["class"] not in CLASSES:
            raise ContractError(
                f"{where}.class {det['class']!r} not in frozen class list {CLASSES}"
            )
        conf = det["confidence"]
        if not isinstance(conf, (int, float)) or not 0.0 <= conf <= 1.0:
            raise ContractError(f"{where}.confidence must be a float in [0,1]")
        bbox = det["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ContractError(f"{where}.bbox must be [x, y, w, h]")
        if any(not isinstance(v, (int, float)) for v in bbox):
            raise ContractError(f"{where}.bbox values must be numbers")
        if bbox[2] <= 0 or bbox[3] <= 0:
            raise ContractError(f"{where}.bbox width/height must be > 0")
        if bbox[0] < 0 or bbox[1] < 0:
            raise ContractError(f"{where}.bbox x/y must be >= 0")
        if bbox[0] + bbox[2] > payload["width"] + 1 or bbox[1] + bbox[3] > payload["height"] + 1:
            raise ContractError(f"{where}.bbox extends past the image bounds")
        for geo_key, lo, hi in (("lat", -90, 90), ("lon", -180, 180)):
            val = det.get(geo_key)
            if val is not None and not lo <= val <= hi:
                raise ContractError(f"{where}.{geo_key} out of range: {val}")
