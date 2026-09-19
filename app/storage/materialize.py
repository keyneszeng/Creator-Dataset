from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.storage.factory import create_object_store_for_backend


@contextmanager
def materialize_media(item: dict) -> Iterator[Path]:
    local_path = item.get("local_path")
    if local_path:
        path = Path(str(local_path))
        if path.exists():
            yield path
            return

    backend = str(item.get("storage_backend") or "")
    key = str(item.get("storage_key") or "")
    if not backend or not key:
        raise FileNotFoundError(
            f"Media {item.get('id')} has no accessible storage reference."
        )

    suffix = Path(key).suffix
    store = create_object_store_for_backend(backend)
    with store.materialize(key=key, suffix=suffix) as path:
        yield path
