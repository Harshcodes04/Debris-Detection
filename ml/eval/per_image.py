"""Per-image evaluation on a YOLO-format test split.

evaluate.py reports the aggregate. This reports one row per image, because a
single mAP hides whether the misses are spread evenly or concentrated in a few
hard scenes - and on this data they are not spread evenly.

    python -m ml.eval.per_image --data path/to/crabpot_yolo --model weights/ghostgear_model.pt

Writes a CSV with, per image: how many targets it holds, how many detections
the model made, TP/FP/FN, the best and mean-matched confidence, the median
target size in pixels, and a single outcome label.
"""

from __future__ import annotations

import argparse
import collections
import csv
from pathlib import Path

from PIL import Image

CONF = 0.20      # the operating point pipeline.py runs at
IOU_HIT = 0.50


def iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def load_truth(label_file: Path, w: int, h: int) -> list[list[float]]:
    if not label_file.exists():
        return []
    boxes = []
    for line in label_file.read_text().splitlines():
        if not line.strip():
            continue
        _, cx, cy, bw, bh = (float(v) for v in line.split()[:5])
        boxes.append([(cx - bw / 2) * w, (cy - bh / 2) * h, bw * w, bh * h])
    return boxes


def verdict(truth: int, preds: int, tp: int, fp: int, fn: int) -> str:
    if not truth and not preds:
        return "correct reject"
    if not truth:
        return "false alarm"
    if tp and not fp and not fn:
        return "perfect"
    if tp and fn:
        return "partial"
    if tp:
        return "hit + false alarm"
    if preds:
        return "wrong place"
    return "missed"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True,
                    help="dataset root holding images/<split> and labels/<split>")
    ap.add_argument("--model", required=True, help="weights to evaluate")
    ap.add_argument("--split", default="test")
    ap.add_argument("--conf", type=float, default=CONF)
    ap.add_argument("--iou", type=float, default=IOU_HIT)
    ap.add_argument("--out", default="per_image.csv")
    args = ap.parse_args()

    from ultralytics import YOLO

    images = sorted((Path(args.data) / "images" / args.split).glob("*.jpg"))
    if not images:
        raise SystemExit(f"no images under {args.data}/images/{args.split}")
    labels = Path(args.data) / "labels" / args.split

    model = YOLO(args.model)
    rows = []

    for f in images:
        w, h = Image.open(f).size
        truth = load_truth(labels / f"{f.stem}.txt", w, h)

        result = model.predict(str(f), conf=args.conf, verbose=False)[0]
        preds = []
        for b in result.boxes:
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
            preds.append((float(b.conf), [x1, y1, x2 - x1, y2 - y1]))
        preds.sort(key=lambda p: p[0], reverse=True)

        # Greedy match, highest confidence first, one detection per target.
        used = [False] * len(truth)
        tp = fp = 0
        matched = []
        for conf, box in preds:
            hit = -1
            for i, gt in enumerate(truth):
                if not used[i] and iou(box, gt) >= args.iou:
                    hit = i
                    break
            if hit >= 0:
                used[hit] = True
                tp += 1
                matched.append(conf)
            else:
                fp += 1
        fn = used.count(False)

        # Median target size, to relate failure to object scale.
        med_px = 0.0
        if truth:
            sizes = sorted(max(t[2], t[3]) for t in truth)
            med_px = sizes[len(sizes) // 2]

        rows.append({
            "image": f.stem,
            "truth": len(truth),
            "predicted": len(preds),
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "best_conf": round(max((c for c, _ in preds), default=0.0), 3),
            "matched_conf": round(sum(matched) / len(matched), 3) if matched else 0.0,
            "median_target_px": round(med_px),
            "verdict": verdict(len(truth), len(preds), tp, fp, fn),
        })

    out = Path(args.out)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    TP = sum(r["TP"] for r in rows)
    FP = sum(r["FP"] for r in rows)
    FN = sum(r["FN"] for r in rows)
    prec = TP / (TP + FP) if TP + FP else 0.0
    rec = TP / (TP + FN) if TP + FN else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    print(f"images      : {len(rows)}")
    print(f"targets     : {sum(r['truth'] for r in rows)}")
    print(f"detections  : {sum(r['predicted'] for r in rows)}  (at conf {args.conf})")
    print(f"TP/FP/FN    : {TP} / {FP} / {FN}")
    print(f"precision   : {prec:.3f}")
    print(f"recall      : {rec:.3f}")
    print(f"F1          : {f1:.3f}")
    print()
    print("per-image outcome:")
    for v, n in collections.Counter(r["verdict"] for r in rows).most_common():
        print(f"   {v:<20} {n:4d}  {n / len(rows):5.1%}")
    print()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
