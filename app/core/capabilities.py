from typing import Any

from app.core.settings import get_settings


def deployment_capabilities() -> dict[str, Any]:
    settings = get_settings()
    database_backend = settings.database_backend
    storage_backend = settings.storage_backend

    postgres = database_backend == "postgres"
    shared_object_storage = storage_backend == "s3"
    multi_host_workers = postgres and shared_object_storage

    return {
        "deployment_mode": settings.deployment_mode,
        "database_backend": database_backend,
        "storage_backend": storage_backend,
        "durable_queue_backend": database_backend,
        "single_node_supported": True,
        "multi_host_database_coordination_supported": postgres,
        "multi_host_workers_supported": multi_host_workers,
        "object_storage_supported": storage_backend in {
            "local",
            "s3",
        },
        "postgres_supported": True,
        "postgres_ready": postgres,
        "shared_object_storage_ready": shared_object_storage,
        "recommended_multi_host_storage": "s3",
        "notes": (
            "SQLite is intended for local and single-node deployments. "
            "Full multi-host Worker execution requires PostgreSQL plus "
            "shared S3-compatible object storage."
        ),
    }
