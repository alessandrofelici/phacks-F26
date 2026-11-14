"""Shared paths and helpers for the harness (Role B). Standard library only."""
from __future__ import annotations

import datetime
import json
import os
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_TASKS = ROOT / "contract" / "fixtures" / "tasks"
GOLDEN_RUN = ROOT / "contract" / "fixtures" / "runs" / "golden"
TASKS = ROOT / "tasks"
RUNS = ROOT / "runs"
ANSWERS = ROOT / "harness" / "answers"

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def task_dir(task_id: str) -> Path | None:
    """Find a task by id. Local tasks/ wins over the fixtures."""
    if not ID_RE.match(task_id or ""):
        return None
    for base in (TASKS, FIXTURE_TASKS):
        candidate = base / task_id
        if (candidate / "task.json").is_file():
            return candidate
    return None


def list_tasks() -> list[dict]:
    seen: dict[str, dict] = {}
    for base in (FIXTURE_TASKS, TASKS):
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            task = read_json(path / "task.json")
            if isinstance(task, dict) and task.get("task_id") == path.name:
                seen[path.name] = task
    return list(seen.values())


def new_run_id() -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"r-{stamp}-{secrets.token_hex(2)}"


def run_dir(run_id: str) -> Path | None:
    if not RUN_ID_RE.match(run_id or ""):
        return None
    return RUNS / run_id


def read_events(rdir: Path, since: int = 0) -> list[dict]:
    """Events with seq > since. Skips a half-written last line."""
    path = rdir / "events.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict) and isinstance(ev.get("seq"), int) and ev["seq"] > since:
            events.append(ev)
    return events


def read_approvals(rdir: Path) -> list[dict]:
    """Every approval request in the run, with its decision if there is one."""
    adir = rdir / "approvals"
    out = []
    if not adir.is_dir():
        return out
    for path in sorted(adir.glob("*.request.json"), key=lambda p: p.stat().st_mtime):
        req = read_json(path)
        if not isinstance(req, dict):
            continue
        name = path.name[: -len(".request.json")]
        out.append({"request": req, "decision": read_json(adir / f"{name}.decision.json")})
    return out
