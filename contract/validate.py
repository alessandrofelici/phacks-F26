"""Referee for contract v1. Standard library only.

    python contract/validate.py task <task_dir>
    python contract/validate.py run  <run_dir> [--task <task_dir>] [--partial]

Exit code 0 = valid. Otherwise prints one line per problem and exits 1.
Unknown fields and unknown event types are allowed (see CONTRACT.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = 1
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
SOURCES = {"fixture", "core-bench", "arxiv"}
QUESTION_TYPES = {"number", "string", "list"}
STATUSES = {"completed", "failed", "timeout", "rejected"}
CONFIDENCES = {"high", "medium", "low"}
STAGES = {"read", "env", "data", "run", "extract", "other"}
APPROVAL_KINDS = {"long_run", "edit_source", "publish"}
DECISIONS = {"approve", "reject"}
DECIDERS = {"human", "auto", "timeout"}
TODO_STATUSES = {"pending", "in_progress", "completed"}
# Optional fields beyond v1 (contract/CHANGES.md, "plan-first runs"): checked only when present.
PLAN_PATHS = {"full", "scaled", "not_verifiable"}

# Required keys of `data` per event type. Unknown types are accepted.
EVENT_DATA = {
    "run_started": ["task_id", "run_id"],
    "todo_updated": ["todos"],
    "subagent_started": ["name", "task"],
    "subagent_finished": ["name", "summary"],
    "tool_call": ["tool", "summary", "ok"],
    "approval_requested": ["id", "kind", "summary"],
    "approval_resolved": ["id", "decision", "by"],
    "memory_read": ["path", "note"],
    "memory_written": ["path", "note"],
    "answer_found": ["question_id", "value"],
    "error": ["message", "fatal"],
    "run_finished": ["status"],
}


def _load(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path}: missing")
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: not valid JSON ({exc})")
    return None


def _value_matches(value, qtype: str) -> bool:
    if value is None:
        return True
    if qtype == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if qtype == "string":
        return isinstance(value, str)
    if qtype == "list":
        return isinstance(value, list)
    return True


def validate_task(task_dir: Path) -> list[str]:
    errors: list[str] = []
    task_dir = Path(task_dir)
    task = _load(task_dir / "task.json", errors)
    if not isinstance(task, dict):
        if task is not None:
            errors.append("task.json: must be an object")
        return errors

    def need(key, check, what):
        if key not in task:
            errors.append(f"task.json: missing '{key}'")
        elif not check(task[key]):
            errors.append(f"task.json: '{key}' must be {what}")

    need("contract_version", lambda v: v == VERSION, str(VERSION))
    need("task_id", lambda v: isinstance(v, str) and bool(ID_RE.match(v)), "lowercase letters, digits and dashes")
    need("title", lambda v: isinstance(v, str) and bool(v), "a non-empty string")
    need("source", lambda v: v in SOURCES, f"one of {sorted(SOURCES)}")
    need("paper_url", lambda v: v is None or isinstance(v, str), "a string or null")
    need("instructions", lambda v: v is None or isinstance(v, str), "a string or null")
    need("questions", lambda v: isinstance(v, list) and len(v) > 0, "a non-empty list")
    need("limits", lambda v: isinstance(v, dict), "an object")

    if isinstance(task.get("task_id"), str) and task["task_id"] != task_dir.resolve().name:
        errors.append(f"task.json: task_id '{task['task_id']}' must equal the directory name '{task_dir.resolve().name}'")

    seen = set()
    for i, q in enumerate(task.get("questions") or []):
        where = f"task.json: questions[{i}]"
        if not isinstance(q, dict):
            errors.append(f"{where} must be an object")
            continue
        if not isinstance(q.get("id"), str) or not q.get("id"):
            errors.append(f"{where}: missing 'id'")
        elif q["id"] in seen:
            errors.append(f"{where}: duplicate id '{q['id']}'")
        else:
            seen.add(q["id"])
        if not isinstance(q.get("text"), str) or not q.get("text"):
            errors.append(f"{where}: missing 'text'")
        if q.get("type") not in QUESTION_TYPES:
            errors.append(f"{where}: 'type' must be one of {sorted(QUESTION_TYPES)}")
        if "needs_figure" in q and not isinstance(q["needs_figure"], bool):
            errors.append(f"{where}: 'needs_figure' must be true or false")

    limits = task.get("limits")
    if isinstance(limits, dict):
        mm = limits.get("max_minutes")
        if not isinstance(mm, (int, float)) or isinstance(mm, bool) or mm <= 0:
            errors.append("task.json: limits.max_minutes must be a positive number")
        for key in ("gpu", "network"):
            if not isinstance(limits.get(key), bool):
                errors.append(f"task.json: limits.{key} must be true or false")

    if not (task_dir / "repo").is_dir():
        errors.append(f"{task_dir}/repo: missing directory")
    for forbidden in ("answers.json", "answer_key.json"):
        if (task_dir / forbidden).exists():
            errors.append(f"{task_dir}/{forbidden}: the answer key must never be inside a task directory")
    return errors


def _validate_events(run_dir: Path, errors: list[str]) -> list[dict]:
    path = run_dir / "events.jsonl"
    events: list[dict] = []
    if not path.exists():
        errors.append(f"{path}: missing")
        return events
    expected = 1
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        where = f"events.jsonl line {n}"
        try:
            ev = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{where}: not valid JSON ({exc})")
            continue
        if not isinstance(ev, dict):
            errors.append(f"{where}: must be an object")
            continue
        events.append(ev)
        if ev.get("seq") != expected:
            errors.append(f"{where}: seq is {ev.get('seq')!r}, expected {expected}")
        expected += 1
        if not isinstance(ev.get("ts"), str) or not TS_RE.match(ev.get("ts", "")):
            errors.append(f"{where}: 'ts' must be UTC ISO 8601 ending in Z")
        if not isinstance(ev.get("agent"), str) or not ev.get("agent"):
            errors.append(f"{where}: missing 'agent'")
        etype = ev.get("type")
        if not isinstance(etype, str) or not etype:
            errors.append(f"{where}: missing 'type'")
            continue
        data = ev.get("data")
        if not isinstance(data, dict):
            errors.append(f"{where}: 'data' must be an object")
            continue
        for key in EVENT_DATA.get(etype, []):
            if key not in data:
                errors.append(f"{where}: {etype} needs data.{key}")
        if etype == "todo_updated" and isinstance(data.get("todos"), list):
            for j, todo in enumerate(data["todos"]):
                if not isinstance(todo, dict) or not isinstance(todo.get("content"), str):
                    errors.append(f"{where}: todos[{j}] needs 'content'")
                elif todo.get("status") not in TODO_STATUSES:
                    errors.append(f"{where}: todos[{j}].status must be one of {sorted(TODO_STATUSES)}")
        if etype == "tool_call" and "ok" in data and not isinstance(data["ok"], bool):
            errors.append(f"{where}: data.ok must be true or false")
        if etype == "run_finished" and data.get("status") not in STATUSES:
            errors.append(f"{where}: data.status must be one of {sorted(STATUSES)}")
    if events and events[0].get("type") != "run_started":
        errors.append("events.jsonl: the first event must be run_started")
    return events


def _validate_approvals(run_dir: Path, events: list[dict], errors: list[str]) -> None:
    adir = run_dir / "approvals"
    requests: dict[str, dict] = {}
    if adir.is_dir():
        for path in sorted(adir.glob("*.request.json")):
            req = _load(path, errors)
            if not isinstance(req, dict):
                continue
            rid = req.get("id")
            name = path.name[: -len(".request.json")]
            if rid != name:
                errors.append(f"{path.name}: id {rid!r} must equal the file name '{name}'")
            if not isinstance(rid, str) or not re.match(r"^[a-z0-9-]+$", rid or ""):
                errors.append(f"{path.name}: 'id' must be lowercase letters, digits and dashes")
            if req.get("kind") not in APPROVAL_KINDS:
                errors.append(f"{path.name}: 'kind' must be one of {sorted(APPROVAL_KINDS)}")
            if not isinstance(req.get("summary"), str) or not req.get("summary"):
                errors.append(f"{path.name}: missing 'summary'")
            for key in ("command", "diff"):
                if key not in req or not (req[key] is None or isinstance(req[key], str)):
                    errors.append(f"{path.name}: '{key}' must be a string or null")
            requests[name] = req
        for path in sorted(adir.glob("*.decision.json")):
            dec = _load(path, errors)
            if not isinstance(dec, dict):
                continue
            name = path.name[: -len(".decision.json")]
            if name not in requests:
                errors.append(f"{path.name}: decision without a request")
            if dec.get("id") != name:
                errors.append(f"{path.name}: id {dec.get('id')!r} must equal the file name '{name}'")
            if dec.get("decision") not in DECISIONS:
                errors.append(f"{path.name}: 'decision' must be one of {sorted(DECISIONS)}")
            if dec.get("by") not in DECIDERS:
                errors.append(f"{path.name}: 'by' must be one of {sorted(DECIDERS)}")
    for ev in events:
        if ev.get("type") == "approval_requested":
            rid = (ev.get("data") or {}).get("id")
            if rid not in requests:
                errors.append(f"events.jsonl seq {ev.get('seq')}: approval_requested '{rid}' has no approvals/{rid}.request.json")


def _validate_report(run_dir: Path, task: dict | None, events: list[dict], errors: list[str]) -> None:
    report = _load(run_dir / "report.json", errors)
    if not isinstance(report, dict):
        if report is not None:
            errors.append("report.json: must be an object")
        return
    if report.get("contract_version") != VERSION:
        errors.append(f"report.json: contract_version must be {VERSION}")
    for key in ("task_id", "run_id"):
        if not isinstance(report.get(key), str) or not report.get(key):
            errors.append(f"report.json: missing '{key}'")
    if report.get("status") not in STATUSES:
        errors.append(f"report.json: 'status' must be one of {sorted(STATUSES)}")

    answers = report.get("answers")
    answered: dict[str, dict] = {}
    if not isinstance(answers, list):
        errors.append("report.json: 'answers' must be a list")
    else:
        for i, ans in enumerate(answers):
            where = f"report.json: answers[{i}]"
            if not isinstance(ans, dict):
                errors.append(f"{where} must be an object")
                continue
            qid = ans.get("question_id")
            if not isinstance(qid, str):
                errors.append(f"{where}: missing 'question_id'")
                continue
            if qid in answered:
                errors.append(f"{where}: duplicate answer for '{qid}'")
            answered[qid] = ans
            if "value" not in ans:
                errors.append(f"{where}: missing 'value' (use null when there is no answer)")
            if "evidence" not in ans:
                errors.append(f"{where}: missing 'evidence' (use null when there is none)")
            elif ans["evidence"] is not None:
                ev = ans["evidence"]
                if not isinstance(ev, dict) or not isinstance(ev.get("file"), str) or not isinstance(ev.get("quote"), str):
                    errors.append(f"{where}: evidence needs string 'file' and 'quote'")
            if ans.get("value") is not None and ans.get("confidence") not in CONFIDENCES:
                errors.append(f"{where}: 'confidence' must be one of {sorted(CONFIDENCES)}")
            if "interval" in ans:
                iv = ans["interval"]
                if not (isinstance(iv, list) and len(iv) == 2 and all(isinstance(b, (int, float)) and not isinstance(b, bool) for b in iv)
                        and iv[0] <= iv[1]):
                    errors.append(f"{where}: 'interval' must be [low, high], two numbers with low <= high")
            if "no_answer" in ans:
                na = ans["no_answer"]
                if ans.get("value") is not None:
                    errors.append(f"{where}: 'no_answer' only goes with a null value")
                if not isinstance(na, dict) or not isinstance(na.get("category"), str) or not isinstance(na.get("reason"), str):
                    errors.append(f"{where}: 'no_answer' needs string 'category' and 'reason'")

    obstacles = report.get("obstacles")
    if not isinstance(obstacles, list):
        errors.append("report.json: 'obstacles' must be a list")
    else:
        for i, ob in enumerate(obstacles):
            where = f"report.json: obstacles[{i}]"
            if not isinstance(ob, dict):
                errors.append(f"{where} must be an object")
                continue
            if ob.get("stage") not in STAGES:
                errors.append(f"{where}: 'stage' must be one of {sorted(STAGES)}")
            if not isinstance(ob.get("summary"), str) or not ob.get("summary"):
                errors.append(f"{where}: missing 'summary'")
            if "fix" not in ob or not (ob["fix"] is None or isinstance(ob["fix"], str)):
                errors.append(f"{where}: 'fix' must be a string or null")
            if not isinstance(ob.get("resolved"), bool):
                errors.append(f"{where}: 'resolved' must be true or false")

    if "plan" in report:
        plan = report["plan"]
        if not isinstance(plan, dict) or plan.get("path") not in PLAN_PATHS:
            errors.append(f"report.json: 'plan.path' must be one of {sorted(PLAN_PATHS)}")

    usage = report.get("usage")
    if not isinstance(usage, dict) or not isinstance(usage.get("wall_seconds"), (int, float)):
        errors.append("report.json: usage.wall_seconds must be a number")
    if "trace_url" not in report or not (report["trace_url"] is None or isinstance(report["trace_url"], str)):
        errors.append("report.json: 'trace_url' must be a string or null")

    if task:
        if report.get("task_id") != task.get("task_id"):
            errors.append(f"report.json: task_id '{report.get('task_id')}' doesn't match the task '{task.get('task_id')}'")
        questions = {q["id"]: q for q in task.get("questions", []) if isinstance(q, dict) and "id" in q}
        for qid, q in questions.items():
            if qid not in answered:
                errors.append(f"report.json: no answer entry for question '{qid}' (every question needs one, null if unanswered)")
            elif not _value_matches(answered[qid].get("value"), q.get("type", "")):
                errors.append(f"report.json: answer to '{qid}' must be a {q.get('type')} or null")
        for qid in answered:
            if qid not in questions:
                errors.append(f"report.json: answer for unknown question '{qid}'")

    if events:
        last = events[-1]
        if last.get("type") != "run_finished":
            errors.append("events.jsonl: the last event must be run_finished once report.json exists")
        elif (last.get("data") or {}).get("status") != report.get("status"):
            errors.append("events.jsonl: run_finished status differs from report.json status")


def validate_run(run_dir: Path, task_dir: Path | None = None, partial: bool = False) -> list[str]:
    errors: list[str] = []
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return [f"{run_dir}: not a directory"]
    task = None
    if task_dir is not None:
        task_errors = validate_task(Path(task_dir))
        errors.extend(f"(task) {e}" for e in task_errors)
        if not task_errors:
            task = json.loads((Path(task_dir) / "task.json").read_text(encoding="utf-8"))
    events = _validate_events(run_dir, errors)
    _validate_approvals(run_dir, events, errors)
    if (run_dir / "report.json").exists():
        _validate_report(run_dir, task, events, errors)
    elif not partial:
        errors.append(f"{run_dir}/report.json: missing (pass --partial for a run that is still going)")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a task or run directory against contract v1.")
    sub = parser.add_subparsers(dest="kind", required=True)
    p_task = sub.add_parser("task")
    p_task.add_argument("task_dir", type=Path)
    p_run = sub.add_parser("run")
    p_run.add_argument("run_dir", type=Path)
    p_run.add_argument("--task", type=Path, default=None)
    p_run.add_argument("--partial", action="store_true")
    args = parser.parse_args(argv)

    if args.kind == "task":
        errors = validate_task(args.task_dir)
        target = args.task_dir
    else:
        errors = validate_run(args.run_dir, args.task, args.partial)
        target = args.run_dir
    if errors:
        for err in errors:
            print(f"FAIL {err}")
        print(f"{len(errors)} problem(s) in {target}")
        return 1
    print(f"OK {target} is valid for contract v{VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
