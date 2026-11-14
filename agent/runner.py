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

from agent import models
from agent.deep import (
    MEMORY_FILE,
    MEMORY_HEADER,
    SKILLS_DIR,
    EventMapper,
    approval_request,
    build_agent,
)
from agent.rundir import APPROVAL_TIMEOUT_S, RunWriter
from agent.sandbox import (
    SandboxError,
    changed_files,
    make_backend,
    make_workdir,
    remove_workdir,
    snapshot,
)
from agent.task import Findings, Task
from agent.tracing import run_trace


class ConfigError(RuntimeError):
    """The run can't start (no model key, bad task). Exits non-zero before any event is written."""


class RunTimeout(Exception):
    """The task's limits.max_minutes is used up."""


def resolve_models(task: Task) -> tuple[Any, Any, str]:
    """Return (main model, subagent model or None, label for the run_started event)."""
    name = models.chosen_model()
    if name == "scripted":
        from agent.scripted import scripted_model_for

        return scripted_model_for(task), None, "scripted (offline replay, no LLM)"
    sub_name = models.chosen_subagent_model()
    try:
        main = models.make_model(name)
        sub = models.make_model(sub_name) if sub_name and sub_name != name else None
    except models.ModelConfigError as exc:
        raise ConfigError(str(exc)) from exc
    return main, sub, name + (f" (subagents: {sub_name})" if sub is not None else "")


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
    model, subagent_model, model_label = resolve_models(task)  # may raise ConfigError before anything is written
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
    originals = snapshot(work / "repo")
    try:
        backend, sandbox_warning = make_backend(task, work, writer, deadline)
    except SandboxError as exc:
        writer.close()
        remove_workdir(work)
        raise ConfigError(str(exc)) from exc
    mapper = EventMapper(writer, backend)
    # `sandbox` is an optional field beyond contract v1; readers ignore what they don't know.
    writer.event("run_started", {"task_id": task.task_id, "run_id": run_id, "model": model_label, "sandbox": backend.label})
    if sandbox_warning:
        writer.event("error", {"message": sandbox_warning, "fatal": False})
    memory_dir = _memory_dir()
    remembered = sum(1 for line in (memory_dir / "fixes.md").read_text(encoding="utf-8").splitlines() if line.startswith("- "))
    if remembered:
        note = f"{remembered} fix{'es' if remembered != 1 else ''} from earlier runs loaded into the agent's instructions"
        writer.event("memory_read", {"path": MEMORY_FILE, "note": note})

    rejected: list[str] = []
    approved_edits: set[str] = set()
    why_missing = "the agent finished without answering it"
    trace: dict[str, Any] = {"url": None}
    try:
        # The agent gets a throwaway copy of the skills, so it can't change the ones in this repository.
        skills_dir = work.with_name(work.name + "-skills")
        shutil.copytree(SKILLS_DIR, skills_dir)
        agent = build_agent(model, backend, findings, memory_dir, skills_dir, subagent_model)
        with run_trace(task.task_id, run_id, model_label) as trace:
            _drive(agent, task, run_id, writer, mapper, deadline, rejected, approved_edits, work)
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
    except Exception as exc:  # noqa: BLE001 - report the failure instead of crashing: exit 0 means a report exists
        traceback.print_exc()
        status = "failed"
        why_missing = f"the run stopped on an error: {type(exc).__name__}: {exc}"
        writer.event("error", {"message": why_missing[:2000], "fatal": True})

    backend.close()
    # Did anything change the files that came with the repository? File-tool edits were
    # approved one by one; a shell command (`sed -i`, a script that rewrites its inputs) is
    # only caught here.
    changes = changed_files(work / "repo", originals)
    for change in changes:
        change["approved"] = change["path"] in approved_edits
    unapproved = [c["path"] for c in changes if not c["approved"]]
    if unapproved:
        shown = ", ".join(unapproved[:5]) + (f" and {len(unapproved) - 5} more" if len(unapproved) > 5 else "")
        findings.record_obstacle(
            "other",
            f"Files that came with the repository were changed during the run without an approval: {shown}. "
            "Results may not come from the code as published.",
            None,
            False,
        )
        writer.event("source_changed", {"files": changes})  # event type beyond contract v1

    writer.event("run_finished", {"status": status})
    report = findings.report(
        run_id=run_id,
        status=status,
        wall_seconds=time.monotonic() - started,
        tokens=mapper.tokens or None,
        why_missing=why_missing,
        trace_url=trace.get("url"),
    )
    report["sandbox"] = backend.label  # optional fields beyond contract v1
    report["source_changes"] = changes
    writer.write_report(report)
    writer.close()
    if os.environ.get("REPRO_KEEP_WORK"):
        print(f"workspace kept at {work}", file=sys.stderr)
    else:
        remove_workdir(work)
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
    approved_edits: set[str],
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
                    if request["kind"] == "edit_source":
                        approved_edits.add(str((action.get("args") or {}).get("file_path") or "").lstrip("/"))
                else:
                    rejected.append(decision["id"])
                    who = "Nobody answered the approval request in time" if decision["by"] == "timeout" else "A human rejected this"
                    note = f" Their note: {decision['note']}" if decision["note"] and decision["by"] != "timeout" else ""
                    decisions.append({"type": "reject", "message": f"{who}, so it was not done.{note}"})
        if time.monotonic() > deadline:
            raise RunTimeout
        # One pending interrupt resumes with its value alone; several need the map by interrupt id.
        payload = Command(resume=next(iter(resume.values())) if len(resume) == 1 else resume)
