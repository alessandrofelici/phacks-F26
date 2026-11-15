"""A stand-in for Role A's agent, so the harness can be built and tested alone.

Same command line as the real one (contract section 3):

    python -m harness.fake_agent --task <task_dir> --run <run_dir> [--auto-approve]

It replays the golden run's events with delays and follows the approval
protocol for real (writes the request, waits for the decision). It calls no
model and runs no code. It "solves" the toy task, and any task with a saved
recording in harness/recordings/<task_id>/ (a real agent run, kept as the demo's
fallback; save one with `python -m harness.record runs/<run_id>`). For any other
task it reports a failure, which is useful for testing the failed state.

Extra flags (not part of the contract, for testing the UI):
    --speed N        divide every delay by N (default 4; 0 = no delays)
    --scenario X     ok | crash | wrong | scaled | not_verifiable   (crash exits 1
                     mid-run with no report; wrong reports a wrong q1; scaled plays a
                     plan-first run scaled down to fit, q1 a projection; not_verifiable
                     plays a plan that can't fit, every question with its reason)
It also imitates memory: once a run has written the numpy fix, later runs
reuse it and skip the failed install.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .common import (
    GOLDEN_RUN,
    ROOT,
    RUNS,
    now_iso,
    read_events,
    read_json,
    write_json_atomic,
)

RECORDINGS = ROOT / "harness" / "recordings"

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
    parser.add_argument("--scenario", choices=["ok", "crash", "wrong", "scaled", "not_verifiable"],
                        default=os.environ.get("REPRO_FAKE_SCENARIO", "ok"))
    args = parser.parse_args(argv)

    started = time.time()
    task = json.loads((args.task / "task.json").read_text(encoding="utf-8"))
    run_id = args.run.resolve().name
    run = Run(args.run, args.speed)

    recording = RECORDINGS / task["task_id"]
    if task["task_id"] != "toy-linreg" and (recording / "report.json").is_file():
        return replay_recording(recording, task, run, run_id, args, started)

    if task["task_id"] != "toy-linreg":
        run.emit("run_started", "main", {"task_id": task["task_id"], "run_id": run_id, "model": "fake agent (no model)"})
        run.wait(4)
        run.emit("error", "main", {"message": "The fake agent only knows the toy task. Use the real agent for this one.", "fatal": True})
        report = base_report(task, run_id, "failed", started)
        report["obstacles"] = [{"stage": "other", "summary": "The fake agent can't work on real tasks", "fix": None, "resolved": False}]
        run.finish(report)
        return 0

    if args.scenario == "not_verifiable":
        return play_not_verifiable(task, run, run_id, started)

    golden = read_events(GOLDEN_RUN)
    golden_report = read_json(GOLDEN_RUN / "report.json")
    request = read_json(GOLDEN_RUN / "approvals" / "a1.request.json")
    if args.scenario == "scaled":
        request = dict(request, summary=request["summary"] + " · scaled down per the plan: " + _SCALE_NOTE,
                       scale_down=SCALED_PLAN["scale_down"])
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
        if etype == "run_started" and args.scenario == "scaled":
            run.wait(2)
            run.emit("plan_recorded", "scoper", {"path": "scaled", "projected_minutes": SCALED_PLAN["projected_minutes"],
                                                 "minutes_left": SCALED_PLAN["minutes_left"], "summary": _SCALED_SUMMARY})
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
    if args.scenario == "scaled":
        quote = "projected test r2: 0.4555 (interval 0.4455 to 0.4655)"
        (run.dir / "logs" / "projection.txt").write_text(f"$ python project.py\n{quote}\n", encoding="utf-8")
        report["answers"][0].update({"evidence": {"file": "logs/projection.txt", "quote": quote}, "confidence": "medium",
                                     "scaled": True, "interval": [0.4455, 0.4655]})
        report["answers"][1]["scaled"] = True
        report["plan"] = SCALED_PLAN
    run.finish(report)
    return 0


# The plans the scaled and not_verifiable scenarios play (shapes as agent/task.py writes them).
SCALED_PLAN = {
    "path": "scaled", "projected_minutes": 96.0, "minutes_left": 14.5, "revision": 1,
    "steps": ["Install numpy from a relaxed requirements file", "Run run.py once per seed", "Project q1 from the seeds run"],
    "missing_steps": ["requirements.txt pins numpy==1.19.5, which can't be installed on a current Python"],
    "heavy_settings": ["seeds: 3 in the paper (demo)"],
    "reason": "Demo: the full run is taken to need 96 minutes; one seed instead of three fits in the time left.",
    "scale_down": [{"setting": "seeds", "original": 3, "scaled": 1, "kind": "precision", "where": "run.py --seed"}],
    "scaled_minutes": 1.0,
}
_SCALE_NOTE = "seeds 3 → 1 (precision)"
_SCALED_SUMMARY = f"scaled run: the full run needs about 96 min of 15 left, the scaled runs about 1 min; {_SCALE_NOTE}"
_NOT_VERIFIABLE_REASON = "Demo: the code is taken to need a GPU, which this task doesn't allow, and nothing can shrink enough."


def play_not_verifiable(task: dict, run: Run, run_id: str, started: float) -> int:
    """A plan-first run whose plan says the paper can't be verified within the budget."""
    run.emit("run_started", "main", {"task_id": task["task_id"], "run_id": run_id, "model": "fake agent (no model)"})
    run.wait(2)
    run.emit("subagent_started", "main", {"name": "scoper", "task": "Plan the run before any experiment"})
    run.wait(3)
    run.emit("tool_call", "scoper", {"tool": "read_file", "summary": "/repo/run.py", "ok": True})
    run.wait(2)
    run.emit("plan_recorded", "scoper", {"path": "not_verifiable", "projected_minutes": None, "minutes_left": 14.8,
                                         "summary": f"not verifiable within budget: {_NOT_VERIFIABLE_REASON}"})
    run.emit("subagent_finished", "main", {"name": "scoper", "summary": "Not verifiable within the budget: it needs a GPU."})
    report = base_report(task, run_id, "completed", started)
    for answer in report["answers"]:
        answer["no_answer"] = {"category": "not_verifiable_within_budget", "reason": _NOT_VERIFIABLE_REASON}
        run.wait(1)
        run.emit("no_answer", "main", {"question_id": answer["question_id"], "category": "not_verifiable_within_budget",
                                       "reason": _NOT_VERIFIABLE_REASON})
        report["obstacles"].append({"stage": "other", "summary": f"No answer for {answer['question_id']}: (not verifiable "
                                    f"within budget) {_NOT_VERIFIABLE_REASON}", "fix": None, "resolved": False})
    report["plan"] = {"path": "not_verifiable", "projected_minutes": None, "minutes_left": 14.8, "revision": 1,
                      "steps": ["Run run.py on a GPU"], "missing_steps": [], "heavy_settings": ["device: cuda (demo)"],
                      "reason": _NOT_VERIFIABLE_REASON}
    run.finish(report)
    return 0


