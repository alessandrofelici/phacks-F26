"""The tester script (README, "Tester script"), run unattended. Standard library only.

    python -m harness.tester_check [--agent real|fake] [--tasks toy-linreg,cb-6460826-medium]

It drives the same functions the web UI's buttons call (start a run, approve, reject) and
checks what a human tester would look for:

1. a run starts for each task;
2. the plan and the agent's steps appear while it runs;
3. an approval is asked for, and approving lets the run continue;
4. the report has an answer per question, each with evidence, and lists obstacles;
5. the score against the answer key (which the agent never saw) is complete;
6. a second run of the toy reuses a remembered fix (memory_read with a fix);
7. rejecting the approval ends the run as rejected, with no answers.

With --agent real and no model credit, set REPRO_MODEL=scripted (toy only). With --agent fake,
real papers replay their recordings in harness/recordings/.
"""
from __future__ import annotations

import argparse
import sys
import time

from . import runs
from .common import RUNS, read_events, read_json, task_dir
from .score import score_run

TIMEOUT_S = 40 * 60


def _wait(run_id: str, until, timeout_s: float = TIMEOUT_S):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        detail = runs.run_detail(run_id) or {}
        found = until(detail)
        if found:
            return detail, found
        time.sleep(1)
    return runs.run_detail(run_id) or {}, None


def _pending(detail: dict):
    return next((a for a in detail.get("approvals", []) if not a.get("decision")), None)


def _finished(detail: dict) -> bool:
    return detail.get("status") not in ("running", "waiting_approval", "starting", None)


def check_task(task_id: str, agent: str, decision: str = "approve") -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    run_id = runs.start_run(task_id, agent, auto_approve=False)
    results.append(("1 run starts", True, run_id))
    detail, approval = _wait(run_id, lambda d: _pending(d) or (_finished(d) and "finished"))
    if not isinstance(approval, dict):
        results.append(("3 approval asked", False, f"no approval before the run ended ({detail.get('status')})"))
        return results
    results.append(("3 approval asked", True, approval["request"]["summary"][:80]))
    runs.decide(run_id, approval["request"]["id"], decision, "tester_check")
    # later approvals are approved too, so the run can finish
    while True:
        detail, state = _wait(run_id, lambda d: _pending(d) or (_finished(d) and "finished"))
        if isinstance(state, dict):
            runs.decide(run_id, state["request"]["id"], "approve", "tester_check")
            continue
        break
    events = read_events(RUNS / run_id)
    kinds = {e["type"] for e in events}
    steps = sum(1 for e in events if e["type"] in ("tool_call", "subagent_started"))
    report = read_json(RUNS / run_id / "report.json") or {}
    tdir = task_dir(task_id)
    task = (read_json(tdir / "task.json") if tdir else None) or {}
    if decision == "reject":
        ok = report.get("status") == "rejected" and all(a.get("value") is None for a in report.get("answers", []))
        results.append(("7 reject ends the run", ok, f"status {report.get('status')}"))
        return results
    results.append(("2 plan and steps appear", "todo_updated" in kinds and steps > 0, f"{steps} steps, plan {'yes' if 'todo_updated' in kinds else 'no'}"))
    answers = report.get("answers", [])
    complete = len(answers) == len(task.get("questions", [])) and all(a.get("evidence") for a in answers)
    results.append(("4 report: answers with evidence, obstacles", complete and "obstacles" in report, f"{len(answers)} answers, {len(report.get('obstacles', []))} obstacles"))
    score = score_run(RUNS / run_id)
    results.append(("5 scored against the key", bool(score and score["all_correct"]), f"{score['correct']}/{score['total']}" if score else "no key"))
    return results


def check_memory(agent: str) -> tuple[str, bool, str]:
    run_id = runs.start_run("toy-linreg", agent, auto_approve=True)
    _wait(run_id, _finished)
    notes = [e["data"].get("note", "") for e in read_events(RUNS / run_id) if e["type"] == "memory_read"]
    ok = any(("fix" in n.lower() and "nothing" not in n.lower()) for n in notes)
    return ("6 second toy run reuses a remembered fix", ok, notes[0][:80] if notes else "no memory_read event")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the tester script unattended.")
    parser.add_argument("--agent", choices=runs.AGENT_KINDS, default="real")
    parser.add_argument("--tasks", default="toy-linreg,cb-6460826-medium,cb-4098236-medium")
    args = parser.parse_args(argv)
    rows: list[tuple[str, str, bool, str]] = []
    for tid in [t.strip() for t in args.tasks.split(",") if t.strip()]:
        rows += [(tid, *r) for r in check_task(tid, args.agent)]
    rows.append(("toy-linreg", *check_memory(args.agent)))
    rows += [("toy-linreg", *r) for r in check_task("toy-linreg", args.agent, decision="reject")[-1:]]
    width = max(len(r[0]) for r in rows)
    for tid, name, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {tid:<{width}}  {name:<44} {detail}")
    failed = sum(1 for r in rows if not r[2])
    print(f"\n{len(rows) - failed}/{len(rows)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
