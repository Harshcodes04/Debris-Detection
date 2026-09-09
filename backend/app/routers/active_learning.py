from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_analyst
from ..models import SurveyFile

router = APIRouter(prefix="/api/active-learning", tags=["active_learning"],
                   dependencies=[Depends(require_analyst)])

class RankRequest(BaseModel):
    images: list[str] | None = None
    top_k: int = 50

@router.post("/rank")
def rank_images(req: RankRequest, db: Session = Depends(get_db)):
    """
    Ranks unlabelled images by how much annotating them would teach the model.
    Note: Requires ultralytics and model weights to be available.
    """
    try:
        # We import locally to avoid failing startup if ML dependencies are missing.
        from ml.pipeline import load_models
        from ml.active import rank_for_annotation, annotation_budget_note
        
        images = req.images
        if not images:
            files = db.query(SurveyFile).all()
            images = [f.storage_path for f in files]
            
        if not images:
            return {"note": "No images available in the database to rank.", "candidates": []}
            
        models = load_models()
        candidates = rank_for_annotation(models, images, top_k=req.top_k)
        
        return {
            "note": annotation_budget_note(len(images), len(candidates)),
            "candidates": [c.to_dict() for c in candidates]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Active learning ranking failed: {str(e)}")
