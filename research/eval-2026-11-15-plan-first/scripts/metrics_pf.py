"""Before/after metrics for the plan-first runs. Usage: python3 metrics_pf.py <dir with runs_pf.json> <usd spent>"""
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

D = Path(sys.argv[1])
USD_SPENT = float(sys.argv[2]) if len(sys.argv) > 2 else None
rows = json.loads((D / "runs_pf.json").read_text())
after = [r for r in rows if r["group"] == "plan-first"]
before = [r for r in rows if r["group"] == "before" and not r["credit_stop"]]
papers = sorted({r["paper"] for r in after})
GROUPS = {"compute wall": ["0238624", "5496369", "9370340"], "reproduced before": ["6460826", "0940461", "1108125"]}
GOOD = ("reproduced",)
med = lambda xs: round(st.median(xs), 1) if xs else None  # noqa: E731


def group_of(p):
    for name, ps in GROUPS.items():
        if p in ps:
            return name
    return "cut off by credit"


m = {"runs_after": len(after), "papers_after": len(papers)}
m["outcomes_after"] = Counter(r["outcome"] for r in after)
m["scoper_first"] = sum(r["scoper_first"] for r in after)
m["plan_recorded"] = sum(1 for r in after if r["plan"])
m["plan_before_experiment"] = sum(1 for r in after if r["plan_before_experiment"])
m["plan_paths"] = Counter((r["plan"] or {}).get("path", "none") for r in after)
m["probes_runs"] = sum(1 for r in after if r["probes"])
m["refused_before_plan_runs"] = sum(1 for r in after if r["refused_before_plan"])
m["plan_minute_median"] = med([r["plan_minute"] for r in after if r["plan_minute"] is not None])
m["timeouts_after"] = sum(1 for r in after if r["outcome"] == "timed out")
m["timeouts_before_same_papers"] = sum(1 for r in before if r["paper"] in papers and r["outcome"] == "timed out")
m["runs_before_same_papers"] = sum(1 for r in before if r["paper"] in papers)

per_paper = {}
for p in papers:
    b = [r for r in before if r["paper"] == p]
    a = [r for r in after if r["paper"] == p]
    per_paper[p] = {
        "group": group_of(p),
        "before": [r["outcome"] for r in b], "after": [r["outcome"] for r in a],
        "plans": [(r["plan"] or {}).get("path") for r in a],
        "projected_minutes": [(r["plan"] or {}).get("projected_minutes") for r in a],
        "scale_down": [(r["plan"] or {}).get("scale_down") for r in a],
        "minutes_before": med([r["wall_seconds"] / 60 for r in b if r["wall_seconds"]]),
        "minutes_after": med([r["wall_seconds"] / 60 for r in a if r["wall_seconds"]]),
        "tokens_before": med([r["tokens"] for r in b if r["tokens"]]),
        "tokens_after": med([r["tokens"] for r in a if r["tokens"]]),
    }
m["per_paper"] = per_paper
for name in ("compute wall", "reproduced before", "cut off by credit"):
    ps = [p for p in papers if group_of(p) == name]
    a = [r for r in after if r["paper"] in ps]
    b = [r for r in before if r["paper"] in ps]
    m[f"group {name}"] = {
        "papers": len(ps), "runs_after": len(a), "outcomes_after": Counter(r["outcome"] for r in a),
        "papers_reproduced_after": sum(1 for p in ps if any(r["outcome"] in GOOD for r in a if r["paper"] == p)),
        "minutes_median_before": med([r["wall_seconds"] / 60 for r in b if r["wall_seconds"]]),
        "minutes_median_after": med([r["wall_seconds"] / 60 for r in a if r["wall_seconds"]]),
        "tokens_median_before": med([r["tokens"] for r in b if r["tokens"]]),
        "tokens_median_after": med([r["tokens"] for r in a if r["tokens"]]),
    }

# Headline across every real run on the 20 papers (14 and 15 November).
everything = [r for r in rows if not r["credit_stop"]]
all_papers = sorted({r["paper"] for r in rows})
m["papers_total"] = len(all_papers)
m["papers_reproduced_any_run"] = sum(1 for p in all_papers if any(r["outcome"] in GOOD for r in everything if r["paper"] == p))
m["papers_reproduced_before"] = sum(1 for p in all_papers if any(r["outcome"] in GOOD for r in before if r["paper"] == p))
m["papers_verifiable_only"] = sum(1 for p in all_papers if not any(r["outcome"] in GOOD for r in everything if r["paper"] == p)
                                  and any(r["outcome"] == "verifiable" for r in everything if r["paper"] == p))
m["tokens_after_total"] = sum(r["tokens"] or 0 for r in after)
m["tokens_median_after"] = med([r["tokens"] for r in after if r["tokens"]])
m["minutes_median_after"] = med([r["wall_seconds"] / 60 for r in after if r["wall_seconds"]])
if USD_SPENT is not None:
    m["usd_spent"] = USD_SPENT
    m["usd_per_run"] = round(USD_SPENT / max(1, len(after)), 3)
    m["usd_per_mtok"] = round(USD_SPENT / max(1e-9, m["tokens_after_total"] / 1e6), 3)
m["answers_after"] = {"total": sum(r["total"] or 0 for r in after), "correct": sum(r["correct"] or 0 for r in after),
                      "verifiable": sum(r["verifiable"] or 0 for r in after), "answered": sum(r["answered"] for r in after),
                      "no_answer_categories": Counter(c for r in after for c in r["no_answer_categories"])}

(D / "metrics_pf.json").write_text(json.dumps(m, indent=1, default=lambda o: dict(o) if isinstance(o, Counter) else str(o)))
print(json.dumps({k: v for k, v in m.items() if k != "per_paper"}, indent=1, default=lambda o: dict(o) if isinstance(o, Counter) else str(o)))
