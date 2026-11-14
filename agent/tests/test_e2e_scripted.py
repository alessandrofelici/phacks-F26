"""End-to-end runs of the real command on the toy task with the offline scripted model.

These start `python -m agent.run` as the harness would, so they cover the deep agent graph,
the sandbox, approvals, events and the report. They need the agent's dependencies and
network access (pip installs numpy):

    agent/.venv/bin/python -m unittest discover -s agent/tests -t .
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOY = REPO_ROOT / "contract" / "fixtures" / "tasks" / "toy-linreg"

_spec = importlib.util.spec_from_file_location("contract_validate", REPO_ROOT / "contract" / "validate.py")
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)

HAVE_DEPS = importlib.util.find_spec("deepagents") is not None


def events_of(run_dir: Path) -> list[dict]:
    return [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]


@unittest.skipUnless(HAVE_DEPS, "needs the agent's dependencies (agent/requirements.txt)")
class ScriptedToyRun(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="repro-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.run_dir = self.tmp / "run"

    def start(self, *flags: str, task: Path = TOY, **env: str) -> subprocess.Popen:
        full_env = {**os.environ, "REPRO_MODEL": "scripted", "REPRO_WORK_ROOT": str(self.tmp / "work"), **env}
        return subprocess.Popen(
            [sys.executable, "-m", "agent.run", "--task", str(task), "--run", str(self.run_dir), *flags],
            cwd=REPO_ROOT,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def finish(self, process: subprocess.Popen, task: Path = TOY) -> dict:
        output, _ = process.communicate(timeout=600)
        self.assertEqual(process.returncode, 0, output)
        self.assertEqual(validate.validate_run(self.run_dir, task), [], output)
        return json.loads((self.run_dir / "report.json").read_text())

    def decide(self, decision: str, note: str = "") -> None:
        """Play the harness: answer the first approval request when it appears."""
        request = self.run_dir / "approvals" / "a1.request.json"
        deadline = time.time() + 300
        while not request.exists() and time.time() < deadline:
            time.sleep(0.2)
        payload = {"id": "a1", "decision": decision, "note": note, "by": "human"}
        (self.run_dir / "approvals" / "a1.decision.json").write_text(json.dumps(payload))

    def test_auto_approve_reproduces_the_toy(self) -> None:
        report = self.finish(self.start("--auto-approve"))
        self.assertEqual(report["status"], "completed")
        answers = {a["question_id"]: a for a in report["answers"]}
        self.assertEqual(answers["q1"]["value"], 0.4555)
        self.assertEqual(answers["q2"]["value"], "ridge-weak")
        for answer in answers.values():  # the evidence quote really is in the cited log
            log = (self.run_dir / answer["evidence"]["file"]).read_text()
            self.assertIn(answer["evidence"]["quote"], log)
        self.assertTrue(any(o["stage"] == "env" and o["resolved"] for o in report["obstacles"]))
        events = events_of(self.run_dir)
        types = [e["type"] for e in events]
        for wanted in ("todo_updated", "tool_call", "approval_requested", "approval_resolved", "answer_found"):
            self.assertIn(wanted, types)
        resolved = next(e for e in events if e["type"] == "approval_resolved")
        self.assertEqual(resolved["data"]["by"], "auto")
        original = (TOY / "repo" / "requirements.txt").read_text()
        self.assertEqual(original.strip(), "numpy==1.19.5", "the task directory must stay untouched")

    def test_human_approval_resumes_the_run(self) -> None:
        process = self.start()
        threading.Thread(target=self.decide, args=("approve",), daemon=True).start()
        report = self.finish(process)
        self.assertEqual(report["status"], "completed")
        resolved = next(e for e in events_of(self.run_dir) if e["type"] == "approval_resolved")
        self.assertEqual((resolved["data"]["decision"], resolved["data"]["by"]), ("approve", "human"))

    def test_rejection_ends_with_status_rejected_and_null_answers(self) -> None:
        process = self.start()
        threading.Thread(target=self.decide, args=("reject", "not on my GPU"), daemon=True).start()
        report = self.finish(process)
        self.assertEqual(report["status"], "rejected")
        self.assertEqual([a["value"] for a in report["answers"]], [None, None])
        self.assertTrue(all(a["evidence"] is None for a in report["answers"]))
        self.assertTrue(any("rejected" in o["summary"] for o in report["obstacles"]))

    def test_unanswered_approval_times_out_as_rejection(self) -> None:
        report = self.finish(self.start(REPRO_APPROVAL_TIMEOUT="2"))
        self.assertEqual(report["status"], "rejected")
        resolved = next(e for e in events_of(self.run_dir) if e["type"] == "approval_resolved")
        self.assertEqual(resolved["data"]["by"], "timeout")

    def test_run_over_its_time_limit_reports_timeout(self) -> None:
        task = self.tmp / "toy-linreg"
        shutil.copytree(TOY, task)
        spec = json.loads((task / "task.json").read_text())
        spec["limits"]["max_minutes"] = 0.02  # about a second
        (task / "task.json").write_text(json.dumps(spec))
        report = self.finish(self.start("--auto-approve", task=task), task=task)
        self.assertEqual(report["status"], "timeout")
        self.assertEqual(events_of(self.run_dir)[-1]["data"]["status"], "timeout")


if __name__ == "__main__":
    unittest.main()