def replay_recording(recording: Path, task: dict, run: Run, run_id: str, args, started: float) -> int:
    """Play back a saved real run: same events, logs and answers, approvals asked for real."""
    import shutil

    for sub in ("logs", "figures"):
        if (recording / sub).is_dir():
            shutil.copytree(recording / sub, run.dir / sub, dirs_exist_ok=True)
    prev_ts = None
    for ev in read_events(recording):
        etype, agent, data = ev["type"], ev["agent"], dict(ev["data"])
        gap = max(0.0, _seconds(ev["ts"]) - _seconds(prev_ts)) if prev_ts else 0.0
        prev_ts = ev["ts"]
        if etype in ("run_finished", "approval_resolved"):
            continue  # run.finish() and run.approval() write these
        run.wait(min(gap, 8))
        if etype == "run_started":
            data.update({"run_id": run_id, "model": f"recorded run ({data.get('model', 'real agent')}), replayed"})
        if etype == "approval_requested":
            request = read_json(recording / "approvals" / f"{data['id']}.request.json") or {
                "id": data["id"], "kind": data.get("kind", "long_run"), "summary": data.get("summary", ""), "command": None, "diff": None}
            decision = run.approval(request, args.auto_approve)
            if decision["decision"] != "approve":
                report = base_report(task, run_id, "rejected", started)
                report["obstacles"] = [{"stage": "run", "summary": "The run command was not approved, so there is nothing to read the answers from", "fix": None, "resolved": False}]
                run.finish(report)
                return 0
            continue
        run.emit(etype, agent, data)
    report = dict(read_json(recording / "report.json"))
    report.update({"run_id": run_id, "trace_url": report.get("trace_url"),
                   "usage": {"wall_seconds": round(time.time() - started, 1), "tokens": None}})
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
