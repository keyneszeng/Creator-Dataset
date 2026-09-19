import json
from pathlib import Path

import pytest

from app.plugin_build import build_plugin


def test_plugin_builder_rewrites_mcp_url(tmp_path: Path) -> None:
    target = build_plugin(
        output_dir=tmp_path,
        mcp_url="https://creator.example.com/mcp",
    )

    config = json.loads(
        (target / "mcp.json").read_text(encoding="utf-8")
    )
    assert (
        config["mcpServers"]["creator-dataset"]["url"]
        == "https://creator.example.com/mcp"
    )

    skill = (
        target
        / "skills"
        / "creator-research"
        / "SKILL.md"
    )
    assert skill.exists()

    openai_yaml = (
        target
        / "skills"
        / "creator-research"
        / "agents"
        / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert 'url: "https://creator.example.com/mcp"' in openai_yaml


def test_plugin_builder_rejects_insecure_remote_url(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        build_plugin(
            output_dir=tmp_path,
            mcp_url="http://creator.example.com/mcp",
        )


def test_plugin_builder_allows_local_http_for_dev(
    tmp_path: Path,
) -> None:
    target = build_plugin(
        output_dir=tmp_path,
        mcp_url="http://127.0.0.1:8765/mcp",
        allow_local_http=True,
    )
    assert (target / "plugin.json").exists()
