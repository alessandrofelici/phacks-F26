"""Run a set of tasks unattended and record the score. Standard library only.

    python -m harness.batch [--agent real|fake] [--tasks id1,id2] [--label "cycle 1"] [--parallel 4]

Every run uses --auto-approve. One row per batch is appended to
harness/SCOREBOARD.md, and the full result goes to runs/.batches/<batch>.json.
Failures are grouped by the stage the agent reported, for triage.
"""
from __future__ import annotations

import argparse
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from . import runs
from .common import ROOT, RUNS, list_tasks, now_iso, read_json, write_json_atomic
from .score import score_run

SCOREBOARD = ROOT / "harness" / "SCOREBOARD.md"
HEADER = (
    "# Scoreboard\n\n"
    "One row per batch run (`python -m harness.batch`). A task counts as reproduced only when every answer matches.\n\n"
)
# Since plan-first runs: two budget columns. Older rows above this header keep their own columns.
TABLE = (
    "| When (UTC) | Label | Agent | Tasks reproduced | Verifiable within budget | Not verifiable within budget "
    "| Answers correct | Not finished | Batch |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)
TABLE_NOTE = (
    "\n## Since plan-first runs\n\n"
    "Verifiable within budget: the paper was too big for the limits, and a scaled-down run projected its numbers "
    "within ±10%. It never counts as reproduced. Not verifiable within budget: too big, and no scaled run could "
    "show it. Neither says the paper is wrong.\n\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run tasks unattended and score them.")
    parser.add_argument("--agent", choices=runs.AGENT_KINDS, default="real")
    parser.add_argument("--tasks", default=None, help="comma-separated task ids (default: every task with an answer key)")
    parser.add_argument("--label", default="")
    parser.add_argument("--parallel", type=int, default=1, help="how many tasks run at the same time")
    args = parser.parse_args(argv)

    all_tasks = {t["task_id"]: t for t in list_tasks()}
    if args.tasks:
        task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()]
        unknown = [t for t in task_ids if t not in all_tasks]
        if unknown:
            print(f"Unknown task(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
    else:
        task_ids = [tid for tid in all_tasks if (ROOT / "harness" / "answers" / f"{tid}.json").exists()]
    if not task_ids:
        print("No tasks to run.", file=sys.stderr)
        return 2

    batch_id = "b-" + now_iso().replace(":", "").replace("-", "").replace("T", "-").rstrip("Z")
    out_of_credit = threading.Event()  # set when a run ends because the model provider refused to bill

    def run_one(numbered: tuple[int, str]) -> dict:
        i, tid = numbered
        if out_of_credit.is_set():
            print(f"    {tid} not started: the model provider is out of credit", flush=True)
            return {"task_id": tid, "run_id": None, "status": "not_started", "correct": 0, "total": 0,
                    "obstacles": [{"stage": "other", "summary": "Not started: the model provider is out of credit", "resolved": False}]}
        limit_min = float((all_tasks[tid].get("limits") or {}).get("max_minutes", 30))
        print(f"[{i}/{len(task_ids)}] {tid} ...", flush=True)
        try:
            run_id = runs.start_run(tid, args.agent, auto_approve=True)
        except ValueError as exc:
            print(f"    {tid} could not start: {exc}", flush=True)
            return {"task_id": tid, "run_id": None, "status": "not_started", "correct": 0, "total": 0, "obstacles": []}
        status = runs.wait_for(run_id, timeout_s=limit_min * 60 + 120)
        rdir = RUNS / run_id
        if _billing_refused(rdir):
            out_of_credit.set()
        score = score_run(rdir)
        report = read_json(rdir / "report.json", {}) or {}
        plan = report.get("plan") if isinstance(report.get("plan"), dict) else {}
        result = {"task_id": tid, "run_id": run_id, "status": status,
                  "correct": score["correct"] if score else 0, "total": score["total"] if score else 0,
                  "all_correct": bool(score and score["all_correct"]),
                  "outcome": score["outcome"] if score else None,
                  "verifiable": score.get("verifiable", 0) if score else 0,
                  "plan": {"path": plan.get("path"), "projected_minutes": plan.get("projected_minutes"),
                           "reason": plan.get("reason")} if plan else None,
                  "obstacles": report.get("obstacles") or []}
        label = f", {score['outcome_label'].lower()}" if score and score["outcome"] in ("verifiable", "not_verifiable") else ""
        projected = f", plan: {plan['path']} ~{plan['projected_minutes']} min" if plan and plan.get("projected_minutes") is not None else (
            f", plan: {plan['path']}" if plan else "")
        print(f"    {tid} {status}: {result['correct']}/{result['total']} answers correct{label}{projected} ({run_id})", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        results = list(pool.map(run_one, enumerate(task_ids, start=1)))  # keeps task order

    reproduced = sum(1 for r in results if r.get("all_correct"))
    verifiable = sum(1 for r in results if r.get("outcome") == "verifiable")
    not_verifiable = sum(1 for r in results if r.get("outcome") == "not_verifiable")
    correct = sum(r["correct"] for r in results)
    total = sum(r["total"] for r in results)
    unfinished = sum(1 for r in results if r["status"] != "completed")

    groups: dict[str, list[str]] = defaultdict(list)
    for r in results:
        if r.get("all_correct"):
            continue
        open_obstacles = [o for o in r["obstacles"] if not o.get("resolved")]
        if r.get("outcome") == "verifiable":
            groups["verifiable within budget (scaled run in range; not counted as reproduced)"].append(r["task_id"])
        elif r.get("outcome") == "not_verifiable":
            reason = ((r.get("plan") or {}).get("reason") or "no scaled run could show it")[:90]
            groups[f"not verifiable within budget: {reason}"].append(r["task_id"])
        elif r["status"] in ("crashed", "stopped", "not_started"):
            groups[f"agent {r['status'].replace('_', ' ')}"].append(r["task_id"])
        elif open_obstacles:
            for o in open_obstacles:
                groups[f"{o.get('stage', 'other')}: {o.get('summary', '')[:90]}"].append(r["task_id"])
        else:
            groups["finished, but an answer doesn't match"].append(r["task_id"])

    write_json_atomic(RUNS / ".batches" / f"{batch_id}.json",
                      {"batch_id": batch_id, "label": args.label, "agent": args.agent, "when": now_iso(),
                       "results": results, "failure_groups": groups})
    if not SCOREBOARD.exists():
        SCOREBOARD.write_text(HEADER, encoding="utf-8")
    if TABLE not in SCOREBOARD.read_text(encoding="utf-8"):
        with open(SCOREBOARD, "a", encoding="utf-8") as fh:
            fh.write(TABLE_NOTE + TABLE)
    with open(SCOREBOARD, "a", encoding="utf-8") as fh:
        fh.write(f"| {now_iso()} | {args.label or '-'} | {args.agent} | {reproduced}/{len(results)} | {verifiable} | "
                 f"{not_verifiable} | {correct}/{total} | {unfinished} | {batch_id} |\n")

    budget = f", {verifiable} verifiable and {not_verifiable} not verifiable within budget" if verifiable or not_verifiable else ""
    print(f"\nReproduced {reproduced}/{len(results)} tasks{budget}, {correct}/{total} answers correct, {unfinished} not finished.")
    if groups:
        print("Failures to triage:")
        for reason, tids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(tids)}x {reason}  [{', '.join(tids)}]")
    return 0


BILLING_ERRORS = ("PaymentRequired", "exceed your available credits", "insufficient credits", "Error code: 402")


def _billing_refused(rdir) -> bool:
    """Did the run end because the model provider refused to bill (out of credit)?"""
    try:
        text = (rdir / "events.jsonl").read_text(encoding="utf-8")
    except OSError:
        return False
    return any(marker in text for marker in BILLING_ERRORS)


if __name__ == "__main__":
    sys.exit(main())
