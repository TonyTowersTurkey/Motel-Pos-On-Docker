from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.training_crops import generate_training_crops


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        result = generate_training_crops(db)
        print(
            f"Snapshots considered: {result.snapshots_considered}; "
            f"created: {result.crops_created}; updated: {result.crops_updated}; "
            f"already current: {result.crops_skipped}; "
            f"missing sources: {result.missing_sources}; failed: {result.failed_sources}"
        )
        return 1 if result.failed_sources else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
