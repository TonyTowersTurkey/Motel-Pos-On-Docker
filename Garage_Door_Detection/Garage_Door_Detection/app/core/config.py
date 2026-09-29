from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Garage Door Detection"
    app_env: str = "local"
    database_url: str = "sqlite:///./local.db"
    sqlite_busy_timeout_ms: int = 30_000
    media_root: Path = Path("media")
    uncertain_sample_dir: Path = Path("media/uncertain_samples")
    camera_snapshot_dir: Path = Path("media/camera_snapshots")
    camera_capture_dir: Path = Path("media/camera_captures")
    training_crop_dir: Path = Path("media/training_crops")
    dataset_export_dir: Path = Path("media/dataset_exports")
    snapshot_scheduler_enabled: bool = True
    inference_worker_enabled: bool = True
    room_pulse_worker_enabled: bool = True
    classification_enabled: bool = True
    classification_model_path: Path = Path("yologaragedetect.pt")
    classification_cache_dir: Path = Path("media/model_cache")
    classification_confidence_threshold: float = 0.75
    classification_confirmation_count: int = 3
    classification_poll_seconds: float = 2.0
    classification_batch_size: int = 16
    classification_max_attempts: int = 3
    unifi_connection_mode: Literal["remote", "local"] = "remote"
    unifi_api_key: SecretStr | None = None
    unifi_console_id: str | None = None
    unifi_remote_base_url: str = "https://api.ui.com"
    unifi_local_base_url: str | None = None
    unifi_local_api_key: SecretStr | None = None
    unifi_verify_ssl: bool = True
    unifi_snapshot_high_quality: bool = True
    unifi_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
