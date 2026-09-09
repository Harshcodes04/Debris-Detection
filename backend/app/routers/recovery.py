from datetime import date
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_analyst, require_viewer
from ..models import RegistryEntry, User
from ml.recovery import plan_recovery, day_plan
from ml.enrich import enrich_detection, to_dict as context_to_dict
from ml.risk import score_detection, to_dict as risk_to_dict

router = APIRouter(prefix="/api/recovery", tags=["recovery"],
                   dependencies=[Depends(require_viewer)])

class DayPlanRequest(BaseModel):
    hazard_ids: list[str]
    hours_available: float = 8.0

def _get_plan_and_risk(e: RegistryEntry):
    # This might make API calls if not cached internally by enrich_detection
    ctx = enrich_detection(e.lat, e.lon, navigation_is_real=True)
    depth_m = ctx.depth_m if ctx else None
    
    transit_hours = None
    if ctx and ctx.nearest_port:
        transit_hours = ctx.nearest_port.get("transit_hours")
    
    age_days = (date.today() - date.fromisoformat(e.first_seen)).days
    
    plan = plan_recovery(
        hazard_id=e.hazard_id,
        cls=e.class_name,
        depth_m=depth_m,
        transit_hours=transit_hours,
        age_days=age_days
    )
    
    risk = score_detection(e.class_name, e.best_confidence, ctx)
    return plan, risk, ctx

@router.get("/hazards/{hazard_id}/plan")
def get_recovery_plan(hazard_id: str, db: Session = Depends(get_db)):
    e = db.query(RegistryEntry).filter(RegistryEntry.hazard_id == hazard_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Hazard not found")
        
    plan, risk, ctx = _get_plan_and_risk(e)
    # Depth, risk and the enrichment were computed to build the plan and then
    # thrown away, which left the UI with nothing to show about a hazard beyond
    # its class and its box. They cost nothing extra to return.
    return {
        **plan.to_dict(),
        "risk": risk_to_dict(risk),
        "context": context_to_dict(ctx),
    }

@router.post("/day-plan")
def create_day_plan(req: DayPlanRequest, db: Session = Depends(get_db),
                    _: User = Depends(require_analyst)):
    entries = db.query(RegistryEntry).filter(RegistryEntry.hazard_id.in_(req.hazard_ids)).all()
    if not entries:
        raise HTTPException(status_code=404, detail="No matching hazards found")
        
    plans_with_risk = []
    for e in entries:
        plan, risk, _ctx = _get_plan_and_risk(e)
        plans_with_risk.append((plan, risk.score))
        
    result = day_plan(plans_with_risk, hours_available=req.hours_available)
    return result
