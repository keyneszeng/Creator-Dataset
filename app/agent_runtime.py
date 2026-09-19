import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

from app.core.settings import get_settings


async def _stream(
    name: str,
    stream: asyncio.StreamReader | None,
) -> None:
    if stream is None:
        return
    while True:
        line = await stream.readline()
        if not line:
            return
        text = line.decode("utf-8", errors="replace").rstrip()
        print(f"[{name}] {text}", flush=True)


async def _terminate(
    processes: list[asyncio.subprocess.Process],
) -> None:
    for process in processes:
        if process.returncode is None:
            process.terminate()

    try:
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    process.wait()
                    for process in processes
                    if process.returncode is None
                ],
                return_exceptions=True,
            ),
            timeout=8,
        )
    except asyncio.TimeoutError:
        for process in processes:
            if process.returncode is None:
                process.kill()
        await asyncio.gather(
            *[process.wait() for process in processes],
            return_exceptions=True,
        )


async def run_runtime(*, with_scheduler: bool = False) -> int:
    settings = get_settings()
    settings.ensure_directories()

    env = os.environ.copy()
    commands: list[tuple[str, list[str]]] = [
        ("worker", [sys.executable, "-m", "app.worker"]),
        ("mcp", [sys.executable, "-m", "app.mcp_server"]),
    ]
    if with_scheduler:
        commands.append(
            ("scheduler", [sys.executable, "-m", "app.scheduler"])
        )

    processes: list[asyncio.subprocess.Process] = []
    stream_tasks: list[asyncio.Task[None]] = []

    print(
        "Creator Dataset Agent runtime starting",
        flush=True,
    )
    print(
        f"MCP: http://{settings.mcp_host}:{settings.mcp_port}/mcp",
        flush=True,
    )
    print(
        f"Free mode: {str(settings.agent_free_mode).lower()}",
        flush=True,
    )

    for name, command in commands:
        process = await asyncio.create_subprocess_exec(
            *command,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        processes.append(process)
        stream_tasks.append(
            asyncio.create_task(_stream(name, process.stdout))
        )

    stop = asyncio.Event()

    def _request_stop() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, _request_stop)
        except NotImplementedError:
            pass

    waiters = {
        asyncio.create_task(process.wait()): (name, process)
        for (name, _), process in zip(commands, processes)
    }
    stop_task = asyncio.create_task(stop.wait())

    done, pending = await asyncio.wait(
        [*waiters.keys(), stop_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    exit_code = 0
    if stop_task not in done:
        for task in done:
            if task in waiters:
                name, process = waiters[task]
                exit_code = int(process.returncode or 0)
                print(
                    f"{name} exited with code {exit_code}; stopping runtime.",
                    flush=True,
                )
                break

    for task in pending:
        task.cancel()

    await _terminate(processes)
    await asyncio.gather(*stream_tasks, return_exceptions=True)
    return exit_code


def _check_environment() -> list[str]:
    settings = get_settings()
    problems: list[str] = []

    if sys.version_info < (3, 12):
        problems.append("Python 3.12+ is required.")

    if settings.database_backend == "sqlite":
        parent = Path(settings.database_path).parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            problems.append(
                f"Database directory is not writable: {exc}"
            )

    if not settings.xhs_cookie.strip():
        problems.append(
            "CREATOR_DATASET_XHS_COOKIE is empty; real Xiaohongshu "
            "imports will require your own logged-in Cookie."
        )

    if not settings.agent_free_mode:
        problems.append(
            "CREATOR_DATASET_AGENT_FREE_MODE is false. "
            "Current personal-use setup expects free mode."
        )

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Creator Dataset Worker + MCP as one local Agent."
    )
    parser.add_argument(
        "--with-scheduler",
        action="store_true",
        help="Also run the incremental refresh scheduler.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check local configuration without starting processes.",
    )
    args = parser.parse_args()

    if args.check:
        problems = _check_environment()
        if not problems:
            print("Creator Dataset Agent configuration looks ready.")
            return
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)

    raise SystemExit(
        asyncio.run(
            run_runtime(with_scheduler=args.with_scheduler)
        )
    )


if __name__ == "__main__":
    main()
