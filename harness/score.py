"""Score a run's report against the answer key. Standard library only.

    python -m harness.score <run_dir>

Answer key: harness/answers/<task_id>.json

    {"task_id": "toy-linreg",
     "questions": {"q1": {"type": "number", "values": [0.4555]},
                   "q2": {"type": "string", "values": ["ridge-weak"]}}}

`values` holds the answer from each reference run (CORE-Bench records three).

Rules, following CORE-Bench's evaluations.py (MIT, Siegel et al.):
- number: correct if inside the 95% prediction interval of the reference runs.
- string: case-insensitive exact match with the first reference value.
- list: equal to the first reference value.
One deliberate difference: the numeric interval is widened by 0.5% of the
mean (so 0.4555 matches a reference of 0.45551, and a single reference run
still gives a usable band). CORE-Bench itself would require an exact match
when the reference runs are identical.

Budget outcomes (beyond CORE-Bench; see research "Plan-First Runs and
Budget-Scaled Verification"). A run whose plan was "scaled" reports number
answers as projections with an interval. Such an answer is never correct; it
is "verifiable" when the reference value lies inside the interval and the
interval's half-width is at most 10% of the projected value. Each run gets one
outcome, the weakest across its answers:
  reproduced | partly | verifiable | not_verifiable | not_reproduced
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from .common import ANSWERS, read_json

# Two-sided 95% t critical values by degrees of freedom.
T_975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
REL_SLACK = 0.005
ABS_SLACK = 1e-9


def load_key(task_id: str) -> dict | None:
    key = read_json(ANSWERS / f"{task_id}.json")
    return key if isinstance(key, dict) and isinstance(key.get("questions"), dict) else None


def to_number(value):
    """CORE-Bench strips '%' and tries float(); do the same."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace("%", "").replace(",", "").strip())
        except ValueError:
            return None
    return None


