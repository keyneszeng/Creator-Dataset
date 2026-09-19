from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Creator Dataset"
    environment: str = "development"

    # Deployment profile:
    # - local: SQLite + local object storage by default
    # - cloud: PostgreSQL + S3-compatible object storage recommended
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

    # PostgreSQL pool per process.
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 10

    # SaaS access control. Local development can keep this disabled.
    saas_auth_enabled: bool = False
    saas_bootstrap_admin_key: str = ""
    saas_default_free_dataset_credits: int = 5

    # Optional user-connected LLM organization layer.
    llm_enabled: bool = False
    llm_credential_encryption_key: str = ""
    llm_allowed_hosts: str = ""
    llm_allow_custom_base_url_local: bool = True
    llm_max_input_chars: int = 120000

    # Agent/MCP local development endpoint.
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765
    mcp_user_api_key: str = ""

    model_config = SettingsConfigDict(
        env_prefix="CREATOR_DATASET_",
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_deployment(self) -> "Settings":
        if self.deployment_mode not in {"local", "cloud"}:
            raise ValueError("deployment_mode must be 'local' or 'cloud'")
        if self.database_backend not in {"sqlite", "postgres"}:
            raise ValueError(
                "database_backend must be 'sqlite' or 'postgres'"
            )
        if self.database_backend == "postgres" and not self.database_url:
            raise ValueError(
                "database_url is required when database_backend=postgres"
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
        if self.database_backend == "sqlite":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
