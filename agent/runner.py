"""Runs one task from start to report.json."""

from __future__ import annotations

import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from langgraph.types import Command

from agent.deep import MEMORY_FILE, MEMORY_HEADER, SKILLS_DIR, EventMapper, approval_request, build_agent
from agent.rundir import APPROVAL_TIMEOUT_S, RunWriter
from agent.sandbox import LoggingShellBackend, make_workdir
from agent.task import Findings, Task

DEFAULT_MODEL = "anthropic:claude-opus-5-5"

# Any one of the listed variables is enough for that provider.
_KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


class ConfigError(RuntimeError):
    """The run can't start (no model key, bad task). Exits non-zero before any event is written."""


class RunTimeout(Exception):
    """The task's limits.max_minutes is used up."""


def resolve_model(task: Task) -> tuple[Any, str]:
    """Return (model for create_deep_agent, label for the run_started event)."""
    name = os.environ.get("REPRO_MODEL", DEFAULT_MODEL)
    if name == "scripted":
        from agent.scripted import scripted_model_for

        return scripted_model_for(task), "scripted (offline replay, no LLM)"
    provider = name.split(":", 1)[0]
    wanted = _KEYS.get(provider, ())
    if wanted and not any(os.environ.get(var) for var in wanted):
        raise ConfigError(
            f"{name} needs {' or '.join(wanted)} in the environment or in .env at the repo root. "
            "Set it, pick another model with REPRO_MODEL, or use REPRO_MODEL=scripted for the offline toy run."
        )
    from langchain.chat_models import init_chat_model

    return init_chat_model(name, max_tokens=16000), name


def _memory_dir() -> Path:
    """Where fixes remembered across runs live; created with an empty list on first use."""
    path = Path(os.environ.get("REPRO_MEMORY_DIR") or Path(__file__).resolve().parent / ".memory")
    path.mkdir(parents=True, exist_ok=True)
    fixes = path / "fixes.md"
    if not fixes.exists():
        fixes.write_text(MEMORY_HEADER, encoding="utf-8")
    return path


def run_task(task_dir: Path | str, run_dir: Path | str, *, auto_approve: bool = False) -> int:
    """Run the task and write the run directory. Returns the process exit code."""
    task = Task.load(task_dir)
    model, model_label = resolve_model(task)  # may raise ConfigError before anything is written
    run_dir = Path(run_dir)
    run_id = run_dir.resolve().name
    writer = RunWriter(
        run_dir,
        auto_approve=auto_approve,
        approval_timeout_s=float(os.environ.get("REPRO_APPROVAL_TIMEOUT", APPROVAL_TIMEOUT_S)),
    )
    findings = Findings(task, writer)
    started = time.monotonic()
    deadline = started + task.max_minutes * 60
    work = make_workdir(task, run_id)
    backend = LoggingShellBackend(work, writer, deadline=deadline)
    mapper = EventMapper(writer, backend)
    writer.event("run_started", {"task_id": task.task_id, "run_id": run_id, "model": model_label})
    memory_dir = _memory_dir()
    remembered = sum(1 for line in (memory_dir / "fixes.md").read_text(encoding="utf-8").splitlines() if line.startswith("- "))
    if remembered:
        note = f"{remembered} fix{'es' if remembered != 1 else ''} from earlier runs loaded into the agent's instructions"
        writer.event("memory_read", {"path": MEMORY_FILE, "note": note})

    rejected: list[str] = []
    why_missing = "the agent finished without answering it"
    try:
        # The agent gets a throwaway copy of the skills, so it can't change the ones in this repository.
        skills_dir = work.with_name(work.name + "-skills")
        shutil.copytree(SKILLS_DIR, skills_dir)
        agent = build_agent(model, backend, findings, memory_dir, skills_dir)
        _drive(agent, task, run_id, writer, mapper, deadline, rejected, work)
        if backend.out_of_time or time.monotonic() > deadline:
            raise RunTimeout
        if findings.missing() and rejected:
            status = "rejected"
            why_missing = f"approval {', '.join(rejected)} was rejected and the run could not continue without it"
        elif findings.answers:
            status = "completed"
        else:
            status = "failed"
            why_missing = "the agent gave up without an answer"
    except RunTimeout:
        status = "timeout"
        why_missing = f"the run went over its {task.max_minutes:g} minute limit"
        writer.event("error", {"message": why_missing, "fatal": True})
    except Exception as exc:  # report the failure instead of crashing: exit code 0 means a report exists
        traceback.print_exc()
        status = "failed"
        why_missing = f"the run stopped on an error: {type(exc).__name__}: {exc}"
        writer.event("error", {"message": why_missing[:2000], "fatal": True})

    writer.event("run_finished", {"status": status})
    writer.write_report(
        findings.report(
            run_id=run_id,
            status=status,
            wall_seconds=time.monotonic() - started,
            tokens=mapper.tokens or None,
            why_missing=why_missing,
        )
    )
    writer.close()
    if os.environ.get("REPRO_KEEP_WORK"):
        print(f"workspace kept at {work}", file=sys.stderr)
    else:
        shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(work.with_name(work.name + "-skills"), ignore_errors=True)
    print(f"{status}: report written to {run_dir}/report.json")
    return 0


def _drive(
    agent: Any,
    task: Task,
    run_id: str,
    writer: RunWriter,
    mapper: EventMapper,
    deadline: float,
    rejected: list[str],
    work: Path,
) -> None:
    """Stream the agent, pausing at each approval until the run ends."""
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 400}
    payload: Any = {"messages": [{"role": "user", "content": task.prompt()}]}
    while True:
        interrupts: dict[str, Any] = {}  # by id: a subagent's interrupt can surface at more than one level
        for namespace, chunk in agent.stream(payload, config, stream_mode="updates", subgraphs=True):
            mapper.handle(namespace, chunk)
            for interrupt in chunk.get("__interrupt__") or ():
                interrupts.setdefault(getattr(interrupt, "id", None) or str(id(interrupt)), interrupt)
            if time.monotonic() > deadline:
                raise RunTimeout
        if not interrupts:
            return
        resume: dict[str, Any] = {}
        for interrupt_id, interrupt in interrupts.items():
            decisions: list[dict[str, Any]] = []
            resume[interrupt_id] = {"decisions": decisions}
            for action in interrupt.value.get("action_requests", []):
                request = approval_request(action, work)
                decision = writer.request_approval(
                    request["kind"],
                    request["summary"],
                    command=request["command"],
                    diff=request["diff"],
                    agent=mapper.current_agent(),
                    deadline=deadline,
                )
                if decision["decision"] == "approve":
                    decisions.append({"type": "approve"})
                else:
                    rejected.append(decision["id"])
                    who = "Nobody answered the approval request in time" if decision["by"] == "timeout" else "A human rejected this"
                    note = f" Their note: {decision['note']}" if decision["note"] and decision["by"] != "timeout" else ""
                    decisions.append({"type": "reject", "message": f"{who}, so it was not done.{note}"})
        if time.monotonic() > deadline:
            raise RunTimeout
        # One pending interrupt resumes with its value alone; several need the map by interrupt id.
        payload = Command(resume=next(iter(resume.values())) if len(resume) == 1 else resume)
