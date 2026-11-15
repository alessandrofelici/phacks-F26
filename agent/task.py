"""Reads a task directory (CONTRACT.md section 1) and collects what the run found.

Standard library only.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from agent.rundir import RunWriter

CONTRACT_VERSION = 1
FIGURE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf")
STAGES = ("read", "env", "data", "run", "extract", "other")
CONFIDENCES = ("high", "medium", "low")

# Plan-first runs (research proposal "Plan-First Runs and Budget-Scaled Verification").
PLAN_PATHS = ("full", "scaled", "not_verifiable")
SCALE_KINDS = ("precision", "convergence", "data", "hardware")
NO_ANSWER_CATEGORIES = ("not_verifiable_within_budget", "environment", "not_in_output", "other")
FULL_RUN_SHARE = 0.6  # a full run may take at most this share of the task's time limit ...
RESERVE_SHARE = 0.15  # ... and must leave this share of it (at least 3 minutes) for reading the output
PLAN_NUDGE_MINUTES = 6  # with no plan by then, command output reminds the scoper to record one
# A projection's half-width, as a share of its value, beyond which harness/score.py calls it too vague.
INTERVAL_CAP = 0.10
# Text that means "I have no answer" and must never be recorded as a value.
PLACEHOLDERS = frozenset(
    {"no answer", "noanswer", "n/a", "na", "none", "null", "nan", "unknown", "not found", "not available",
     "error", "failed", "-", "--", "?", "tbd", "could not reproduce", "not reproduced"}
)
# A number not glued to a word or another number ("r2", the second half of "0.44-0.46"): a sign counts
# only after a space or punctuation, so a range's dash isn't read as a minus.
_NUMBER = re.compile(r"(?<![\w.])(?:[-+](?=\.?\d))?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?(%?)")
_THOUSANDS = re.compile(r"(?<![\w.,])(?:[-+](?=\d))?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])")
NO_PLAN_MESSAGE = (
    "Error: there is no plan for this run yet, so nothing was run. Hand the task to the `scoper` helper first "
    "(task tool, subagent_type 'scoper'; give it the question texts, the task's instructions and the time "
    "limit). It records a plan with the projected runtime; experiments are allowed once it has."
)


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
            number = value
        elif isinstance(value, str):
            text = value.strip().rstrip("%").replace(",", "")
            try:
                number = int(text)
            except ValueError:
                number = float(text)  # raises ValueError when it isn't a number
        else:
            raise ValueError("a number is needed")
        if not math.isfinite(number):
            raise ValueError("a finite number is needed (inf and nan can't be checked or stored as JSON)")
        return number
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


def _tokens(text: str) -> list[tuple[float, bool]]:
    """Every number written in ``text``, with whether it may be a percentage of a fraction or the reverse.

    A number counts as such when it is written with a decimal point or followed by ``%``: 81.2 and
    0.812 are the same accuracy, but "seed 3" is not 0.03. A comma group such as 1,234 is read both as
    one number and as a list (1 and 234), since outputs use commas for both.
    """
    text = (text or "").replace("\u2212", "-")  # a typographic minus counts as one
    found: list[tuple[float, bool]] = []
    for match in _NUMBER.finditer(text):
        raw = match.group(0).rstrip("%")
        try:
            number = float(raw)
        except ValueError:
            continue
        if math.isfinite(number):
            found.append((number, "." in raw or bool(match.group(1))))
    for match in _THOUSANDS.finditer(text):
        try:
            found.append((float(match.group(0).replace(",", "")), "." in match.group(0)))
        except ValueError:
            continue
    return found


def numbers_in(text: str) -> list[float]:
    """Every number written in ``text``."""
    return [number for number, _ in _tokens(text)]


def _half_unit(value: float) -> float:
    """Half of the last written digit of ``value``: how far a correctly rounded number can be off.

    The value is taken as written: 1 allows 0.5, but 1.0 allows only 0.05.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return 0.5
    try:
        exponent = Decimal(repr(float(value))).as_tuple().exponent
    except (InvalidOperation, ValueError):
        return 1e-9
    if not isinstance(exponent, int):
        return 1e-9
    return 0.5 * 10.0 ** min(0, exponent)


