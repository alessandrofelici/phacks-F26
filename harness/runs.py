"""Start, watch and stop agent runs. Used by the web server and the batch runner."""
from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .common import ROOT, RUNS, new_run_id, now_iso, read_approvals, read_events, read_json, run_dir, task_dir, write_json_atomic
from .score import score_run

AGENT_KINDS = ("real", "fake")
_procs: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def real_agent_available() -> bool:
    return bool(os.environ.get("REPRO_AGENT_CMD")) or (ROOT / "agent" / "run.py").is_file() or (ROOT / "agent" / "run" / "__main__.py").is_file()


def agent_command(kind: str) -> list[str]:
    if kind == "fake":
        return [sys.executable, "-m", "harness.fake_agent"]
    custom = os.environ.get("REPRO_AGENT_CMD")
    if custom:
        return shlex.split(custom)
    return [sys.executable, "-m", "agent.run"]


def start_run(task_id: str, kind: str = "real", auto_approve: bool = False, extra_args: list[str] | None = None) -> str:
    tdir = task_dir(task_id)
    if tdir is None:
        raise ValueError(f"unknown task '{task_id}'")
    if kind not in AGENT_KINDS:
        raise ValueError(f"agent must be one of {AGENT_KINDS}")
    if kind == "real" and not real_agent_available():
        raise ValueError("the real agent isn't in this checkout yet (no agent/run.py); use the fake agent")

    run_id = new_run_id()
    rdir = RUNS / run_id
    (rdir / ".harness").mkdir(parents=True)
    cmd = agent_command(kind) + ["--task", str(tdir.relative_to(ROOT)), "--run", str(rdir.relative_to(ROOT))]
    if auto_approve:
        cmd.append("--auto-approve")
    cmd += extra_args or []

    log = open(rdir / ".harness" / "process.log", "wb")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    meta = {"run_id": run_id, "task_id": task_id, "agent": kind, "auto_approve": auto_approve,
            "command": cmd, "pid": proc.pid, "started": now_iso(), "started_epoch": time.time(),
            "exit_code": None, "ended": None, "stopped": False}
    write_json_atomic(rdir / ".harness" / "meta.json", meta)
    with _lock:
        _procs[run_id] = proc

    def waiter():
        code = proc.wait()
        log.close()
        current = read_json(rdir / ".harness" / "meta.json", meta)
        current.update({"exit_code": code, "ended": now_iso(), "ended_epoch": time.time()})
        write_json_atomic(rdir / ".harness" / "meta.json", current)
        with _lock:
            _procs.pop(run_id, None)

    threading.Thread(target=waiter, daemon=True).start()
    return run_id


def _alive(meta: dict) -> bool:
    if meta.get("exit_code") is not None:
        return False
    with _lock:
        proc = _procs.get(meta.get("run_id", ""))
    if proc is not None:
        return proc.poll() is None
    pid = meta.get("pid")
    if not pid:
        return False
    try:  # started by an earlier server process
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_run(run_id: str) -> bool:
    rdir = run_dir(run_id)
    meta = read_json(rdir / ".harness" / "meta.json") if rdir else None
    if not meta or not _alive(meta):
        return False
    meta["stopped"] = True
    write_json_atomic(rdir / ".harness" / "meta.json", meta)
    try:
        os.killpg(meta["pid"], signal.SIGTERM)
    except OSError:
        return False
    return True


def decide(run_id: str, approval_id: str, decision: str, note: str = "") -> None:
    rdir = run_dir(run_id)
    if rdir is None or not rdir.is_dir():
        raise ValueError("unknown run")
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be approve or reject")
    adir = rdir / "approvals"
    if not (adir / f"{approval_id}.request.json").is_file() or "/" in approval_id or ".." in approval_id:
        raise ValueError("unknown approval")
    if (adir / f"{approval_id}.decision.json").exists():
        raise ValueError("already decided")
    write_json_atomic(adir / f"{approval_id}.decision.json", {"id": approval_id, "decision": decision, "note": note, "by": "human"})


