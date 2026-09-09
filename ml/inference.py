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
from ml.interfaces import ReferencePostProcessor, ReferencePreprocessor, _iou
from ml.pipeline import HEADS

# The package sits at the repo root, so its parent IS the root: configs and
# weights live beside the package, not inside it.
_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = _ROOT / "configs" / "inference.yaml"
_DETECTORS: dict[str, tuple[Detector, float]] | None = None


# Which heads ship, and the confidence each runs at, comes from ml.pipeline so
# the demo and the backend cannot disagree about it.


def load_config(path: str | Path | None = None) -> dict:
    cfg_path = Path(path) if path else _CONFIG_PATH
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    # A configured path that no longer exists is the usual way this ends up
    # running something other than what it claims. Drop it and fall back to the
    # shipped heads rather than carrying a stale path forward.
    if cfg.get("weights") and not Path(cfg["weights"]).exists():
        cfg.pop("weights")
    # env overrides let the backend container point at its own paths
    if os.getenv("SIH_ML_WEIGHTS"):
        cfg["weights"] = os.environ["SIH_ML_WEIGHTS"]
    if os.getenv("SIH_ML_OUTPUT_DIR"):
        cfg["output_dir"] = os.environ["SIH_ML_OUTPUT_DIR"]
    return cfg


def get_detectors(cfg: dict | None = None) -> dict[str, tuple[Detector, float]]:
    """Every detection head, loaded once per process.

    Both heads have to run. A YOLO head only ever finds the classes it was
    trained on, so the wreck head alone reports nothing at all on ghost-gear
    imagery - which is the case the problem statement is actually about.

    Each head keeps its own confidence: ghost gear is less confident everywhere
    and runs at 0.20, the wreck head at 0.25. An explicit conf_threshold in the
    config overrides both.

    Setting `weights` (in the config or as SIH_ML_WEIGHTS) pins inference to
    that single checkpoint instead, so a container can still be told exactly
    what to run.

    The worker should call this at startup, so the first upload of the demo is
    not the one that pays the model-load cost.
    """
    global _DETECTORS
    if _DETECTORS is not None:
        return _DETECTORS

    cfg = cfg or load_config()
    common = {
        "iou": cfg.get("iou_threshold", 0.45),
        "imgsz": cfg.get("imgsz", INPUT_IMAGE_SIZE),
    }
    override = cfg.get("conf_threshold")

    if cfg.get("weights"):
        conf = 0.25 if override is None else override
        _DETECTORS = {"custom": (Detector(weights=cfg["weights"], conf=conf, **common), conf)}
        return _DETECTORS

    heads: dict[str, tuple[Detector, float]] = {}
    missing: list[str] = []
    for name, spec in HEADS.items():
        path = Path(spec["weights"])
        if not path.exists():
            missing.append(str(path))
            continue
        conf = spec["conf"] if override is None else override
        heads[name] = (Detector(weights=str(path), conf=conf, **common), conf)

    # A detector built with no weights returns mock detections, and mock output
    # reaching the backend looks exactly like the real thing. Fail loudly here.
    if not heads:
        raise FileNotFoundError(
            "no model weights found: " + ", ".join(missing)
            + ". Set SIH_WEIGHTS_DIR, or SIH_ML_WEIGHTS to pin one checkpoint."
        )
    _DETECTORS = heads
    return _DETECTORS


def get_detector(cfg: dict | None = None) -> Detector:
    """The first head. Kept for callers that only want one; prefer
    get_detectors, which is what actually runs."""
    return next(iter(get_detectors(cfg).values()))[0]


def _merge_heads(per_head: list[list[dict]], iou_threshold: float) -> list[dict]:
    """Fold every head's detections into one list.

    Two heads can box the same object - a crab pot is a small bright return
    with a shadow, which is also what a small wreck looks like. Keeping both
    would report one object twice under two class names, so the more confident
    box wins.
    """
    kept: list[dict] = []
    for det in sorted((d for head in per_head for d in head),
                      key=lambda d: d["confidence"], reverse=True):
        if all(_iou(det["bbox"], k["bbox"]) < iou_threshold for k in kept):
            kept.append(det)
    return kept


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
    detectors = get_detectors(cfg)
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
    stitch_iou = cfg.get("stitch_iou", 0.5)

    # Every head sees every tile. Each is thresholded at its own confidence
    # before the heads are folded together, so a head that is less confident
    # everywhere is not silently cut off by the other one's threshold.
    per_head: list[list[dict]] = []
    for head_detector, head_conf in detectors.values():
        per_tile: list[list[dict]] = []
        for i in range(0, len(tiles), batch_size):
            chunk = tiles[i : i + batch_size]
            per_tile.extend(head_detector.predict_tiles([t.image for t in chunk]))
        stitched = post.stitch(list(zip(tiles, per_tile)), iou_threshold=stitch_iou)
        per_head.append([d for d in stitched if d["confidence"] >= head_conf])

    merged = _merge_heads(per_head, cfg.get("head_merge_iou", 0.55))
    merged = post.georeference(merged, sonar)
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
        model_version="+".join(sorted(d.version for d, _ in detectors.values())),
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
