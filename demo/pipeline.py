"""SIH PS57 — side-scan sonar anomaly detection pipeline.

    sonar image -> two detection heads -> merged detections
                -> geo-referencing -> JSON/CSV anomaly report

    python pipeline.py                       # random sample
    python pipeline.py path/to/image.jpg
    python pipeline.py --live                # models stay loaded
    python pipeline.py --only ghostgear      # one head instead of both

Two heads, one sensor. They detect different things, so they run together and
their detections merge:

    wreck      shipwrecks, submerged aircraft   large anomalies
    ghostgear  derelict crab pots               ghost fishing gear

Both are side-scan models, so there is no sensor routing - every image goes
through both.

NAVIGATION IS SIMULATED. There is no raw XTF here, so a plausible survey track
is attached. The geo-referencing maths is the real implementation; every report
declares its navigation source.
"""

import argparse
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from ml.pipeline import HEADS, load_models                    # noqa: E402
from ml.interfaces import SonarImage, ReferencePostProcessor  # noqa: E402
from ml.survey import attach_track                            # noqa: E402
from ml.report import build_report, write_json, write_csv     # noqa: E402
from ml.enrich import enrich_detection, to_dict as ctx_dict   # noqa: E402
from ml.risk import score_detection, to_dict as risk_dict     # noqa: E402

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
SURVEY_SUFFIXES = {".xtf"}          # raw survey files carry their own navigation
READABLE = IMAGE_SUFFIXES | SURVEY_SUFFIXES


def resolve_image(raw: str) -> Path | None:
    """Turn whatever the user typed into a single image path."""
    path = Path(raw)
    if not path.exists():
        print(f"  no such path: {path}")
        return None
    if path.is_dir():
        found = [f for f in sorted(path.iterdir())
                 if f.suffix.lower() in READABLE]
        if not found:
            print(f"  no images in that folder: {path}")
            return None
        pick = random.choice(found)
        print(f"  (folder given - picked {pick.name} from {len(found)} images)")
        return pick
    if path.suffix.lower() not in READABLE:
        print(f"  not a sonar image or survey file: {path.name}")
        return None
    return path


def _before_after(original: Path, annotated: Path, out: Path, n: int) -> Path:
    """Raw sonar on the left, detections on the right."""
    from PIL import Image, ImageDraw

    a = Image.open(original).convert("RGB")
    b = Image.open(annotated).convert("RGB")
    h = 620
    a = a.resize((int(a.width * h / a.height), h))
    b = b.resize((int(b.width * h / b.height), h))

    pad, bar = 16, 46
    canvas = Image.new("RGB", (a.width + b.width + pad * 3, h + bar + pad * 2), "#111318")
    canvas.paste(a, (pad, bar + pad))
    canvas.paste(b, (pad * 2 + a.width, bar + pad))

    d = ImageDraw.Draw(canvas)
    d.text((pad + 4, 16), "RAW SONAR", fill="#8b93a7")
    label = f"DETECTED  ({n} anomal{'y' if n == 1 else 'ies'})"
    d.text((pad * 2 + a.width + 4, 16), label, fill="#4ade80" if n else "#8b93a7")
    canvas.save(out, quality=92)
    return out


