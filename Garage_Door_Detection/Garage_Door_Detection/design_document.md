# Lightweight Garage Door State Detection MVP Design

## 1. Project Goal

Build a lightweight local server that monitors IP camera snapshots and determines the state of motel garage doors.

The system should identify each garage door as:

* Open
* Closed
* Unknown

The MVP focuses on garage-door state detection. Later phases may infer room/car occupancy, integrate with motel POS, export reports, and publish data to Home Assistant or MQTT.

---

## 2. MVP Scope

### Included in MVP

* Support RTSP streams from ONVIF-compatible IP cameras
* Support UniFi and generic IP cameras
* Manage approximately 3 cameras
* Track approximately 15 garage doors
* One camera may view 4–10 garage doors
* Admin can configure cameras
* Admin can draw/set one square ROI per garage door
* Each ROI is linked to a room number
* System captures snapshots every minute
* System classifies each ROI as open, closed, or unknown
* Confirm state changes only after 3 consecutive matching detections
* Store detection logs in PostgreSQL
* Store current confirmed state per garage door
* Save uncertain cropped images for manual review/training
* Provide a simple web dashboard
* Provide a simple API for future motel POS integration

### Excluded from MVP

* User login
* Role permissions
* Manual state override
* Full video recording
* Long-term image snapshot storage
* SMB report export
* Motel POS integration
* Home Assistant/MQTT integration
* Automatic room-number OCR
* GPU acceleration

---

## 3. Recommended Lightweight Stack

Use a single Python application.

### Backend

* FastAPI

### Web UI

* Jinja2 templates
* Plain HTML/CSS
* Minimal JavaScript for ROI drawing

### Database

* PostgreSQL

### Database Access

* SQLAlchemy or SQLModel

### Computer Vision

* OpenCV

### Scheduled Detection

* APScheduler inside the FastAPI app
  or
* Separate Python worker launched by systemd timer

Recommended MVP choice: **separate worker with systemd timer**.

This keeps the web app and detection process separate and easier to debug.

### Deployment

* Proxmox LXC container
* Python virtual environment
* PostgreSQL installed locally or on another local server
* systemd services

---

## 4. High-Level Architecture

```text
IP Cameras / ONVIF / RTSP
        ↓
Snapshot Capture Worker
        ↓
Garage Door ROI Crop
        ↓
Classifier
        ↓
3-Consecutive-State Confirmation Logic
        ↓
PostgreSQL Database
        ↓
FastAPI Web UI + API
```

---

## 5. Main Components

## 5.1 FastAPI Web Server

The web server handles:

* Camera setup
* Room setup
* Garage-door ROI setup
* Dashboard display
* Uncertain image review
* API endpoints

It does not continuously process video. It only provides configuration, status display, and API access.

---

## 5.2 Detection Worker

The detection worker runs once per minute.

For each enabled camera:

1. Connect to RTSP stream.
2. Capture one current frame.
3. Save latest camera snapshot temporarily for GUI preview.
4. For each configured garage-door ROI on that camera:

   * Crop the garage door area.
   * Resize crop to classifier input size.
   * Run classifier.
   * Save raw detection result.
   * Check if the same state has appeared 3 times consecutively.
   * If yes, update confirmed garage-door state.
   * If confidence is low, save cropped image as an uncertain sample.

---

## 5.3 Database

PostgreSQL stores:

* Camera configuration
* Room list
* Garage-door ROI coordinates
* Detection history
* Current confirmed state
* Uncertain samples for review/training

---

## 6. Detection States

Allowed garage-door states:

```text
open
closed
unknown
```

### Meaning

* `open`: door appears fully open
* `closed`: door appears fully closed
* `unknown`: classifier could not determine state reliably

The system should prefer `unknown` over a low-confidence wrong answer.

---

## 7. State Confirmation Rule

A confirmed state change requires **3 consecutive matching detections**.

Example:

```text
10:00 detected open
10:01 detected open
10:02 detected open
→ confirmed state changes to open
```

