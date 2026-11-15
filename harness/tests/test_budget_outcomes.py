"""Scoring of plan-first runs: projections, the width cap and the one outcome per run.

Standard library only:  python3 -m unittest discover -s harness/tests -t .
Uses a made-up answer key, never a real one.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness.score import classify, score_report

ROOT = Path(__file__).resolve().parents[2]
TOY = ROOT / "contract" / "fixtures" / "tasks" / "toy-linreg"
KEY = {"task_id": "toy-linreg", "questions": {"q1": {"type": "number", "values": [0.4555]},
                                              "q2": {"type": "string", "values": ["ridge-weak"]}}}

_spec = importlib.util.spec_from_file_location("contract_validate", ROOT / "contract" / "validate.py")
assert _spec is not None and _spec.loader is not None
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


def answer(qid, value, **extra):
    return {"question_id": qid, "value": value, "evidence": None, "confidence": "medium", **extra}


def report(*answers, plan=None):
    out = {"task_id": "toy-linreg", "status": "completed", "answers": list(answers)}
    if plan:
        out["plan"] = {"path": plan}
    return out


class OutcomeTest(unittest.TestCase):
    def test_runs_without_a_plan_score_as_before(self) -> None:
        self.assertEqual(score_report(report(answer("q1", 0.4555), answer("q2", "ridge-weak")), KEY)["outcome"], "reproduced")
        self.assertEqual(score_report(report(answer("q1", 0.4555), answer("q2", "lasso")), KEY)["outcome"], "partly")
        self.assertEqual(score_report(report(answer("q1", None), answer("q2", None)), KEY)["outcome"], "not_reproduced")

    def test_a_projection_in_range_is_verifiable_never_correct(self) -> None:
        score = score_report(report(answer("q1", 0.452, scaled=True, interval=[0.44, 0.47]),
                                    answer("q2", "ridge-weak", scaled=True), plan="scaled"), KEY)
        self.assertEqual((score["outcome"], score["correct"], score["verifiable"]), ("verifiable", 0, 2))
        self.assertFalse(score["all_correct"])
        self.assertEqual(score["outcome_label"], "Verifiable within budget")
        q1 = score["per_question"]["q1"]
        self.assertEqual((q1["scaled"], q1["verifiable"], q1["interval"]), (True, True, [0.44, 0.47]))

    def test_a_projection_out_of_range_or_too_vague_is_not_verifiable(self) -> None:
        out = score_report(report(answer("q1", 0.305, scaled=True, interval=[0.30, 0.31]),
                                  answer("q2", "ridge-weak", scaled=True), plan="scaled"), KEY)
        self.assertEqual(out["outcome"], "not_verifiable")
        self.assertIn("outside", out["per_question"]["q1"]["why"])
        vague = score_report(report(answer("q1", 0.45, scaled=True, interval=[0.30, 0.60]),
                                    answer("q2", "ridge-weak", scaled=True), plan="scaled"), KEY)
        self.assertEqual(vague["outcome"], "not_verifiable")
        self.assertIn("too vague", vague["per_question"]["q1"]["why"])

    def test_the_weakest_answer_decides(self) -> None:
        # One exact answer from a full part, one projection out of range: not verifiable.
        mixed = score_report(report(answer("q1", 0.40, scaled=True, interval=[0.39, 0.41]), answer("q2", "ridge-weak"),
                                    plan="scaled"), KEY)
        self.assertEqual(mixed["outcome"], "not_verifiable")
        # One exact answer and one projection in range: verifiable, not reproduced.
        good = score_report(report(answer("q1", 0.452, scaled=True, interval=[0.44, 0.47]), answer("q2", "ridge-weak"),
                                   plan="scaled"), KEY)
        self.assertEqual((good["outcome"], good["correct"]), ("verifiable", 1))

    def test_a_not_verifiable_plan_or_a_budget_no_answer(self) -> None:
        reason = {"category": "not_verifiable_within_budget", "reason": "needs a GPU"}
        planned = score_report(report(answer("q1", None, no_answer=reason), answer("q2", None, no_answer=reason),
                                      plan="not_verifiable"), KEY)
        self.assertEqual(planned["outcome"], "not_verifiable")
        self.assertEqual(planned["per_question"]["q1"]["no_answer_reason"], "needs a GPU")
        # A full plan whose experiment turned out too slow, said so per question: not verifiable either.
        late = score_report(report(answer("q1", None, no_answer=reason), answer("q2", "ridge-weak"), plan="full"), KEY)
        self.assertEqual(late["outcome"], "not_verifiable")
        # A scaled plan that ran out of time with nothing recorded.
        self.assertEqual(classify({"plan": {"path": "scaled"}}, {"q1": {"correct": False}}), "not_verifiable")


class FakeAgentScenarioTest(unittest.TestCase):
    """The demo replays of the two new paths write valid runs that score as intended."""

    def play(self, scenario: str) -> tuple[Path, dict]:
        tmp = Path(tempfile.mkdtemp(prefix="repro-fake-"))
        run_dir = tmp / "run"
        done = subprocess.run([sys.executable, "-m", "harness.fake_agent", "--task", str(TOY), "--run", str(run_dir),
                               "--auto-approve", "--speed", "0", "--scenario", scenario],
                              cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(validate.validate_run(run_dir, TOY), [])
        return run_dir, json.loads((run_dir / "report.json").read_text())

    def test_scaled(self) -> None:
        run_dir, rep = self.play("scaled")
        self.assertEqual(score_report(rep, KEY)["outcome"], "verifiable")
        request = json.loads((run_dir / "approvals" / "a1.request.json").read_text())
        self.assertIn("scaled down", request["summary"])
        self.assertEqual(request["scale_down"][0]["setting"], "seeds")

    def test_not_verifiable(self) -> None:
        _, rep = self.play("not_verifiable")
        self.assertEqual(rep["status"], "completed")
        self.assertEqual(score_report(rep, KEY)["outcome"], "not_verifiable")


if __name__ == "__main__":
    unittest.main()
