from typing import Any

from app.core.settings import get_settings


def deployment_capabilities() -> dict[str, Any]:
    settings = get_settings()
    database_backend = settings.database_backend
    postgres = database_backend == "postgres"

    return {
        "deployment_mode": settings.deployment_mode,
        "database_backend": database_backend,
        "storage_backend": settings.storage_backend,
        "durable_queue_backend": database_backend,
        "single_node_supported": True,
        "multi_host_workers_supported": postgres,
        "object_storage_supported": settings.storage_backend in {
            "local",
            "s3",
        },
        "postgres_supported": True,
        "postgres_ready": postgres,
        "recommended_multi_host_storage": "s3",
        "notes": (
            "SQLite is intended for local and single-node deployments. "
            "PostgreSQL enables multi-host API/Worker coordination."
        ),
    }