This avoids false changes caused by glare, headlights, rain, blur, or temporary camera artifacts.

---

## 8. Web UI Requirements

## 8.1 Dashboard Page

Show one row per garage door:

* Room number
* Camera name
* Current confirmed state
* Last raw detected state
* Confidence
* Last detection time
* Last confirmed state change time
* Camera health/error status

Example:

```text
Room 101 | Camera Front-East | Closed | 94% | Last checked 12:30 PM
Room 102 | Camera Front-East | Open   | 91% | Last checked 12:30 PM
Room 103 | Camera Front-East | Unknown | 42% | Last checked 12:30 PM
```

---

## 8.2 Camera Setup Page

Admin can:

* Add camera name
* Add RTSP URL
* Add camera location
* Enable/disable camera
* Test snapshot capture
* View latest snapshot

Fields:

* camera name
* location
* RTSP URL
* enabled
* last successful frame time
* last error

---

## 8.3 Room Setup Page

Admin can:

* Add room number
* Mark room active/inactive
* Add optional description

Example:

```text
Room 101
Room 102
Room 103
```

---

## 8.4 ROI Setup Page

Admin can:

* Select a camera
* View the latest snapshot
* Draw a square box over each garage door
* Assign the box to a room
* Save ROI coordinates
* Preview the cropped garage-door image

ROI should be stored as:

```text
x
y
width
height
```

For MVP, use square bounding boxes only.

Polygon support can be added later.

---

## 8.5 Uncertain Review Page

Show cropped images that the classifier could not confidently classify.

Admin can label each uncertain sample as:

* Open
* Closed
* Unknown
* Bad sample

This review workflow is important because the real-world training data will come from the motel’s actual cameras.

---

## 9. Database Schema Draft

## 9.1 cameras

Stores camera configuration.

Fields:

```text
id
name
location
unifi_camera_id
enabled
last_snapshot_path
last_snapshot_at
last_error
created_at
updated_at
```

---

## 9.2 rooms

Stores motel room references.

Fields:

```text
id
room_number
description
active
created_at
updated_at
```

---

## 9.3 garage_doors

Stores one configured garage door per room.

Fields:

```text
id
room_id
camera_id
name
roi_x
roi_y
roi_width
roi_height
current_state
current_confidence
last_detected_state
last_detected_confidence
consecutive_state
consecutive_count
last_detection_at
last_confirmed_change_at
active
created_at
updated_at
```

---

## 9.4 detection_events

Stores every detection result.

Fields:

```text
id
garage_door_id
detected_state
confidence
confirmed_state_before
confirmed_state_after
was_confirmed_change
created_at
```

---

## 9.5 uncertain_samples

Stores cropped images that require human review.

Fields:

```text
id
garage_door_id
image_path
detected_state
confidence
reviewed_label
reviewed_at
created_at
```

---

## 10. File Storage

The system should not store full video.

The system may store:

```text
/app/data/latest_snapshots/
/app/data/uncertain_samples/
```

### latest_snapshots

Stores latest frame from each camera for web UI setup.

These files may be overwritten every minute.

### uncertain_samples

Stores cropped garage-door images that need review.

These are kept because they become training data.

---

## 11. API Requirements

The API prepares the system for later motel POS integration.

---

## 11.1 Get All Garage Door States

```http
GET /api/garage-doors
```

Example response:

```json
[
  {
    "room_number": "101",
    "state": "closed",
    "confidence": 0.94,
    "last_detection_at": "2026-06-26T12:30:00-04:00",
    "last_confirmed_change_at": "2026-06-26T11:42:00-04:00"
  },
  {
    "room_number": "102",
    "state": "open",
    "confidence": 0.91,
    "last_detection_at": "2026-06-26T12:30:00-04:00",
    "last_confirmed_change_at": "2026-06-26T12:10:00-04:00"
  }
]
```

---

## 11.2 Get Garage Door State by Room

