"""Where the paper's code runs.

First slice: deepagents' ``LocalShellBackend`` on a private copy of the task's repo.
It runs commands as this user with no isolation, so a determined model could read
other files on the disk. That is acceptable for the toy task and plumbing; scored
runs need a real sandbox (see BACKLOG.md).
"""

from __future__ import annotations

import math
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse

from agent.rundir import RunWriter
from agent.task import Task

# Commands that take longer than this need an approval (contract 3.1: "more than about a minute").
SHORT_TIMEOUT_S = int(os.environ.get("REPRO_SHORT_TIMEOUT", "90"))

# Passed through to commands so installs work behind a proxy. API keys are deliberately not.
_PASS_ENV = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy", "LANG", "TZ")


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


def command_env(work: Path) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(work / ".home"),
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUNBUFFERED": "1",
    }
    for name in _PASS_ENV:
        if os.environ.get(name):
            env[name] = os.environ[name]
    env.setdefault("LANG", "C.UTF-8")
    return env


class LoggingShellBackend(LocalShellBackend):
    """Local shell that saves every command's full output into the run directory's logs/."""

    def __init__(self, work: Path, writer: RunWriter, *, deadline: float | None = None) -> None:
        super().__init__(
            root_dir=work,
            virtual_mode=True,
            timeout=SHORT_TIMEOUT_S,
            max_output_bytes=1_000_000,
            env=command_env(work),
            inherit_env=False,
        )
        self._writer = writer
        self._deadline = deadline  # time.monotonic() value for the whole run
        self.commands: list[CommandRecord] = []
        self.out_of_time = False  # set when a command was refused because the run's time is used up

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        effective = timeout if timeout is not None else SHORT_TIMEOUT_S
        if self._deadline is not None:
            # Never let one command outlive the run's time budget.
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                self.out_of_time = True
                return ExecuteResponse(output="Error: the run's time limit is used up; nothing was run.", exit_code=124)
            effective = max(1, min(effective, math.ceil(remaining)))
        response = super().execute(command, timeout=effective)
        text = f"$ {command}\n{response.output}\n"
        log = self._writer.save_log(command, text)
        # Same file inside the workspace, so the agent can grep it as /logs/...
        mirror = Path(self.cwd) / log
        mirror.parent.mkdir(exist_ok=True)
        mirror.write_text(text, encoding="utf-8")
        self.commands.append(CommandRecord(command, response.exit_code, log, response.output))
        return response

    def take_record(self, command: str) -> CommandRecord | None:
        """The oldest unclaimed record of ``command``, removed from the list."""
        for i, record in enumerate(self.commands):
            if record.command == command:
                return self.commands.pop(i)
        return None
