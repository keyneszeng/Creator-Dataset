from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Creator Dataset"
    environment: str = "development"
    data_dir: Path = Path("data")
    database_path: Path = Path("data/creator_dataset.sqlite3")

    # Xiaohongshu auth is environment-only. Never persist this value.
    xhs_cookie: str = ""

    # Durable worker defaults.
    worker_poll_seconds: float = 2.0
    worker_lease_seconds: int = 180
    worker_heartbeat_seconds: int = 45

    # Conservative shared Xiaohongshu request spacing across workers.
    xhs_min_interval_seconds: float = 1.5

    model_config = SettingsConfigDict(
        env_prefix="CREATOR_DATASET_",
        env_file=".env",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
