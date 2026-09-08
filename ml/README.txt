SIH PS57 - side-scan sonar anomaly detection and recovery planning
=================================================================

TWO COMMANDS

Copy-paste these, from this folder. Plain `python` will not work - the system
Python is 3.14 and has no PyTorch wheels, so each command names the 3.11
environment explicitly.

  1. detection on a sonar image

     "C:\Users\aksha\sih-venv\Scripts\python.exe" pipeline.py --live

  2. the survey-to-survey layer - registry, retrieval times, heatmap, map

     "C:\Users\aksha\sih-venv\Scripts\python.exe" demo_planning.py

Both run on CPU with no internet. run.bat wraps command 1 for
double-clicking. On another machine, substitute your own Python 3.11 with
ultralytics installed.


1. DETECTION            pipeline.py --live   (or double-click run.bat)

Two heads run on every image and their detections merge:

  wreck      shipwrecks, submerged aircraft     mAP50 0.625, precision 0.923
  ghostgear  derelict crab pots (ghost gear)    mAP50 0.310, precision 0.293

Each detection gets a latitude/longitude, size in metres and confidence, and a
JSON + CSV report is written into reports/, plus a raw-vs-detected
comparison picture.

  ENTER at the prompt   random sample
  paste a path          specific image
  --range 13            realistic swath for shallow-bay consumer sonar.
                        The 75 m default suits a towed survey and would report
                        a 1 m crab pot as 15 m.

BEST DEMO IMAGES
  samples/000346.jpg    shipwreck in sand ripples, 87%
  samples/000032.jpg    submerged aircraft
  samples/Rec14_wcp_ss_star_00012_...jpg   7 ghost pots  (use --range 13)


2. SURVEY PLANNING      demo_planning.py

Simulates three surveys of one area over nine months and shows:

  - which hazards are new, which are still there, which have stopped appearing
  - what has been sitting uncollected for months
  - retrieval time per hazard, and whether to send a diver or an ROV
  - a working day packed by risk per hour
  - a risk heatmap

Writes risk_heatmap.geojson (opens in QGIS or geojson.io) and survey_map.html
(self-contained, double-click).


WHAT IS IN ml/

  contract.py    frozen output schema the backend builds against
  detector.py    model loading, isolates .pt vs .onnx
  interfaces.py  preprocessing/postprocessing seams, geo-referencing
  survey.py      navigation - real from XTF, or a simulated track
  report.py      JSON and CSV anomaly reports
  router.py      sensor detection (side-scan vs forward-looking)
  enrich.py      depth from GEBCO, species from OBIS, port distance and ETA
  risk.py        recovery priority, with its reasoning
  registry.py    hazards tracked across repeat surveys
  recovery.py    retrieval time, diver vs ROV, day planning
  heatmap.py     risk grid as GeoJSON
  mapview.py     standalone HTML map, no server or network
  active.py      ranks unlabelled imagery by annotation value


NAVIGATION IS SIMULATED

There is no raw XTF file here, so a plausible survey track is attached. The
geo-referencing maths is the real implementation, and every report declares
its navigation source.

enrich.py refuses to run on simulated coordinates by design - it would return
a genuine depth for a place the sonar never saw.

Reading navigation from XTF ping headers unlocks the enrichment, the registry
matching, the heatmap and the recovery planning. One dependency, four features.


ENVIRONMENT

  C:\Users\aksha\sih-venv    Python 3.11 with torch and ultralytics

The system Python is 3.14 and has no PyTorch wheels, so plain `python` will
not work. run.bat points at the right one.
