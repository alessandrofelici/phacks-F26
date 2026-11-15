"""Per-run rows comparing plan-first runs (15 November) with the runs before them (14 November).

Usage: python3 -I pf_dataset.py <scratchpad> <out_dir>
Reads <sp>/data/runs (run directories and .batches), <sp>/data/tasks, <sp>/data/harness/answers, and
the plan-first scorer from <sp>/repo3/harness/score.py. Writes <out_dir>/runs_pf.json.
Expected answer values, and anything they could be recovered from, are not written out.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SP, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(SP / "repo3"))
from harness.score import score_report  # noqa: E402

DATA = SP / "data"
OUT.mkdir(parents=True, exist_ok=True)
CREDIT = re.compile(r"PaymentRequired|exceed your available credits|insufficient credits|Error code: 402")


def rj(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


labels = {}
for bf in sorted((DATA / "runs" / ".batches").glob("*.json")):
    b = rj(bf) or {}
    for r in b.get("results", []):
        if r.get("run_id"):
            labels[r["run_id"]] = b.get("label") or b.get("batch_id")

rows = []
for rdir in sorted(p for p in (DATA / "runs").iterdir() if p.is_dir() and not p.name.startswith(".")):
    ev_path = rdir / "events.jsonl"
    events = [json.loads(line) for line in ev_path.read_text().splitlines() if line.strip()] if ev_path.exists() else []
    if not events:
        continue
    started = next((e for e in events if e["type"] == "run_started"), {"data": {}})
    model = str(started["data"].get("model") or "")
    task_id = str(started["data"].get("task_id") or "")
    if "haiku" not in model.lower() or not task_id.startswith("cb-"):
        continue  # real-model CORE-Bench runs only
    report = rj(rdir / "report.json") or {}
    key = rj(DATA / "harness" / "answers" / f"{task_id}.json")
    score = score_report(report, key) if (report and key) else None
    label = labels.get(rdir.name)
    group = "plan-first" if label and label.startswith("plan-first") else "before"
    fatal = [e["data"].get("message", "") for e in events if e["type"] == "error" and e["data"].get("fatal")]
    credit_stop = any(CREDIT.search(m) for m in fatal) or any(
        CREDIT.search(str(o.get("summary", ""))) for o in report.get("obstacles") or [])
    status = report.get("status") or "crashed"
    outcome = score["outcome"] if score else "crashed"
    if credit_stop:
        outcome = "not run (credit)"
    elif outcome == "not_reproduced":
        outcome = {"timeout": "timed out", "failed": "gave up", "rejected": "rejected"}.get(status, "finished, answers wrong")
    subagents = [e["data"].get("name") for e in events if e["type"] == "subagent_started"]
    plan_ev = [i for i, e in enumerate(events) if e["type"] == "plan_recorded"]
    exp_ev = [i for i, e in enumerate(events) if e["type"] == "approval_requested"
              and str(e["data"].get("summary", "")).startswith("Run ") and " (allowed up to " not in str(e["data"].get("summary", ""))]
    tools = [e["data"].get("tool") for e in events if e["type"] == "tool_call"]
    refused = sum(1 for e in events if e["type"] == "tool_call" and e["data"].get("tool") in ("run_experiment", "start_background_run")
                  and "no plan" in str(e["data"].get("detail", "")))
    plan = report.get("plan") if isinstance(report.get("plan"), dict) else None
    task = rj(DATA / "tasks" / task_id / "task.json") or {}
    t0 = ts(events[0]["ts"])
    rows.append({
        "run_id": rdir.name, "group": group, "batch": label, "task_id": task_id,
        "paper": task_id.removeprefix("cb-").removesuffix("-medium").removesuffix("-hard"),
        "title": task.get("title"), "language": (task.get("core_bench") or {}).get("language"),
        "status": status, "outcome": outcome, "credit_stop": credit_stop,
        "correct": score["correct"] if score else None, "verifiable": score.get("verifiable") if score else None,
        "total": score["total"] if score else None,
        "answered": sum(1 for a in report.get("answers") or [] if a.get("value") is not None),
        "no_answer_categories": [a["no_answer"]["category"] for a in report.get("answers") or [] if isinstance(a.get("no_answer"), dict)],
        "scaled_answers": sum(1 for a in report.get("answers") or [] if a.get("scaled")),
        "wall_seconds": (report.get("usage") or {}).get("wall_seconds") or (ts(events[-1]["ts"]) - t0).total_seconds(),
        "tokens": (report.get("usage") or {}).get("tokens"),
        "subagents": subagents, "scoper_first": bool(subagents) and subagents[0] == "scoper",
        "plan": {k: plan.get(k) for k in ("path", "projected_minutes", "minutes_left", "scaled_minutes", "scale_down",
                                          "missing_steps", "heavy_settings", "reason")} if plan else None,
        "plan_minute": round((ts(events[plan_ev[0]]["ts"]) - t0).total_seconds() / 60, 1) if plan_ev else None,
        "plan_before_experiment": (plan_ev[0] < exp_ev[0]) if (plan_ev and exp_ev) else (bool(plan_ev) if not exp_ev else False),
        "experiment_requests": len(exp_ev),
        "probes": tools.count("probe_runtime"), "refused_before_plan": refused,
        "approvals": sum(1 for e in events if e["type"] == "approval_requested"),
        "obstacles": [str(o.get("summary", ""))[:200] for o in report.get("obstacles") or []
                      if not str(o.get("summary", "")).startswith("No answer for")],
    })

(OUT / "runs_pf.json").write_text(json.dumps(rows, indent=1))
print(len(rows), "runs;", sum(r["group"] == "plan-first" for r in rows), "plan-first")
