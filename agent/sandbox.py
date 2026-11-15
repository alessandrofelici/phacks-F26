"""Where the paper's code runs.

Two sandboxes, chosen with ``REPRO_SANDBOX`` (``auto``, ``podman`` or ``local``):

- **podman**: a rootless container with only the workspace mounted. The paper's code can't
  see this repository (so not the harness's answer keys either), other files on the disk, or
  API keys, and it has no network when the task says ``limits.network: false``.
- **local**: deepagents' ``LocalShellBackend`` on the workspace. No isolation: a command can
  read anything this user can. Fine for plumbing and the toy task, not for scored runs.

File tools always work on the workspace directory on the host; in the container the same
directory is mounted at ``/work``.
"""

from __future__ import annotations

import hashlib
import math
import os
import shlex
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse

from agent.rundir import RunWriter
from agent.task import Task

# Commands that take longer than this need an approval (contract 3.1: "more than about a minute").
SHORT_TIMEOUT_S = int(os.environ.get("REPRO_SHORT_TIMEOUT", "90"))
DEFAULT_IMAGE = "docker.io/library/python:3.12-slim"
# Built by agent/sandbox-image/build.sh: conda, uv, compilers, R, nbconvert. Used when present.
FULL_IMAGE = "localhost/repro-sandbox:2"

# Passed through to commands so installs work behind a proxy. API keys are deliberately not.
_PASS_ENV = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy", "LANG", "TZ")
_HASH_LIMIT = 2_000_000  # larger files are compared by size and modification time


class SandboxError(RuntimeError):
    """The sandbox could not be started."""


@dataclass
class CommandRecord:
    command: str
    exit_code: int | None
    log: str  # path relative to the run directory
    output: str


def make_workdir(task: Task, run_id: str) -> Path:
    """Copy the task's repo (and paper) to a fresh directory outside the code repository.

    The task directory is read-only for the agent (contract section 1), and the agent
    must not see the rest of this repository, which holds fixtures with the toy answers.
    """
    root = Path(os.environ.get("REPRO_WORK_ROOT") or tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f"repro-{run_id}-", dir=root))
    shutil.copytree(task.task_dir / "repo", work / "repo", symlinks=True)
    paper = task.task_dir / "paper.md"
    if paper.is_file():
        shutil.copy2(paper, work / "paper.md")
    (work / ".home").mkdir()
    return work


