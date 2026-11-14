"""A stand-in for Role A's agent, so the harness can be built and tested alone.

Same command line as the real one (contract section 3):

    python -m harness.fake_agent --task <task_dir> --run <run_dir> [--auto-approve]

It replays the golden run's events with delays and follows the approval
protocol for real (writes the request, waits for the decision). It calls no
model and runs no code. It only "solves" the toy task; for any other task it
reports a failure, which is useful for testing the failed state.

Extra flags (not part of the contract, for testing the UI):
    --speed N        divide every delay by N (default 4; 0 = no delays)
    --scenario X     ok | crash | wrong   (crash exits 1 mid-run with no report;
                     wrong reports a wrong q1)
It also imitates memory: once a run has written the numpy fix, later runs
reuse it and skip the failed install.
"""
from __future__ import annotations

import argparse
import os
import json
import sys
import time
from pathlib import Path

from .common import GOLDEN_RUN, RUNS, now_iso, read_events, read_json, write_json_atomic

MEMORY = RUNS / ".fake_memory.json"
APPROVAL_TIMEOUT_S = 600


class Run:
    def __init__(self, rdir: Path, speed: float):
        self.dir = rdir
        self.speed = speed
        self.seq = 0
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "approvals").mkdir(exist_ok=True)
        (self.dir / "logs").mkdir(exist_ok=True)
        self.events = open(self.dir / "events.jsonl", "a", encoding="utf-8")

    def emit(self, etype: str, agent: str, data: dict) -> None:
        self.seq += 1
        self.events.write(json.dumps({"seq": self.seq, "ts": now_iso(), "type": etype, "agent": agent, "data": data}) + "\n")
        self.events.flush()

    def wait(self, seconds: float) -> None:
        if self.speed > 0 and seconds > 0:
            time.sleep(seconds / self.speed)

    def approval(self, request: dict, auto: bool) -> dict:
        rid = request["id"]
        write_json_atomic(self.dir / "approvals" / f"{rid}.request.json", request)
        self.emit("approval_requested", "main", {"id": rid, "kind": request["kind"], "summary": request["summary"]})
        decision_path = self.dir / "approvals" / f"{rid}.decision.json"
        if auto:
            write_json_atomic(decision_path, {"id": rid, "decision": "approve", "note": "", "by": "auto"})
        deadline = time.time() + APPROVAL_TIMEOUT_S
        decision = None
        while time.time() < deadline:
            decision = read_json(decision_path)
            if isinstance(decision, dict) and decision.get("decision") in ("approve", "reject"):
                break
            decision = None
            time.sleep(0.5)
        if decision is None:
            decision = {"id": rid, "decision": "reject", "note": "no decision in 10 minutes", "by": "timeout"}
        self.emit("approval_resolved", "main", {"id": rid, "decision": decision["decision"], "by": decision.get("by", "human")})
        return decision

    def finish(self, report: dict) -> None:
        self.emit("run_finished", "main", {"status": report["status"]})
        self.events.close()
        write_json_atomic(self.dir / "report.json", report)


def null_answers(task: dict) -> list[dict]:
    return [{"question_id": q["id"], "value": None, "evidence": None, "confidence": "low"} for q in task["questions"]]


