import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.storage.base import StoredObject


class LocalObjectStore:
    name = "local"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        normalized = key.strip("/")
        if not normalized or ".." in Path(normalized).parts:
            raise ValueError("Invalid object key.")
        path = (self.root / normalized).resolve()
        root = self.root.resolve()
        if root not in path.parents and path != root:
            raise ValueError("Object key escapes storage root.")
        return path

    def put_file(self, source: Path, *, key: str) -> StoredObject:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".part")
        shutil.copyfile(source, temp)
        os.replace(temp, target)
        return StoredObject(
            backend=self.name,
            key=key,
            size=target.stat().st_size,
            local_path=str(target),
            uri=target.as_uri(),
        )

    def exists(self, *, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, *, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def access_url(
        self,
        *,
        key: str,
        expires_seconds: int = 900,
    ) -> str | None:
        # Local objects are served through the authenticated SaaS API.
        return None

    @contextmanager
    def materialize(
        self,
        *,
        key: str,
        suffix: str = "",
    ) -> Iterator[Path]:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(path)
        yield path
