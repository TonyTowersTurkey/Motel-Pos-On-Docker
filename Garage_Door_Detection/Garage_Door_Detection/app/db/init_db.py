from sqlalchemy import inspect, text

from app.db.session import engine
from app.models import Base


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _add_automatic_snapshots_column()
    _add_room_detection_columns()
    _add_inference_backfill_column()
    _add_training_label_audit_columns()
    _add_vehicle_label_columns()
    _ensure_inference_indexes()
    _remove_legacy_camera_columns()


def _add_automatic_snapshots_column() -> None:
    inspector = inspect(engine)
    if "cameras" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("cameras")}
    if "automatic_snapshots" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE cameras ADD COLUMN automatic_snapshots "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )


def _add_room_detection_columns() -> None:
    inspector = inspect(engine)
    if "room" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("room")}
    if "last_detected_confidence" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE room ADD COLUMN last_detected_confidence REAL")
            )


def _add_inference_backfill_column() -> None:
    inspector = inspect(engine)
    if "inference_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("inference_jobs")}
    if "is_backfill" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE inference_jobs ADD COLUMN is_backfill "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "UPDATE inference_jobs SET is_backfill = TRUE "
                    "WHERE status = 'queued'"
                )
            )


def _add_training_label_audit_columns() -> None:
    inspector = inspect(engine)
    if "training_crops" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("training_crops")}
    definitions = {
        "label_source": "VARCHAR(20)",
        "label_batch_id": "INTEGER",
        "label_confidence": "REAL",
        "labeled_at": "DATETIME",
    }
    with engine.begin() as connection:
        for column, definition in definitions.items():
            if column not in columns:
                connection.execute(
                    text(f"ALTER TABLE training_crops ADD COLUMN {column} {definition}")
                )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_training_crops_label "
                "ON training_crops (label)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_training_crops_label_batch_id "
                "ON training_crops (label_batch_id)"
            )
        )


def _add_vehicle_label_columns() -> None:
    inspector = inspect(engine)
    if "training_crops" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("training_crops")}
    definitions = {
        "vehicle_label": "VARCHAR(20)",
        "vehicle_label_source": "VARCHAR(20)",
        "vehicle_labeled_at": "DATETIME",
    }
    with engine.begin() as connection:
        for column, definition in definitions.items():
            if column not in columns:
                connection.execute(
                    text(f"ALTER TABLE training_crops ADD COLUMN {column} {definition}")
                )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_training_crops_vehicle_label "
                "ON training_crops (vehicle_label)"
            )
        )


def _ensure_inference_indexes() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "inference_jobs" in tables:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_inference_jobs_status "
                    "ON inference_jobs (status)"
                )
            )
        if "detection_events" in tables:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_detection_events_room_id "
                    "ON detection_events (room_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_detection_events_training_crop_id_id "
                    "ON detection_events (training_crop_id, id)"
                )
            )


def _remove_legacy_camera_columns() -> None:
    """Remove fields from the retired manual RTSP/ONVIF camera workflow."""
    inspector = inspect(engine)
    if "cameras" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("cameras")}
    legacy_columns = (
        "rtsp_url",
        "onvif_xaddr",
        "onvif_profile_token",
        "capture_source",
    )
    with engine.begin() as connection:
        for column in legacy_columns:
            if column in columns:
                connection.execute(text(f"ALTER TABLE cameras DROP COLUMN {column}"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_cameras_unifi_camera_id "
                "ON cameras (unifi_camera_id)"
            )
        )


if __name__ == "__main__":
    init_db()
