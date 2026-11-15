"""Per paper: the overnight re-test (one run each) against the plan-first runs of 15 November (two each).

Usage: python3 -I compare_overnight.py <scratchpad> <out_dir>
Scores through <sp>/repo4/harness/score.py (the overnight branch's rule). Writes <out_dir>/overnight_compare.json.
No expected values are written or printed.
"""
import json
import statistics as st
import sys
from datetime import datetime
from pathlib import Path

SP, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(SP / "repo4"))
from harness.score import score_report  # noqa: E402

DATA = SP / "data"
PAPERS = ["0238624", "5496369", "9370340", "6460826", "0940461", "1108125"]


def rj(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


labels = {}
for bf in (DATA / "runs" / ".batches").glob("*.json"):
    b = rj(bf) or {}
    for r in b.get("results", []):
        if r.get("run_id"):
            labels[r["run_id"]] = b.get("label") or ""

rows = []
for rdir in sorted(p for p in (DATA / "runs").iterdir() if p.is_dir() and not p.name.startswith(".")):
    label = labels.get(rdir.name, "")
    group = "overnight" if label.startswith("overnight") else ("plan-first" if label.startswith("plan-first") else None)
    if group is None:
        continue
    events = [json.loads(line) for line in (rdir / "events.jsonl").read_text().splitlines() if line.strip()]
    task_id = events[0]["data"]["task_id"]
    paper = task_id.removeprefix("cb-").removesuffix("-medium")
    if paper not in PAPERS:
        continue
    report = rj(rdir / "report.json") or {}
    key = rj(DATA / "harness" / "answers" / f"{task_id}.json")
    score = score_report(report, key) if report and key else None
    t0 = ts(events[0]["ts"])
    plan_ev = next((e for e in events if e["type"] == "plan_recorded"), None)
    plan = report.get("plan") or {}
    rows.append({
        "group": group, "paper": paper, "run_id": rdir.name, "status": report.get("status", "crashed"),
        "outcome": score["outcome"] if score else "crashed",
        "plan_path": plan.get("path"), "projected": plan.get("projected_minutes"),
        "plan_minute": round((ts(plan_ev["ts"]) - t0).total_seconds() / 60, 1) if plan_ev else None,
        "minutes": round(((report.get("usage") or {}).get("wall_seconds") or 0) / 60, 1),
        "tokens": (report.get("usage") or {}).get("tokens"),
        "probes": sum(1 for e in events if e["type"] == "tool_call" and e["data"].get("tool") == "probe_runtime"),
        "reminded": sum(1 for e in events if e["type"] == "tool_call" and "and still no plan" in str(e["data"].get("detail", ""))),
    })

med = lambda xs: round(st.median(xs), 1) if xs else None  # noqa: E731
summary = {}
for g in ("plan-first", "overnight"):
    rs = [r for r in rows if r["group"] == g]
    summary[g] = {"runs": len(rs), "plan_minute_median": med([r["plan_minute"] for r in rs if r["plan_minute"] is not None]),
                  "minutes_median": med([r["minutes"] for r in rs]), "tokens_median": med([r["tokens"] for r in rs if r["tokens"]]),
                  "outcomes": {o: sum(1 for r in rs if r["outcome"] == o) for o in sorted({r["outcome"] for r in rs})},
                  "probes": sum(r["probes"] for r in rs), "timeouts": sum(1 for r in rs if r["status"] == "timeout")}
    for name, ps in (("easy", PAPERS[3:]), ("compute wall", PAPERS[:3])):
        sel = [r for r in rs if r["paper"] in ps]
        summary[g][name] = {"plan_minute_median": med([r["plan_minute"] for r in sel if r["plan_minute"] is not None]),
                            "minutes_median": med([r["minutes"] for r in sel]),
                            "tokens_median": med([r["tokens"] for r in sel if r["tokens"]])}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "overnight_compare.json").write_text(json.dumps({"rows": rows, "summary": summary}, indent=1))
for r in sorted(rows, key=lambda r: (r["paper"], r["group"])):
    print(f"{r['paper']} {r['group']:10} {r['outcome']:15} {r['status']:9} plan@{r['plan_minute']} {r['plan_path']} "
          f"proj={r['projected']} {r['minutes']} min {r['tokens']} tok probes={r['probes']} reminded={r['reminded']}")
print(json.dumps(summary, indent=1))
