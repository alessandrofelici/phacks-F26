"""Reads a task directory (CONTRACT.md section 1) and collects what the run found.

Standard library only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.rundir import RunWriter

CONTRACT_VERSION = 1
STAGES = ("read", "env", "data", "run", "extract", "other")
CONFIDENCES = ("high", "medium", "low")


class TaskError(RuntimeError):
    """The task directory can't be used."""


@dataclass
class Task:
    task_dir: Path
    task_id: str
    title: str
    instructions: str | None
    questions: list[dict[str, Any]]
    max_minutes: float
    gpu: bool
    network: bool

    @classmethod
    def load(cls, task_dir: Path | str) -> Task:
        task_dir = Path(task_dir)
        try:
            raw = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TaskError(f"cannot read {task_dir}/task.json: {exc}") from exc
        if raw.get("contract_version") != CONTRACT_VERSION:
            raise TaskError(f"task.json has contract_version {raw.get('contract_version')!r}, expected {CONTRACT_VERSION}")
        if not (task_dir / "repo").is_dir():
            raise TaskError(f"{task_dir}/repo is missing")
        limits = raw.get("limits") or {}
        return cls(
            task_dir=task_dir,
            task_id=raw["task_id"],
            title=raw.get("title", raw["task_id"]),
            instructions=raw.get("instructions"),
            questions=list(raw["questions"]),
            max_minutes=float(limits.get("max_minutes", 15)),
            gpu=bool(limits.get("gpu", False)),
            network=bool(limits.get("network", True)),
        )

    def question(self, question_id: str) -> dict[str, Any] | None:
        return next((q for q in self.questions if q.get("id") == question_id), None)

    def prompt(self) -> str:
        """The user message that starts the run."""
        lines = [f"Task: {self.title} (id {self.task_id})", ""]
        if self.instructions:
            lines += ["Instructions from the task:", self.instructions, ""]
        else:
            lines += ["The task gives no instructions: work out from the repository what to run.", ""]
        lines.append("Questions to answer:")
        for q in self.questions:
            figure = " The answer has to be read off a figure the code produces." if q.get("needs_figure") else ""
            lines.append(f"- {q['id']} ({q['type']}): {q['text']}{figure}")
        lines += [
            "",
            (
                f"Limits: {self.max_minutes:g} minutes for the whole run, "
                f"GPU {'allowed' if self.gpu else 'not allowed'}, "
                f"network {'allowed' if self.network else 'not allowed'}."
            ),
        ]
        return "\n".join(lines)


def _coerce(value: Any, qtype: str) -> Any:
    """Return ``value`` in the question's type, or raise ValueError."""
    if qtype == "number":
        if isinstance(value, bool):
            raise ValueError("a number is needed, not true/false")
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip().rstrip("%").replace(",", "")
            try:
                return int(text)
            except ValueError:
                return float(text)  # raises ValueError when it isn't a number
        raise ValueError("a number is needed")
    if qtype == "string":
        if isinstance(value, (dict, list)):
            raise ValueError("a string is needed")
        return str(value).strip()
    if qtype == "list":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            parsed = json.loads(value)  # JSONDecodeError is a ValueError
            if isinstance(parsed, list):
                return parsed
        raise ValueError("a list is needed")
    return value


@dataclass
class Findings:
    """Answers and obstacles recorded during a run, and the report built from them."""

    task: Task
    writer: RunWriter
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    obstacles: list[dict[str, Any]] = field(default_factory=list)

    def record_answer(self, question_id: str, value: Any, quote: str, confidence: str, agent: str = "main") -> str:
        """Store an answer if its quote is in a saved command output. Returns a message for the model."""
        question = self.task.question(question_id)
        if question is None:
            known = ", ".join(q["id"] for q in self.task.questions)
            return f"Error: there is no question '{question_id}'. The questions are: {known}."
        try:
            value = _coerce(value, question["type"])
        except ValueError as exc:
            return f"Error: {question_id} is a {question['type']} question; {exc}."
        if confidence not in CONFIDENCES:
            return f"Error: confidence must be one of {', '.join(CONFIDENCES)}."
        quote = (quote or "").strip()
        if not quote:
            return "Error: quote is empty. Give the exact line of command output the answer came from."
        log = self.writer.find_quote(quote)
        if log is None:
            return (
                "Error: that quote is not in the output of any command run so far. "
                "Answers must come from output produced in this run: copy the line exactly, "
                "or run the command that prints it."
            )
        self.answers[question_id] = {
            "question_id": question_id,
            "value": value,
            "evidence": {"file": log, "quote": quote},
            "confidence": confidence,
        }
        self.writer.event("answer_found", {"question_id": question_id, "value": value}, agent)
        return f"Recorded {question_id} = {value!r} with evidence from {log}."

    def record_obstacle(self, stage: str, summary: str, fix: str | None, resolved: bool) -> str:
        if stage not in STAGES:
            return f"Error: stage must be one of {', '.join(STAGES)}."
        if not summary or not summary.strip():
            return "Error: summary is empty."
        self.obstacles.append(
            {"stage": stage, "summary": summary.strip(), "fix": (fix or "").strip() or None, "resolved": bool(resolved)}
        )
        return "Obstacle recorded."

    def missing(self) -> list[str]:
        return [q["id"] for q in self.task.questions if q["id"] not in self.answers]

    def report(
        self,
        *,
        run_id: str,
        status: str,
        wall_seconds: float,
        tokens: int | None,
        why_missing: str,
        trace_url: str | None = None,
    ) -> dict[str, Any]:
        """The report.json payload: one answer entry per question, always."""
        answers = []
        obstacles = list(self.obstacles)
        for q in self.task.questions:
            if q["id"] in self.answers:
                answers.append(self.answers[q["id"]])
                continue
            answers.append({"question_id": q["id"], "value": None, "evidence": None, "confidence": "low"})
            obstacles.append(
                {"stage": "other", "summary": f"No answer for {q['id']}: {why_missing}", "fix": None, "resolved": False}
            )
        return {
            "contract_version": CONTRACT_VERSION,
            "task_id": self.task.task_id,
            "run_id": run_id,
            "status": status,
            "answers": answers,
            "obstacles": obstacles,
            "usage": {"wall_seconds": round(wall_seconds, 1), "tokens": tokens},
            "trace_url": trace_url,
        }
