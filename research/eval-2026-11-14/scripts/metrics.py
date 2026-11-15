"""Aggregate metrics from out/runs.json and out/questions.json into out/metrics.json."""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

SP = Path(sys.argv[1])
runs = json.load(open(SP / "out/runs.json"))
qs = json.load(open(SP / "out/questions.json"))
KEY_SPEND_USD = 3.1774399  # OpenRouter key usage read 2026-11-14, after the credit ran out

CAUSE = {
    "r-20261114-160408-5431": "Compute: CPU training > 30 min",
    "r-20261114-160408-d657": "Environment: R packages",
    "r-20261114-160458-0576": "Environment: R packages",
    "r-20261114-162357-a512": "Environment: R packages",
    "r-20261114-163036-e0d6": "Environment: R packages",
    "r-20261114-163323-8ff9": "Environment: R packages",
    "r-20261114-170405-c9ca": "Environment: R packages",
    "r-20261114-163507-772b": "Environment: R packages",
    "r-20261114-165512-06ab": "Harness crash (Podman lock)",
    "r-20261114-170117-b371": "Compute: CPU training > 30 min",
    "r-20261114-172045-8629": "Compute: GPU-only code",
    "r-20261114-174449-199b": "Compute: CPU training > 30 min",
    "r-20261114-174449-374c": "Environment: R packages",
    "r-20261114-181710-a082": "Compute: GPU-only code",
    "strict-cb-5496369-medium": "Compute: CPU training > 30 min",
}

real = [r for r in runs if r["agent_kind"] == "real"]
cb = [r for r in real if str(r["task_id"]).startswith("cb-")]
cb_ran = [r for r in cb if not r["credit_stop"]]
for r in cb_ran:
    r["cause"] = None if r["outcome"] == "reproduced" else CAUSE.get(r["run_id"], "unclassified")

m = {}
pct = lambda a, b: round(100 * a / b, 1) if b else None

# --- paper level
papers = sorted({r["paper"] for r in cb})
best = {}
for p in papers:
    rs = [r for r in cb_ran if r["paper"] == p]
    frac = max(((r["correct"] or 0) / r["total"]) if r["total"] else 0 for r in rs) if rs else 0
    best[p] = {"best_fraction": frac, "ever_reproduced": any(r["outcome"] == "reproduced" for r in rs),
               "runs": len(rs), "language": rs[0]["language"] if rs else None, "field": rs[0]["field"] if rs else None,
               "title": rs[0]["title"] if rs else None, "n_q": rs[0]["n_questions"] if rs else None,
               "fig_q": rs[0]["n_figure_q"] if rs else None,
               "causes": sorted({r["cause"] for r in rs if r["cause"]})}
m["papers_total"] = len(papers)
m["papers_ever_reproduced"] = sum(1 for b in best.values() if b["ever_reproduced"])
m["papers_partial_best"] = sum(1 for b in best.values() if not b["ever_reproduced"] and b["best_fraction"] > 0)
m["paper_best"] = best

# --- per batch
def batch_stats(name):
    rs = [r for r in runs if r["batch"] == name and str(r["task_id"]).startswith("cb-")]
    ran = [r for r in rs if not r["credit_stop"]]
    return {
        "papers": len(rs), "ran_to_end": len(ran), "credit_stopped": len(rs) - len(ran),
        "reproduced": sum(1 for r in ran if r["outcome"] == "reproduced"),
        "partial": sum(1 for r in ran if r["outcome"] == "partly reproduced"),
        "answers_correct": sum(r["correct"] or 0 for r in ran), "answers_total": sum(r["total"] or 0 for r in ran if r["total"]),
        "outcomes": Counter(r["outcome"] for r in rs),
        "toy": next((r["outcome"] for r in runs if r["batch"] == name and r["task_id"] == "toy-linreg"), None),
    }
m["cycle1"] = batch_stats("Cycle 1")
m["cycle2"] = batch_stats("Cycle 2")
c2_ran = {r["paper"] for r in runs if r["batch"] == "Cycle 2" and str(r["task_id"]).startswith("cb-") and not r["credit_stop"]}
c1_same = [r for r in runs if r["batch"] == "Cycle 1" and r["paper"] in c2_ran]
m["same_papers"] = {"n": len(c2_ran), "cycle1_reproduced": sum(1 for r in c1_same if r["outcome"] == "reproduced"),
                    "cycle2_reproduced": m["cycle2"]["reproduced"]}

