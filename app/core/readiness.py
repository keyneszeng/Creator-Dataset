import tempfile
from pathlib import Path
from uuid import uuid4

from app.core.database import db_session
from app.core.migrations import CURRENT_SCHEMA_VERSION
from app.core.settings import get_settings
from app.storage.factory import create_object_store


def check_readiness(*, deep_storage: bool = False) -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, object] = {}
    ready = True

    try:
        with db_session() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version "
                "FROM schema_migrations"
            ).fetchone()
            version = int(row["version"])
            connection.execute("SELECT 1").fetchone()
        db_ok = version == CURRENT_SCHEMA_VERSION
        checks["database"] = {
            "ok": db_ok,
            "backend": settings.database_backend,
            "schema_version": version,
            "expected_schema_version": CURRENT_SCHEMA_VERSION,
        }
        ready = ready and db_ok
    except Exception as exc:
        checks["database"] = {
            "ok": False,
            "backend": settings.database_backend,
            "error": str(exc),
        }
        ready = False

    checks["storage"] = {
        "ok": True,
        "backend": settings.storage_backend,
        "deep_checked": deep_storage,
    }

    if deep_storage:
        key = f"_health/{uuid4().hex}.txt"
        try:
            store = create_object_store()
            with tempfile.NamedTemporaryFile(delete=False) as handle:
                source = Path(handle.name)
                handle.write(b"creator-dataset-readiness")
            try:
                stored = store.put_file(source, key=key)
                with store.materialize(key=stored.key, suffix=".txt") as path:
                    payload = path.read_bytes()
                if payload != b"creator-dataset-readiness":
                    raise ValueError("Object storage roundtrip payload mismatch.")
                store.delete(key=stored.key)
                checks["storage"] = {
                    "ok": True,
                    "backend": stored.backend,
                    "deep_checked": True,
                }
            finally:
                source.unlink(missing_ok=True)
        except Exception as exc:
            checks["storage"] = {
                "ok": False,
                "backend": settings.storage_backend,
                "deep_checked": True,
                "error": str(exc),
            }
            ready = False

    return {
        "ready": ready,
        "deployment_mode": settings.deployment_mode,
        "checks": checks,
    }
