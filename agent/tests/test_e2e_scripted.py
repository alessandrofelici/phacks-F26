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
assert _spec is not None and _spec.loader is not None
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
        full_env = {
            **os.environ,
            "REPRO_MODEL": "scripted",
            "REPRO_WORK_ROOT": str(self.tmp / "work"),
            "REPRO_MEMORY_DIR": str(self.tmp / "memory"),  # each test starts with nothing remembered
            "REPRO_SANDBOX": "local",  # fast; the Podman sandbox has its own tests below
            "LANGSMITH_TRACING": "false",  # a developer's .env must not turn tracing on in tests
            **env,
        }
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

    def decide(self, decision: str, note: str = "", approval_id: str = "a1") -> None:
        """Play the harness: answer an approval request when it appears."""
        request = self.run_dir / "approvals" / f"{approval_id}.request.json"
        deadline = time.time() + 300
        while not request.exists() and time.time() < deadline:
            time.sleep(0.2)
        payload = {"id": approval_id, "decision": decision, "note": note, "by": "human"}
        (self.run_dir / "approvals" / f"{approval_id}.decision.json").write_text(json.dumps(payload))

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
        for wanted in (
            "todo_updated",
            "subagent_started",
            "subagent_finished",
            "tool_call",
            "approval_requested",
            "approval_resolved",
            "memory_read",
            "memory_written",
            "answer_found",
        ):
            self.assertIn(wanted, types)
        started = [e["data"]["name"] for e in events if e["type"] == "subagent_started"]
        self.assertEqual(started, ["paper-reader", "env-builder", "runner", "result-judge"])
        doers = {e["agent"] for e in events if e["type"] == "tool_call"}
        self.assertEqual(doers, {"paper-reader", "env-builder", "runner", "result-judge"}, "steps name the subagent that did them")
        self.assertEqual({e["agent"] for e in events if e["type"] == "answer_found"}, {"result-judge"})
        resolved = next(e for e in events if e["type"] == "approval_resolved")
        self.assertEqual(resolved["data"]["by"], "auto")
        original = (TOY / "repo" / "requirements.txt").read_text()
        self.assertEqual(original.strip(), "numpy==1.19.5", "the task directory must stay untouched")

    def test_second_run_reuses_the_remembered_fix(self) -> None:
        first = self.finish(self.start("--auto-approve"))
        self.assertTrue(first["obstacles"], "the first run hits the numpy pin")
        first_commands = [e["data"]["summary"] for e in events_of(self.run_dir) if e["data"].get("tool") == "execute"]
        self.assertTrue(any("repo/requirements.txt" in c for c in first_commands))

        self.run_dir = self.tmp / "run2"
        second = self.finish(self.start("--auto-approve"))
        self.assertEqual(second["status"], "completed")
        self.assertEqual({a["question_id"]: a["value"] for a in second["answers"]}, {"q1": 0.4555, "q2": "ridge-weak"})
        events = events_of(self.run_dir)
        reads = [e for e in events if e["type"] == "memory_read"]
        self.assertTrue(any("1 " in e["data"]["note"] for e in reads), "the remembered fix is reported as read")
        commands = [e["data"] for e in events if e["data"].get("tool") == "execute"]
        self.assertFalse(any("repo/requirements.txt" in c["summary"] for c in commands), "the failing install is skipped")
        self.assertTrue(all(c["ok"] for c in commands))
        self.assertEqual(second["obstacles"], [])

    def test_changing_a_repo_file_needs_an_edit_source_approval(self) -> None:
        process = self.start(REPRO_SCRIPT_EDIT_SOURCE="1")

        def harness() -> None:
            self.decide("reject", "leave the paper's files alone", "a1")
            self.decide("approve", "", "a2")

        threading.Thread(target=harness, daemon=True).start()
        report = self.finish(process)
        self.assertEqual(report["status"], "completed", "a rejected edit is not fatal when another way works")
        request = json.loads((self.run_dir / "approvals" / "a1.request.json").read_text())
        self.assertEqual(request["kind"], "edit_source")
        self.assertIn("/repo/requirements.txt", request["summary"])
        self.assertIn("-numpy==1.19.5", request["diff"])
        self.assertIn("+numpy>=1.26", request["diff"])
        events = events_of(self.run_dir)
        edit = next(e for e in events if e["data"].get("tool") == "edit_file")
        self.assertFalse(edit["data"]["ok"], "the rejected edit shows as not done")
        asked = [e for e in events if e["type"] == "approval_requested"]
        self.assertEqual([e["data"]["kind"] for e in asked], ["edit_source", "long_run"])
        self.assertEqual({e["agent"] for e in asked}, {"env-builder", "runner"})
        self.assertEqual(report["source_changes"], [], "the rejected edit left the file alone")

    def test_an_approved_edit_is_listed_as_approved(self) -> None:
        process = self.start(REPRO_SCRIPT_EDIT_SOURCE="1")

        def harness() -> None:
            self.decide("approve", "", "a1")
            self.decide("approve", "", "a2")

        threading.Thread(target=harness, daemon=True).start()
        report = self.finish(process)
        self.assertEqual(report["source_changes"], [{"path": "repo/requirements.txt", "change": "modified", "approved": True}])
        self.assertFalse(any("without an approval" in o["summary"] for o in report["obstacles"]))

    def test_a_shell_command_that_changes_a_repo_file_is_reported(self) -> None:
        report = self.finish(self.start("--auto-approve", REPRO_SCRIPT_TAMPER="1"))
        self.assertEqual(report["source_changes"], [{"path": "repo/run.py", "change": "modified", "approved": False}])
        self.assertTrue(any("without an approval" in o["summary"] and "repo/run.py" in o["summary"] for o in report["obstacles"]))

    def check_background_run(self, sandbox: str) -> None:
        report = self.finish(self.start("--auto-approve", REPRO_SCRIPT_BACKGROUND="1", REPRO_SANDBOX=sandbox))
        self.assertEqual(report["status"], "completed")
        self.assertEqual({a["question_id"]: a["value"] for a in report["answers"]}, {"q1": 0.4555, "q2": "ridge-weak"})
        events = events_of(self.run_dir)
        steps = [e["data"]["summary"] for e in events if e["type"] == "tool_call" and e["agent"] == "runner"]
        self.assertTrue(steps[0].startswith("start in the background"))
        self.assertTrue(any("still running" in step for step in steps), "the agent got control back while it ran")
        self.assertTrue(any("exit code 0" in step for step in steps))
        asked = next(e for e in events if e["type"] == "approval_requested")
        self.assertIn("in the background", asked["data"]["summary"])
        evidence = report["answers"][0]["evidence"]
        self.assertIn(evidence["quote"], (self.run_dir / evidence["file"]).read_text(), "background output is saved as a log")

    def test_background_run_local(self) -> None:
        self.check_background_run("local")

    @unittest.skipUnless(shutil.which("podman"), "needs podman")
    def test_background_run_podman(self) -> None:
        self.check_background_run("podman")

    @unittest.skipUnless(shutil.which("podman"), "needs podman")
    def test_podman_sandbox_reproduces_the_toy_out_of_reach_of_the_host(self) -> None:
        secret = self.tmp / "host-only.txt"
        secret.write_text("answer key stand-in")
        report = self.finish(self.start("--auto-approve", REPRO_SANDBOX="podman", REPRO_SCRIPT_PROBE=str(secret)))
        self.assertEqual(report["status"], "completed")
        self.assertEqual({a["question_id"]: a["value"] for a in report["answers"]}, {"q1": 0.4555, "q2": "ridge-weak"})
        self.assertTrue(report["sandbox"].startswith("podman"))
        events = events_of(self.run_dir)
        self.assertTrue(events[0]["data"]["sandbox"].startswith("podman"))
        probe = next(e for e in events if e["data"].get("tool") == "execute" and "host-only" in e["data"]["summary"])
        self.assertFalse(probe["data"]["ok"], "a file outside the workspace can't be read from the sandbox")
        self.assertNotIn("answer key stand-in", probe["data"].get("detail", ""))
        container = events[0]["data"]["container"]  # other runs may have their own containers right now
        leftovers = subprocess.run(
            ["podman", "ps", "-a", "-q", "--filter", f"name=^{container}$"], capture_output=True, text=True, check=False
        )
        self.assertEqual(leftovers.stdout.strip(), "", "the container is removed after the run")

    def test_tracing_with_a_bad_key_does_not_break_the_run(self) -> None:
        report = self.finish(
            self.start("--auto-approve", LANGSMITH_TRACING="true", LANGSMITH_API_KEY="lsv2_not_a_real_key")
        )
        self.assertEqual(report["status"], "completed")
        self.assertEqual({a["question_id"]: a["value"] for a in report["answers"]}, {"q1": 0.4555, "q2": "ridge-weak"})
        self.assertTrue(report["trace_url"] is None or report["trace_url"].startswith("https://"))

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