# --- run level (all real CORE-Bench runs that ran to the end)
m["runs_cb_ran"] = len(cb_ran)
m["runs_cb_reproduced"] = sum(1 for r in cb_ran if r["outcome"] == "reproduced")
m["runs_cb_outcomes"] = Counter(r["outcome"] for r in cb_ran)
m["runs_causes"] = Counter(r["cause"] for r in cb_ran if r["cause"])
m["runs_credit_stopped"] = sum(1 for r in cb if r["credit_stop"])

# --- question level (real CORE-Bench, not credit-stopped)
cbq = [q for q in qs if q["task_id"].startswith("cb-") and not q["credit_stop"]
       and next(r for r in runs if r["run_id"] == q["run_id"])["agent_kind"] == "real"]
answered = [q for q in cbq if q["answered"]]
m["q_total"] = len(cbq)
m["q_correct"] = sum(q["correct"] for q in cbq)
m["q_answered"] = len(answered)
m["q_answered_correct"] = sum(q["correct"] for q in answered)
m["q_answered_wrong"] = len(answered) - m["q_answered_correct"]
m["q_unanswered"] = len(cbq) - len(answered)
conf = defaultdict(lambda: [0, 0])
for q in answered:
    conf[q["confidence"]][0] += q["correct"]
    conf[q["confidence"]][1] += 1
m["confidence"] = {k: {"correct": v[0], "answered": v[1]} for k, v in conf.items()}
for label, sel in [("figure", lambda q: q["needs_figure"]), ("text", lambda q: not q["needs_figure"])]:
    s = [q for q in cbq if sel(q)]
    m[f"q_{label}"] = {"total": len(s), "correct": sum(q["correct"] for q in s), "answered": sum(q["answered"] for q in s)}

# --- partial credit in runs that were not reproduced
notrep = [r for r in cb_ran if r["outcome"] != "reproduced" and r["total"]]
m["failed_runs"] = len(notrep)
m["failed_runs_answers_correct"] = sum(r["correct"] or 0 for r in notrep)
m["failed_runs_answers_total"] = sum(r["total"] for r in notrep)
m["failed_runs_answers_given"] = sum(r["answered"] for r in notrep)

# --- by language and field (run level, ran to end)
for dim in ("language", "field"):
    d = defaultdict(lambda: {"runs": 0, "reproduced": 0, "papers": set(), "papers_reproduced": set()})
    for r in cb_ran:
        x = d[r[dim]]
        x["runs"] += 1
        x["reproduced"] += r["outcome"] == "reproduced"
        x["papers"].add(r["paper"])
        if r["outcome"] == "reproduced":
            x["papers_reproduced"].add(r["paper"])
    m[f"by_{dim}"] = {k: {"runs": v["runs"], "reproduced": v["reproduced"], "papers": len(v["papers"]),
                         "papers_reproduced": len(v["papers_reproduced"])} for k, v in d.items()}
for cyc in ("Cycle 1", "Cycle 2"):
    d = defaultdict(lambda: [0, 0])
    for r in cb_ran:
        if r["batch"] == cyc:
            d[r["language"]][0] += r["outcome"] == "reproduced"
            d[r["language"]][1] += 1
    m[f"by_language_{cyc}"] = dict(d)

# --- time and tokens
rep = [r for r in cb_ran if r["outcome"] == "reproduced"]
nrep = [r for r in cb_ran if r["outcome"] != "reproduced" and r["wall_seconds"]]
med = lambda xs: round(st.median(xs), 1) if xs else None
m["wall_median_reproduced_s"] = med([r["wall_seconds"] for r in rep])
m["wall_median_failed_s"] = med([r["wall_seconds"] for r in nrep])
m["failed_hit_time_limit"] = sum(1 for r in nrep if r["wall_seconds"] and r["wall_seconds"] > 1700)
m["tokens_median_reproduced"] = med([r["tokens"] for r in rep if r["tokens"]])
m["tokens_median_failed"] = med([r["tokens"] for r in nrep if r["tokens"]])
all_tokens = sum(r["tokens"] or 0 for r in real)
m["tokens_all_real_runs"] = all_tokens
m["usd_per_mtok_blended"] = round(KEY_SPEND_USD / (all_tokens / 1e6), 3)
m["usd_key_spend"] = KEY_SPEND_USD
m["usd_per_reproduced_paper_median"] = round(m["tokens_median_reproduced"] / 1e6 * m["usd_per_mtok_blended"], 3)
cb_tokens_ran = sum(r["tokens"] or 0 for r in cb_ran)
m["tokens_per_correct_answer"] = round(cb_tokens_ran / max(1, m["q_correct"]))
m["tokens_spent_on_failed_runs_pct"] = pct(sum(r["tokens"] or 0 for r in nrep), cb_tokens_ran)
m["time_spent_on_failed_runs_pct"] = pct(sum(r["wall_seconds"] or 0 for r in nrep), sum(r["wall_seconds"] or 0 for r in cb_ran))

