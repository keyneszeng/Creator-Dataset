from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    backend: str
    key: str
    size: int
    local_path: str | None = None


class ObjectStore(Protocol):
    name: str

    def put_file(self, source: Path, *, key: str) -> StoredObject:
        ...

    def exists(self, *, key: str) -> bool:
        ...

    def delete(self, *, key: str) -> None:
        ...

    def materialize(
        self,
        *,
        key: str,
        suffix: str = "",
    ) -> AbstractContextManager[Path]:
        ...
