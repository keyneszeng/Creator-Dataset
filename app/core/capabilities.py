from typing import Any

from app.core.settings import get_settings


def deployment_capabilities() -> dict[str, Any]:
    settings = get_settings()
    database_backend = settings.database_backend

    return {
        "deployment_mode": settings.deployment_mode,
        "database_backend": database_backend,
        "storage_backend": settings.storage_backend,
        "durable_queue_backend": database_backend,
        "single_node_supported": database_backend == "sqlite",
        "multi_host_workers_supported": database_backend != "sqlite",
        "object_storage_supported": settings.storage_backend in {"local", "s3"},
        "postgres_ready": False,
        "notes": (
            "SQLite supports local and single-node cloud deployments. "
            "Multi-host workers require the future Postgres repository backend."
        ),
    }
