"""THE handoff point. Backend calls exactly one function from the ML track:

    from ml.inference import run_inference
    result = run_inference("/data/uploads/3/line_03.png")

Everything else in ml/ is private to the ML track. The returned dict is
validated against ml.contract before it is returned, so a broken model can
never hand the backend a broken shape.

CLI:
    python -m ml.inference <file> --out result.json
    python -m ml.inference <file> --weights runs/best.pt
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import yaml

from ml.contract import (
    INPUT_IMAGE_SIZE,
    TILE_OVERLAP,
    Detection,
    InferenceResult,
    validate_result,
)
from ml.detector import Detector
from ml.interfaces import ReferencePostProcessor, ReferencePreprocessor

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "inference.yaml"
_DETECTOR: Detector | None = None


# Shipped weights, used when no config or env var overrides them. Without this
# the pipeline silently fell back to mock detections, which is the worst
# possible default: the backend gets well-formed JSON full of invented objects
# and nothing anywhere says it is fake.
_DEFAULT_WEIGHTS = Path(__file__).resolve().parent.parent / "weights" / "sidescan_v1.pt"


def load_config(path: str | Path | None = None) -> dict:
    cfg_path = Path(path) if path else _CONFIG_PATH
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    # Fall back to the shipped weights when none are configured OR when the
    # configured path does not exist - a stale path in a config file is the
    # usual way this ends up silently mocking.
    configured = cfg.get("weights")
    if (not configured or not Path(configured).exists()) and _DEFAULT_WEIGHTS.exists():
        cfg["weights"] = str(_DEFAULT_WEIGHTS)
    # env overrides let the backend container point at its own paths
    if os.getenv("SIH_ML_WEIGHTS"):
        cfg["weights"] = os.environ["SIH_ML_WEIGHTS"]
    if os.getenv("SIH_ML_OUTPUT_DIR"):
        cfg["output_dir"] = os.environ["SIH_ML_OUTPUT_DIR"]
    return cfg


def get_detector(cfg: dict | None = None) -> Detector:
    """Loaded once per process. The worker should call this at startup so the
    first upload of the demo is not the one that pays the model-load cost."""
    global _DETECTOR
    if _DETECTOR is None:
        cfg = cfg or load_config()
        _DETECTOR = Detector(
            weights=cfg.get("weights"),
            conf=cfg.get("conf_threshold", 0.25),
            iou=cfg.get("iou_threshold", 0.45),
            imgsz=cfg.get("imgsz", INPUT_IMAGE_SIZE),
        )
    return _DETECTOR


def run_inference(file_path: str, config: dict | None = None,
                  progress_cb=None) -> dict:
    """Raw sonar file (or preprocessed image) -> detections, in the frozen schema.

    Args:
        file_path: path to an .xtf/.jsf survey file or a preprocessed .png/.jpg.
        config: optional overrides for configs/inference.yaml.
        progress_cb: optional callable(stage: str, pct: int) so the backend
            worker can drive a real progress bar (B4 in the plan).

    Returns:
        dict matching ml.contract / schemas/detection_result.schema.json.

    Raises:
        FileNotFoundError: file_path does not exist.
        ContractError: the pipeline produced something off-contract (a bug on
            our side; the worker should mark the job failed and log it).
    """
    started = time.perf_counter()
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(file_path)

    cfg = {**load_config(), **(config or {})}
    detector = get_detector(cfg)
    pre = ReferencePreprocessor()
    post = ReferencePostProcessor()

    def report(stage: str, pct: int) -> None:
        if progress_cb:
            progress_cb(stage, pct)

    report("parsed", 10)
    sonar = pre.load(str(src))

    report("preprocessed", 30)
    tiles = pre.tile(
        sonar,
        size=cfg.get("imgsz", INPUT_IMAGE_SIZE),
        overlap=cfg.get("tile_overlap", TILE_OVERLAP),
    )

    report("inferred", 70)
    batch_size = cfg.get("batch_size", 16)
    per_tile: list[list[dict]] = []
    for i in range(0, len(tiles), batch_size):
        chunk = tiles[i : i + batch_size]
        per_tile.extend(detector.predict_tiles([t.image for t in chunk]))

    merged = post.stitch(
        list(zip(tiles, per_tile)), iou_threshold=cfg.get("stitch_iou", 0.5)
    )
    merged = post.georeference(merged, sonar)
    merged = [d for d in merged if d["confidence"] >= cfg.get("conf_threshold", 0.25)]
    merged = _clip_to_image(merged, sonar.width, sonar.height)

    overlay_path = None
    if cfg.get("write_overlay", True):
        overlay_path = _write_overlay(sonar.image, merged, sonar.image_id,
                                      Path(cfg.get("output_dir", "data/overlays")))

    result = InferenceResult(
        image_id=sonar.image_id,
        width=sonar.width,
        height=sonar.height,
        processing_ms=int((time.perf_counter() - started) * 1000),
        detections=[Detection.from_dict(d) for d in merged],
        overlay_path=overlay_path,
        model_version=detector.version,
    ).to_dict()

    validate_result(result)   # never hand the backend an off-contract payload
    report("stored", 100)
    return result


def _clip_to_image(dets: list[dict], width: int, height: int) -> list[dict]:
    """Tiles are zero-padded at the right/bottom edge, so a box can land in the
    padding. Clip it back and drop anything that collapses."""
    out = []
    for d in dets:
        x, y, w, h = d["bbox"]
        x = max(0.0, min(x, width - 1.0))
        y = max(0.0, min(y, height - 1.0))
        w = min(w, width - x)
        h = min(h, height - y)
        if w > 1 and h > 1:
            out.append({**d, "bbox": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)]})
    return out


def _write_overlay(image: np.ndarray, dets: list[dict], image_id: str,
                   out_dir: Path) -> str:
    from PIL import Image, ImageDraw

    colours = {
        "tyre": (255, 87, 51), "drum": (255, 189, 51), "net": (51, 214, 255),
        "plastic_debris": (162, 89, 255), "wreck": (255, 51, 153),
        "unidentified": (160, 160, 160),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    canvas = Image.fromarray(image).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    for d in dets:
        x, y, w, h = d["bbox"]
        colour = colours.get(d["class"], (255, 255, 255))
        draw.rectangle([x, y, x + w, y + h], outline=colour, width=2)
        draw.text((x + 2, max(0, y - 11)),
                  f"{d['class']} {d['confidence']:.2f}", fill=colour)
    path = out_dir / f"{image_id}_overlay.png"
    canvas.save(path)
    return str(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the PS57 detection pipeline")
    ap.add_argument("file")
    ap.add_argument("--weights", default=None)
    ap.add_argument("--conf", type=float, default=None)
    ap.add_argument("--out", default=None, help="write result JSON here")
    args = ap.parse_args()

    overrides = {}
    if args.weights:
        overrides["weights"] = args.weights
    if args.conf is not None:
        overrides["conf_threshold"] = args.conf

    result = run_inference(args.file, overrides,
                           progress_cb=lambda s, p: print(f"[{p:3d}%] {s}"))
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out}  ({len(result['detections'])} detections)")
    else:
        print(text)


if __name__ == "__main__":
    main()
