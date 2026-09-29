from app.core.config import settings
from app.db import session as db_session


def test_sqlite_connections_enable_wal_and_busy_timeout(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "sqlite_busy_timeout_ms", 30_000)
    engine = db_session.create_engine(settings.database_url)

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 30_000
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

    engine.dispose()
