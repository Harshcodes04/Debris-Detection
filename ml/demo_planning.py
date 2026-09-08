"""Demonstrates the survey-to-survey layer: registry, recovery planning, heatmap.

    python demo_planning.py

Simulates three surveys of the same area over nine months and shows what the
system knows at the end: what is new, what is still there, what has been sitting
uncollected, how long each item takes to recover, and where the risk concentrates.

Positions here are invented so the mechanism can be shown. With real navigation
these come from the pipeline's own output.
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from ml.registry import Registry                      # noqa: E402
from ml.recovery import plan_recovery, day_plan       # noqa: E402
from ml.heatmap import build, summary, write_geojson  # noqa: E402
from ml.risk import score_detection                   # noqa: E402
from ml.mapview import render                         # noqa: E402


def rule(title):
    print()
    print(title)
    print("-" * len(title))


def main():
    store = Path(tempfile.gettempdir()) / "sih_demo_registry.json"
    store.unlink(missing_ok=True)
    reg = Registry(store)

    surveys = [
        ("SURVEY-2026-01", "2026-01-15", [
            {"class": "crab_pot", "confidence": 0.44, "lat": 12.92310, "lon": 74.60120},
            {"class": "crab_pot", "confidence": 0.31, "lat": 12.92380, "lon": 74.60210},
            {"class": "crab_pot", "confidence": 0.36, "lat": 12.92660, "lon": 74.60560},
            {"class": "ship",     "confidence": 0.91, "lat": 12.92450, "lon": 74.60350},
        ]),
        # six months later: first pot still there (position drifts a few metres),
        # one new pot appears, one is no longer detected
        ("SURVEY-2026-06", "2026-06-15", [
            {"class": "crab_pot", "confidence": 0.52, "lat": 12.92312, "lon": 74.60123},
            {"class": "crab_pot", "confidence": 0.33, "lat": 12.92661, "lon": 74.60558},
            {"class": "crab_pot", "confidence": 0.28, "lat": 12.92600, "lon": 74.60500},
            {"class": "ship",     "confidence": 0.88, "lat": 12.92451, "lon": 74.60349},
        ]),
        ("SURVEY-2026-09", "2026-09-08", [
            {"class": "crab_pot", "confidence": 0.49, "lat": 12.92311, "lon": 74.60121},
            {"class": "crab_pot", "confidence": 0.30, "lat": 12.92662, "lon": 74.60559},
            {"class": "ship",     "confidence": 0.90, "lat": 12.92450, "lon": 74.60351},
        ]),
    ]

    rule("Three surveys of the same area")
    for name, when, dets in surveys:
        print("  " + reg.reconcile(dets, name, when=when).summary())
    reg.save()

    rule("What is still out there, oldest first")
    for e in reg.outstanding():
        months = e.age_days // 30
        age = f"{months} months" if months else "new this survey"
        print(f"  {e.hazard_id}  {e.cls:9s} {e.status:12s} "
              f"seen {e.times_seen}x   {age}")

    confirmed = reg.persistent()
    if confirmed:
        print()
        print(f"  Confirmed across multiple surveys and still uncollected: "
              f"{', '.join(e.hazard_id for e in confirmed)}")
        print("  These are the ones a crew should be sent to - repeated")
        print("  detection means they are real, and nobody has collected them.")

    rule("Retrieval estimates  (38 m water, 1.45 h from New Mangalore)")
    plans = []
    for e in reg.outstanding():
        p = plan_recovery(e.hazard_id, e.cls, depth_m=38.0,
                          transit_hours=1.45, age_days=e.age_days)
        risk = score_detection(e.cls, e.best_confidence, None)
        plans.append((p, risk.score))
        total = f"{p.total_hours} h" if p.total_hours else "n/a"
        print(f"  {p.hazard_id}  {p.method:24s} {total:>7}   risk {risk.score:.2f}")
        for n in p.notes:
            print(f"      {n}")

    rule("One working day, packed by risk per hour")
    d = day_plan(plans, hours_available=8.0)
    print(f"  {d['hours_planned']} h planned of {d['hours_available']} h, "
          f"{d['deferred']} deferred to another day")
    for it in d["items"]:
        print(f"    {it['hazard_id']}  {it['class']:9s} {it['method']:24s} "
              f"{it['hours']} h")
    print(f"  {d['note']}")

    rule("Risk heatmap")
    scores = {p.hazard_id: r for p, r in plans}
    cells = build(reg.entries, risk_scores=scores)
    print("  " + summary(cells))
    out = write_geojson(cells, HERE / "risk_heatmap.geojson")
    print(f"  wrote {out.name} - opens in QGIS, or geojson.io in a browser")

    page = render(reg.entries, cells, HERE / "survey_map.html",
                  title="Survey area - accumulated hazards, 3 surveys")
    print(f"  wrote {page.name} - self-contained, double-click to open")
    import os
    os.startfile(page)

    print()
    print("Note: positions here are invented to show the mechanism. Matching")
    print("hazards across surveys needs real navigation from XTF ping headers.")


if __name__ == "__main__":
    main()
