"""Generate a fake side-scan waterfall image so the pipeline is runnable on day
one, before Neha's dataset lands and before Priyanshu's XTF reader exists.

    python -m ml.data.make_synthetic_sonar --out samples/synthetic_line_01.png

It reproduces the four features that matter for testing the plumbing:
  * a dark nadir (water column) band down the centre
  * intensity falling off with across-track range
  * bright targets on the seabed
  * an acoustic shadow trailing each target away from the towfish

This is test scaffolding, NOT training data. Never put it in the dataset.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def synthesize(height: int, width: int, n_targets: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centre = width / 2.0

    # Base seabed reverberation + speckle (multiplicative, as in real sonar).
    img = rng.gamma(shape=3.0, scale=18.0, size=(height, width))

    # Range falloff: bright near nadir, dark at the outer edge.
    across = np.abs(np.arange(width) - centre) / centre
    img *= (1.25 - 0.75 * across)[None, :]

    # Water column: no seabed return until the first bottom hit.
    nadir_px = int(width * 0.045)
    img[:, int(centre) - nadir_px : int(centre) + nadir_px] *= 0.12

    for _ in range(n_targets):
        y = int(rng.integers(40, height - 60))
        side = rng.choice([-1, 1])
        x = int(centre + side * rng.integers(nadir_px + 40, centre - 40))
        h = int(rng.integers(10, 26))
        w = int(rng.integers(10, 26))

        # Bright return.
        img[y : y + h, x : x + w] += rng.uniform(120, 210)

        # Acoustic shadow: away from the towfish, length grows with range.
        shadow = int(w * rng.uniform(1.5, 3.5))
        sx = x + w if side > 0 else x - shadow
        sx = max(0, min(sx, width - 1))
        img[y : y + h, sx : sx + shadow] *= 0.15

    img = np.clip(img, 0, None)
    lo, hi = np.percentile(img, [1, 99])
    return np.clip((img - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="samples/synthetic_line_01.png")
    ap.add_argument("--height", type=int, default=2400)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--targets", type=int, default=14)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    from PIL import Image

    arr = synthesize(args.height, args.width, args.targets, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(out)
    print(f"wrote {out}  ({arr.shape[1]}x{arr.shape[0]}, {args.targets} targets)")


if __name__ == "__main__":
    main()
