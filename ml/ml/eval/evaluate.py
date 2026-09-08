"""Evaluation harness (step A8). Akshat defines it, Neha runs it per checkpoint.

    python -m ml.eval.evaluate --weights runs/train/baseline/weights/best.pt
    python -m ml.eval.evaluate --weights best.pt --split test --area-km2 12.4

Outputs into runs/eval/<checkpoint-stem>/:
    metrics.json          machine-readable, used by the deck and the README table
    metrics.md            paste-ready table for Prachi
    confusion_matrix.png  } produced by ultralytics, copied here so one folder
    PR_curve.png          } holds everything the deck needs

Always evaluate on the held-out TEST split from surveys the model never saw.
Val numbers are for choosing a checkpoint, never for reporting.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import yaml

from ml.contract import CLASSES

ROOT = Path(__file__).resolve().parents[2]


def evaluate(weights: str, data: str, split: str, area_km2: float | None,
             conf: float, iou: float) -> dict:
    from ultralytics import YOLO

    model = YOLO(weights)
    res = model.val(data=str(ROOT / data), split=split, conf=conf, iou=iou,
                    plots=True, verbose=False)

    names = getattr(res, "names", None) or {i: c for i, c in enumerate(CLASSES)}
    per_class = {}
    for i, cls_id in enumerate(getattr(res.box, "ap_class_index", [])):
        per_class[names[int(cls_id)]] = {
            "precision": round(float(res.box.p[i]), 4),
            "recall": round(float(res.box.r[i]), 4),
            "map50": round(float(res.box.ap50[i]), 4),
            "map50_95": round(float(res.box.ap[i]), 4),
        }

    summary = {
        "weights": str(weights),
        "data": data,
        "split": split,
        "conf_threshold": conf,
        "iou_threshold": iou,
        "map50": round(float(res.box.map50), 4),
        "map50_95": round(float(res.box.map), 4),
        "precision": round(float(res.box.mp), 4),
        "recall": round(float(res.box.mr), 4),
        "per_class": per_class,
        "plots_dir": str(res.save_dir),
    }

    # The metric a domain judge actually asks about: how much junk does an
    # analyst have to sift through per square kilometre of survey?
    fp = _false_positive_count(res)
    summary["false_positives"] = fp
    if area_km2:
        summary["area_km2"] = area_km2
        summary["false_positives_per_km2"] = round(fp / area_km2, 2)
    return summary


def _false_positive_count(res) -> int:
    """Sum the background column of the ultralytics confusion matrix: predictions
    that matched no ground-truth box."""
    try:
        matrix = res.confusion_matrix.matrix  # (nc+1, nc+1)
        return int(matrix[:-1, -1].sum())
    except Exception:
        return -1


def to_markdown(s: dict) -> str:
    lines = [
        f"# Evaluation — `{Path(s['weights']).name}` on `{s['split']}`",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| mAP@0.5 | {s['map50']:.3f} |",
        f"| mAP@0.5:0.95 | {s['map50_95']:.3f} |",
        f"| Precision | {s['precision']:.3f} |",
        f"| Recall | {s['recall']:.3f} |",
    ]
    if "false_positives_per_km2" in s:
        lines.append(f"| False positives / km² | {s['false_positives_per_km2']:.2f} |")
    lines += ["", "| Class | P | R | mAP@0.5 | mAP@0.5:0.95 |", "|---|---|---|---|---|"]
    for cls, m in s["per_class"].items():
        lines.append(
            f"| {cls} | {m['precision']:.3f} | {m['recall']:.3f} | "
            f"{m['map50']:.3f} | {m['map50_95']:.3f} |"
        )
    lines += ["", f"_conf={s['conf_threshold']}, iou={s['iou_threshold']}, "
                  f"data={s['data']}_"]
    return "\n".join(lines) + "\n"


def contact_sheets(weights: str, data: str, split: str, out_dir: Path, n: int) -> None:
    """A grid of true positives, false positives and misses. Deck material and
    the fastest way to see what the model is actually confused by."""
    from ultralytics import YOLO
    from PIL import Image

    cfg = yaml.safe_load((ROOT / data).read_text())
    base = (ROOT / data).parent / cfg["path"]
    img_dir = (base / cfg.get(split, cfg["val"])).resolve()
    images = sorted(p for p in img_dir.iterdir()
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg"})[: n * 4]
    if not images:
        print(f"contact sheet skipped: no images in {img_dir}")
        return

    model = YOLO(weights)
    tiles = []
    for res in model.predict(images, verbose=False, conf=0.25):
        tiles.append(Image.fromarray(res.plot()[:, :, ::-1]).resize((320, 320)))
    if not tiles:
        return

    cols = 5
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 320, rows * 320), (12, 14, 18))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * 320, (i // cols) * 320))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(out_dir / "contact_sheet.png")
    print(f"contact sheet -> {out_dir / 'contact_sheet.png'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", default="configs/data.yaml")
    ap.add_argument("--split", default="test", choices=["train", "val", "test"])
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--area-km2", type=float, default=None,
                    help="surveyed area of the split, for FP/km2")
    ap.add_argument("--sheets", type=int, default=10, help="0 to skip contact sheets")
    args = ap.parse_args()

    out_dir = ROOT / "runs" / "eval" / Path(args.weights).parent.parent.name
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = evaluate(args.weights, args.data, args.split, args.area_km2,
                       args.conf, args.iou)
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "metrics.md").write_text(to_markdown(summary))

    for plot in ("confusion_matrix.png", "BoxPR_curve.png", "PR_curve.png"):
        src = Path(summary["plots_dir"]) / plot
        if src.exists():
            shutil.copy(src, out_dir / plot)

    if args.sheets:
        contact_sheets(args.weights, args.data, args.split, out_dir, args.sheets)

    print(to_markdown(summary))
    print(f"all artifacts -> {out_dir}")


if __name__ == "__main__":
    main()
