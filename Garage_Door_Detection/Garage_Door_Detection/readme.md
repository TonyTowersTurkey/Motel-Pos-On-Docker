# Garage Door Detection

Local FastAPI application that collects camera snapshots, maps garage-door regions to rooms,
and provides the foundation for classifying each door as open, closed, or unknown.

## What Works Today

- UniFi camera import/edit/delete and room CRUD API.
- UniFi Protect camera discovery/import through the official integration API.
- Remote Protect JPEG snapshots, individually or for all enabled cameras.
- One-shot worker for cron or a systemd timer.
- Permanent, timestamped training archive under `media/camera_captures/`.
- Camera-image upload and browser-based ROI drawing.
- Automatic YOLO classification of every new room crop.
- Restart-safe inference jobs, detection history, and three-match state confirmation.
- SQLite locally, with SQLAlchemy support for PostgreSQL.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install uv==0.11.32
uv sync --locked --extra dev
cp .env.example .env
```

Production deployments should omit the development extra:

```bash
uv sync --locked
```

`uv.lock` records the complete cross-platform dependency graph and package hashes. Run
`uv lock --upgrade` intentionally when updating dependencies, then execute the full test suite
before committing the changed lock file.

Initialize or upgrade the database:

```bash
python -m app.db.init_db
```

Run the web server:

```bash
uvicorn app.main:app --reload
```

Open the dashboard at <http://127.0.0.1:8000> or API documentation at
<http://127.0.0.1:8000/docs>.

## Configure Remote UniFi Protect

The remote integration requires UniFi Console firmware 5.0.3 or later.

1. Sign in to UniFi Site Manager at <https://unifi.ui.com>.
2. Open **Settings → API Keys**, create an API key, and copy it immediately.
3. Obtain the console/host ID for the Protect console from Site Manager or the Site Manager API.
4. Put the API key in `.env`:

```dotenv
UNIFI_CONNECTION_MODE=remote
UNIFI_API_KEY=replace-with-api-key
UNIFI_REMOTE_BASE_URL=https://api.ui.com
UNIFI_SNAPSHOT_HIGH_QUALITY=true
UNIFI_TIMEOUT_SECONDS=15
```

Do not commit `.env`; it contains the API key.

Restart the web server after changing `.env`. On the dashboard:

1. Click **Protect Settings**, enter the console ID, and save it. The console ID is stored in the
   application database and overrides `UNIFI_CONSOLE_ID` from `.env`.
2. Click **Sync UniFi** to import and refresh the cameras attached to Protect.
3. Click **Capture All** to test one snapshot from every enabled imported camera.
4. Select a camera, add its rooms, and draw a garage-door ROI for each room.
5. In Camera Details, enable **Automatic snapshot every minute** for each camera that should be
   archived. The web server captures enabled cameras at every minute boundary while it is running.

Imported cameras retain their local room and ROI configuration when synchronized again. Sync only
adds cameras and refreshes their names/status; it does not delete cameras missing from Protect.

## Run Every Minute

One capture pass synchronizes the Protect camera inventory and downloads a JPEG for every enabled
UniFi camera:

```bash
python -m app.worker.detect_once
```

Example crontab entry:

```cron
* * * * * cd /path/to/Garage_Door_Detection && .venv/bin/python -m app.worker.detect_once >> /var/log/garage-door-capture.log 2>&1
```

Each successful capture creates a `camera_snapshots` database record and a timestamped image in
`media/camera_captures/camera_NNNN/YYYY/MM/DD/`. Images are never overwritten or automatically
deleted. Each JPEG has a JSON sidecar containing the camera identity and the room ROI coordinates
that were active when the image was captured. A failed request records the error on that camera
without replacing its last good image.

The archive defaults to the project filesystem. To keep it on a dedicated persistent disk, set an
absolute path in `.env` before starting the web server and worker:

```dotenv
CAMERA_CAPTURE_DIR=/path/to/persistent-disk/garage-door-training-images
```

The configured directory must remain inside `MEDIA_ROOT` so the dashboard can serve the images.
For an external disk, configure both paths:

```dotenv
MEDIA_ROOT=/path/to/persistent-disk/garage-door-media
CAMERA_CAPTURE_DIR=/path/to/persistent-disk/garage-door-media/camera_captures
```

Back up both the media directory and `local.db`; the database connects each archived image to its
camera and capture time.

## Generate ROI Training Crops

Each new Protect capture automatically creates one crop for every active room with a valid ROI.
To process the existing snapshot backlog, run:

```bash
python -m app.worker.generate_training_crops
```

The command is idempotent: crops that already match the room ROI are skipped. Crops are stored in
`media/training_crops/camera_NNNN/room_NNNN_PPPP/YYYY/MM/DD/`, and each crop is tracked in the
`training_crops` database table for the labeling interface. You can also trigger the same
batch through `POST /api/training/crops/generate`.

## Automatic Door Classification

The Docker image packages every model in `classificationModels/`. Select which packaged model to
use at runtime with `CLASSIFICATION_MODEL_PATH` in `.env`; changing the selection does not require
rebuilding the image. Classification models must have exactly two classes named `open` and
`closed`:

```dotenv
CLASSIFICATION_ENABLED=true
CLASSIFICATION_MODEL_PATH=classificationModels/garageclassify_v0.4_y11n_224.pt
CLASSIFICATION_CONFIDENCE_THRESHOLD=0.75
CLASSIFICATION_CONFIRMATION_COUNT=3
CLASSIFICATION_POLL_SECONDS=2
CLASSIFICATION_BATCH_SIZE=16
CLASSIFICATION_MAX_ATTEMPTS=3
```

Every new crop is committed with a persistent `inference_jobs` record. A background worker loads
the model once, processes queued crops in batches, and writes every successful prediction to
`detection_events`. Predictions below the confidence threshold become `unknown`. A room changes
its confirmed `current_state` only after three consecutive matching `open` or `closed` results;
an `unknown` result resets the matching streak without discarding the last confirmed state.
Manual labels in `training_crops.label` are never overwritten by model predictions.

On the Training page, each crop has two independent review dimensions. Door state supports Open,
Closed, Partial, Unsure, and Bad Image. Vehicle visibility supports Present, Absent, Not Observable,
and Unsure. Existing Open/Closed values remain in `training_crops.label` as door labels; the vehicle
fields are added empty so a migration never guesses whether a hidden vehicle was absent. A crop
remains in the default review queue until both dimensions are labeled, except Bad Image crops, which
do not require a vehicle label.

Saving or batch-approving a Closed door automatically records vehicle visibility as Not Observable.
Changing or undoing that door label clears the derived vehicle value. A vehicle value that an
operator manually corrected is preserved instead of being silently erased.

The latest door model prediction is shown with its confidence. Press Space to confirm an Open or
Closed suggestion. Door shortcuts are O, C, P, U, and B; vehicle shortcuts are V, N, X, and ?. Hold
Shift with O/C/P or V/N/X to apply that dimension to as many as eight chronological crops from the
same room. Undo clears only the dimension changed by the latest action. Independent door, vehicle,
preliminary-status, and room filters support focused review. Progress cards report door, vehicle,
fully labeled, and remaining-review totals.

Historical crops without a prediction are automatically queued as lower-priority backfill so new
minute-by-minute captures continue to be classified first.

The Batch Approval panel approves unlabeled Open or Closed predictions at or above a selected
confidence threshold, optionally for one room. It previews the affected counts and never approves
Unknown predictions. Each confirmed run records its threshold, room filter, model version,
timestamp, and affected crops. The latest batch can be undone without erasing labels that were
manually corrected afterward.

The Dashboard requests fresh room states every 15 seconds. Failed jobs are retried up to the
configured attempt limit and remain in the database with their error message for troubleshooting.

## Export a Curated Classification Dataset

The Training page builds versioned, downloadable ZIPs under `media/dataset_exports/` in four modes:

- **Door state:** conventional Open, Closed, and Partial class folders.
- **Vehicle presence:** conventional Present and Absent class folders.
- **Both separate:** both folder datasets in one ZIP with shared camera/time split assignments.
- **Multi-task:** each image is written once and `manifest.csv` supplies both targets plus validity
  flags for masking either training loss.

Unsure and Bad Image are excluded as door targets. Not Observable and Unsure are excluded as
vehicle classes; in multi-task mode their vehicle validity flag is false. This avoids teaching the
model that a hidden vehicle is absent.
The curation controls prioritize corrected model mistakes, low-confidence or small-margin predictions, and
automatically detected dark, glare, or blurry images. A configurable deterministic percentage of
routine images is retained so ordinary production conditions remain represented without allowing
near-identical minute-by-minute captures to dominate the dataset.

Door and vehicle targets have independent balance sliders. A 40% minimum-to-largest ratio limits
each larger class to 2.5 times the smallest available class. Informative examples are retained before
routine images. Classes with no reviewed images are ignored until examples exist. Set a slider to
0% to disable balancing for that task. Fixed test images are never
downsampled.

Use **Captured from** and **Captured through** to limit an export to an inclusive UTC capture-date
range. The filter is applied before duplicate removal, sampling, balancing, and split assignment.
When a range is active, only fixed benchmark images inside that range appear in the ZIP; the saved
benchmark definition itself remains unchanged.

Exact duplicates are removed globally. Perceptual hashing also removes visually similar images from
the same camera, room, label, and configurable time window unless the scene changed significantly.
Byte-identical images carrying conflicting labels are excluded and reported. Single-task ZIPs use
the common image-folder layout:

```text
train/open/
train/closed/
train/partial/
val/open/
val/closed/
test/open/
test/closed/
```

Separate mode prefixes that layout with `door/` and `vehicle/`. Multi-task mode uses
`<split>/images/`. Every ZIP includes `manifest.csv`, class files, `dataset.json`, and a README. The
manifest records both reviewed labels and validity flags along with camera and door IDs, timestamps,
preliminary predictions and probabilities, model versions, selection reasons, edge-case signals,
and image hashes.

Each export mode has a persistent benchmark file under `media/dataset_exports/`. It stores fixed test
crop IDs and camera/hour groups. Later exports in that mode reuse those exact test images and prevent
new images from entering the test split. Back up these files with `local.db` and the media directory.

## Room Pulse Webhook

Use the **Room Pulse** tab to relay all active room states to another system in one JSON request.
Configure the destination URL, heartbeat interval, state-change delivery, optional Bearer token,
request timeout, and public app URL for crop links. The worker can send immediately after a
confirmed state change and periodically as a heartbeat. Each request has a unique event ID, retries
up to three times, and appears in the Pulse Trail delivery history. The saved token is never returned
by the configuration API.

## Local Protect Mode (Later)

The provider already has a local connection mode. Once the application runs on the same network as
Protect, update `.env` and restart the worker/web server:

```dotenv
UNIFI_CONNECTION_MODE=local
UNIFI_LOCAL_BASE_URL=https://192.168.1.10/proxy/protect/integration
UNIFI_LOCAL_API_KEY=replace-with-local-key
UNIFI_VERIFY_SSL=false
```

Use certificate verification in production when the console has a trusted certificate. The remote
and local modes share the same camera sync, capture, database, and storage code.

## Other Snapshot Sources

The standalone helper still supports an RTSP URL, a video file, or a directory of MP4 files:

```bash
scripts/snapshot_every_minute.sh rtsp://user:pass@192.168.1.120/stream media/manual_snapshots 60
```
