"""Which model heads exist, where their weights live, and how to load them.

Both the demo CLI and the backend need this, so it lives in the package rather
than in the demo script. One place decides a weights path or a threshold.

Weights are data, not code, so they sit in weights/ beside the package instead
of inside it. SIH_WEIGHTS_DIR overrides that for a container that mounts them
somewhere else.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_DIR = Path(os.getenv("SIH_WEIGHTS_DIR") or ROOT / "weights")

# Per-head confidence. Ghost gear runs lower because the model is less
# confident everywhere - a threshold sweep on the held-out test split put its
# best F1 at 0.20, where precision is 0.42 and recall 0.33. The wreck model is
# sharper and 0.25 is comfortable.
HEADS: dict[str, dict] = {
    "wreck": {"weights": WEIGHTS_DIR / "sidescan_model.pt", "conf": 0.25,
              "about": "shipwrecks, submerged aircraft"},
    "ghostgear": {"weights": WEIGHTS_DIR / "ghostgear_model.pt", "conf": 0.20,
                  "about": "derelict crab pots (ghost fishing gear)"},
}


def load_models(only: str | None = None) -> dict:
    """Load the detection heads. `only` restricts it to a single head.

    Missing weights raise here rather than later. A detector constructed with
    no weights falls back to mock detections, and mock output that reaches the
    backend looks exactly like real output - so the failure has to be loud at
    the point it happens.
    """
    from ultralytics import YOLO

    heads = {k: v for k, v in HEADS.items() if only is None or k == only}
    missing = [str(v["weights"]) for v in heads.values()
               if not Path(v["weights"]).exists()]
    if missing:
        raise FileNotFoundError(
            "model weights not found:\n  " + "\n  ".join(missing)
            + f"\nLooked in {WEIGHTS_DIR}. Set SIH_WEIGHTS_DIR to point elsewhere."
        )
    return {k: YOLO(str(v["weights"])) for k, v in heads.items()}
