SIH PS57 - side-scan sonar anomaly detection and recovery planning
=================================================================

THREE COMMANDS

Copy-paste these, from this demo/ folder. Plain `python` will not work - the system
Python is 3.14 and has no PyTorch wheels, so each command names the 3.11
environment explicitly.

  1. detection on a sonar image

     "C:\Users\aksha\sih-venv\Scripts\python.exe" pipeline.py --live

  2. which images to annotate next

     "C:\Users\aksha\sih-venv\Scripts\python.exe" demo_active.py

  3. the survey-to-survey layer - registry, retrieval times, heatmap, map

     "C:\Users\aksha\sih-venv\Scripts\python.exe" demo_planning.py

All three run on CPU. Only --enrich reaches the network. run.bat wraps
command 1 for double-clicking. On another machine, substitute your own
Python 3.11 with ultralytics and pyxtf installed - the dependency list is
requirements.txt at the repo root.

The model weights live in weights/ at the repo root, one level up from here.
Set SIH_WEIGHTS_DIR if you keep them somewhere else.


1. DETECTION            pipeline.py --live   (or double-click run.bat)

Two heads run on every image and their detections merge:

  wreck      shipwrecks, submerged aircraft     mAP50 0.625, precision 0.923
  ghostgear  derelict crab pots (ghost gear)    mAP50 0.310, precision 0.293

EVALUATION.md at the repo root breaks the ghostgear model down image by image
on its held-out split - where the misses are, how it behaves on empty seabed,
and why the confidence score cannot be used to rank detections for review.

Each detection gets a latitude/longitude, size in metres and confidence, and a
JSON + CSV report is written into reports/, plus a raw-vs-detected
comparison picture.

  ENTER at the prompt   random sample
  paste a path          specific image
  --range 13            realistic range for shallow-bay consumer sonar.
                        The 75 m default suits a towed survey and would report
                        a 1 m crab pot as 15 m.
  --altitude 2          height above the seabed. Defaults to 16% of --range,
                        which is where a towfish is actually flown. Range and
                        altitude together fix the ground swath, and the swath
                        is what turns a box in pixels into metres.

                        On an image file both are assumptions, so treat the
                        metres as indicative. On an XTF they are read from the
                        ping headers and the sizes are real - which is the
                        reason to demo with an XTF rather than a JPEG.
  --enrich              look up depth (GEBCO), species (OBIS) and port distance
                        for each detection, score its recovery priority and
                        estimate retrieval time. Needs a network. On an image
                        file the position is simulated and the output says so;
                        on an XTF file it is real.

BEST DEMO IMAGES
  samples/000346.jpg    shipwreck in sand ripples, 87%
  samples/000032.jpg    submerged aircraft
  samples/Rec14_wcp_ss_star_00012_...jpg   7 ghost pots  (use --range 13)


2. ANNOTATION PRIORITY  demo_active.py

Ranks unlabelled imagery by how much annotating it would teach the model -
cases near its decision boundary, cluttered scenes it cannot resolve, and busy
images where it found nothing. Labelling the top of that list moves the model
further than labelling ten times as many chosen at random. Needs no labels, so
it runs on raw survey imagery before anyone has looked at it.


3. SURVEY PLANNING      demo_planning.py

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
  xtf.py         reads raw XTF: imagery plus per-ping navigation
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


NAVIGATION

Give the pipeline an XTF file and positions are real, read from the ping
headers - towfish location, heading, altitude and slant range per ping.

Give it a PNG or JPG and there are no ping headers to read, so a plausible
survey track is attached instead. The geo-referencing maths is the same
implementation either way; only the positions feeding it differ, and every
report declares which it used.

enrich.py refuses to run on simulated coordinates by design - it would return
a genuine depth for a place the sonar never saw. On an XTF file it runs.


ENVIRONMENT

  C:\Users\aksha\sih-venv    Python 3.11 with torch, ultralytics and pyxtf

The system Python is 3.14 and has no PyTorch wheels, so plain `python` will
not work. run.bat points at the right one.
