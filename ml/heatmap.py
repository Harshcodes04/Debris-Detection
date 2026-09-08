"""Risk heatmap: where the seabed is worst, aggregated over surveys.

One detection is a point. A cleanup programme plans in areas - which stretch of
coast to work next season, where the problem is concentrating, whether last
year's effort actually reduced anything.

This bins registry entries into a geographic grid and weights each cell by
accumulated risk. It reads the persistent registry rather than a single
survey's detections, so a cell's value reflects everything known to be there,
including hazards found years ago that nobody has collected.

Output is a GeoJSON FeatureCollection - it opens in QGIS, Leaflet, or any GIS
a marine agency already runs, which matters more than a picture would.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# Roughly 500 m at the equator. Coarse enough that a cell means "this area",
# fine enough to plan a day's work around.
DEFAULT_CELL_DEG = 0.0045


@dataclass
class Cell:
    lat: float          # cell centre
    lon: float
    count: int
    risk_sum: float
    classes: dict
    oldest_days: int
    persistent: int     # hazards seen across more than one survey


def _cell_key(lat: float, lon: float, size: float) -> tuple[int, int]:
    return (math.floor(lat / size), math.floor(lon / size))


def build(entries, risk_scores: dict[str, float] | None = None,
          cell_deg: float = DEFAULT_CELL_DEG) -> list[Cell]:
    """Bin registry entries into grid cells.

    `entries` are ml.registry.Entry objects. `risk_scores` optionally maps
    hazard_id to a score from ml.risk; without it every hazard counts equally,
    which measures density rather than risk.
    """
    buckets = defaultdict(list)
    for e in entries:
        buckets[_cell_key(e.lat, e.lon, cell_deg)].append(e)

    cells: list[Cell] = []
    for (i, j), items in buckets.items():
        classes: dict[str, int] = defaultdict(int)
        for e in items:
            classes[e.cls] += 1
        cells.append(Cell(
            lat=round((i + 0.5) * cell_deg, 6),
            lon=round((j + 0.5) * cell_deg, 6),
            count=len(items),
            risk_sum=round(sum((risk_scores or {}).get(e.hazard_id, 1.0)
                               for e in items), 3),
            classes=dict(classes),
            oldest_days=max((e.age_days for e in items), default=0),
            persistent=sum(1 for e in items if e.times_seen > 1),
        ))
    return sorted(cells, key=lambda c: c.risk_sum, reverse=True)


def to_geojson(cells: list[Cell], cell_deg: float = DEFAULT_CELL_DEG) -> dict:
    """Grid squares as GeoJSON polygons, ready for QGIS or Leaflet."""
    peak = max((c.risk_sum for c in cells), default=1.0) or 1.0
    features = []
    for c in cells:
        half = cell_deg / 2
        ring = [[c.lon - half, c.lat - half], [c.lon + half, c.lat - half],
                [c.lon + half, c.lat + half], [c.lon - half, c.lat + half],
                [c.lon - half, c.lat - half]]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "hazards": c.count,
                "risk_sum": c.risk_sum,
                "intensity": round(c.risk_sum / peak, 3),   # 0-1, for styling
                "classes": c.classes,
                "persistent": c.persistent,
                "oldest_days": c.oldest_days,
            },
        })
    return {"type": "FeatureCollection",
            "properties": {"cell_size_deg": cell_deg,
                           "note": "intensity is risk_sum normalised to the "
                                   "hottest cell in this collection"},
            "features": features}


def write_geojson(cells: list[Cell], path: str | Path,
                  cell_deg: float = DEFAULT_CELL_DEG) -> Path:
    path = Path(path)
    path.write_text(json.dumps(to_geojson(cells, cell_deg), indent=2),
                    encoding="utf-8")
    return path


def summary(cells: list[Cell]) -> str:
    if not cells:
        return "no hazards in the registry yet"
    hot = cells[0]
    total = sum(c.count for c in cells)
    stale = sum(c.persistent for c in cells)
    return (f"{total} hazards across {len(cells)} cells. "
            f"Worst cell {hot.lat:.4f},{hot.lon:.4f}: {hot.count} hazards, "
            f"risk {hot.risk_sum:.2f}. "
            f"{stale} confirmed across multiple surveys and still uncollected.")
