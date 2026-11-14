"""Checks of the run-directory writer and the findings against contract/validate.py.

Standard library only:  python3 -m unittest discover -s agent/tests -t .
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from agent.rundir import RunDirError, RunWriter
from agent.task import Findings, Task

REPO_ROOT = Path(__file__).resolve().parents[2]
TOY = REPO_ROOT / "contract" / "fixtures" / "tasks" / "toy-linreg"

_spec = importlib.util.spec_from_file_location("contract_validate", REPO_ROOT / "contract" / "validate.py")
assert _spec is not None and _spec.loader is not None
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


class RunWriterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name) / "r1"
        self.addCleanup(self.tmp.cleanup)

    def finish(self, writer: RunWriter, findings: Findings, status: str = "completed") -> dict:
        writer.event("run_finished", {"status": status})
        report = findings.report(run_id="r1", status=status, wall_seconds=1.0, tokens=None, why_missing="test")
        writer.write_report(report)
        writer.close()
        return report

    def start(self, **kwargs) -> tuple[RunWriter, Findings]:
        writer = RunWriter(self.run_dir, **kwargs)
        writer.event("run_started", {"task_id": "toy-linreg", "run_id": "r1"})
        return writer, Findings(Task.load(TOY), writer)

    def test_valid_run_with_answers_and_auto_approval(self) -> None:
        writer, findings = self.start(auto_approve=True)
        decision = writer.request_approval("long_run", "Run python run.py", command="python run.py")
        self.assertEqual((decision["decision"], decision["by"]), ("approve", "auto"))
        writer.save_log("python run.py", "$ python run.py\nbest model: ridge-weak\ntest r2: 0.4555\n")
        self.assertIn("Recorded", findings.record_answer("q1", "0.4555", "test r2: 0.4555", "high"))
        self.assertIn("Recorded", findings.record_answer("q2", "ridge-weak", "best model: ridge-weak", "high"))
        report = self.finish(writer, findings)
        self.assertEqual(validate.validate_run(self.run_dir, TOY), [])
        self.assertEqual(report["answers"][0]["value"], 0.4555)
        self.assertEqual(report["answers"][0]["evidence"]["file"], "logs/01-python-run-py.txt")
        self.assertFalse(list(self.run_dir.glob(".*.tmp")), "temp files must not be left behind")

    def test_quote_must_come_from_saved_output(self) -> None:
        writer, findings = self.start()
        writer.save_log("python run.py", "test r2: 0.4555\n")
        self.assertIn("Error", findings.record_answer("q1", 0.46, "test r2: 0.46", "high"))
        self.assertIn("Error", findings.record_answer("q9", 1, "test r2: 0.4555", "high"))
        self.assertIn("Error", findings.record_answer("q1", "not a number", "test r2: 0.4555", "high"))
        self.assertEqual(findings.answers, {})
        report = self.finish(writer, findings, status="failed")
        self.assertEqual(validate.validate_run(self.run_dir, TOY), [])
        self.assertEqual([a["value"] for a in report["answers"]], [None, None])
        self.assertEqual(len(report["obstacles"]), 2, "each unanswered question explains itself")

    def test_human_decision_is_picked_up(self) -> None:
        writer, findings = self.start(poll_s=0.05)

        def harness() -> None:
            request = self.run_dir / "approvals" / "a1.request.json"
            while not request.exists():
                time.sleep(0.02)
            decision = {"id": "a1", "decision": "reject", "note": "too slow", "by": "human"}
            (self.run_dir / "approvals" / "a1.decision.json").write_text(json.dumps(decision))

        thread = threading.Thread(target=harness)
        thread.start()
        decision = writer.request_approval("long_run", "Run train.py", command="python train.py")
        thread.join()
        self.assertEqual((decision["decision"], decision["by"], decision["note"]), ("reject", "human", "too slow"))
        self.finish(writer, findings, status="rejected")
        self.assertEqual(validate.validate_run(self.run_dir, TOY), [])

    def test_no_decision_counts_as_rejection_by_timeout(self) -> None:
        writer, findings = self.start(poll_s=0.05, approval_timeout_s=0.2)
        decision = writer.request_approval("long_run", "Run train.py", command="python train.py")
        self.assertEqual((decision["decision"], decision["by"]), ("reject", "timeout"))
        written = json.loads((self.run_dir / "approvals" / "a1.decision.json").read_text())
        self.assertEqual(written["by"], "timeout")
        self.finish(writer, findings, status="rejected")
        self.assertEqual(validate.validate_run(self.run_dir, TOY), [])

    def test_events_are_numbered_and_flushed(self) -> None:
        writer, _ = self.start()
        writer.event("tool_call", {"tool": "execute", "summary": "ls", "ok": True})
        lines = (self.run_dir / "events.jsonl").read_text().splitlines()  # readable before close
        self.assertEqual([json.loads(line)["seq"] for line in lines], [1, 2])
        self.assertEqual(validate.validate_run(self.run_dir, TOY, partial=True), [])
        writer.close()

    def test_a_used_run_directory_is_refused(self) -> None:
        writer, _ = self.start()
        writer.close()
        with self.assertRaises(RunDirError):
            RunWriter(self.run_dir)


if __name__ == "__main__":
    unittest.main()