```http
GET /api/rooms/{room_number}/garage-door
```

Example response:

```json
{
  "room_number": "101",
  "state": "closed",
  "confidence": 0.94,
  "last_detection_at": "2026-06-26T12:30:00-04:00",
  "last_confirmed_change_at": "2026-06-26T11:42:00-04:00"
}
```

---

## 11.3 Health Check

```http
GET /api/health
```

Example response:

```json
{
  "status": "ok",
  "database": "ok",
  "enabled_cameras": 3,
  "active_garage_doors": 15
}
```

---

## 12. Initial Classifier Strategy

The MVP should start with a lightweight classifier, not full object detection.

Reason:

* Cameras are fixed.
* ROIs are manually configured.
* Each ROI already isolates one garage door.
* The model only needs to classify a cropped image.

Recommended labels:

```text
open
closed
unknown
```

### First Phase

Start in data-collection mode:

1. Configure cameras.
2. Draw ROIs.
3. Save uncertain or periodic ROI crops.
4. Manually label images.
5. Train classifier using real camera images.

### Recommended First Training Target

Collect at least:

```text
100 closed samples
100 open samples
night samples
rain samples
headlight/glare samples
```

---

## 13. Error Handling

The system should handle:

* RTSP connection failure
* Camera offline
* Bad frame capture
* Missing ROI
* Classifier failure
* Database write failure

Camera errors should not automatically change garage-door state.

Example:

```text
If camera is offline, mark camera health as error.
Do not change room state to unknown unless the camera has been offline beyond a configured threshold.
```

---

## 14. Recommended Folder Structure

```text
garage-door-detector/
    app/
        main.py
        database.py
        models.py
        schemas.py
        routes/
            cameras.py
            rooms.py
            garage_doors.py
            api.py
        services/
            rtsp.py
            detection.py
            classifier.py
            state_confirmation.py
            storage.py
        templates/
            dashboard.html
            cameras.html
            roi_setup.html
            uncertain_review.html
        static/
            app.css
            roi_draw.js
    worker/
        run_detection.py
    migrations/
    data/
        latest_snapshots/
        uncertain_samples/
    scripts/
        install_service.sh
    requirements.txt
    README.md
```

---

## 15. Deployment Design

Target: Proxmox LXC container.

### Services

Run two systemd services:

```text
garage-door-web.service
garage-door-detection.timer
garage-door-detection.service
```

### Web Service

Runs FastAPI:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Detection Timer

Runs once per minute:

```text
python -m worker.run_detection
```

---

## 16. Suggested MVP Build Order

1. Create FastAPI project.
2. Connect to PostgreSQL.
3. Create database tables.
4. Add camera CRUD page.
5. Add room CRUD page.
6. Add latest snapshot capture.
7. Add ROI setup page.
8. Store garage-door ROI coordinates.
9. Build detection worker.
10. Add placeholder classifier.
11. Save raw detection events.
12. Add 3-consecutive confirmation logic.
13. Build dashboard.
14. Add uncertain-sample saving.
15. Add uncertain review page.
16. Add REST API.
17. Test with 3 cameras and 15 garage doors.

---

## 17. MVP Success Criteria

The MVP is successful if:

* It can connect to 3 RTSP cameras.
* Admin can draw ROIs for approximately 15 garage doors.
* The system checks each door every minute.
* The system stores raw detections.
* The system updates confirmed state only after 3 matching detections.
* The dashboard shows current state per room.
* The API returns current garage-door state by room.
* Uncertain detections are saved for review/training.

---

## 18. Later Phase Features

### Phase 2

* State-change audit history page
* Occupancy inference
* Motel POS API integration
* SMB report export
* Home Assistant/MQTT integration
* Camera offline alerts
* Better model training pipeline

### Phase 3

* User accounts
* Permissions
* Manual override with audit log
* Multi-site support
* Analytics/reporting
* Automatic retraining workflow
* Full maintenance dashboard integration