def remove_workdir(work: Path) -> None:
    """Delete the workspace, including files a container wrote as another user."""
    shutil.rmtree(work, ignore_errors=True)
    if work.exists() and shutil.which("podman"):
        try:
            subprocess.run(["podman", "unshare", "rm", "-rf", str(work)], capture_output=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass  # a leftover temp directory is not worth failing the run over


def _base_env() -> dict[str, str]:
    env = {"PIP_DISABLE_PIP_VERSION_CHECK": "1", "PYTHONUNBUFFERED": "1"}
    for name in _PASS_ENV:
        if os.environ.get(name):
            env[name] = os.environ[name]
    env.setdefault("LANG", "C.UTF-8")
    return env


def _format(stdout: str, stderr: str, returncode: int, limit: int) -> ExecuteResponse:
    """Same output shape as LocalShellBackend: stdout, then stderr lines marked, then the exit code."""
    parts = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.extend(f"[stderr] {line}" for line in stderr.strip().split("\n"))
    output = "\n".join(parts) if parts else "<no output>"
    truncated = False
    raw = output.encode("utf-8")
    if len(raw) > limit:
        output = raw[:limit].decode("utf-8", errors="ignore") + f"\n\n... Output truncated at {limit} bytes."
        truncated = True
    if returncode != 0:
        output = f"{output.rstrip()}\n\nExit code: {returncode}"
    return ExecuteResponse(output=output, exit_code=returncode, truncated=truncated)


class LoggingShellBackend(LocalShellBackend):
    """Local shell that saves every command's full output into the run directory's logs/."""

    label = "local"

    def __init__(self, work: Path, writer: RunWriter, *, deadline: float | None = None) -> None:
        super().__init__(
            root_dir=work,
            virtual_mode=True,
            timeout=SHORT_TIMEOUT_S,
            max_output_bytes=1_000_000,
            env={
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "HOME": str(work / ".home"),
                **_base_env(),
            },
            inherit_env=False,
        )
        self._writer = writer
        self._deadline = deadline  # time.monotonic() value for the whole run
        self.commands: list[CommandRecord] = []
        self.out_of_time = False  # set when a command was refused because the run's time is used up
        self.background: dict[str, dict] = {}  # runs started with start_background, by id
        self._bg_lock = threading.Lock()  # parallel tool calls can start several background runs at once
        # Set by the runner: returns a short note to append to command output (a run with no plan yet).
        self.reminder: Callable[[], str | None] | None = None

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        effective = timeout if timeout is not None else SHORT_TIMEOUT_S
        if self._deadline is not None:
            # Never let one command outlive the run's time budget.
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                self.out_of_time = True
                return ExecuteResponse(output="Error: the run's time limit is used up; nothing was run.", exit_code=124)
            effective = max(1, min(effective, math.ceil(remaining)))
        response = self._run(command, effective)
        text = f"$ {command}\n{response.output}\n"
        log = self._writer.save_log(command, text)
        # Same file inside the workspace, so the agent can search it as /logs/...
        mirror = Path(self.cwd) / log
        mirror.parent.mkdir(exist_ok=True)
        mirror.write_text(text, encoding="utf-8")
        self.commands.append(CommandRecord(command, response.exit_code, log, response.output))
        note = self.reminder() if self.reminder is not None else None
        if note:
            # Only the model sees the note; the saved log, and so the evidence, stays the command's own output.
            response = ExecuteResponse(output=f"{response.output}\n\n[{note}]", exit_code=response.exit_code,
                                       truncated=response.truncated)
        return response

    def _run(self, command: str, timeout: int) -> ExecuteResponse:
        return LocalShellBackend.execute(self, command, timeout=timeout)

    # -- background runs: a long experiment that doesn't block the agent ---------------

    def start_background(self, command: str, limit_s: int) -> str:
        """Start ``command`` detached in the sandbox and return its id. Output goes to .bg/<id>.out."""
        remaining = None if self._deadline is None else self._deadline - time.monotonic()
        if remaining is not None and remaining <= 0:
            self.out_of_time = True
            return ""
        limit = limit_s if remaining is None else max(1, min(limit_s, math.ceil(remaining)))
        with self._bg_lock:
            # Choose and register the id together, so runs started in parallel never share one.
            run_id = f"bg{len(self.background) + 1}"
            self.background[run_id] = {"command": command, "started": time.monotonic(), "log": None, "limit": limit}
        (Path(self.cwd) / ".bg").mkdir(exist_ok=True)
        inner = f"timeout -k 5 {limit} sh -c {shlex.quote(command)}"
        launcher = (
            f"(({inner}) > .bg/{run_id}.out 2>&1; echo $? > .bg/{run_id}.exit) > /dev/null 2>&1 & "
            f"echo $! > .bg/{run_id}.pid"
        )
        self._run(launcher, 30)
        return run_id

    def check_background(self, run_id: str, tail_lines: int = 30) -> dict | None:
        """State of a background run. When it has finished, its output is saved to logs/ once."""
        run = self.background.get(run_id)
        if run is None:
            return None
        base = Path(self.cwd) / ".bg"
        out_file, exit_file = base / f"{run_id}.out", base / f"{run_id}.exit"
        output = out_file.read_text(encoding="utf-8", errors="replace") if out_file.exists() else ""
        exit_code: int | None = None
        if exit_file.exists():
            try:
                exit_code = int(exit_file.read_text().strip() or "1")
            except ValueError:
                exit_code = 1
        if exit_code is not None and run["log"] is None:
            ending = "" if exit_code == 0 else f"\n\nExit code: {exit_code}"
            text = f"$ {run['command']}\n{output.rstrip()}{ending}\n"
            run["log"] = self._writer.save_log(run["command"], text)
            run["seconds"] = time.monotonic() - run["started"]
            mirror = Path(self.cwd) / run["log"]
            mirror.parent.mkdir(exist_ok=True)
            mirror.write_text(text, encoding="utf-8")
        return {
            "done": exit_code is not None,
            "exit_code": exit_code,
            "timed_out": exit_code in (124, 137),
            "seconds": run.get("seconds", time.monotonic() - run["started"]),
            "tail": "\n".join(output.splitlines()[-tail_lines:]),
            "log": run["log"],
        }

    def background_output(self, run_id: str) -> str:
        """Everything a background run has printed so far."""
        out_file = Path(self.cwd) / ".bg" / f"{run_id}.out"
        return out_file.read_text(encoding="utf-8", errors="replace") if out_file.exists() else ""

    def take_record(self, command: str) -> CommandRecord | None:
        """The oldest unclaimed record of ``command``, removed from the list."""
        for i, record in enumerate(self.commands):
            if record.command == command:
                return self.commands.pop(i)
        return None

    def close(self) -> None:
        """Stop background runs that are still going."""
        for run_id in self.background:
            pid_file = Path(self.cwd) / ".bg" / f"{run_id}.pid"
            if (Path(self.cwd) / ".bg" / f"{run_id}.exit").exists() or not pid_file.exists():
                continue
            try:
                os.killpg(os.getpgid(int(pid_file.read_text().strip())), signal.SIGKILL)
            except (OSError, ValueError):
                pass


class PodmanShellBackend(LoggingShellBackend):
    """Runs commands in a rootless Podman container that only has the workspace mounted."""

    def __init__(
        self,
        work: Path,
        writer: RunWriter,
        *,
        deadline: float | None = None,
        image: str = DEFAULT_IMAGE,
        network: bool = True,
    ) -> None:
        super().__init__(work, writer, deadline=deadline)
        self.container = f"repro-{uuid.uuid4().hex[:12]}"
        self.label = f"podman ({image.rsplit('/', 1)[-1]}, network {'on' if network else 'off'})"
        start = ["podman", "run", "-d", "--rm", "--name", self.container]
        start += ["--network", "host" if network else "none"]
        start += ["-v", f"{work}:/work", "-w", "/work", "-e", "HOME=/work/.home"]
        for name, value in _base_env().items():
            start += ["-e", f"{name}={value}"]
        start += [image, "sleep", "infinity"]
        try:
            # May pull the image on first use, which is slow on a bad connection.
            result = subprocess.run(start, capture_output=True, text=True, timeout=900, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxError(f"podman did not start: {exc}") from exc
        if result.returncode != 0:
            raise SandboxError(f"podman could not start {image}: {result.stderr.strip()[-400:]}")

    def _run(self, command: str, timeout: int) -> ExecuteResponse:
        # `timeout` inside the container ends the command; the outer limit only guards podman itself.
        argv = ["podman", "exec", "-w", "/work", self.container, "timeout", "-k", "5", str(timeout), "sh", "-c", command]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout + 30, check=False
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(output=f"Error: Command timed out after {timeout} seconds.", exit_code=124)
        except OSError as exc:
            return ExecuteResponse(output=f"Error: could not run the command in the sandbox: {exc}", exit_code=1)
        if result.returncode in (124, 137):
            partial = _format(result.stdout, result.stderr, result.returncode, self._max_output_bytes).output
            return ExecuteResponse(
                output=f"{partial}\n\nError: Command timed out after {timeout} seconds. For long-running "
                "commands, re-run using the timeout parameter.",
                exit_code=124,
            )
        return _format(result.stdout, result.stderr, result.returncode, self._max_output_bytes)

    def close(self) -> None:
        """Remove the container. Never raises: a slow podman (another build holding the storage
        lock, a busy machine) must not cost the run its report."""
        argv = ["podman", "rm", "-f", "-t", "0", self.container]
        try:
            subprocess.run(argv, capture_output=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired):
            try:  # finish the removal in the background; the run goes on to write its report
                subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                pass


def default_image() -> str:
    """``REPRO_SANDBOX_IMAGE``, else the full image when it has been built, else the slim one."""
    if os.environ.get("REPRO_SANDBOX_IMAGE"):
        return os.environ["REPRO_SANDBOX_IMAGE"]
    try:
        found = subprocess.run(["podman", "image", "exists", FULL_IMAGE], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return DEFAULT_IMAGE
    return FULL_IMAGE if found.returncode == 0 else DEFAULT_IMAGE


def make_backend(task: Task, work: Path, writer: RunWriter, deadline: float) -> tuple[LoggingShellBackend, str | None]:
    """Start the sandbox ``REPRO_SANDBOX`` asks for. Returns it and a warning, if it had to fall back."""
    choice = os.environ.get("REPRO_SANDBOX", "auto").lower()
    if choice not in ("auto", "podman", "local"):
        raise SandboxError(f"REPRO_SANDBOX must be auto, podman or local, not '{choice}'")
    if choice == "local" or (choice == "auto" and not shutil.which("podman")):
        return LoggingShellBackend(work, writer, deadline=deadline), None
    image = default_image()
    try:
        return PodmanShellBackend(work, writer, deadline=deadline, image=image, network=task.network), None
    except SandboxError as exc:
        if choice == "podman":
            raise
        warning = f"{exc}. Falling back to the local shell, which has no isolation."
        return LoggingShellBackend(work, writer, deadline=deadline), warning


# -- did the run change the paper's own files? ---------------------------------------


_CACHE_DIRS = {"__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".Rproj.user"}


def _is_cache(path: Path) -> bool:
    """Compiled or editor caches that running the code rewrites; they are not the paper's source."""
    return path.suffix in (".pyc", ".pyo") or any(part in _CACHE_DIRS for part in path.parts)


def snapshot(repo: Path) -> dict[str, str]:
    """A fingerprint of every file that came with the repository."""
    marks: dict[str, str] = {}
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or path.is_symlink() or _is_cache(path):
            continue
        stat = path.stat()
        if stat.st_size <= _HASH_LIMIT:
            marks[str(path.relative_to(repo))] = hashlib.sha1(path.read_bytes()).hexdigest()
        else:
            marks[str(path.relative_to(repo))] = f"size{stat.st_size}-mtime{stat.st_mtime_ns}"
    return marks


def changed_files(repo: Path, before: dict[str, str]) -> list[dict[str, Any]]:
    """Original files that were modified or deleted since ``before``. New files are not listed."""
    after = snapshot(repo)
    changes = []
    for rel, mark in before.items():
        if rel not in after:
            changes.append({"path": f"repo/{rel}", "change": "deleted"})
        elif after[rel] != mark:
            changes.append({"path": f"repo/{rel}", "change": "modified"})
    return changes