def run_status(rdir: Path, meta: dict | None, report: dict | None, approvals: list[dict]) -> str:
    """running | waiting_approval | completed | failed | timeout | rejected | crashed | stopped"""
    if isinstance(report, dict) and report.get("status"):
        return report["status"]
    if meta is None:
        return "crashed"  # a run directory we didn't start and that has no report
    if _alive(meta):
        return "waiting_approval" if any(a["decision"] is None for a in approvals) else "running"
    if meta.get("exit_code") is None and not meta.get("stopped"):
        # the process just exited and the waiter thread hasn't recorded it yet
        return "running" if time.time() - meta.get("started_epoch", 0) < 2 else "crashed"
    return "stopped" if meta.get("stopped") else "crashed"


def run_summary(rdir: Path) -> dict:
    meta = read_json(rdir / ".harness" / "meta.json")
    report = read_json(rdir / "report.json")
    approvals = read_approvals(rdir)
    status = run_status(rdir, meta, report, approvals)
    score = score_run(rdir) if isinstance(report, dict) else None
    task_id = (meta or {}).get("task_id") or (report or {}).get("task_id")
    return {"run_id": rdir.name, "task_id": task_id, "agent": (meta or {}).get("agent"),
            "status": status, "started": (meta or {}).get("started"), "ended": (meta or {}).get("ended"),
            "score": {"correct": score["correct"], "total": score["total"]} if score else None}


def run_detail(run_id: str, since: int = 0) -> dict | None:
    rdir = run_dir(run_id)
    if rdir is None or not rdir.is_dir():
        return None
    meta = read_json(rdir / ".harness" / "meta.json")
    report = read_json(rdir / "report.json")
    approvals = read_approvals(rdir)
    status = run_status(rdir, meta, report, approvals)
    finished = status not in ("running", "waiting_approval")
    tail = ""
    if status == "crashed":
        try:
            tail = (rdir / ".harness" / "process.log").read_text(encoding="utf-8", errors="replace")[-3000:]
        except OSError:
            pass
    return {"run_id": run_id, "task_id": (meta or {}).get("task_id") or (report or {}).get("task_id"),
            "meta": meta, "status": status, "events": read_events(rdir, since), "approvals": approvals,
            "report": report if isinstance(report, dict) else None,
            # the expected answers are only sent once the run is over
            "score": score_run(rdir) if finished else None,
            "process_log_tail": tail}


def list_runs() -> list[dict]:
    if not RUNS.is_dir():
        return []
    dirs = [p for p in RUNS.iterdir() if p.is_dir() and not p.name.startswith(".")]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [run_summary(p) for p in dirs]


def wait_for(run_id: str, timeout_s: float) -> str:
    """Block until the run is over (used by the batch runner). Returns the final status."""
    rdir = run_dir(run_id)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = run_summary(rdir)
        if summary["status"] not in ("running", "waiting_approval"):
            return summary["status"]
        time.sleep(1)
    stop_run(run_id)
    time.sleep(1)
    return "stopped"


_batch: subprocess.Popen | None = None


def batch_running() -> bool:
    return _batch is not None and _batch.poll() is None


def start_batch(kind: str) -> None:
    """Run `python -m harness.batch` in the background (one at a time)."""
    global _batch
    if kind not in AGENT_KINDS:
        raise ValueError(f"agent must be one of {AGENT_KINDS}")
    if kind == "real" and not real_agent_available():
        raise ValueError("the real agent isn't in this checkout yet (no agent/run.py); use the fake agent")
    if batch_running():
        raise ValueError("a batch is already running")
    RUNS.mkdir(exist_ok=True)
    log = open(RUNS / ".batch.log", "ab")
    _batch = subprocess.Popen([sys.executable, "-m", "harness.batch", "--agent", kind, "--label", "started from the UI"],
                              cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def list_batches() -> list[dict]:
    bdir = RUNS / ".batches"
    if not bdir.is_dir():
        return []
    out = [b for b in (read_json(p) for p in sorted(bdir.glob("*.json"), reverse=True)) if isinstance(b, dict)]
    return out[:30]
