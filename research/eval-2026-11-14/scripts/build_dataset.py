"""Build a per-run and per-question dataset from the CT 120 run directories.

Usage: python3 -I build_dataset.py <scratchpad>
Reads <sp>/data/runs, <sp>/data/tasks, <sp>/data/harness/answers; scoring logic from <sp>/repo2/harness/score.py.
Writes <sp>/out/runs.json and <sp>/out/questions.json. Expected answer values, and anything they could be recovered from, are not written out.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SP = Path(sys.argv[1])
sys.path.insert(0, str(SP / "repo2"))
from harness.score import score_report  # noqa: E402

DATA = SP / "data"
OUT = SP / "out"
OUT.mkdir(exist_ok=True)


def rj(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


batches = {}
for bf in sorted((DATA / "runs" / ".batches").glob("*.json")):
    b = rj(bf)
    for r in b["results"]:
        if r.get("run_id"):
            batches[r["run_id"]] = {"batch_id": b["batch_id"], "label": b["label"]}

BATCH_NAME = {"b-20261114-142611": "UI check (toy)", "b-20261114-160408": "Cycle 1", "b-20261114-174449": "Cycle 2"}

OBSTACLE_CATS = [
    ("credit", r"PaymentRequired|out of credit|exceed your available credits"),
    ("time limit / slow CPU training", r"minute limit|time limit|over the 30|epochs|too slow|hours on CPU|would take|timed out|still running"),
    ("GPU / CUDA only", r"CUDA|cuda|GPU|gpu"),
    ("R packages / R version", r"\bR\b|CRAN|Rscript|install\.packages|Bioconductor|R >=|R version|devtools|renv"),
    ("Python version / old pins", r"numpy|pip|wheel|Python 3|python3\.|pin|version|scikit|sklearn|pandas|tensorflow|keras|torch|h5py|protobuf|distutils|setuptools|venv|conda"),
    ("paths / data layout", r"/data|/results|/code|path|No such file|not found|missing file|directory"),
    ("figure / output reading", r"figure|plot|png|image|pdf"),
    ("no answer (summary line)", r"^No answer for"),
]


def obstacle_cat(o):
    text = f"{o.get('summary','')} {o.get('fix') or ''}"
    if text.startswith("No answer for"):
        if re.search(OBSTACLE_CATS[0][1], text):
            return "credit"
        return "no answer (summary line)"
    for name, pat in OBSTACLE_CATS:
        if name == "no answer (summary line)":
            continue
        if re.search(pat, text):
            return name
    return "other"


runs, questions = [], []
for rdir in sorted(p for p in (DATA / "runs").iterdir() if p.is_dir() and not p.name.startswith(".")):
    ev_path = rdir / "events.jsonl"
    events = [json.loads(l) for l in ev_path.read_text().splitlines() if l.strip()] if ev_path.exists() else []
    report = rj(rdir / "report.json") or {}
    meta = rj(rdir / ".harness" / "meta.json") or {}
    started = next((e for e in events if e["type"] == "run_started"), {"data": {}})
    task_id = report.get("task_id") or meta.get("task_id") or started["data"].get("task_id")
    task = rj(DATA / "tasks" / str(task_id) / "task.json") or {}
    if task_id == "toy-linreg":
        task = rj(SP / "repo2/contract/fixtures/tasks/toy-linreg/task.json") or {}
    cb = task.get("core_bench") or {}
    key = rj(DATA / "harness" / "answers" / f"{task_id}.json")
    score = score_report(report, key) if (report and key) else None

    types = {}
    for e in events:
        types[e["type"]] = types.get(e["type"], 0) + 1
    tool_events = [e for e in events if e["type"] == "tool_call"]
    tools = {}
    for e in tool_events:
        t = e["data"].get("tool")
        tools[t] = tools.get(t, 0) + 1
    approvals = [e for e in events if e["type"] == "approval_requested"]
    resolved = [e for e in events if e["type"] == "approval_resolved"]
    subagents = [e["data"].get("name") for e in events if e["type"] == "subagent_started"]
    agents_acting = sorted({e.get("agent") for e in events})
    fatal = [e["data"].get("message", "") for e in events if e["type"] == "error" and e["data"].get("fatal")]
    dur = None
    if len(events) >= 2:
        dur = (ts(events[-1]["ts"]) - ts(events[0]["ts"])).total_seconds()
    # approval wait time: requested -> resolved by id
    req_t = {e["data"]["id"]: ts(e["ts"]) for e in approvals}
    wait = sum(max(0.0, (ts(e["ts"]) - req_t[e["data"]["id"]]).total_seconds()) for e in resolved if e["data"].get("id") in req_t)
    first_answer = next((e for e in events if e["type"] == "answer_found"), None)
    t_first_answer = (ts(first_answer["ts"]) - ts(events[0]["ts"])).total_seconds() if first_answer and events else None

    obstacles = report.get("obstacles") or []
    real_obs = [o for o in obstacles if not str(o.get("summary", "")).startswith("No answer for")]
    status = report.get("status") or ("crashed" if not report else None)
    credit_stop = any(re.search(OBSTACLE_CATS[0][1], m) for m in fatal) or any(obstacle_cat(o) == "credit" for o in obstacles)

    model = started["data"].get("model") or ""
    agent_kind = meta.get("agent") or ("real" if model else "unknown")
    if "scripted" in model:
        agent_kind = "scripted"
    model_short = (
        "Haiku 5.5" if "haiku" in model else "Opus 5.5" if "opus" in model else "scripted" if "scripted" in model else ("fake replay" if agent_kind == "fake" else (model or "?"))
    )

    # outcome class
    if credit_stop:
        outcome = "not run (credit ran out)"
    elif not report:
        outcome = "crashed (no report)"
    elif score and score["all_correct"]:
        outcome = "reproduced"
    elif score and score["correct"] > 0:
        outcome = "partly reproduced"
    elif status == "timeout":
        outcome = "timed out"
    elif status == "completed":
        outcome = "finished, answers wrong"
    elif status == "failed":
        outcome = "gave up / failed"
    else:
        outcome = status or "unknown"

    run = {
        "run_id": rdir.name,
        "batch": BATCH_NAME.get(batches.get(rdir.name, {}).get("batch_id"), None),
        "task_id": task_id,
        "paper": cb.get("capsule_id", task_id),
        "level": cb.get("level") or ("toy" if task_id == "toy-linreg" else ("arxiv" if task.get("source") == "arxiv" else None)),
        "source": task.get("source"),
        "title": task.get("title"),
        "language": cb.get("language") or ("Python" if task_id == "toy-linreg" else None),
        "field": cb.get("field"),
        "n_questions": len(task.get("questions") or []),
        "n_figure_q": sum(1 for q in task.get("questions") or [] if q.get("needs_figure")),
        "agent_kind": agent_kind,
        "model": model_short,
        "sandbox": started["data"].get("sandbox"),
        "status": status,
        "outcome": outcome,
        "credit_stop": credit_stop,
        "correct": score["correct"] if score else None,
        "total": score["total"] if score else None,
        "answered": sum(1 for a in report.get("answers") or [] if a.get("value") is not None) if report else 0,
        "wall_seconds": (report.get("usage") or {}).get("wall_seconds") if report else dur,
        "tokens": (report.get("usage") or {}).get("tokens") if report else None,
        "trace": bool(report.get("trace_url")) if report else False,
        "events": len(events),
        "tool_calls": len(tool_events),
        "tool_calls_failed": sum(1 for e in tool_events if not e["data"].get("ok")),
        "tools": tools,
        "approvals": len(approvals),
        "approval_kinds": [e["data"].get("kind") for e in approvals],
        "approvals_by": [e["data"].get("by") for e in resolved],
        "approval_wait_s": wait,
        "subagents": subagents,
        "agents_acting": agents_acting,
        "todo_updates": types.get("todo_updated", 0),
        "memory_read": types.get("memory_read", 0),
        "memory_written": types.get("memory_written", 0),
        "answers_found": types.get("answer_found", 0),
        "t_first_answer_s": t_first_answer,
        "fatal_errors": [m[:200] for m in fatal],
        "obstacles": [{"stage": o.get("stage"), "cat": obstacle_cat(o), "resolved": bool(o.get("resolved")), "summary": str(o.get("summary", ""))[:220]} for o in real_obs],
        "source_changes": report.get("source_changes") if report else None,
        "first_ts": events[0]["ts"] if events else None,
    }
    runs.append(run)

    if score:
        qmeta = {q["id"]: q for q in task.get("questions") or []}
        for qid, r in score["per_question"].items():
            q = qmeta.get(qid, {})
            ans = next((a for a in report.get("answers") or [] if a.get("question_id") == qid), {})
            questions.append({
                "run_id": rdir.name, "batch": run["batch"], "task_id": task_id, "qid": qid,
                "type": q.get("type"), "needs_figure": bool(q.get("needs_figure")),
                "answered": r["answered"], "correct": r["correct"],
                "confidence": ans.get("confidence"), "credit_stop": credit_stop,
                "evidence_kind": ("figure" if str((ans.get("evidence") or {}).get("file", "")).lower().endswith((".png", ".jpg", ".pdf")) else "log") if ans.get("evidence") else None,
            })

(OUT / "runs.json").write_text(json.dumps(runs, indent=1))
(OUT / "questions.json").write_text(json.dumps(questions, indent=1))
print(len(runs), "runs;", len(questions), "scored questions")
