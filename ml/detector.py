"""Model loading and raw prediction. Nothing outside this file knows whether
we are running a .pt checkpoint or an .onnx export.

Backend NEVER imports this. Backend imports ml.inference.run_inference only.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

import numpy as np

from ml.contract import CLASSES, INPUT_IMAGE_SIZE

# A model's own class names are whatever its training set used; the contract
# fixes what the backend is allowed to receive. Mapping by NAME, never by
# index - the index of "ship" in one model is the index of something else
# entirely in the contract, and mapping by index silently relabels every
# detection. Anything unmapped becomes "unidentified", which is the honest
# answer for a class the contract has no word for.
NAME_TO_CONTRACT = {
    # sidescan_v1 (SCTD)
    "ship": "wreck", "aircraft": "wreck", "human": "unidentified",
    # ghostgear_v1 (Ghost Pot SSS) - a derelict crab pot is lost
    # fishing gear, which is what the contract's "net" class covers
    "crab_pot": "net",
    # debris_fls_v1 (Marine Debris FLS)
    "tire": "tyre", "tyre": "tyre",
    "bottle": "plastic_debris", "standing-bottle": "plastic_debris",
    "shampoo-bottle": "plastic_debris", "drink-carton": "plastic_debris",
    "can": "plastic_debris",
    "chain": "net", "hook": "net",
    "valve": "unidentified", "propeller": "unidentified",
}


def to_contract_class(name: str) -> str:
    """Map a model's own label onto the frozen contract vocabulary."""
    return NAME_TO_CONTRACT.get(name.lower().strip(), "unidentified")


class Detector:
    """Wraps whatever backend actually runs the model."""

    def __init__(self, weights: str | None, conf: float = 0.25, iou: float = 0.45,
                 imgsz: int = INPUT_IMAGE_SIZE):
        self.weights = weights
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self._impl = None
        self._kind = "mock"
        if weights and Path(weights).exists():
            self._load(Path(weights))
        else:
            # Mock mode is for unblocking the backend before a model exists.
            # It must never be reached silently: well-formed JSON describing
            # objects that were never detected is worse than a hard failure,
            # because it looks like a working integration.
            import warnings
            warnings.warn(
                f"Detector running in MOCK mode - detections are INVENTED. "
                f"weights={weights!r} "
                f"({'missing' if weights else 'not configured'}). "
                f"Set SIH_ML_WEIGHTS or pass a real checkpoint.",
                RuntimeWarning, stacklevel=2,
            )

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def version(self) -> str:
        if self._kind == "mock":
            return "mock-0"
        p = Path(self.weights)
        digest = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
        return f"{p.stem}-{digest}"

    def _load(self, path: Path) -> None:
        # ultralytics runs .pt and .onnx through the same predict API, NMS decode
        # included. One path means the parity check in ml/export/export_onnx.py
        # compares like with like.
        from ultralytics import YOLO

        self._impl = YOLO(str(path))
        self._kind = "onnx" if path.suffix == ".onnx" else "torch"

    def predict_tiles(self, tiles: list[np.ndarray]) -> list[list[dict]]:
        """One list of detections per tile, in TILE-LOCAL pixel coordinates."""
        if self._kind == "mock":
            return [_mock_predict(t) for t in tiles]
        return self._predict(tiles)

    def _predict(self, tiles: list[np.ndarray]) -> list[list[dict]]:
        batch = [np.repeat(t[:, :, None], 3, axis=2) for t in tiles]
        results = self._impl.predict(
            batch, imgsz=self.imgsz, conf=self.conf, iou=self.iou, verbose=False
        )
        out = []
        for res in results:
            dets = []
            for box in res.boxes:
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                dets.append(
                    {
                        "class": to_contract_class(
                            self._impl.names[int(box.cls[0])]),
                        "confidence": round(float(box.conf[0]), 4),
                        "bbox": [x1, y1, x2 - x1, y2 - y1],
                    }
                )
            out.append(dets)
        return out


def _mock_predict(tile: np.ndarray) -> list[dict]:
    """Deterministic fake detections so the backend and frontend can be built
    and demoed before the real checkpoint exists. Seeded on tile content, so
    the same file always produces the same boxes."""
    rng = random.Random(int(tile.sum()) % 10_000_019)
    dets = []
    for _ in range(rng.randint(0, 2)):
        w = rng.uniform(24, 90)
        h = rng.uniform(24, 90)
        dets.append(
            {
                "class": rng.choice(CLASSES[:-1]),
                "confidence": round(rng.uniform(0.35, 0.95), 4),
                "bbox": [
                    round(rng.uniform(0, max(1.0, tile.shape[1] - w)), 1),
                    round(rng.uniform(0, max(1.0, tile.shape[0] - h)), 1),
                    round(w, 1),
                    round(h, 1),
                ],
            }
        )
    return dets
