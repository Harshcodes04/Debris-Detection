import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RegistryEntry
from ml.registry import Entry as MLEntry
from ml.heatmap import build as build_heatmap, to_geojson as heatmap_to_geojson

router = APIRouter(prefix="/api/registry", tags=["registry"])

def _to_ml_entry(e: RegistryEntry) -> MLEntry:
    return MLEntry(
        hazard_id=e.hazard_id,
        cls=e.class_name,
        lat=e.lat,
        lon=e.lon,
        first_seen=e.first_seen,
        last_seen=e.last_seen,
        times_seen=e.times_seen,
        consecutive_misses=e.consecutive_misses,
        status=e.status,
        best_confidence=e.best_confidence,
        surveys=json.loads(e.surveys),
        note=e.note
    )

@router.get("")
def list_registry(db: Session = Depends(get_db)):
    entries = db.query(RegistryEntry).all()
    # Serialize DB models for response
    results = []
    for e in entries:
        results.append({
            "hazard_id": e.hazard_id,
            "class": e.class_name,
            "lat": e.lat,
            "lon": e.lon,
            "status": e.status,
            "times_seen": e.times_seen,
            "last_seen": e.last_seen,
            "surveys": json.loads(e.surveys),
            "note": e.note
        })
    return {"entries": results}

@router.get("/heatmap")
def get_heatmap(db: Session = Depends(get_db)):
    # We build the heatmap only for active/unconfirmed items
    active_entries = db.query(RegistryEntry).filter(
        RegistryEntry.status.in_(["present", "unconfirmed"])
    ).all()
    
    ml_entries = [_to_ml_entry(e) for e in active_entries]
    
    # We could also provide a risk_scores dict if we joined with the detections table to get max risk.
    # For now, let's just pass the entries to the heatmap builder.
    cells = build_heatmap(ml_entries)
    geojson = heatmap_to_geojson(cells)
    
    return geojson
