import argparse
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse


PLUGIN_SOURCE = Path(__file__).resolve().parents[1] / "plugins" / "creator-dataset"


def _validate_mcp_url(url: str, *, allow_local_http: bool) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("MCP URL must be an absolute http/https URL.")

    is_local = (parsed.hostname or "").lower() in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
    if parsed.scheme != "https" and not (
        allow_local_http and is_local
    ):
        raise ValueError(
            "Remote Plugin MCP URLs must use HTTPS. "
            "Plain HTTP is allowed only for localhost development."
        )
    return url.rstrip("/")


def build_plugin(
    *,
    output_dir: Path,
    mcp_url: str,
    allow_local_http: bool = False,
) -> Path:
    safe_url = _validate_mcp_url(
        mcp_url,
        allow_local_http=allow_local_http,
    )
    target = output_dir / "creator-dataset"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(PLUGIN_SOURCE, target)

    mcp_path = target / "mcp.json"
    mcp_config = json.loads(mcp_path.read_text(encoding="utf-8"))
    mcp_config["mcpServers"]["creator-dataset"]["url"] = safe_url
    mcp_path.write_text(
        json.dumps(mcp_config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    agent_path = (
        target
        / "skills"
        / "creator-research"
        / "agents"
        / "openai.yaml"
    )
    if agent_path.exists():
        text = agent_path.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("url:"):
                indent = line[: len(line) - len(line.lstrip())]
                lines.append(f'{indent}url: "{safe_url}"')
            else:
                lines.append(line)
        agent_path.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an installable Creator Dataset Agent Plugin."
    )
    parser.add_argument(
        "--mcp-url",
        help="Streamable HTTP MCP endpoint, normally ending in /mcp.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Build for the default local MCP endpoint.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/plugins"),
    )
    parser.add_argument(
        "--allow-local-http",
        action="store_true",
        help="Allow http://localhost URLs for local development only.",
    )
    args = parser.parse_args()

    if args.local:
        if args.mcp_url:
            parser.error("--local and --mcp-url cannot be used together.")
        mcp_url = "http://127.0.0.1:8765/mcp"
        allow_local_http = True
    else:
        if not args.mcp_url:
            parser.error("Provide --mcp-url or use --local.")
        mcp_url = args.mcp_url
        allow_local_http = args.allow_local_http

    result = build_plugin(
        output_dir=args.output,
        mcp_url=mcp_url,
        allow_local_http=allow_local_http,
    )
    print(result)


if __name__ == "__main__":
    main()
