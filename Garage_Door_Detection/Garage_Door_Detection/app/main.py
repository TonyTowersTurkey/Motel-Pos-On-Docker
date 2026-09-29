import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.services.inference import automatic_inference_worker
from app.services.room_pulse import automatic_room_pulse_worker
from app.services.snapshot_scheduler import automatic_snapshot_scheduler

APP_DIR = Path(__file__).resolve().parent

settings.media_root.mkdir(parents=True, exist_ok=True)
settings.camera_snapshot_dir.mkdir(parents=True, exist_ok=True)
settings.camera_capture_dir.mkdir(parents=True, exist_ok=True)
settings.training_crop_dir.mkdir(parents=True, exist_ok=True)
settings.dataset_export_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    workers = (
        (settings.snapshot_scheduler_enabled, automatic_snapshot_scheduler),
        (settings.inference_worker_enabled, automatic_inference_worker),
        (settings.room_pulse_worker_enabled, automatic_room_pulse_worker),
    )
    tasks = [
        asyncio.create_task(worker())
        for enabled, worker in workers
        if enabled
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)

app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "room_dashboard.html",
        {"app_name": settings.app_name, "active_page": "dashboard"},
    )


@app.get("/cameras", response_class=HTMLResponse)
def cameras(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"app_name": settings.app_name, "active_page": "cameras"},
    )


@app.get("/training", response_class=HTMLResponse)
def training(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "training.html",
        {"app_name": settings.app_name, "active_page": "training"},
    )


@app.get("/room-pulse", response_class=HTMLResponse)
def room_pulse(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "room_pulse.html",
        {"app_name": settings.app_name, "active_page": "room-pulse"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
