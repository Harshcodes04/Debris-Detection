"""Export the chosen checkpoint and PROVE the export is faithful (step A9).

    python -m ml.export.export_onnx --weights runs/train/baseline/weights/best.pt

An ONNX file that silently disagrees with the PyTorch model is the worst kind
of bug: metrics in the deck come from PyTorch, the demo runs ONNX, and the
numbers stop matching the day before the presentation. So the export is not
"done" until the parity check passes on real images.

Parity criteria (both must hold on every check image):
    * same number of detections above the confidence threshold
    * every matched box within 2 px, confidence within 0.02
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from ml.contract import CONTRACT_VERSION, INPUT_IMAGE_SIZE

ROOT = Path(__file__).resolve().parents[2]


def export(weights: str, imgsz: int, half: bool, opset: int) -> Path:
    from ultralytics import YOLO

    model = YOLO(weights)
    out = model.export(format="onnx", imgsz=imgsz, opset=opset, half=half,
                       dynamic=False, simplify=True)
    path = Path(out)
    print(f"exported -> {path}  ({path.stat().st_size / 1e6:.1f} MB)")
    return path


def parity_check(pt_weights: str, onnx_path: Path, images: list[Path],
                 conf: float) -> bool:
    from ultralytics import YOLO

    pt_model = YOLO(pt_weights)
    onnx_model = YOLO(str(onnx_path))
    ok = True

    for img in images:
        a = _boxes(pt_model.predict(str(img), conf=conf, verbose=False)[0])
        b = _boxes(onnx_model.predict(str(img), conf=conf, verbose=False)[0])
        if len(a) != len(b):
            print(f"  MISMATCH {img.name}: pytorch {len(a)} boxes, onnx {len(b)}")
            ok = False
            continue
        for (xa, ca), (xb, cb) in zip(a, b):
            if np.max(np.abs(np.array(xa) - np.array(xb))) > 2.0 or abs(ca - cb) > 0.02:
                print(f"  MISMATCH {img.name}: box/conf drift "
                      f"{np.max(np.abs(np.array(xa) - np.array(xb))):.2f}px "
                      f"{abs(ca - cb):.3f}")
                ok = False
                break
        else:
            print(f"  OK {img.name}: {len(a)} boxes agree")
    return ok


def _boxes(result) -> list[tuple[list[float], float]]:
    out = []
    for box in result.boxes:
        out.append(([float(v) for v in box.xyxy[0].tolist()], float(box.conf[0])))
    return sorted(out, key=lambda t: (-t[1], t[0]))


def write_model_meta(onnx_path: Path, pt_weights: str, imgsz: int,
                     parity: bool) -> None:
    meta = {
        "contract_version": CONTRACT_VERSION,
        "onnx": str(onnx_path),
        "source_checkpoint": str(pt_weights),
        "input_size": [1, 3, imgsz, imgsz],
        "input_dtype": "float32",
        "input_range": "0.0-1.0 (uint8 / 255), channels replicated from grayscale",
        "parity_verified": parity,
    }
    path = onnx_path.with_suffix(".meta.json")
    path.write_text(json.dumps(meta, indent=2))
    print(f"model metadata -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--imgsz", type=int, default=INPUT_IMAGE_SIZE)
    ap.add_argument("--opset", type=int, default=12)
    ap.add_argument("--half", action="store_true", help="fp16; GPU inference only")
    ap.add_argument("--check-dir", default=None,
                    help="folder of images for the parity check (default: val split)")
    ap.add_argument("--n-check", type=int, default=5)
    ap.add_argument("--conf", type=float, default=0.25)
    args = ap.parse_args()

    onnx_path = export(args.weights, args.imgsz, args.half, args.opset)

    check_dir = Path(args.check_dir) if args.check_dir else _default_check_dir()
    images = []
    if check_dir and check_dir.exists():
        images = sorted(p for p in check_dir.iterdir()
                        if p.suffix.lower() in {".png", ".jpg", ".jpeg"})[: args.n_check]

    if not images:
        print("\nNO PARITY CHECK RUN - no check images found.")
        print("Do not hand this export to the backend until you have run:")
        print("  python -m ml.export.export_onnx --weights ... --check-dir <images>")
        write_model_meta(onnx_path, args.weights, args.imgsz, parity=False)
        sys.exit(1)

    print(f"\nparity check on {len(images)} images:")
    ok = parity_check(args.weights, onnx_path, images, args.conf)
    write_model_meta(onnx_path, args.weights, args.imgsz, parity=ok)

    if ok:
        print("\nPARITY OK - safe to hand to backend.")
        print("Next: update configs/inference.yaml -> weights, tell Harshit the path.")
    else:
        print("\nPARITY FAILED - do not ship this export.")
        print("Try: --opset 12, simplify=False, or export without --half.")
        sys.exit(1)


def _default_check_dir() -> Path | None:
    import yaml

    data = ROOT / "configs" / "data.yaml"
    if not data.exists():
        return None
    cfg = yaml.safe_load(data.read_text())
    return (data.parent / cfg["path"] / cfg["val"]).resolve()


if __name__ == "__main__":
    main()
