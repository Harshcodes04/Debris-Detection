"""Sanity gate before any real training run (step A5).

Trains on a handful of images with augmentation off. If the model cannot
memorise 20 images, the labels or the loader are broken -- and no amount of
hyperparameter tuning will save the run.

    python -m ml.training.overfit_check --n 20

PASS = mAP50 > 0.90 on the same images it trained on.
FAIL = go and look at the labels; draw them back onto three images.
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def build_subset(data_yaml: Path, n: int, workdir: Path) -> Path:
    cfg = yaml.safe_load(data_yaml.read_text())
    base = (data_yaml.parent / cfg["path"]).resolve()
    img_dir = base / cfg["train"]
    lbl_dir = base / cfg["train"].replace("images", "labels")

    images = sorted(p for p in img_dir.iterdir()
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    if not images:
        sys.exit(f"no images found in {img_dir}")

    # Prefer images that actually contain boxes: an all-empty subset proves nothing.
    labelled = []
    for p in images:
        lbl = lbl_dir / f"{p.stem}.txt"
        if lbl.exists() and lbl.read_text().strip():
            labelled.append(p)
    pool = labelled or images
    picked = random.Random(0).sample(pool, min(n, len(pool)))

    for split in ("train", "val"):
        (workdir / "images" / split).mkdir(parents=True, exist_ok=True)
        (workdir / "labels" / split).mkdir(parents=True, exist_ok=True)
        for img in picked:
            shutil.copy(img, workdir / "images" / split / img.name)
            lbl = lbl_dir / f"{img.stem}.txt"
            if lbl.exists():
                shutil.copy(lbl, workdir / "labels" / split / lbl.name)

    sub = dict(cfg, path=str(workdir), train="images/train", val="images/val")
    sub.pop("test", None)
    out = workdir / "data.yaml"
    out.write_text(yaml.safe_dump(sub))
    print(f"overfit subset: {len(picked)} images ({len(labelled)} labelled) -> {workdir}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="configs/data.yaml")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--model", default="yolov8s.pt")
    args = ap.parse_args()

    from ultralytics import YOLO

    workdir = ROOT / "runs" / "_overfit_subset"
    shutil.rmtree(workdir, ignore_errors=True)
    data = build_subset(ROOT / args.data, args.n, workdir)

    model = YOLO(args.model)
    res = model.train(
        data=str(data), epochs=args.epochs, imgsz=640, batch=4, seed=0,
        name="overfit_check", project="runs/sanity", patience=0,
        mosaic=0.0, hsv_h=0.0, hsv_s=0.0, hsv_v=0.0, fliplr=0.0, flipud=0.0,
        translate=0.0, scale=0.0, erasing=0.0, verbose=False,
    )
    map50 = (getattr(res, "results_dict", {}) or {}).get("metrics/mAP50(B)", 0.0)
    print(f"\nmAP50 on the memorised images: {map50:.3f}")
    if map50 > 0.90:
        print("PASS - loader and labels are sane. Start the real run.")
        return
    print("FAIL - do NOT start the real run.")
    print("  1. draw the labels back onto 3 images and look at them")
    print("  2. check class ids are 0-indexed and inside the class list")
    print("  3. check boxes are normalised cx cy w h, all within [0,1]")
    sys.exit(1)


if __name__ == "__main__":
    main()