def number_in_quote(value: float, quote: str, precision_of: float | None = None) -> bool:
    """True when the quote shows ``value``, possibly with more digits, or as a fraction of a percentage.

    ``precision_of``: also require at least the precision of this number (an interval's bounds
    must be written as precisely as its value, so they can't be loosened by rounding).
    """
    unit = _half_unit(value) if precision_of is None else min(_half_unit(value), _half_unit(precision_of))
    tolerance = unit + 1e-9 * abs(value)
    for seen, scalable in _tokens(quote):
        # Zero is zero as a fraction or a percentage, so it never needs (or allows) a conversion.
        candidates = (seen, seen * 100.0, seen / 100.0) if scalable and value != 0 else (seen,)
        if any(abs(candidate - value) <= tolerance for candidate in candidates):
            return True
    return False


def quote_shows(value: Any, quote: str, qtype: str) -> bool:
    """Does the evidence quote contain the answer? Numbers may be rounded; text must appear as written."""
    if qtype == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and number_in_quote(value, quote)
    if qtype == "list":
        return bool(value) and all(
            quote_shows(item, quote, "number" if isinstance(item, (int, float)) and not isinstance(item, bool) else "string")
            for item in value
        )
    wanted, seen = (" ".join(str(s).casefold().split()) for s in (value, quote))
    return bool(wanted) and wanted in seen


