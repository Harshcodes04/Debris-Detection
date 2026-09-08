import json
import math
from datetime import date
from sqlalchemy.orm import Session

from ..models import RegistryEntry


MATCH_RADIUS_M = 25.0        # positional tolerance when matching to the registry
MISSES_TO_GONE = 2           # consecutive surveys missing before presumed removed

IMMOVABLE = {"ship", "wreck", "aircraft"}

PRESENT = "present"          # seen in the most recent survey covering it
UNCONFIRMED = "unconfirmed"  # missed once - could be a miss, could be gone
GONE = "gone"                # missed repeatedly, presumed recovered or shifted
RECOVERED = "recovered"      # a crew reported recovering it - authoritative


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6_371_008.8
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


class RegistryService:
    """Backend service for managing the persistent debris registry in the database."""

    def __init__(self, db: Session):
        self.db = db

    def _next_id(self) -> str:
        count = self.db.query(RegistryEntry).count()
        return f"HZ-{count + 1:05d}"

    def _nearest(self, lat: float, lon: float, cls: str) -> RegistryEntry | None:
        entries = self.db.query(RegistryEntry).filter(
            RegistryEntry.class_name == cls,
            RegistryEntry.status != RECOVERED
        ).all()

        best, best_d = None, MATCH_RADIUS_M
        for e in entries:
            d = haversine_m((lat, lon), (e.lat, e.lon))
            if d < best_d:
                best, best_d = e, d
        return best

    def reconcile(self, detections: list[dict], survey: str,
                  when: str | None = None,
                  covered: list[str] | None = None) -> None:
        """Fold one survey's detections into the registry."""
        when = when or date.today().isoformat()
        matched: set[str] = set()

        for d in detections:
            lat, lon = d.get("lat"), d.get("lon")
            if lat is None or lon is None:
                continue
            cls = d.get("class", "unidentified")
            conf = float(d.get("confidence", 0.0))

            hit = self._nearest(lat, lon, cls)
            if hit:
                hit.last_seen = when
                hit.times_seen += 1
                hit.consecutive_misses = 0
                hit.status = PRESENT
                hit.best_confidence = max(hit.best_confidence, conf)
                
                surveys = json.loads(hit.surveys)
                if survey not in surveys:
                    surveys.append(survey)
                    hit.surveys = json.dumps(surveys)
                
                matched.add(hit.hazard_id)
            else:
                new_entry = RegistryEntry(
                    hazard_id=self._next_id(),
                    class_name=cls,
                    lat=lat,
                    lon=lon,
                    first_seen=when,
                    last_seen=when,
                    best_confidence=conf,
                    surveys=json.dumps([survey])
                )
                self.db.add(new_entry)
                self.db.flush()
                matched.add(new_entry.hazard_id)

        # anything covered by this survey but not matched counts as a miss
        all_live = self.db.query(RegistryEntry).filter(
            ~RegistryEntry.status.in_([GONE, RECOVERED])
        ).all()
        
        for e in all_live:
            if e.hazard_id in matched:
                continue
            if covered is not None and e.hazard_id not in covered:
                continue  # survey never went near it
            
            e.consecutive_misses += 1
            if e.class_name in IMMOVABLE:
                if e.status != UNCONFIRMED:
                    e.status = UNCONFIRMED
                    e.note = (f"missed {e.consecutive_misses}x, but a {e.class_name} "
                              f"cannot be recovered - treat as a detection miss "
                              f"and keep the position as a permanent snag hazard")
            elif e.consecutive_misses >= MISSES_TO_GONE:
                if e.status != GONE:
                    e.status = GONE
                    e.note = (f"not detected in {e.consecutive_misses} consecutive "
                              f"surveys - presumed recovered or moved")
            else:
                if e.status != UNCONFIRMED:
                    e.status = UNCONFIRMED
                    e.note = ("missed once; detector recall is 0.46, so a single "
                              "miss is not evidence of removal")

        self.db.commit()

    def mark_recovered(self, hazard_id: str, when: str | None = None) -> bool:
        e = self.db.query(RegistryEntry).filter(RegistryEntry.hazard_id == hazard_id).first()
        if e:
            e.status = RECOVERED
            e.note = f"recovered {when or date.today().isoformat()}"
            self.db.commit()
            return True
        return False
