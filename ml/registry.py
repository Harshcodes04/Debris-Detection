"""Persistent debris registry: what is out there, and what changed since last time.

A single survey answers "what is on the seabed today". A cleanup programme
needs more than that:

    - which of these did we already know about?
    - which are new since the last survey?
    - did the ones we sent a crew to recover actually get removed?
    - what has been sitting there for two years that nobody has collected?

That is bookkeeping across surveys, not detection. This module keeps a registry
of known hazards and reconciles each new survey against it.

Matching is by position, with a tolerance, because the same object never
reports the identical coordinate twice - navigation drifts, the tow path
differs, the box lands a few pixels elsewhere. MATCH_RADIUS_M is that
tolerance, and it should be set from the survey's own positional accuracy
rather than left at the default.

An important asymmetry: not detecting something is weak evidence. A pot missed
because the tow line passed further away is indistinguishable from a pot that
was recovered. So a single miss marks an entry UNCONFIRMED, and only repeated
misses across separate surveys mark it GONE. Recall is 0.46 - one miss means
almost nothing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path

MATCH_RADIUS_M = 25.0        # positional tolerance when matching to the registry
MISSES_TO_GONE = 2           # consecutive surveys missing before presumed removed

# Classes a cleanup crew cannot remove. If one of these stops appearing it is
# a detection miss, not a recovery - a shipwreck does not leave. Marking them
# GONE would quietly delete real, permanent snag hazards from the registry.
IMMOVABLE = {"ship", "wreck", "aircraft"}

PRESENT = "present"          # seen in the most recent survey covering it
UNCONFIRMED = "unconfirmed"  # missed once - could be a miss, could be gone
GONE = "gone"                # missed repeatedly, presumed recovered or shifted
RECOVERED = "recovered"      # a crew reported recovering it - authoritative


@dataclass
class Entry:
    hazard_id: str
    cls: str
    lat: float
    lon: float
    first_seen: str
    last_seen: str
    times_seen: int = 1
    consecutive_misses: int = 0
    status: str = PRESENT
    best_confidence: float = 0.0
    surveys: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def age_days(self) -> int:
        return (date.fromisoformat(self.last_seen)
                - date.fromisoformat(self.first_seen)).days


@dataclass
class Reconciliation:
    """What one survey changed."""
    survey: str
    new: list[Entry] = field(default_factory=list)
    still_present: list[Entry] = field(default_factory=list)
    newly_unconfirmed: list[Entry] = field(default_factory=list)
    newly_gone: list[Entry] = field(default_factory=list)

    def summary(self) -> str:
        return (f"{self.survey}: {len(self.new)} new, "
                f"{len(self.still_present)} still present, "
                f"{len(self.newly_unconfirmed)} unconfirmed, "
                f"{len(self.newly_gone)} presumed removed")


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6_371_008.8
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


class Registry:
    """Known hazards, persisted as JSON between surveys."""

    def __init__(self, path: str | Path = "registry.json"):
        self.path = Path(path)
        self.entries: list[Entry] = []
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = [Entry(**e) for e in raw.get("entries", [])]

    def save(self) -> None:
        self.path.write_text(
            json.dumps({"entries": [asdict(e) for e in self.entries]}, indent=2),
            encoding="utf-8")

    def _next_id(self) -> str:
        return f"HZ-{len(self.entries) + 1:05d}"

    def _nearest(self, lat: float, lon: float, cls: str) -> Entry | None:
        """Closest registry entry of the same class within the tolerance.

        Class must match: a crab pot and a wreck at the same spot are two
        hazards, not one object that changed identity.
        """
        best, best_d = None, MATCH_RADIUS_M
        for e in self.entries:
            if e.cls != cls or e.status == RECOVERED:
                continue
            d = haversine_m((lat, lon), (e.lat, e.lon))
            if d < best_d:
                best, best_d = e, d
        return best

    def reconcile(self, detections: list[dict], survey: str,
                  when: str | None = None,
                  covered: list[str] | None = None) -> Reconciliation:
        """Fold one survey's detections into the registry.

        `covered` optionally lists hazard_ids the survey actually passed over.
        Without it, every entry is treated as covered, which will mark hazards
        outside the survey area as missed - so pass it whenever the survey
        footprint is known.
        """
        when = when or date.today().isoformat()
        result = Reconciliation(survey=survey)
        matched: set[str] = set()

        for d in detections:
            lat, lon = d.get("lat"), d.get("lon")
            if lat is None or lon is None:
                continue                      # ungeotagged cannot be tracked
            cls = d.get("class", "unidentified")
            conf = float(d.get("confidence", 0.0))

            hit = self._nearest(lat, lon, cls)
            if hit:
                hit.last_seen = when
                hit.times_seen += 1
                hit.consecutive_misses = 0
                hit.status = PRESENT
                hit.best_confidence = max(hit.best_confidence, conf)
                if survey not in hit.surveys:
                    hit.surveys.append(survey)
                matched.add(hit.hazard_id)
                result.still_present.append(hit)
            else:
                e = Entry(hazard_id=self._next_id(), cls=cls, lat=lat, lon=lon,
                          first_seen=when, last_seen=when, best_confidence=conf,
                          surveys=[survey])
                self.entries.append(e)
                matched.add(e.hazard_id)
                result.new.append(e)

        # anything covered by this survey but not matched counts as a miss
        for e in self.entries:
            if e.hazard_id in matched or e.status in (GONE, RECOVERED):
                continue
            if covered is not None and e.hazard_id not in covered:
                continue                      # survey never went near it
            e.consecutive_misses += 1
            if e.cls in IMMOVABLE:
                # cannot have been removed, so this is the detector missing it
                if e.status != UNCONFIRMED:
                    e.status = UNCONFIRMED
                    e.note = (f"missed {e.consecutive_misses}x, but a {e.cls} "
                              f"cannot be recovered - treat as a detection miss "
                              f"and keep the position as a permanent snag hazard")
                    result.newly_unconfirmed.append(e)
            elif e.consecutive_misses >= MISSES_TO_GONE:
                if e.status != GONE:
                    e.status = GONE
                    e.note = (f"not detected in {e.consecutive_misses} consecutive "
                              f"surveys - presumed recovered or moved")
                    result.newly_gone.append(e)
            else:
                if e.status != UNCONFIRMED:
                    e.status = UNCONFIRMED
                    e.note = ("missed once; detector recall is 0.46, so a single "
                              "miss is not evidence of removal")
                    result.newly_unconfirmed.append(e)

        return result

    def mark_recovered(self, hazard_id: str, when: str | None = None) -> bool:
        """A crew reported recovering this. Authoritative - beats detection."""
        for e in self.entries:
            if e.hazard_id == hazard_id:
                e.status = RECOVERED
                e.note = f"recovered {when or date.today().isoformat()}"
                return True
        return False

    def outstanding(self) -> list[Entry]:
        """Still out there, oldest first - the backlog nobody has collected."""
        live = [e for e in self.entries if e.status in (PRESENT, UNCONFIRMED)]
        return sorted(live, key=lambda e: e.first_seen)

    def persistent(self, min_surveys: int = 2) -> list[Entry]:
        """Seen across several surveys - confirmed real, and still uncollected."""
        return [e for e in self.outstanding() if e.times_seen >= min_surveys]