def interval(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    half = 0.0
    if n > 1:
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        t = T_975.get(n - 1, 1.96)
        half = t * math.sqrt(var) * math.sqrt(1 + 1 / n)
    slack = abs(mean) * REL_SLACK + ABS_SLACK
    return mean - half - slack, mean + half + slack


def score_answer(value, ref: dict) -> dict:
    """Return {'correct': bool, 'expected': display value, 'why': str}."""
    rtype = ref.get("type")
    values = ref.get("values") or []
    if not values:
        return {"correct": False, "expected": None, "why": "no reference value"}
    if rtype == "number":
        nums = [float(v) for v in values]
        lo, hi = interval(nums)
        expected = sum(nums) / len(nums)
        got = to_number(value)
        if got is None:
            return {"correct": False, "expected": expected, "range": [lo, hi], "why": "no numeric answer"}
        ok = lo <= got <= hi
        return {"correct": ok, "expected": expected, "range": [lo, hi],
                "why": "inside the accepted range" if ok else "outside the accepted range"}
    if rtype == "list":
        ok = value == values[0]
        return {"correct": ok, "expected": values[0], "why": "lists match" if ok else "lists differ"}
    ok = value is not None and str(value).strip().lower() == str(values[0]).strip().lower()
    return {"correct": ok, "expected": values[0], "why": "text matches" if ok else "text differs"}


INTERVAL_CAP = 0.10  # a projection's half-width may be at most this share of its value
OUTCOMES = {
    "reproduced": "Reproduced",
    "partly": "Partly reproduced",
    "verifiable": "Verifiable within budget",
    "not_verifiable": "Not verifiable within budget",
    "not_reproduced": "Not reproduced",
}
BUDGET_CATEGORY = "not_verifiable_within_budget"


def score_projection(answer: dict, ref: dict) -> dict:
    """Score an answer from a scaled-down run. It is never correct, at best verifiable."""
    plain = score_answer(answer.get("value"), ref)
    result = {"correct": False, "scaled": True, "expected": plain.get("expected")}
    if "range" in plain:
        result["range"] = plain["range"]
    interval_ = answer.get("interval")
    if ref.get("type") != "number" or not isinstance(interval_, list):
        # A text or list answer from a scaled run: verifiable when it matches.
        result["verifiable"] = bool(plain["correct"])
        result["why"] = "matches the reference" if plain["correct"] else "differs from the reference"
        return result
    value = to_number(answer.get("value"))
    try:
        lo, hi = (float(b) for b in interval_)
    except (TypeError, ValueError):
        result.update({"verifiable": False, "why": "the projection's interval is unreadable"})
        return result
    result["interval"] = [lo, hi]
    expected = plain.get("expected")
    if value is None or expected is None:
        result.update({"verifiable": False, "why": plain.get("why", "no reference value")})
        return result
    half = (hi - lo) / 2
    if half > INTERVAL_CAP * abs(value):
        result.update({"verifiable": False, "why": f"projection too vague (±{half / abs(value):.0%} > ±{INTERVAL_CAP:.0%})"
                       if value else "projection too vague"})
    elif lo <= expected <= hi:
        result.update({"verifiable": True, "why": "the reference value lies inside the projection's interval"})
    else:
        result.update({"verifiable": False, "why": "the reference value lies outside the projection's interval"})
    return result


def classify(report: dict, per_question: dict) -> str:
    """One outcome per run, the weakest across its answers (see the module docstring)."""
    plan = report.get("plan")
    plan_path = plan.get("path") if isinstance(plan, dict) else None
    results = list(per_question.values())
    budget = plan_path in ("scaled", "not_verifiable") or any(
        r.get("scaled") or r.get("no_answer_category") == BUDGET_CATEGORY for r in results)
    if budget:
        if results and any(r.get("scaled") for r in results) and all(r["correct"] or r.get("verifiable") for r in results):
            return "verifiable"
        return "not_verifiable"
    correct = sum(1 for r in results if r["correct"])
    if results and correct == len(results):
        return "reproduced"
    return "partly" if correct else "not_reproduced"


def score_report(report: dict, key: dict) -> dict:
    answers = {a.get("question_id"): a for a in report.get("answers") or [] if isinstance(a, dict)}
    per_question = {}
    correct = verifiable = 0
    for qid, ref in key["questions"].items():
        answer = answers.get(qid) or {}
        value = answer.get("value")
        if answer.get("scaled") and value is not None:
            result = score_projection(answer, ref)
        else:
            result = score_answer(value, ref)
        result["answered"] = value is not None
        no_answer = answer.get("no_answer")
        if value is None and isinstance(no_answer, dict):
            result["no_answer_category"] = no_answer.get("category")
            result["no_answer_reason"] = no_answer.get("reason")
        per_question[qid] = result
        correct += 1 if result["correct"] else 0
        verifiable += 1 if result.get("verifiable") else 0
    total = len(key["questions"])
    outcome = classify(report, per_question)
    return {"task_id": key.get("task_id"), "correct": correct, "verifiable": verifiable, "total": total,
            "all_correct": total > 0 and correct == total, "outcome": outcome, "outcome_label": OUTCOMES[outcome],
            "per_question": per_question}


def score_run(rdir: Path) -> dict | None:
    """None when there is no report or no answer key for the task."""
    report = read_json(Path(rdir) / "report.json")
    if not isinstance(report, dict):
        return None
    key = load_key(str(report.get("task_id", "")))
    if key is None:
        return None
    return score_report(report, key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score a run against its answer key.")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    result = score_run(args.run_dir)
    if result is None:
        print("No score: the run has no report.json, or there is no answer key for its task.")
        return 2
    for qid, r in result["per_question"].items():
        if r.get("scaled"):
            mark = "in range" if r.get("verifiable") else "no range"
        else:
            mark = "correct " if r["correct"] else "wrong   "
        print(f"{mark}  {qid}  expected {r['expected']!r}  ({r['why']})")
    print(f"{result['correct']}/{result['total']} correct · {result['outcome_label']}")
    return 0 if result["all_correct"] else 1


if __name__ == "__main__":
    sys.exit(main())
