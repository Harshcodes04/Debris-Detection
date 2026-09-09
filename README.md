# Marine Debris Detection from Side-Scan Sonar Imagery

Side-scan sonar produces long greyscale waterfall images of the seabed. Somewhere in them are tyres, oil drums, lost fishing gear and wrecks. This project finds them, puts a latitude and longitude on each one, works out how deep it is and how long it would take to recover, tracks what changes between surveys, and shows the result on an interactive map.

---

## The AI Pipeline: What happens to a file

1. **Read & Parse:** A `.xtf` survey file is parsed for its waterfall image *and* its per-ping navigation. Invalid navigation (e.g., projected metres) is gracefully ignored to prevent failures, while corrupt files are safely stopped with detailed logs. A `.png`/`.jpg` provides pixels only.
2. **Tile:** The image is cut into 640 px windows at 20% overlap. A survey line is a few hundred pixels wide and thousands of pings long; feeding it to the model whole squashes it to a square and destroys small targets.
3. **Detect (Dual-Head YOLOv8s):** Both YOLOv8s heads run over every tile. Bounding boxes are merged with Non-Maximum Suppression (NMS) within a single head, and then across heads via IoU (Intersection over Union) stitching so objects are not duplicated.
4. **Geo-reference:** Ground range is `sqrt(slant² - altitude²)`. The swath is mapped over the image width, and the across-track offset is applied as a bearing from the nearest ping's fix. On an XTF these numbers are read from the file.
5. **Enrich:** Detections are contextually enriched with depth from the GEBCO 2020 grid, species counts from OBIS, and transit times calculated from 29 Indian harbours.
6. **AI Risk Scoring & Recovery Planning:** The system assigns a risk score based on ecological harm, biodiversity, access, and certainty. It then generates an optimized eight-hour day plan packed by *risk per hour*.
7. **Registry Reconciliation:** Detections are matched against the permanent debris registry by position. The system tracks what is new, what is confirmed, and what has disappeared across multiple surveys.

---

## AI Models & Active Learning

Two **YOLOv8s** heads ship with this project, both trained via staged transfer learning because no single sonar dataset is large enough to train from scratch:

| Stage | Checkpoint | Trained on | mAP50 |
|-------|------------|------------|-------|
| 1 | `debris_fls_v1` | Marine Debris FLS (water tank) | 0.988 |
| 2 | `sidescan_v1` | SCTD wrecks and aircraft | 0.625 |
| 3 | `ghostgear_v1` | Ghost Pot side-scan | 0.310 |

*(Note: Stage 1's 0.988 is a baseline from a controlled water tank with clean backgrounds. It serves as a transfer starting point, not a field performance metric.)*

### Active Learning Uncertainty Queue
Annotation is the bottleneck in sonar object detection. To solve this, the platform features a built-in **Active Learning Pipeline** that automatically scans the database for unlabelled `.xtf` or `.jpg` imagery. 
It ranks images by how much annotating them would teach the model using the formula:
`0.60·boundary + 0.25·spread + 0.15·novelty`
This guarantees that analysts spend their limited time labelling borderline, confusing cases rather than confirming what the model already knows confidently.

### Performance & Validation
On the held-out ghost gear split, the pipeline runs at:
```
398 images, 567 targets
precision 0.416   recall 0.330   F1 0.368
```
Because bounding box confidence alone does not perfectly separate right from wrong in sonar, the model acts as a highly-efficient **candidate generator**. It narrows an analyst's search dramatically before final review. 

---

## System Architecture

```text
ml/                The detection package (YOLO, pipelines, geo-referencing)
weights/           The two trained YOLOv8s checkpoints (~22 MB each)
backend/           FastAPI service, SQLAlchemy (PostgreSQL), Celery worker
frontend/          Vite + React 18 + TypeScript, Leaflet maps
demo/              CLI scripts for local headless execution
requirements.txt   ML & Python dependencies
```

### The Output Contract
`ml/contract.py` is the single source of truth for everything the ML side hands the backend. It guarantees that the detection output (6 classes: `tyre`, `drum`, `net`, `plastic_debris`, `wreck`, `unidentified`) is strictly typed before the backend processes it. Clean PNGs are automatically generated and served directly to the frontend to ensure crisp rendering reliability across all browsers, bypassing XTF compatibility issues.

---

## Getting Started

### Full Stack Docker Deployment (Recommended)

First, create your environment file from the provided template:
```bash
cp .env.example .env
```
*(Open `.env` and fill in any required passwords or keys before proceeding).*

Then, bring up the entire stack (FastAPI backend, Celery worker, PostgreSQL database, Redis, and React frontend):
```bash
docker compose up -d --build
```
The first build pulls PyTorch and Node.js dependencies, taking ~10 minutes. 

The UI will automatically be available at **http://localhost:5200**. No manual `npm` commands are needed!

### Local Python Setup (Without Docker)
Requires **Python 3.11** specifically (PyTorch compatibility).
```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r backend/requirements.txt
```
Run the backend with SQLite (in-memory processing, no Celery):
```bash
set PYTHONPATH=.
uvicorn app.main:app --app-dir backend --reload
```

---

## API Capabilities

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/api/surveys/{id}/upload` | Upload `.xtf` or imagery to the Celery pipeline |
| GET    | `/api/jobs/{id}/image`     | Retrieve clean PNG rendering of the sonar processing |
| GET    | `/api/registry`            | Fetch all known tracking hazards |
| POST   | `/api/recovery/day-plan`   | Generate AI-optimized Operational Day Plan |
| POST   | `/api/active-learning/rank`| Rank database unlabelled imagery for annotation |

*(Interactive Swagger docs available at `/docs` when the backend is running).*

## Frontend
React 18, TypeScript, TanStack Query, Leaflet, Tailwind. Routes include `/detect`, `/hazards`, `/map`, `/recovery`, `/annotate`, and `/dashboard`.

The interactive map draws hazards over a risk grid. Clicking a hazard displays its tracking history, geo-coordinates, GEBCO depth, OBIS biodiversity metrics, nearest port distance, optimal recovery method, and the AI-calculated risk breakdown.
