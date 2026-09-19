from app.core.settings import Settings, get_settings
from app.storage.base import ObjectStore
from app.storage.local import LocalObjectStore
from app.storage.s3 import S3ObjectStore


def create_object_store_for_backend(
    backend: str,
    settings: Settings | None = None,
) -> ObjectStore:
    settings = settings or get_settings()

    if backend == "local":
        return LocalObjectStore(settings.storage_local_dir)

    if backend == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3 bucket is not configured.")
        return S3ObjectStore(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            prefix=settings.s3_prefix,
        )

    raise ValueError(f"Unsupported storage backend: {backend}")


def create_object_store(
    settings: Settings | None = None,
) -> ObjectStore:
    settings = settings or get_settings()
    return create_object_store_for_backend(
        settings.storage_backend,
        settings=settings,
    )