def process(image_path: Path, models, survey="DEMO-LINE-01",
            conf_override=None, show=True, slant_range_m=75.0, altitude_m=None,
            enrich=False) -> dict:
    import numpy as np
    from PIL import Image, ImageDraw

    line = None
    if image_path.suffix.lower() in SURVEY_SUFFIXES:
        from ml.xtf import read_xtf

        line = read_xtf(image_path)
        sonar = line.sonar
        # The detector and the overlay both read a file from disk, so the
        # waterfall this survey builds is written out once and used as the
        # image from here on.
        rendered = HERE / "reports"
        rendered.mkdir(exist_ok=True)
        image_path = rendered / f"{sonar.image_id}_waterfall.png"
        Image.fromarray(sonar.image).save(image_path)
    else:
        arr = np.array(Image.open(image_path).convert("L"), dtype=np.uint8)
        sonar = SonarImage(image=arr, image_id=image_path.stem)

    # --- run every head ---------------------------------------------------
    detections, per_head, total_ms = [], {}, 0.0
    for name, model in models.items():
        conf = conf_override if conf_override is not None else HEADS[name]["conf"]
        t0 = time.perf_counter()
        r = model.predict(str(image_path), conf=conf, verbose=False)[0]
        total_ms += (time.perf_counter() - t0) * 1000
        per_head[name] = len(r.boxes)
        for b in r.boxes:
            x1, y1, x2, y2 = [float(v) for v in b.xyxy[0]]
            detections.append({
                "class": r.names[int(b.cls)],
                "confidence": round(float(b.conf), 4),
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "head": name,
            })

    # --- pixels -> coordinates -------------------------------------------
    # Object size in metres falls straight out of the assumed swath, so the
    # range has to match the imagery. 75 m per channel suits a towed survey;
    # the ghost-pot imagery is shallow-bay consumer sonar where ~13 m is
    # realistic, and using the wrong one reports a 1 m crab pot as 15 m.
    if line is not None:
        # The file carries its own track, its own slant range and its own
        # altitude. --range and --altitude are assumptions for imagery that has
        # none, and applying them here would replace measurements with guesses.
        navigation_is_real = True
        nav_source = (f"REAL - XTF ping headers: {line.n_fixes} fixes, "
                      f"{line.interpolated} interpolated, {line.dropped} rejected")
    else:
        attach_track(sonar, slant_range_m=slant_range_m, altitude_m=altitude_m)
        navigation_is_real = False
        nav_source = "SIMULATED survey track (no raw XTF available)"
    detections = ReferencePostProcessor().georeference(detections, sonar)

    # --- context and recovery priority (optional) -------------------------
    # enrich_detection refuses simulated coordinates, because a real depth for
    # a place the sonar never saw is worse than no depth at all. Passing
    # navigation_is_real here is a demonstration of the capability, and every
    # enriched field below is printed and stored as UNVERIFIED so the
    # distinction survives into the report.
    if enrich:
        for det in detections:
            ctx = enrich_detection(det.get("lat"), det.get("lon"),
                                   navigation_is_real=navigation_is_real)
            det["context"] = ctx_dict(ctx)
            det["risk"] = risk_dict(
                score_detection(det["class"], det["confidence"], ctx))
            if det["context"]:
                det["context"]["position_source"] = (
                    "REAL - read from the survey file's ping headers"
                    if navigation_is_real else
                    "SIMULATED - these lookups are real but the coordinate "
                    "they were made at is not")

    result = {
        "image_id": sonar.image_id,
        "width": sonar.width,
        "height": sonar.height,
        "processing_ms": int(total_ms),
        "detections": detections,
        "overlay_path": None,
    }
    report = build_report(
        result, survey_name=survey,
        navigation_source=nav_source,
        model_version="+".join(models),
    )

    # --- draw -------------------------------------------------------------
    OUT = HERE / "reports"
    OUT.mkdir(exist_ok=True)
    stem = f"report_{sonar.image_id}"
    write_json(report, OUT / f"{stem}.json")
    write_csv(report, OUT / f"{stem}.csv")

    colour = {"wreck": "#38bdf8", "ghostgear": "#f472b6"}
    im = Image.open(image_path).convert("RGB")
    d = ImageDraw.Draw(im)
    for det in detections:
        x, y, w, h = det["bbox"]
        c = colour.get(det["head"], "#4ade80")
        d.rectangle([x, y, x + w, y + h], outline=c, width=3)
        d.text((x + 3, max(0, y - 12)),
               f"{det['class']} {det['confidence']:.2f}", fill=c)
    im.save(OUT / f"{stem}.jpg", quality=92)
    _before_after(image_path, OUT / f"{stem}.jpg",
                  OUT / f"{stem}_compare.jpg", len(detections))

    # --- print ------------------------------------------------------------
    print(f"  image    {image_path.name}   {sonar.width} x {sonar.height} px")
    heads_str = "   ".join(f"{k}:{v}" for k, v in per_head.items())
    print(f"  heads    {heads_str}")
    print(f"  swath    {sonar.meta['swath_m']} m across track")
    print(f"  time     {total_ms:.0f} ms")
    print()
    if not detections:
        print("  no anomalies above threshold")
    else:
        print(f"  {len(detections)} anomaly(ies), "
              f"{report['summary']['geotagged']} geotagged:")
        print(f"    {'CLASS':<14}{'HEAD':<11}{'CONF':>7}"
              f"{'LATITUDE':>13}{'LONGITUDE':>13}{'LEN(m)':>9}")
        for a, det in zip(report["anomalies"], detections):
            print(f"    {a['classification']:<14}{det['head']:<11}"
                  f"{a['confidence_pct']:>6.1f}%"
                  f"{a['latitude']:>13.6f}{a['longitude']:>13.6f}"
                  f"{a['dimensions_m']['length']:>9.2f}")
    if enrich and detections:
        print()
        print("  CONTEXT AND RECOVERY PRIORITY")
        print("  (lookups are live; the coordinate they were made at is simulated)")
        for det in detections:
            c, r = det.get("context"), det.get("risk")
            if not c:
                continue
            depth = f"{c['depth_m']:.0f} m" if c["depth_m"] is not None else "unknown"
            bio = c.get("biodiversity") or {}
            port = c.get("nearest_port") or {}
            print(f"    {det['class']:<12} risk {r['band']:<7} {r['score']:.2f}")
            print(f"       depth {depth}"
                  + ("  diver range" if c.get("diveable") else "  ROV")
                  + f",  {bio.get('species', '?')} species within 5 km")
            if port:
                print(f"       {port['distance_km']} km from {port['port']}, "
                      f"{port['transit_hours']} h transit")
            print(f"       {r['reasons'][0]}")

    print()
    print(f"  wrote reports/{stem}.json / .csv / .jpg / _compare.jpg")

    if show:
        import os
        os.startfile(OUT / f"{stem}_compare.jpg")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="SIH PS57 side-scan anomaly pipeline")
    ap.add_argument("image", nargs="?")
    ap.add_argument("--only", choices=list(HEADS), default=None,
                    help="run a single head instead of both")
    ap.add_argument("--conf", type=float, default=None,
                    help="override the per-head confidence threshold")
    ap.add_argument("--altitude", type=float, default=None, dest="altitude_m",
                    help="height of the sonar above the seabed, metres. "
                         "Defaults to 16%% of --range, the usual towing height. "
                         "Set it when you know it: with --range it decides the "
                         "ground swath, and the swath decides reported sizes.")
    ap.add_argument("--survey", default="DEMO-LINE-01")
    ap.add_argument("--range", type=float, default=75.0, dest="slant_range",
                    help="sonar slant range per channel, metres. Sets the "
                         "swath and therefore reported object sizes. "
                         "75 = towed survey; 13 = shallow-bay consumer sonar")
    ap.add_argument("--live", action="store_true",
                    help="keep models loaded and process image after image")
    ap.add_argument("--no-show", action="store_true")
    ap.add_argument("--enrich", action="store_true",
                    help="look up depth, biodiversity and port distance for each "
                         "detection and score its recovery priority. Lookups are "
                         "live; the position is simulated, and the output says so")
    args = ap.parse_args()

    for name, h in HEADS.items():
        if (args.only is None or args.only == name) and not h["weights"].exists():
            print(f"Missing model: {h['weights']}")
            return 1

    print("loading models ...")
    models = load_models(args.only)
    for name in models:
        print(f"   {name:<11} {HEADS[name]['about']}")

    pool = sorted(HERE.glob("samples/*.jpg"))
    if pool:
        for m in models.values():
            m.predict(str(pool[0]), verbose=False)   # warm up
    print("ready\n")

    show = not args.no_show
    if not args.live:
        image = resolve_image(args.image) if args.image else random.choice(pool)
        if image is None:
            return 1
        process(image, models, args.survey, args.conf, show,
                args.slant_range, args.altitude_m, args.enrich)
        return 0

    print("  ENTER      random image      <path>   specific image      q   quit\n")
    while True:
        try:
            line = input("> ").strip().strip('"')
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line.lower() in {"q", "quit", "exit"}:
            return 0
        image = resolve_image(line) if line else random.choice(pool)
        if image is None:
            continue
        process(image, models, args.survey, args.conf, show,
                args.slant_range, args.altitude_m, args.enrich)
        print()


if __name__ == "__main__":
    sys.exit(main())
