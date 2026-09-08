"""Active learning: which unlabelled images are worth an analyst's time.

    python demo_active.py [folder] [--top 10]

Annotation is the bottleneck in this problem - no public dataset pairs
side-scan sonar with debris labels, so every improvement costs analyst hours.
This ranks raw imagery by how much labelling it would teach the model, so those
hours go where they buy the most.

Needs no labels. It runs on survey imagery before anyone has looked at it.
"""

import argparse
import glob
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from ml.pipeline import load_models                                # noqa: E402
from ml.active import rank_for_annotation, annotation_budget_note  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank imagery by annotation value")
    ap.add_argument("folder", nargs="?", default=str(HERE / "samples"),
                    help="folder of unlabelled images (default: samples/)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--limit", type=int, default=60,
                    help="how many images to scan")
    args = ap.parse_args()

    images = (sorted(glob.glob(os.path.join(args.folder, "*.jpg")))
              + sorted(glob.glob(os.path.join(args.folder, "*.png"))))[:args.limit]
    if not images:
        print(f"no images in {args.folder}")
        return 1

    print(f"scanning {len(images)} unlabelled images ...")
    models = load_models()

    ranked = rank_for_annotation(models, images, top_k=len(images))
    top = ranked[:args.top]

    print()
    print(annotation_budget_note(len(images), len(top)))
    print()
    print("LABEL THESE FIRST")
    print("-" * 60)
    for i, c in enumerate(top, 1):
        print(f"{i:2d}. {c.score:.3f}  {os.path.basename(c.path)[:44]}")
        print(f"        {c.n_detections} detections, best {c.max_confidence:.2f}")
        for r in c.reasons:
            print(f"        {r}")

    print()
    print("SKIP THESE - the model is already sure")
    print("-" * 60)
    for c in ranked[-3:]:
        print(f"    {c.score:.3f}  {os.path.basename(c.path)[:44]}")

    print()
    print("The model is confident about most of this imagery, so labelling it")
    print("teaches nothing. The value is in the cases it cannot resolve.")
    print("After labelling, retrain and re-rank - what it finds hard changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