# --- improvement on papers reproduced in both cycles
both = []
for p in papers:
    a = next((r for r in runs if r["batch"] == "Cycle 1" and r["paper"] == p and r["outcome"] == "reproduced"), None)
    b = next((r for r in runs if r["batch"] == "Cycle 2" and r["paper"] == p and r["outcome"] == "reproduced"), None)
    if a and b:
        both.append({"paper": p, "c1_s": a["wall_seconds"], "c2_s": b["wall_seconds"], "c1_tok": a["tokens"], "c2_tok": b["tokens"]})
m["reproduced_both_cycles"] = both

# --- behaviour (real CORE-Bench runs that ran to the end)
nonstrict = [r for r in cb_ran if not r["run_id"].startswith("strict-")]
m["behaviour"] = {
    "runs": len(cb_ran),
    "delegated_nonstrict": sum(1 for r in nonstrict if r["subagents"]),
    "nonstrict_runs": len(nonstrict),
    "strict_runs": [{"run": r["run_id"], "subagents": r["subagents"], "outcome": r["outcome"]} for r in cb_ran if r["run_id"].startswith("strict-")],
    "kept_plan": sum(1 for r in cb_ran if r["todo_updates"] > 0),
    "approvals_median": med([r["approvals"] for r in cb_ran]),
    "approvals_max": max(r["approvals"] for r in cb_ran),
    "approvals_total": sum(r["approvals"] for r in cb_ran),
    "used_background": sum(1 for r in cb_ran if r["tools"].get("start_background_run")),
    "used_figure_tool": sum(1 for r in cb_ran if r["tools"].get("look_at_figure")),
    "tool_calls": sum(r["tool_calls"] for r in cb_ran),
    "tool_calls_failed": sum(r["tool_calls_failed"] for r in cb_ran),
    "tool_mix": Counter(),
    "obstacles": sum(len(r["obstacles"]) for r in cb_ran),
    "obstacles_resolved": sum(o["resolved"] for r in cb_ran for o in r["obstacles"]),
    "obstacle_stages": Counter(o["stage"] for r in cb_ran for o in r["obstacles"]),
    "unapproved_source_changes_runs": sum(1 for r in cb_ran if any(not c.get("approved") for c in (r["source_changes"] or []))),
    "memory_read_runs": sum(1 for r in cb_ran if r["memory_read"]),
    "memory_written_runs": sum(1 for r in cb_ran if r["memory_written"]),
}
for r in cb_ran:
    m["behaviour"]["tool_mix"].update(r["tools"])
plan_rep = [r for r in cb_ran if r["todo_updates"] > 0]
noplan = [r for r in cb_ran if r["todo_updates"] == 0]
m["behaviour"]["reproduced_with_plan"] = f"{sum(r['outcome']=='reproduced' for r in plan_rep)}/{len(plan_rep)}"
m["behaviour"]["reproduced_without_plan"] = f"{sum(r['outcome']=='reproduced' for r in noplan)}/{len(noplan)}"

# --- toy and other
toy = [r for r in real if r["task_id"] == "toy-linreg"]
m["toy"] = {"runs": len(toy), "reproduced": sum(r["outcome"] == "reproduced" for r in toy),
            "models": Counter(r["model"] for r in toy), "tokens_median": med([r["tokens"] for r in toy if r["tokens"]]),
            "wall_median": med([r["wall_seconds"] for r in toy])}
mem = {r["run_id"]: r for r in real if r["run_id"].startswith("memory-")}
m["memory_pair"] = {k: {"tokens": v["tokens"], "wall": v["wall_seconds"], "obstacles": len(v["obstacles"]), "memory_read": v["memory_read"]} for k, v in mem.items()}
m["arxiv"] = [{"run": r["run_id"], "outcome": r["outcome"], "correct": r["correct"], "total": r["total"], "tokens": r["tokens"]} for r in real if r["source"] == "arxiv"]
offline = [r for r in runs if r["agent_kind"] in ("scripted", "fake")]
m["offline_runs"] = {"n": len(offline), "outcomes": Counter(r["outcome"] for r in offline)}

(SP / "out/metrics.json").write_text(json.dumps(m, indent=1, default=lambda o: dict(o) if isinstance(o, Counter) else str(o)))
(SP / "out/runs_ran.json").write_text(json.dumps(cb_ran, indent=1))
print(json.dumps({k: v for k, v in m.items() if k not in ("paper_best",)}, indent=1, default=lambda o: dict(o) if isinstance(o, Counter) else str(o)))
