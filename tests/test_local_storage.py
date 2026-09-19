from pathlib import Path

import pytest

from app.storage.local import LocalObjectStore


def test_local_object_store_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    store = LocalObjectStore(tmp_path / "objects")
    stored = store.put_file(source, key="posts/a/file.txt")

    assert stored.backend == "local"
    assert store.exists(key=stored.key)

    with store.materialize(key=stored.key) as path:
        assert path.read_text(encoding="utf-8") == "hello"

    store.delete(key=stored.key)
    assert not store.exists(key=stored.key)


def test_local_object_store_rejects_parent_escape(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    with pytest.raises(ValueError):
        store.exists(key="../secret")
