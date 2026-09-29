import asyncio

from app.core.config import settings
from app.main import app, lifespan


def test_lifespan_starts_only_enabled_workers(monkeypatch) -> None:
    started: list[str] = []

    async def worker(name: str) -> None:
        started.append(name)
        await asyncio.Event().wait()

    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr(
        "app.main.automatic_snapshot_scheduler",
        lambda: worker("snapshot"),
    )
    monkeypatch.setattr(
        "app.main.automatic_inference_worker",
        lambda: worker("inference"),
    )
    monkeypatch.setattr(
        "app.main.automatic_room_pulse_worker",
        lambda: worker("room_pulse"),
    )
    monkeypatch.setattr(settings, "snapshot_scheduler_enabled", True)
    monkeypatch.setattr(settings, "inference_worker_enabled", False)
    monkeypatch.setattr(settings, "room_pulse_worker_enabled", True)

    async def run_lifespan() -> None:
        async with lifespan(app):
            await asyncio.sleep(0)
            assert started == ["snapshot", "room_pulse"]

    asyncio.run(run_lifespan())


def test_lifespan_allows_all_workers_to_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr(settings, "snapshot_scheduler_enabled", False)
    monkeypatch.setattr(settings, "inference_worker_enabled", False)
    monkeypatch.setattr(settings, "room_pulse_worker_enabled", False)

    async def run_lifespan() -> None:
        async with lifespan(app):
            await asyncio.sleep(0)

    asyncio.run(run_lifespan())
