"""Answers read off a figure: only an image this run wrote counts (standard library only)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from agent.rundir import RunWriter
from agent.task import Findings, Task


class FigureAnswers(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        task_dir = self.tmp / "task"
        (task_dir / "repo").mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "contract_version": 1,
                    "task_id": "fig-task",
                    "title": "Figure task",
                    "source": "fixture",
                    "instructions": "Run plot.py.",
                    "questions": [
                        {"id": "q1", "text": "Read the GRU accuracy off figure 1.", "type": "number", "needs_figure": True},
                        {"id": "q2", "text": "Report the printed loss.", "type": "number"},
                    ],
                    "limits": {"max_minutes": 5, "gpu": False, "network": False},
                }
            ),
            encoding="utf-8",
        )
        self.writer = RunWriter(self.tmp / "run", auto_approve=True, approval_timeout_s=1)
        self.findings = Findings(Task.load(task_dir), self.writer)
        self.work = self.tmp / "work"
        self.work.mkdir()

    def tearDown(self) -> None:
        self.writer.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def image(self, name: str, age_s: float = 0) -> Path:
        path = self.work / name
        path.write_bytes(b"\x89PNG\r\n\x1a\n fake")
        if age_s:
            old = time.time() - age_s
            os.utime(path, (old, old))
        return path

    def test_an_image_written_by_the_run_is_kept_as_evidence(self) -> None:
        reply = self.findings.record_answer("q1", 87.5, "ACC panel, GRU bar at 87.5", "medium", figure=self.image("fig1.png"))
        self.assertIn("Recorded", reply)
        evidence = self.findings.answers["q1"]["evidence"]
        self.assertEqual(evidence, {"file": "figures/q1-fig1.png", "quote": "ACC panel, GRU bar at 87.5"})
        self.assertTrue((self.tmp / "run" / evidence["file"]).is_file())

    def test_an_image_that_came_with_the_repository_is_refused(self) -> None:
        reply = self.findings.record_answer("q1", 87.5, "GRU bar", "medium", figure=self.image("old.png", age_s=3600))
        self.assertIn("came with the repository", reply)
        self.assertNotIn("q1", self.findings.answers)

    def test_a_figure_is_refused_for_a_question_about_printed_output(self) -> None:
        reply = self.findings.record_answer("q2", 0.3, "loss line", "high", figure=self.image("fig2.png"))
        self.assertIn("not read off a figure", reply)

    def test_a_file_that_is_not_an_image_is_refused(self) -> None:
        path = self.work / "table.csv"
        path.write_text("a,b\n", encoding="utf-8")
        self.assertIn("is not an image", self.findings.record_answer("q1", 1, "row", "low", figure=path))


if __name__ == "__main__":
    unittest.main()
