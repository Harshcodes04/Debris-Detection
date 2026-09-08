"""Anomaly reporting: turn detections into the structured output PS 57 asks for.

The problem statement requires a report giving, per detected hazard, its exact
location (latitude/longitude), bounding dimensions, and classification, in
JSON or CSV. This module is that engine.

JSON carries the full record including survey provenance. CSV is the flat
table an analyst opens in a spreadsheet or loads into GIS.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_VERSION = "1.0"


def build_report(
    result: dict[str, Any],
    *,
    survey_name: str = "unnamed-survey",
    navigation_source: str = "unknown",
    model_version: str = "unset",
) -> dict[str, Any]:
    """Assemble the anomaly report from a run_inference() result.

    `navigation_source` is recorded verbatim in the report. When positions come
    from a simulated track it must say so - a geotagged report that does not
    disclose simulated navigation is a report that can mislead someone into
    sending a vessel to a coordinate.
    """
    detections = result.get("detections", [])
    geotagged = [d for d in detections if d.get("lat") is not None]

    anomalies = []
    for i, d in enumerate(detections, 1):
        x, y, w, h = d["bbox"]
        anomalies.append(
            {
                "anomaly_id": f"{result['image_id']}-{i:03d}",
                "classification": d["class"],
                "confidence_pct": round(float(d["confidence"]) * 100, 1),
                "latitude": d.get("lat"),
                "longitude": d.get("lon"),
                "bbox_pixels": {"x": round(x), "y": round(y),
                                "width": round(w), "height": round(h)},
                "dimensions_m": {"length": d.get("size_m")},
                "frame_index": d.get("frame_index"),
            }
        )

    by_class: dict[str, int] = {}
    for d in detections:
        by_class[d["class"]] = by_class.get(d["class"], 0) + 1

    return {
        "report_version": REPORT_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "survey": {
            "name": survey_name,
            "source_image": result["image_id"],
            "image_size_px": [result["width"], result["height"]],
            "navigation_source": navigation_source,
        },
        "model": {
            "version": model_version,
            "processing_ms": result.get("processing_ms"),
        },
        "summary": {
            "total_anomalies": len(detections),
            "geotagged": len(geotagged),
            "by_classification": by_class,
            "mean_confidence_pct": round(
                sum(float(d["confidence"]) for d in detections) / len(detections) * 100, 1
            ) if detections else 0.0,
        },
        "anomalies": anomalies,
    }


def write_json(report: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def write_csv(report: dict[str, Any], path: str | Path) -> Path:
    """Flat one-row-per-anomaly table for spreadsheets and GIS import."""
    path = Path(path)
    fields = [
        "anomaly_id", "classification", "confidence_pct",
        "latitude", "longitude", "length_m",
        "bbox_x", "bbox_y", "bbox_width", "bbox_height",
        "frame_index", "survey", "navigation_source",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for a in report["anomalies"]:
            b = a["bbox_pixels"]
            w.writerow({
                "anomaly_id": a["anomaly_id"],
                "classification": a["classification"],
                "confidence_pct": a["confidence_pct"],
                "latitude": a["latitude"],
                "longitude": a["longitude"],
                "length_m": a["dimensions_m"]["length"],
                "bbox_x": b["x"], "bbox_y": b["y"],
                "bbox_width": b["width"], "bbox_height": b["height"],
                "frame_index": a["frame_index"],
                "survey": report["survey"]["name"],
                "navigation_source": report["survey"]["navigation_source"],
            })
    return path
