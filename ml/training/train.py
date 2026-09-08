"""Training entry point. Every run is reproducible and logged.

    python -m ml.training.train --config configs/baseline_yolov8s.yaml
    python -m ml.training.train --config configs/baseline_yolov8s.yaml --epochs 5

A run that is not in runs/RUN_LOG.csv did not happen. The log is what lets us
say "v3 beat v2 because of X" in the deck instead of guessing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUN_LOG = ROOT / "runs" / "RUN_LOG.csv"
LOG_FIELDS = [
    "run_id", "started_utc", "config", "config_hash", "dataset_version",
    "model", "epochs", "imgsz", "seed", "freeze", "git_sha",
    "map50", "map50_95", "precision", "recall", "checkpoint", "notes",
]


def set_seed(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np
        import torch
    except ImportError:
        return
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def config_hash(cfg: dict) -> str:
    blob = json.dumps(cfg, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:10]


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "nogit"


def log_run(row: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not RUN_LOG.exists()
    with RUN_LOG.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in LOG_FIELDS})
    print(f"logged run -> {RUN_LOG}")


def train(config_path: str, overrides: dict, notes: str = "") -> dict:
    from ultralytics import YOLO

    cfg = yaml.safe_load(Path(config_path).read_text())
    cfg.update({k: v for k, v in overrides.items() if v is not None})

    set_seed(cfg.get("seed", 0))
    chash = config_hash(cfg)
    run_id = f"{cfg.get('name', 'run')}_{datetime.now().strftime('%m%d_%H%M')}_{chash}"
    data_cfg = yaml.safe_load((ROOT / cfg["data"]).read_text())

    print(f"run_id       : {run_id}")
    print(f"model        : {cfg['model']}")
    print(f"dataset      : {cfg['data']} ({data_cfg.get('dataset_version', '?')})")
    print(f"seed / freeze: {cfg.get('seed')} / {cfg.get('freeze')}")
    print(f"host         : {platform.node()}")

    train_kwargs = {k: v for k, v in cfg.items()
                    if k not in {"model", "name", "notes", "dataset_version"}}
    model = YOLO(cfg["model"])
    results = model.train(name=run_id, **train_kwargs)

    metrics = getattr(results, "results_dict", {}) or {}
    ckpt = Path(results.save_dir) / "weights" / "best.pt"
    row = {
        "run_id": run_id,
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": config_path,
        "config_hash": chash,
        "dataset_version": data_cfg.get("dataset_version", "?"),
        "model": cfg["model"],
        "epochs": cfg.get("epochs"),
        "imgsz": cfg.get("imgsz"),
        "seed": cfg.get("seed"),
        "freeze": cfg.get("freeze"),
        "git_sha": git_sha(),
        "map50": round(metrics.get("metrics/mAP50(B)", 0.0), 4),
        "map50_95": round(metrics.get("metrics/mAP50-95(B)", 0.0), 4),
        "precision": round(metrics.get("metrics/precision(B)", 0.0), 4),
        "recall": round(metrics.get("metrics/recall(B)", 0.0), 4),
        "checkpoint": str(ckpt),
        "notes": notes,
    }
    log_run(row)
    print(f"\nbest checkpoint: {ckpt}")
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/baseline_yolov8s.yaml")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--freeze", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--notes", default="", help="one line: what am I testing?")
    args = ap.parse_args()
    cli = {k: v for k, v in vars(args).items() if k not in {"config", "notes"}}
    train(args.config, cli, notes=args.notes)


if __name__ == "__main__":
    main()