def base_report(task: dict, run_id: str, status: str, started: float) -> dict:
    return {"contract_version": 1, "task_id": task["task_id"], "run_id": run_id, "status": status,
            "answers": null_answers(task), "obstacles": [],
            "usage": {"wall_seconds": round(time.time() - started, 1), "tokens": None}, "trace_url": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fake agent that replays the golden run.")
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--speed", type=float, default=float(os.environ.get("REPRO_FAKE_SPEED", "4")))
    parser.add_argument("--scenario", choices=["ok", "crash", "wrong"], default="ok")
    args = parser.parse_args(argv)

    started = time.time()
    task = json.loads((args.task / "task.json").read_text(encoding="utf-8"))
    run_id = args.run.resolve().name
    run = Run(args.run, args.speed)

    if task["task_id"] != "toy-linreg":
        run.emit("run_started", "main", {"task_id": task["task_id"], "run_id": run_id, "model": "fake agent (no model)"})
        run.wait(4)
        run.emit("error", "main", {"message": "The fake agent only knows the toy task. Use the real agent for this one.", "fatal": True})
        report = base_report(task, run_id, "failed", started)
        report["obstacles"] = [{"stage": "other", "summary": "The fake agent can't work on real tasks", "fix": None, "resolved": False}]
        run.finish(report)
        return 0

    golden = read_events(GOLDEN_RUN)
    golden_report = read_json(GOLDEN_RUN / "report.json")
    request = read_json(GOLDEN_RUN / "approvals" / "a1.request.json")
    remembered = MEMORY.exists()
    # Golden events 9-13: memory miss, failed install, write the fix file, install, memory write.
    skip_when_remembered = {10, 13}

    prev_ts = None
    for ev in golden:
        etype, agent, data = ev["type"], ev["agent"], dict(ev["data"])
        gap = 0.0
        if prev_ts is not None:
            gap = max(0.0, _seconds(ev["ts"]) - _seconds(prev_ts))
        prev_ts = ev["ts"]

        if etype == "run_finished":
            break
        if etype == "approval_resolved":
            continue  # emitted by run.approval()
        if remembered and ev["seq"] in skip_when_remembered:
            continue
        run.wait(min(gap, 12))

        if etype == "run_started":
            data.update({"run_id": run_id, "model": "fake agent (no model)"})
        elif etype == "memory_read" and remembered:
            data["note"] = "Found a remembered fix: numpy==1.19.5 can't be installed on Python 3.10+, install numpy>=1.26 instead"
        elif etype == "tool_call" and remembered and ev["seq"] == 11:
            data["summary"] = "requirements.repro.txt (numpy>=1.26), using the remembered fix"
        elif etype == "subagent_finished" and remembered and data.get("name") == "env-builder":
            data["summary"] = "Environment ready on the first try, using the fix remembered from an earlier run."

        if etype == "approval_requested":
            decision = run.approval(request, args.auto_approve)
            if decision["decision"] != "approve":
                report = base_report(task, run_id, "rejected", started)
                report["obstacles"] = [{"stage": "run", "summary": "The run command was not approved, so there is nothing to read the answers from", "fix": None, "resolved": False}]
                run.finish(report)
                return 0
            continue

        if args.scenario == "crash" and etype == "subagent_started" and data.get("name") == "runner":
            run.emit("error", "main", {"message": "Simulated crash (fake agent, --scenario crash)", "fatal": True})
            print("fake agent: simulated crash", file=sys.stderr)
            return 1
        if args.scenario == "wrong" and etype == "answer_found" and data.get("question_id") == "q1":
            data["value"] = 0.91

        run.emit(etype, agent, data)
        if etype == "memory_written":
            MEMORY.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(MEMORY, {"fixes": [data["note"]], "saved": now_iso()})
        if etype == "tool_call" and data.get("tool") == "execute":
            _copy_log(run.dir, data)

    report = dict(golden_report)
    report.update({"run_id": run_id, "usage": {"wall_seconds": round(time.time() - started, 1), "tokens": None}})
    report["answers"] = [dict(a) for a in golden_report["answers"]]
    if args.scenario == "wrong":
        report["answers"][0]["value"] = 0.91
        report["answers"][0]["evidence"] = {"file": "logs/run.txt", "quote": "test r2: 0.91"}
        report["answers"][0]["confidence"] = "low"
    if remembered:
        report["obstacles"] = [{"stage": "env", "summary": "numpy==1.19.5 can't be installed on this Python (known from an earlier run)",
                                "fix": "Applied the remembered fix straight away: numpy>=1.26 from requirements.repro.txt", "resolved": True}]
    run.finish(report)
    return 0


def _seconds(ts: str) -> float:
    return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))


def _copy_log(rdir: Path, data: dict) -> None:
    name = "run.txt" if "run.py" in data.get("summary", "") else ("pip-install-1.txt" if not data.get("ok") else None)
    if name and (GOLDEN_RUN / "logs" / name).exists():
        (rdir / "logs" / name).write_text((GOLDEN_RUN / "logs" / name).read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