@dataclass
class Findings:
    """Answers and obstacles recorded during a run, and the report built from them."""

    task: Task
    writer: RunWriter
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    obstacles: list[dict[str, Any]] = field(default_factory=list)
    # The workspace is copied with the capsule's own timestamps, so a file modified after
    # this moment was written by the run.
    started: float = field(default_factory=time.time)
    deadline: float | None = None  # time.monotonic() value when the run's limit is reached
    plan: dict[str, Any] | None = None  # recorded by the scoper before any experiment
    no_answers: dict[str, dict[str, str]] = field(default_factory=dict)  # question id -> category and reason

    # -- the plan ---------------------------------------------------------------

    def minutes_left(self) -> float:
        if self.deadline is not None:
            return max(0.0, (self.deadline - time.monotonic()) / 60)
        return max(0.0, self.task.max_minutes - (time.time() - self.started) / 60)

    def reserve_minutes(self) -> float:
        """Time kept after the experiment for reading its output and recording the answers."""
        return max(3.0, RESERVE_SHARE * self.task.max_minutes)

    def full_run_allowance(self) -> float:
        """The longest run a plan may choose now.

        At most 60% of the task's whole limit, and never more than what is left minus the reserve.
        Measured against the whole limit rather than the minutes left, so a plan recorded late
        (after a slow setup) doesn't scale a paper whose full run still fits.
        """
        return max(0.0, min(FULL_RUN_SHARE * self.task.max_minutes, self.minutes_left() - self.reserve_minutes()))

    def plan_reminder(self) -> str | None:
        """A note for command output when a run is past the point where it should have a plan."""
        if self.plan is not None:
            return None
        spent = self.task.max_minutes - self.minutes_left()
        if spent < min(PLAN_NUDGE_MINUTES, 0.25 * self.task.max_minutes):
            return None
        return (
            f"Note from the run: minute {spent:.0f} of {self.task.max_minutes:g} and still no plan. The scoper should "
            "record it now with record_plan, estimating the runtime from the code if setup isn't finished; setup "
            "can continue after the plan."
        )

    def record_plan(
        self,
        path: str,
        projected_minutes: float | None,
        steps: list[str],
        reason: str,
        missing_steps: list[str] | None = None,
        heavy_settings: list[str] | None = None,
        scale_down: list[dict[str, Any]] | None = None,
        scaled_minutes: float | None = None,
        agent: str = "scoper",
    ) -> str:
        """Store the run's plan if it is consistent with the time left. Returns a message for the model."""
        if path not in PLAN_PATHS:
            return f"Error: path must be one of {', '.join(PLAN_PATHS)}."
        steps = [str(s).strip() for s in (steps or []) if str(s).strip()]
        if not steps:
            return "Error: list the steps that produce the answers (at least one)."
        reason = (reason or "").strip()
        if not reason:
            return "Error: give the reason for this path in one or two sentences."
        projected = _minutes(projected_minutes)
        left = self.minutes_left()
        allowed = self.full_run_allowance()
        if path in ("full", "scaled") and projected is None:
            return "Error: give projected_minutes, your estimate of the full run's time in minutes (from a probe when the code has a heavy setting)."
        plan: dict[str, Any] = {"path": path, "projected_minutes": None if projected is None else round(projected, 1),
                                "minutes_left": round(left, 1), "steps": steps,
                                "missing_steps": [str(s).strip() for s in (missing_steps or []) if str(s).strip()],
                                "heavy_settings": [str(s).strip() for s in (heavy_settings or []) if str(s).strip()],
                                "reason": reason}
        if path == "full" and projected is not None and projected > allowed:
            return (
                f"Error: a full run needs about {projected:g} min, but {left:.0f} min are left and a run may take at "
                f"most {allowed:.0f} min now (60% of the task's {self.task.max_minutes:g} minutes, leaving "
                f"{self.reserve_minutes():.0f} min after it for the answers). Choose 'scaled' with a scale_down, or "
                "'not_verifiable' with the reason."
            )
        if path == "scaled":
            if projected is not None and projected <= allowed:
                return f"Error: the full run (about {projected:g} min) fits in the {allowed:.0f} min allowed, so don't scale it: choose 'full'."
            changes, problem = _clean_scale_down(scale_down)
            if problem:
                return problem
            scaled = _minutes(scaled_minutes)
            if scaled is None:
                return "Error: give scaled_minutes, the time all the scaled runs together will take."
            if scaled > allowed:
                return f"Error: the scaled runs (about {scaled:g} min) still don't fit in the {allowed:.0f} min allowed. Shrink further, or choose 'not_verifiable'."
            plan["scale_down"] = changes
            plan["scaled_minutes"] = round(scaled, 1)
        plan["revision"] = (self.plan or {}).get("revision", 0) + 1
        self.plan = plan
        self.writer.event("plan_recorded", {"path": path, "projected_minutes": plan["projected_minutes"],
                                            "minutes_left": plan["minutes_left"], "summary": self.plan_summary()}, agent)
        if path == "full":
            return f"Plan recorded: {self.plan_summary()}. Experiments may run now."
        if path == "scaled":
            return (
                f"Plan recorded: {self.plan_summary()}. The experiment's approval request will show these changes. "
                "After the scaled runs, compute each projected value and its interval with a short script that "
                "prints them, and record each number answer with interval=[low, high] quoting that line."
            )
        return (
            f"Plan recorded: {self.plan_summary()}. Experiments are now refused. Record each question with "
            "record_no_answer(category='not_verifiable_within_budget', reason=...)."
        )

    def plan_summary(self) -> str:
        plan = self.plan or {}
        path = plan.get("path")
        if path == "full":
            return f"full run, about {plan['projected_minutes']:g} min of {plan['minutes_left']:.0f} left"
        if path == "scaled":
            return (
                f"scaled run: the full run needs about {plan['projected_minutes']:g} min of {plan['minutes_left']:.0f} "
                f"left, the scaled runs about {plan['scaled_minutes']:g} min; {self.scale_note()}"
            )
        if path == "not_verifiable":
            return f"not verifiable within budget: {plan.get('reason', '')}"
        return "no plan"

    def scale_note(self) -> str:
        """The plan's scale-down in one line, for approval requests."""
        changes = (self.plan or {}).get("scale_down") or []
        return "; ".join(f"{c['setting']} {c['original']} → {c['scaled']} ({c['kind']})" for c in changes)

    def runs_allowed(self) -> tuple[bool, str]:
        """May an experiment run now? (False, the reason for the model) when it may not."""
        if self.plan is None:
            return False, NO_PLAN_MESSAGE
        if self.plan["path"] == "not_verifiable":
            return False, (
                "Error: the plan says this paper can't be verified within the budget "
                f"({self.plan.get('reason', '')}), so nothing was run. Call record_no_answer for each question "
                "with category 'not_verifiable_within_budget'. If something new shows it fits after all, ask "
                "`scoper` to revise the plan."
            )
        return True, ""

    # -- answers ----------------------------------------------------------------

    def record_answer(
        self,
        question_id: str,
        value: Any,
        quote: str,
        confidence: str,
        agent: str = "main",
        figure: Path | None = None,
        interval: Any = None,
    ) -> str:
        """Store an answer if its evidence holds up. Returns a message for the model.

        The evidence is a quote found in a saved command output or, for a question that
        needs a figure, an image this run wrote (copied into the run directory) with the
        quote saying what was read off it. A quote from command output must contain the
        value. On a scaled plan a number answer is a projection with its interval.
        """
        question = self.task.question(question_id)
        if question is None:
            known = ", ".join(q["id"] for q in self.task.questions)
            return f"Error: there is no question '{question_id}'. The questions are: {known}."
        try:
            value = _coerce(value, question["type"])
        except ValueError as exc:
            return f"Error: {question_id} is a {question['type']} question; {exc}."
        placeholder = question["type"] == "string" and " ".join(str(value).casefold().split()) in PLACEHOLDERS
        if placeholder and figure is not None:
            return (
                f"Error: {value!r} is not an answer. When a question can't be answered, call record_no_answer "
                "with the reason instead."
            )
        if confidence not in CONFIDENCES:
            return f"Error: confidence must be one of {', '.join(CONFIDENCES)}."
        scaled = bool(self.plan and self.plan.get("path") == "scaled")
        bounds: list[float] | None = None
        if interval not in (None, "", []):
            if not scaled:
                return "Error: an interval is only for a scaled run's projection, and this run's plan is not scaled. Leave it out."
            try:
                bounds = [float(b) for b in (json.loads(interval) if isinstance(interval, str) else interval)]
            except (TypeError, ValueError):
                bounds = None
            if bounds is None or len(bounds) != 2 or not all(math.isfinite(b) for b in bounds):
                return "Error: interval must be two numbers, [low, high]."
            if question["type"] != "number":
                return "Error: an interval only goes with a number question."
            if not bounds[0] <= value <= bounds[1]:
                return f"Error: the projected value {value:g} must lie inside its interval [{bounds[0]:g}, {bounds[1]:g}]."
        elif scaled and question["type"] == "number" and figure is None:
            return (
                "Error: this is a scaled run, so a number answer is a projection of the full run: give "
                "interval=[low, high] too, both printed by the script that computed the projection."
            )
        quote = (quote or "").strip()
        if figure is not None:
            if not question.get("needs_figure"):
                return f"Error: {question_id} is not read off a figure. Quote the line of command output instead."
            if not quote:
                return "Error: quote is empty. Say what you read off the figure (which panel, bar or point, and its value)."
            log = self._keep_figure(question_id, figure)
            if log.startswith("Error"):
                return log
        else:
            if not quote:
                return "Error: quote is empty. Give the exact line of command output the answer came from."
            found = self.writer.find_quote(quote)
            if found is None:
                hint = " For this question you may instead pass the image as `figure`." if question.get("needs_figure") else ""
                return (
                    "Error: that quote is not in the output of any command run so far. "
                    "Answers must come from output produced in this run: copy the line exactly, "
                    f"or run the command that prints it.{hint}"
                )
            log = found
            if not quote_shows(value, quote, question["type"]):
                if placeholder:
                    return (
                        f"Error: {value!r} is not an answer. When a question can't be answered, call "
                        "record_no_answer with the reason instead."
                    )
                seen = ", ".join(f"{n:g}" for n in numbers_in(quote)[:8]) or "none"
                return (
                    f"Error: the quote doesn't show the answer {value!r}. Quote the output line that contains the "
                    f"value itself (rounding it is fine). Numbers in your quote: {seen}."
                )
            if bounds is not None and not all(number_in_quote(b, quote, precision_of=value) for b in bounds):
                return (
                    "Error: the quote must show the interval's bounds too: quote the line where your projection "
                    "script printed the value and its interval."
                )
        entry: dict[str, Any] = {
            "question_id": question_id,
            "value": value,
            "evidence": {"file": log, "quote": quote},
            "confidence": confidence,
        }
        note = ""
        if scaled:
            entry["scaled"] = True  # optional fields beyond contract v1
            if bounds is not None:
                entry["interval"] = bounds
                half = (bounds[1] - bounds[0]) / 2
                if half > INTERVAL_CAP * abs(value):
                    note = (
                        " Note: this interval is wider than ±10% of the value, so the harness will count it as not "
                        "verifiable within budget. That is an honest result; don't narrow it by hand."
                    )
        self.answers[question_id] = entry
        self.no_answers.pop(question_id, None)
        self.writer.event("answer_found", {"question_id": question_id, "value": value}, agent)
        kind = "projection" if bounds is not None else "answer"
        return f"Recorded {question_id} = {value!r} ({kind}) with evidence from {log}.{note}"

    def record_no_answer(self, question_id: str, category: str, reason: str, agent: str = "main") -> str:
        """Say why a question has no answer, instead of recording a placeholder value."""
        if self.task.question(question_id) is None:
            known = ", ".join(q["id"] for q in self.task.questions)
            return f"Error: there is no question '{question_id}'. The questions are: {known}."
        if category not in NO_ANSWER_CATEGORIES:
            return f"Error: category must be one of {', '.join(NO_ANSWER_CATEGORIES)}."
        reason = (reason or "").strip()
        if not reason:
            return "Error: give the reason in one sentence, with the key error text or the projected runtime."
        if question_id in self.answers:
            return f"Error: {question_id} already has an answer with evidence; it stays."
        self.no_answers[question_id] = {"category": category, "reason": reason}
        self.writer.event("no_answer", {"question_id": question_id, "category": category, "reason": reason}, agent)
        return f"Recorded: no answer for {question_id} ({category.replace('_', ' ')}). The report says why."

    def _keep_figure(self, question_id: str, figure: Path) -> str:
        """Copy an image this run wrote into the run directory; its relative path, or an error."""
        if not figure.is_file():
            return "Error: there is no such image. Give its path as the file tools show it (for example /repo/results/fig1.png)."
        if figure.suffix.lower() not in FIGURE_SUFFIXES:
            return f"Error: {figure.name} is not an image ({', '.join(FIGURE_SUFFIXES)})."
        if figure.stat().st_mtime < self.started - 2:
            return (
                f"Error: {figure.name} came with the repository; this run didn't write it. "
                "Run the code that draws the figure and read the new image."
            )
        rel = f"figures/{question_id}-{figure.name}"
        dest = self.writer.run_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(figure, dest)
        return rel

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

    def missing_questions(self) -> list[dict[str, Any]]:
        return [q for q in self.task.questions if q["id"] not in self.answers]

    def finished_within_budget(self) -> bool:
        """A planned run that says, for every unanswered question, that it can't be shown within the budget.

        That is an honest finish (status ``completed``), whether the plan said so from the start or a
        scaled run found out on the way. A no-answer for any other reason is still a give-up.
        """
        return self.plan is not None and all(
            (self.no_answers.get(q["id"]) or {}).get("category") == "not_verifiable_within_budget"
            for q in self.missing_questions()
        )

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
            entry: dict[str, Any] = {"question_id": q["id"], "value": None, "evidence": None, "confidence": "low"}
            given = self.no_answers.get(q["id"])
            if given:
                entry["no_answer"] = dict(given)  # optional field beyond contract v1
                why = f"({given['category'].replace('_', ' ')}) {given['reason']}"
            else:
                why = why_missing
            answers.append(entry)
            obstacles.append({"stage": "other", "summary": f"No answer for {q['id']}: {why}", "fix": None, "resolved": False})
        report: dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "task_id": self.task.task_id,
            "run_id": run_id,
            "status": status,
            "answers": answers,
            "obstacles": obstacles,
            "usage": {"wall_seconds": round(wall_seconds, 1), "tokens": tokens},
            "trace_url": trace_url,
        }
        if self.plan is not None:
            report["plan"] = self.plan  # optional field beyond contract v1
        return report


