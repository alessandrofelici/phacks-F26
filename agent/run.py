"""The contract's command (CONTRACT.md section 3).

    python -m agent.run --task <task_dir> --run <run_dir> [--auto-approve]

Exit code 0 means report.json was written, whatever its status. Anything else is a crash.

This file imports only the standard library, so any ``python`` can start it. If that
interpreter lacks the agent's dependencies, it re-runs itself with ``agent/.venv``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent


def main_checkout(root: Path | None = None) -> Path | None:
    """The main checkout when ``root`` is a linked git worktree, else None.

    A worktree has no copy of the gitignored ``.env`` or ``agent/.venv``; both are borrowed
    from the main checkout so an agent working in a worktree can run without setup.
    """
    git = (root or REPO_ROOT) / ".git"
    if not git.is_file():  # a directory (main checkout) or missing (not a git checkout)
        return None
    text = git.read_text(encoding="utf-8").strip()
    if not text.startswith("gitdir:"):
        return None
    gitdir = ((root or REPO_ROOT) / text.removeprefix("gitdir:").strip()).resolve()  # <main>/.git/worktrees/<name>
    commondir = gitdir / "commondir"
    common = (gitdir / commondir.read_text(encoding="utf-8").strip()).resolve() if commondir.is_file() else gitdir.parent.parent
    return common.parent


def env_file() -> Path:
    """The repo's ``.env``; in a worktree without one, the main checkout's."""
    own = REPO_ROOT / ".env"
    main = main_checkout()
    if not own.is_file() and main is not None and (main / ".env").is_file():
        return main / ".env"
    return own


def load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from the repo's .env without overriding the environment."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def ensure_dependencies(argv: list[str], module: str = "agent.run") -> None:
    """Switch to agent/.venv when this interpreter can't import deepagents."""
    if importlib.util.find_spec("deepagents") is not None:
        return
    venv_python = AGENT_DIR / ".venv" / "bin" / "python"
    main = main_checkout()
    if not venv_python.exists() and main is not None:  # a worktree: use the main checkout's venv
        venv_python = main / "agent" / ".venv" / "bin" / "python"
    if venv_python.exists() and not os.environ.get("REPRO_REEXEC"):
        os.environ["REPRO_REEXEC"] = "1"
        os.execv(str(venv_python), [str(venv_python), "-m", module, *argv])
    sys.exit(
        f"{module}: the agent's dependencies are not installed.\n"
        "From the repo root run:\n"
        "  python3 -m venv agent/.venv && agent/.venv/bin/pip install -r agent/requirements.txt\n"
        "(or: uv venv agent/.venv && uv pip install -p agent/.venv -r agent/requirements.txt)"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="python -m agent.run", description="Run Repro Bot on one task.")
    parser.add_argument("--task", required=True, type=Path, help="task directory (contains task.json and repo/)")
    parser.add_argument("--run", required=True, type=Path, help="run directory to write")
    parser.add_argument("--auto-approve", action="store_true", help="approve every gated action (batch runs)")
    args = parser.parse_args(argv)

    load_dotenv(env_file())
    ensure_dependencies(argv)

    from agent.rundir import RunDirError
    from agent.runner import ConfigError, run_task
    from agent.task import TaskError

    try:
        return run_task(args.task, args.run, auto_approve=args.auto_approve)
    except (ConfigError, TaskError, RunDirError) as exc:
        print(f"agent.run: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
