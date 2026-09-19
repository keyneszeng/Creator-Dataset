from pathlib import Path

from app.core.settings import Settings


def test_agent_runtime_check_accepts_free_local_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.agent_runtime as runtime

    settings = Settings(
        database_path=tmp_path / "creator.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        xhs_cookie="a1=test",
        agent_free_mode=True,
    )
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)

    assert runtime._check_environment() == []


def test_agent_runtime_check_reports_missing_cookie(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.agent_runtime as runtime

    settings = Settings(
        database_path=tmp_path / "creator.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        xhs_cookie="",
        agent_free_mode=True,
    )
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)

    problems = runtime._check_environment()

    assert any("XHS_COOKIE" in item for item in problems)
