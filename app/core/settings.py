from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Creator Dataset"
    environment: str = "development"

    # Deployment profile:
    # - local: SQLite + local object storage
    # - cloud: externally managed DB + object storage are expected
    deployment_mode: str = "local"

    data_dir: Path = Path("data")
    database_backend: str = "sqlite"
    database_path: Path = Path("data/creator_dataset.sqlite3")
    database_url: str | None = None

    # Storage abstraction.
    storage_backend: str = "local"
    storage_local_dir: Path = Path("data/objects")
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_prefix: str = "creator-dataset"

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

    @model_validator(mode="after")
    def validate_deployment(self) -> "Settings":
        if self.deployment_mode not in {"local", "cloud"}:
            raise ValueError("deployment_mode must be 'local' or 'cloud'")
        if self.database_backend != "sqlite":
            raise ValueError(
                "Only database_backend=sqlite is implemented in V0.x. "
                "Postgres is reserved for the multi-node cloud milestone."
            )
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("storage_backend must be 'local' or 's3'")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("s3_bucket is required when storage_backend=s3")
        return self

    @property
    def is_cloud(self) -> bool:
        return self.deployment_mode == "cloud"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.storage_backend == "local":
            self.storage_local_dir.mkdir(parents=True, exist_ok=True)
        # SQLite remains the active DB backend in V0.x. A database_url is
        # reserved for the upcoming Postgres repository implementation.
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
