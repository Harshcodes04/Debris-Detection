from __future__ import annotations

import html
from pathlib import Path
from time import perf_counter


def run_fake_inference(file_path: str | Path, overlay_dir: str | Path) -> dict:
    """Return the frozen model contract until the real ML wrapper is available."""
    started = perf_counter()
    source = Path(file_path)
    output_dir = Path(overlay_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = output_dir / f"{source.stem}_overlay.svg"

    width = 1024
    height = 768
    detections = [
        {
            "class": "debris",
            "confidence": 0.87,
            "bbox": [320, 220, 144, 96],
            "lat": None,
            "lon": None,
            "size_m": 0.9,
            "frame_index": 0,
        }
    ]

    safe_label = html.escape(source.name)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#17202a"/>
  <text x="24" y="42" fill="#d8dee9" font-family="Arial, sans-serif" font-size="22">Fake sonar overlay: {safe_label}</text>
  <rect x="320" y="220" width="144" height="96" fill="none" stroke="#f2c14e" stroke-width="4"/>
  <text x="320" y="208" fill="#f2c14e" font-family="Arial, sans-serif" font-size="18">debris 0.87</text>
</svg>
'''
    overlay_path.write_text(svg, encoding="utf-8")

    return {
        "image_id": source.stem,
        "width": width,
        "height": height,
        "processing_ms": max(1, round((perf_counter() - started) * 1000)),
        "detections": detections,
        "overlay_path": str(overlay_path),
    }