def _minutes(value: Any) -> float | None:
    """A non-negative number of minutes, or None."""
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        return None
    return minutes if math.isfinite(minutes) and minutes >= 0 else None


def _clean_scale_down(scale_down: Any) -> tuple[list[dict[str, Any]], str]:
    """Validate the scale-down list; returns (changes, "") or ([], an error for the model)."""
    if isinstance(scale_down, str):
        try:
            scale_down = json.loads(scale_down)
        except json.JSONDecodeError:
            scale_down = None
    if not isinstance(scale_down, list) or not scale_down:
        return [], (
            "Error: a scaled plan needs scale_down: a list of changes, each "
            '{"setting": "epochs", "original": 150, "scaled": 30, "kind": "convergence", "where": "train.py line 12"}.'
        )
    changes = []
    for i, change in enumerate(scale_down):
        if not isinstance(change, dict):
            return [], f"Error: scale_down[{i}] must be an object with setting, original, scaled and kind."
        setting = str(change.get("setting") or "").strip()
        kind = str(change.get("kind") or "").strip().lower()
        if not setting or change.get("original") in (None, "") or change.get("scaled") in (None, ""):
            return [], f"Error: scale_down[{i}] needs setting, original and scaled."
        if kind not in SCALE_KINDS:
            return [], f"Error: scale_down[{i}].kind must be one of {', '.join(SCALE_KINDS)}."
        changes.append({"setting": setting, "original": change["original"], "scaled": change["scaled"], "kind": kind,
                        "where": str(change.get("where") or "").strip() or None})
    if not any(c["kind"] != "hardware" for c in changes):
        return [], "Error: moving GPU code to the CPU is not a scale-down by itself; add the setting that shrinks (epochs, trees, samples)."
    return changes, ""
