PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS app_settings (
  key VARCHAR(120) PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS room_pulse_config (
  id INTEGER PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT 0,
  endpoint_url TEXT,
  public_base_url TEXT,
  interval_seconds INTEGER NOT NULL DEFAULT 60,
  send_on_change BOOLEAN NOT NULL DEFAULT 1,
  include_image_url BOOLEAN NOT NULL DEFAULT 1,
  bearer_token TEXT,
  timeout_seconds INTEGER NOT NULL DEFAULT 10,
  last_sent_at TIMESTAMP,
  last_error TEXT,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS room_pulse_deliveries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id VARCHAR(36) NOT NULL UNIQUE,
  event_type VARCHAR(30) NOT NULL,
  status VARCHAR(20) NOT NULL,
  endpoint_url TEXT NOT NULL,
  http_status INTEGER,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  room_count INTEGER NOT NULL,
  payload TEXT NOT NULL,
  error TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  delivered_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cameras (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(120) NOT NULL,
  unifi_camera_id VARCHAR(120) NOT NULL UNIQUE,
  location VARCHAR(120),
  enabled BOOLEAN NOT NULL DEFAULT 1,
  automatic_snapshots BOOLEAN NOT NULL DEFAULT 0,
  last_snapshot_at TIMESTAMP,
  snapshot_image_path TEXT,
  last_error TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS camera_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  camera_id INTEGER NOT NULL,
  image_path TEXT NOT NULL,
  captured_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS room (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL,
  camera_id INTEGER NOT NULL,
  name VARCHAR(120) NOT NULL,
  roi_x INTEGER NOT NULL DEFAULT 0,
  roi_y INTEGER NOT NULL DEFAULT 0,
  roi_width INTEGER NOT NULL DEFAULT 0,
  roi_height INTEGER NOT NULL DEFAULT 0,
  current_state TEXT NOT NULL DEFAULT 'unknown'
    CHECK (current_state IN ('open', 'closed', 'unknown')),
  current_confidence REAL,
  last_detected_state TEXT
    CHECK (last_detected_state IS NULL OR last_detected_state IN ('open', 'closed', 'unknown')),
  last_detected_confidence REAL,
  consecutive_match_count INTEGER NOT NULL DEFAULT 0,
  last_detection_at TIMESTAMP,
  last_confirmed_change_at TIMESTAMP,
  active BOOLEAN NOT NULL DEFAULT 1,
  FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS training_label_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  confidence_threshold REAL NOT NULL,
  room_number INTEGER,
  images_approved INTEGER NOT NULL,
  open_approved INTEGER NOT NULL,
  closed_approved INTEGER NOT NULL,
  model_versions TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  undone_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_crops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  room_id INTEGER NOT NULL,
  image_path TEXT NOT NULL,
  roi_x INTEGER NOT NULL,
  roi_y INTEGER NOT NULL,
  roi_width INTEGER NOT NULL,
  roi_height INTEGER NOT NULL,
  label VARCHAR(20),
  label_source VARCHAR(20),
  label_batch_id INTEGER,
  label_confidence REAL,
  labeled_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (snapshot_id) REFERENCES camera_snapshots(id) ON DELETE CASCADE,
  FOREIGN KEY (room_id) REFERENCES room(id) ON DELETE CASCADE,
  FOREIGN KEY (label_batch_id) REFERENCES training_label_batches(id) ON DELETE SET NULL,
  UNIQUE (snapshot_id, room_id)
);

CREATE TABLE IF NOT EXISTS inference_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  training_crop_id INTEGER NOT NULL UNIQUE,
  status VARCHAR(20) NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  is_backfill BOOLEAN NOT NULL DEFAULT 0,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  model_version VARCHAR(255),
  last_error TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  FOREIGN KEY (training_crop_id) REFERENCES training_crops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS detection_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  training_crop_id INTEGER NOT NULL,
  room_id INTEGER NOT NULL,
  snapshot_id INTEGER NOT NULL,
  predicted_state VARCHAR(20) NOT NULL
    CHECK (predicted_state IN ('open', 'closed', 'unknown')),
  confidence REAL NOT NULL,
  closed_probability REAL NOT NULL,
  open_probability REAL NOT NULL,
  model_version VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (training_crop_id) REFERENCES training_crops(id) ON DELETE CASCADE,
  FOREIGN KEY (room_id) REFERENCES room(id) ON DELETE CASCADE,
  FOREIGN KEY (snapshot_id) REFERENCES camera_snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_camera_snapshots_camera_id
  ON camera_snapshots(camera_id);

CREATE INDEX IF NOT EXISTS idx_room_camera_id
  ON room(camera_id);

CREATE INDEX IF NOT EXISTS idx_room_room_id
  ON room(room_id);

CREATE INDEX IF NOT EXISTS idx_training_crops_snapshot_id
  ON training_crops(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_training_crops_room_id
  ON training_crops(room_id);

CREATE INDEX IF NOT EXISTS idx_training_crops_label_batch_id
  ON training_crops(label_batch_id);

CREATE INDEX IF NOT EXISTS idx_inference_jobs_status
  ON inference_jobs(status);

CREATE INDEX IF NOT EXISTS idx_detection_events_room_id
  ON detection_events(room_id);

CREATE INDEX IF NOT EXISTS idx_detection_events_training_crop_id_id
  ON detection_events(training_crop_id, id);

CREATE TRIGGER IF NOT EXISTS trg_cameras_updated_at
AFTER UPDATE ON cameras
FOR EACH ROW
BEGIN
  UPDATE cameras
  SET updated_at = CURRENT_TIMESTAMP
  WHERE id = OLD.id;
END;
