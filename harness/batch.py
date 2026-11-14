"""Run a set of tasks unattended and record the score. Standard library only.

    python -m harness.batch [--agent real|fake] [--tasks id1,id2] [--label "cycle 1"]

Every run uses --auto-approve. One row per batch is appended to
harness/SCOREBOARD.md, and the full result goes to runs/.batches/<batch>.json.
Failures are grouped by the stage the agent reported, for triage.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from . import runs
from .common import ROOT, RUNS, list_tasks, now_iso, read_json, write_json_atomic
from .score import score_run

SCOREBOARD = ROOT / "harness" / "SCOREBOARD.md"
HEADER = (
    "# Scoreboard\n\n"
    "One row per batch run (`python -m harness.batch`). A task counts as reproduced only when every answer matches.\n\n"
    "| When (UTC) | Label | Agent | Tasks reproduced | Answers correct | Not finished | Batch |\n"
    "|---|---|---|---|---|---|---|\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run tasks unattended and score them.")
    parser.add_argument("--agent", choices=runs.AGENT_KINDS, default="real")
    parser.add_argument("--tasks", default=None, help="comma-separated task ids (default: every task with an answer key)")
    parser.add_argument("--label", default="")
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
    results = []
    for i, tid in enumerate(task_ids, start=1):
        limit_min = float((all_tasks[tid].get("limits") or {}).get("max_minutes", 30))
        print(f"[{i}/{len(task_ids)}] {tid} ...", flush=True)
        try:
            run_id = runs.start_run(tid, args.agent, auto_approve=True)
        except ValueError as exc:
            print(f"    could not start: {exc}")
            results.append({"task_id": tid, "run_id": None, "status": "not_started", "correct": 0, "total": 0, "obstacles": []})
            continue
        status = runs.wait_for(run_id, timeout_s=limit_min * 60 + 120)
        rdir = RUNS / run_id
        score = score_run(rdir)
        report = read_json(rdir / "report.json", {}) or {}
        results.append({"task_id": tid, "run_id": run_id, "status": status,
                        "correct": score["correct"] if score else 0, "total": score["total"] if score else 0,
                        "all_correct": bool(score and score["all_correct"]),
                        "obstacles": report.get("obstacles") or []})
        print(f"    {status}: {results[-1]['correct']}/{results[-1]['total']} answers correct ({run_id})")

    reproduced = sum(1 for r in results if r.get("all_correct"))
    correct = sum(r["correct"] for r in results)
    total = sum(r["total"] for r in results)
    unfinished = sum(1 for r in results if r["status"] != "completed")

    groups: dict[str, list[str]] = defaultdict(list)
    for r in results:
        if r.get("all_correct"):
            continue
        open_obstacles = [o for o in r["obstacles"] if not o.get("resolved")]
        if r["status"] in ("crashed", "stopped", "not_started"):
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
    with open(SCOREBOARD, "a", encoding="utf-8") as fh:
        fh.write(f"| {now_iso()} | {args.label or '-'} | {args.agent} | {reproduced}/{len(results)} | {correct}/{total} | {unfinished} | {batch_id} |\n")

    print(f"\nReproduced {reproduced}/{len(results)} tasks, {correct}/{total} answers correct, {unfinished} not finished.")
    if groups:
        print("Failures to triage:")
        for reason, tids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(tids)}x {reason}  [{', '.join(tids)}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
