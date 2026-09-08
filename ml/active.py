"""Active learning: decide which unlabelled images are worth annotating.

Annotation is the bottleneck in this problem - no public dataset pairs
side-scan sonar with debris labels, so every improvement costs analyst hours.
This module spends those hours where they buy the most.

The idea: a model already detects obvious wrecks confidently and empty seabed
confidently. Labelling more of either teaches it nothing. What teaches it is
the cases it is unsure about - the objects sitting near its decision boundary.
Rank unlabelled images by that uncertainty and an analyst labelling 50 of them
moves the model further than labelling 500 at random.

Three signals, combined:

    boundary   detections whose confidence sits near the threshold, where the
               model is genuinely undecided rather than wrong or right
    spread     several detections at middling confidence in one image - a
               cluttered scene the model cannot resolve
    novelty    nothing detected at all, but the image is not obviously empty -
               possible misses, which recall data cannot come from anywhere else

Head disagreement was tried and dropped. The two heads detect different objects,
so one firing without the other is the normal case, not an informative one - it
flagged every wreck image identically and discriminated nothing. Query-by-
committee needs models that answer the same question, and these do not.

Nothing here needs labels. That is the point: it runs on raw survey imagery
before anyone has looked at it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

# Confidence at which the model is maximally undecided. Detections here are
# worth far more than a 0.95 that only confirms what it already knows.
BOUNDARY = 0.30
BOUNDARY_WIDTH = 0.18      # how quickly informativeness falls away either side

SCAN_CONF = 0.05           # scan low: we want the uncertain ones, not the safe ones


@dataclass
class Candidate:
    path: str
    score: float
    n_detections: int
    max_confidence: float
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _boundary_value(conf: float) -> float:
    """How informative a detection at this confidence is. Peaks at BOUNDARY."""
    return math.exp(-((conf - BOUNDARY) ** 2) / (2 * BOUNDARY_WIDTH ** 2))


def _texture(path: str) -> float:
    """Rough busyness of an image, 0-1. Used only to separate 'nothing there
    because the seabed is featureless' from 'nothing detected in a scene with
    plenty going on' - the second is a likely miss and worth a look."""
    from PIL import Image

    a = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    if a.size == 0:
        return 0.0
    gx = np.abs(np.diff(a, axis=1)).mean()
    gy = np.abs(np.diff(a, axis=0)).mean()
    return float(min((gx + gy) / 40.0, 1.0))


def score_image(detections_per_head: dict[str, list[float]],
                path: str) -> Candidate:
    """Score one unlabelled image. `detections_per_head` maps head name to the
    confidences it produced."""
    all_conf = [c for v in detections_per_head.values() for c in v]
    reasons: list[str] = []

    # 1. boundary - the strongest single signal
    boundary = max((_boundary_value(c) for c in all_conf), default=0.0)
    if boundary > 0.6:
        near = [c for c in all_conf if abs(c - BOUNDARY) < 0.15]
        reasons.append(
            f"{len(near)} detection(s) near the decision boundary "
            f"({', '.join(f'{c:.2f}' for c in near[:3])})")

    # 2. spread - several middling detections means a scene it cannot resolve
    middling = [c for c in all_conf if 0.15 <= c <= 0.55]
    spread = min(len(middling) / 4.0, 1.0)
    if len(middling) >= 3:
        reasons.append(f"{len(middling)} detections at middling confidence - "
                       f"cluttered scene")

    # 3. nothing found in a busy scene: a candidate miss
    novelty = 0.0
    if not all_conf:
        t = _texture(path)
        if t > 0.35:
            novelty = t
            reasons.append(f"no detections despite busy seabed (texture {t:.2f}) "
                           f"- possible miss")

    score = 0.60 * boundary + 0.25 * spread + 0.15 * novelty

    return Candidate(
        path=path,
        score=round(score, 4),
        n_detections=len(all_conf),
        max_confidence=round(max(all_conf), 3) if all_conf else 0.0,
        reasons=reasons or ["confident and uncontested - little to learn here"],
    )


def rank_for_annotation(models: dict, images: list[str], top_k: int = 50,
                        conf: float = SCAN_CONF) -> list[Candidate]:
    """Rank unlabelled images by how much annotating them would teach the model.

    `models` maps head name to a loaded YOLO. Returns the top_k, most
    informative first - the order an analyst should work through.
    """
    out: list[Candidate] = []
    for path in images:
        per_head: dict[str, list[float]] = {}
        for name, model in models.items():
            r = model.predict(path, conf=conf, verbose=False)[0]
            per_head[name] = [float(b.conf) for b in r.boxes]
        out.append(score_image(per_head, path))

    out.sort(key=lambda c: c.score, reverse=True)
    return out[:top_k]


def annotation_budget_note(total: int, top_k: int) -> str:
    """The line worth putting in front of whoever is doing the labelling."""
    return (f"{top_k} of {total} images selected ({top_k/max(total,1):.0%}). "
            f"Labelling these first should move the model further than "
            f"labelling all {total} in arbitrary order, because the model "
            f"already agrees with itself on most of them.")
