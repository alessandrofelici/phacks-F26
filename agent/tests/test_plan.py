"""Plan-first runs: the plan, the answer checks, no-answers and the runtime probe's projection.

Standard library only:  python3 -m unittest discover -s agent/tests -t .
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path

from agent.probe import describe, project
from agent.rundir import RunWriter, prints_only
from agent.task import Findings, Task, number_in_quote

REPO_ROOT = Path(__file__).resolve().parents[2]
TOY = REPO_ROOT / "contract" / "fixtures" / "tasks" / "toy-linreg"

_spec = importlib.util.spec_from_file_location("contract_validate", REPO_ROOT / "contract" / "validate.py")
assert _spec is not None and _spec.loader is not None
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)

RUN_OUTPUT = "$ python run.py\nbest model: ridge-weak\ntest r2: 0.4555\nbaseline r2: 0.3000\n"
PROJECTION = "projected test r2: 0.4555 (interval 0.4455 to 0.4655)"
SCALE_DOWN = [{"setting": "epochs", "original": 150, "scaled": 30, "kind": "convergence", "where": "train.py line 12"}]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name) / "r1"
        self.writer = RunWriter(self.run_dir)
        self.addCleanup(self.writer.close)
        self.writer.event("run_started", {"task_id": "toy-linreg", "run_id": "r1"})
        self.findings = Findings(Task.load(TOY), self.writer)
        self.findings.deadline = time.monotonic() + 15 * 60  # the toy's limit

    def finish(self, status: str = "completed") -> dict:
        self.writer.event("run_finished", {"status": status})
        report = self.findings.report(run_id="r1", status=status, wall_seconds=1.0, tokens=None, why_missing="test")
        self.writer.write_report(report)
        self.writer.close()
        self.assertEqual(validate.validate_run(self.run_dir, TOY), [])
        return report

    def plan_full(self) -> None:
        self.assertIn("Plan recorded", self.findings.record_plan("full", 1, ["run run.py"], "one short script"))

    def plan_scaled(self) -> None:
        message = self.findings.record_plan(
            "scaled", 100, ["train", "project"], "100 min don't fit", scale_down=SCALE_DOWN, scaled_minutes=5
        )
        self.assertIn("Plan recorded", message)

    def events(self, etype: str) -> list[dict]:
        lines = (self.run_dir / "events.jsonl").read_text().splitlines()
        return [e for e in map(json.loads, lines) if e["type"] == etype]


class PlanTest(Base):
    def test_no_plan_blocks_experiments(self) -> None:
        allowed, why = self.findings.runs_allowed()
        self.assertFalse(allowed)
        self.assertIn("scoper", why)

    def test_a_full_run_must_fit_in_sixty_percent_of_the_time_left(self) -> None:
        refused = self.findings.record_plan("full", 14, ["run run.py"], "guess")
        self.assertTrue(refused.startswith("Error"))
        self.assertIn("60%", refused)
        self.assertIsNone(self.findings.plan)
        self.assertTrue(self.findings.record_plan("full", None, ["run run.py"], "guess").startswith("Error"))
        self.plan_full()
        self.assertEqual(self.findings.runs_allowed(), (True, ""))
        event = self.events("plan_recorded")[-1]["data"]
        self.assertEqual(event["path"], "full")
        self.assertIn("full run", event["summary"])

    def test_a_scaled_plan_needs_a_scale_down_that_fits(self) -> None:
        def plan(**kwargs) -> str:
            args = {"scale_down": SCALE_DOWN, "scaled_minutes": 5, **kwargs}
            projected = args.pop("projected", 100)
            return self.findings.record_plan("scaled", projected, ["train"], "too long", **args)

        self.assertIn("choose 'full'", plan(projected=2))
        self.assertIn("needs scale_down", plan(scale_down=None))
        self.assertIn("kind must be one of", plan(scale_down=[{**SCALE_DOWN[0], "kind": "faster"}]))
        hardware = [{"setting": "device", "original": "cuda", "scaled": "cpu", "kind": "hardware"}]
        self.assertIn("not a scale-down by itself", plan(scale_down=hardware))
        self.assertIn("still don't fit", plan(scaled_minutes=60))
        self.assertIn("give scaled_minutes", plan(scaled_minutes=None))
        self.assertIsNone(self.findings.plan)
        self.assertIn("Plan recorded", plan(scale_down=json.dumps(SCALE_DOWN)))  # JSON text is accepted too
        self.assertEqual(self.findings.scale_note(), "epochs 150 → 30 (convergence)")
        self.assertTrue(self.findings.runs_allowed()[0])
        self.assertEqual(self.findings.plan["revision"], 1)

    def test_not_verifiable_refuses_runs_and_every_question_says_why(self) -> None:
        self.assertIn("Plan recorded", self.findings.record_plan("not_verifiable", None, ["run on a GPU"], "needs CUDA"))
        allowed, why = self.findings.runs_allowed()
        self.assertFalse(allowed)
        self.assertIn("record_no_answer", why)
        self.assertTrue(self.findings.record_no_answer("q1", "too_slow", "x").startswith("Error"))
        self.assertTrue(self.findings.record_no_answer("q1", "not_verifiable_within_budget", " ").startswith("Error"))
        for qid in ("q1", "q2"):
            self.assertIn("Recorded", self.findings.record_no_answer(qid, "not_verifiable_within_budget", "needs CUDA"))
        report = self.finish()
        self.assertEqual(report["plan"]["path"], "not_verifiable")
        self.assertEqual([a["no_answer"]["category"] for a in report["answers"]], ["not_verifiable_within_budget"] * 2)
        self.assertTrue(all(a["value"] is None for a in report["answers"]))
        self.assertTrue(any("not verifiable within budget" in o["summary"] for o in report["obstacles"]))
        self.assertEqual(len(self.events("no_answer")), 2)

    def test_a_finish_within_budget_needs_a_plan_and_a_budget_reason_for_every_gap(self) -> None:
        self.findings.no_answers["q1"] = {"category": "not_verifiable_within_budget", "reason": "x"}
        self.findings.no_answers["q2"] = {"category": "not_verifiable_within_budget", "reason": "x"}
        self.assertFalse(self.findings.finished_within_budget(), "no plan, no finish within budget")
        self.plan_scaled()  # a scaled run that found out on the way (0238624, 15 November)
        self.assertTrue(self.findings.finished_within_budget())
        self.findings.no_answers["q2"] = {"category": "environment", "reason": "R packages failed"}
        self.assertFalse(self.findings.finished_within_budget(), "an environment failure is still a give-up")


class AnswerCheckTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.plan_full()
        self.writer.save_log("python run.py", RUN_OUTPUT)

    def test_the_quote_must_show_the_value(self) -> None:
        refused = self.findings.record_answer("q1", 0.4555, "baseline r2: 0.3000", "high")
        self.assertIn("doesn't show the answer", refused)
        self.assertIn("0.3", refused)
        self.assertIn("Error", self.findings.record_answer("q1", 0.45, "test r2: 0.4555", "high"), "a wrong rounding is refused")
        self.assertIn("Recorded", self.findings.record_answer("q1", 0.46, "test r2: 0.4555", "high"), "rounding is fine")
        self.assertIn("Error", self.findings.record_answer("q2", "ridge", "test r2: 0.4555", "high"))
        self.assertIn("Recorded", self.findings.record_answer("q2", "Ridge-Weak", "best model: ridge-weak", "high"))
        report = self.finish()
        self.assertNotIn("scaled", report["answers"][0])

    def test_numbers_match_with_rounding_percentages_and_separators(self) -> None:
        self.assertTrue(number_in_quote(81.2, "accuracy: 0.812"))
        self.assertTrue(number_in_quote(0.812, "accuracy 81.2%"))
        self.assertTrue(number_in_quote(12, "n = 12.0"))
        self.assertTrue(number_in_quote(1234.5, "total 1,234.5"))
        self.assertTrue(number_in_quote(1.2e-05, "p = 1.2e-05"))
        self.assertTrue(number_in_quote(-0.53, "slope -0.5312"))
        self.assertFalse(number_in_quote(0.5, "value 0.4"))
        self.assertFalse(number_in_quote(0.53, "slope -0.5312"))

    def test_placeholder_text_is_refused(self) -> None:
        self.writer.save_log("Rscript install.R", "$ Rscript install.R\ninstallation of 7 packages failed:\n")
        refused = self.findings.record_answer("q2", "no answer", "installation of 7 packages failed:", "low")
        self.assertIn("record_no_answer", refused)
        self.assertEqual(self.findings.answers, {})

    def test_echo_output_and_the_command_line_are_not_evidence(self) -> None:
        self.writer.save_log("cd repo && echo 'test r2: 0.99'", "$ cd repo && echo 'test r2: 0.99'\ntest r2: 0.99\n")
        self.assertIn("not in the output", self.findings.record_answer("q1", 0.99, "test r2: 0.99", "high"))
        command = "python3 -c 'print(1)'  # test r2: 0.77"
        self.writer.save_log(command, f"$ {command}\n1\n")
        self.assertIn("not in the output", self.findings.record_answer("q1", 0.77, "test r2: 0.77", "high"))
        self.assertTrue(prints_only("cd repo && echo hi"))
        self.assertTrue(prints_only("printf '%s\\n' 'acc 0.9'"))
        self.assertFalse(prints_only("python run.py && echo done"))
        self.assertFalse(prints_only("echo 0 | python3 run.py"))

    def test_a_recorded_answer_is_not_replaced_by_a_no_answer(self) -> None:
        self.findings.record_answer("q1", 0.4555, "test r2: 0.4555", "high")
        self.assertTrue(self.findings.record_no_answer("q1", "other", "changed my mind").startswith("Error"))

    def test_an_interval_needs_a_scaled_plan(self) -> None:
        refused = self.findings.record_answer("q1", 0.4555, "test r2: 0.4555", "high", interval=[0.44, 0.47])
        self.assertIn("not scaled", refused)


class ScaledAnswerTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.plan_scaled()
        self.writer.save_log("python run.py", RUN_OUTPUT)
        self.writer.save_log("python project.py", f"$ python project.py\n{PROJECTION}\n")

    def test_number_answers_are_projections_with_printed_intervals(self) -> None:
        self.assertIn("give interval", self.findings.record_answer("q1", 0.4555, PROJECTION, "medium"))
        self.assertIn("bounds too", self.findings.record_answer("q1", 0.4555, PROJECTION, "medium", interval=[0.40, 0.50]))
        self.assertIn("must lie inside", self.findings.record_answer("q1", 0.5, PROJECTION, "medium", interval=[0.4455, 0.4655]))
        self.assertIn("two numbers", self.findings.record_answer("q1", 0.4555, PROJECTION, "medium", interval=[0.4455]))
        recorded = self.findings.record_answer("q1", 0.4555, PROJECTION, "medium", interval="[0.4455, 0.4655]")
        self.assertIn("projection", recorded)
        self.assertNotIn("Note", recorded)
        self.assertIn("Recorded", self.findings.record_answer("q2", "ridge-weak", "best model: ridge-weak", "high"))
        report = self.finish()
        q1, q2 = report["answers"]
        self.assertEqual((q1["interval"], q1["scaled"], q2["scaled"]), ([0.4455, 0.4655], True, True))
        self.assertNotIn("interval", q2)
        self.assertEqual(report["plan"]["scale_down"][0]["setting"], "epochs")

    def test_a_vague_interval_is_kept_with_a_warning(self) -> None:
        wide = "projected test r2: 0.45 (interval 0.30 to 0.60)"
        self.writer.save_log("python project.py --wide", f"$ python project.py --wide\n{wide}\n")
        recorded = self.findings.record_answer("q1", 0.45, wide, "low", interval=[0.30, 0.60])
        self.assertIn("Note", recorded)
        self.assertIn("not verifiable", recorded)
        self.assertEqual(self.findings.answers["q1"]["interval"], [0.30, 0.60])


class ProbeProjectionTest(unittest.TestCase):
    def test_keras_epochs_with_a_progress_bar(self) -> None:
        out = "Epoch 1/150\n250/250 [==============================] - 20s\nEpoch 2/150\n125/250 [=========>.........] - ETA: 10s"
        estimate = project(out, 60)
        self.assertEqual(estimate["progress"], "epoch 2 of 150")
        self.assertAlmostEqual(estimate["projected_minutes"], 100.0)  # 1.5 epochs in 60 s

    def test_epoch_lines_alone(self) -> None:
        estimate = project("loading\nEpoch 1/10 loss 0.9\nEpoch 2/10 loss 0.5\nEpoch 3/10 loss 0.2\n", 50)
        self.assertAlmostEqual(estimate["projected_minutes"], round(50 * 10 / 2.5 / 60, 1))

    def test_first_epoch_only_is_too_early(self) -> None:
        estimate = project("Epoch 1/150\n", 30)
        self.assertIsNone(estimate["projected_minutes"])
        self.assertIn("too early", describe("Epoch 1/150\n", 30, False, 124))

    def test_tqdm_states_its_remaining_time(self) -> None:
        bar = "fold:  40%|████      | 2/5 [00:30<00:45, 15.00s/it]"
        estimate = project(f"start\r{bar}", 40)
        self.assertAlmostEqual(estimate["projected_minutes"], round((40 + 45) / 60, 1))

    def test_other_counters(self) -> None:
        estimate = project("growing forest\ntree 40 of 1000\n", 60)
        self.assertEqual(estimate["progress"], "tree 40 of 1000")
        self.assertAlmostEqual(estimate["projected_minutes"], round(60 * 1000 / 39.5 / 60, 1))

    def test_no_progress_line(self) -> None:
        self.assertIsNone(project("loading data...\n", 30))
        self.assertIn("no progress line", describe("loading data...\n", 30, False, 124))

    def test_a_command_that_finishes_inside_the_probe(self) -> None:
        self.assertIn("finished in 12 s", describe("done\n", 12, True, 0))
        self.assertIn("failed", describe("Traceback\n", 3, True, 1))
        self.assertIn("about 100 min", describe("Epoch 1/150\n250/250 [====] - 20s\nEpoch 2/150\n125/250 [==>..] - ETA: 10s", 60, False, 124))


if __name__ == "__main__":
    unittest.main()
