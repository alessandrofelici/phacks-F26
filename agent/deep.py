"""The deep agent: prompt, tools, approvals, and the mapping from its stream to contract events."""

from __future__ import annotations

import base64
import difflib
import os
import sys
import time
from pathlib import Path
from typing import Any

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend
from langchain.agents.middleware import (
    AgentMiddleware,
    InterruptOnConfig,
    ModelRequest,
    ModelResponse,
    TodoListMiddleware,
    ToolCallRequest,
)
from langchain.agents.middleware.human_in_the_loop import DecisionType
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from agent.probe import describe as describe_probe
from agent.rundir import RunWriter
from agent.sandbox import SHORT_TIMEOUT_S, LoggingShellBackend
from agent.task import Findings

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
MEMORY_FILE = "/memories/fixes.md"
MEMORY_HEADER = "# Fixes that worked\n"
PROBE_MAX_S = 180  # a runtime probe never runs longer than this


def probe_cap(seconds: Any) -> int:
    """The probe's time cap in seconds, 30 to 180 (120 when not given). Shown in its approval and enforced."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            return 120
    return max(30, min(int(seconds), PROBE_MAX_S))
_SCOPER_ONLY = frozenset({"record_plan", "probe_runtime"})  # the main agent must delegate planning

SYSTEM_PROMPT = f"""You are Repro Bot. You check whether a paper's published code produces the numbers \
the task asks about. You get a private copy of the paper's repository and a list of questions. \
Each question asks for a value the code prints or writes when it runs. Get the code running, run it, \
and answer each question from what the run produced.

What matters more than finishing:
- Answers come only from output produced in this run. Never answer from the paper text, the README, \
code comments or memory. If the code can't be made to run, the honest result is "no answer" with the \
reason. A plausible number that the run didn't produce is the worst outcome.
- Don't change files that came with the repository, code or data, to make it run or to make numbers \
match. Fix the environment in new files (for example a separate requirements file) and leave the \
originals as they are. Writing inside `/repo` with the file tools asks a human for approval and shows \
them the change, so only do it when nothing else works, and record it as an obstacle either way.

Your workspace:
- Commands run in a sandbox that holds only this workspace. Nothing outside it is reachable, and \
it is thrown away after the run.
- File tools see the workspace as `/`: the repository is `/repo`, and `/paper.md` exists when the \
task comes with paper text.
- Shell commands start in that same directory, but file-tool paths are not real shell paths. In the \
shell use relative paths (`repo/run.py`, not `/repo/run.py`).
- For Python, create a virtual environment in the workspace and install into it, never into the \
system Python. The sandbox's own `python3` may be much newer than the code: match the repository's era \
(a Dockerfile, an environment file, version pins). Where available, `uv venv -p 3.10 .venv` makes any \
Python from 3.8 up and `conda create -y -p ./.py36 python=3.6` older ones; otherwise `python3 -m venv .venv`.

Running commands:
- `execute` is for setup and inspection. It stops a command after {SHORT_TIMEOUT_S} seconds. Passing \
a longer `timeout` is allowed for slow installs, and a human is asked to approve it first.
- `run_experiment` is for the command that produces the paper's results. A human is asked to approve \
it before it runs, so give an honest time estimate and say what it will do.
- `start_background_run` is for an experiment that takes more than a couple of minutes. It is \
approved the same way, returns at once, and `check_background_run` reports on it. Use the wait for \
work that doesn't depend on the result. To wait for it, call `check_background_run` with \
`wait_seconds` (up to 300) rather than running `sleep`, which needs an approval past 90 seconds.
- Every run starts with a plan. Before any experiment, hand the task to `scoper` (give it the question \
texts, the task's instructions and the time limit): it lists the steps, flags missing ones, estimates the \
runtime (timing a short probe when the code has a heavy setting) and records the plan. `run_experiment` \
and `start_background_run` refuse until a plan exists.
- The plan's path decides what happens next:
  - `full`: reproduce as usual. Start anything longer than about 5 minutes with `start_background_run`, \
so partial output stays visible and you can stop waiting in time.
  - `scaled`: the full run doesn't fit in the time left, so run the smaller version the plan lists \
(`scale_down`: fewer epochs, trees, samples or seeds), passing each change as a command-line option or a \
new config file; changing the paper's files needs an approval. Then compute the projection of the full \
run with a short script that prints the value and its interval: for precision settings the mean of 3 small \
runs with different seeds and their spread, for epochs a fit of the learning curve extrapolated to the full \
count. Record each number answer with `interval=[low, high]`, quoting that printed line. A scaled answer \
never counts as reproduced; it shows whether the paper's number is within reach.
  - `not_verifiable`: don't run the experiment. Call `record_no_answer` for each question with category \
`not_verifiable_within_budget` and the reason.
- Never pipe a run's output through `tail` or `head`: all output is saved anyway, and a run cut off at its \
limit would then show nothing.
- If an approval is rejected, don't retry the same thing. Find another way, or finish with what you have.

How to split the work (each helper starts with only the message you give it, so include the \
file paths, commands and question texts it needs):
- `scoper` first, in every run: it plans the run and records the plan. Nothing runs an experiment before it has. \
Its report already covers the repository, the missing steps and how to start the code (it may have set up the \
environment too), so build on it instead of reading everything again.
- `paper-reader` when you want a closer reading: it finds which command produces each asked value and \
what the repository needs to run. It reads and never runs anything.
- `env-builder`: it gets the environment installed and tells you how to start the code.
- `runner`: it runs the experiment through `run_experiment` and reports where the output is.
- `result-judge`: it finds each answer in the output and records it with its evidence.
Delegate setup to `env-builder` and answer extraction to `result-judge` unless the repository is a \
single short script: their long install logs and searches then stay in their own context instead of \
yours, which keeps the run fast and cheap. Reading the repository you may do yourself.

What carries over between papers:
- `/memories/fixes.md` lists fixes that worked on earlier papers; its content is included below when \
there is any. When a problem is solved in a way that would help with another repository, add one \
line: the symptom, then the fix. Keep it general (package and version, not this paper's file names).
- `/skills` holds short how-to notes for setups that come up often (old Python pins, conda, R, \
notebooks). Read the matching one before improvising.

Recording results:
- Every command's output is saved under `/logs`, one file per command, so you and the helpers can \
search it.
- When something fails, read the error, fix the cause, and call `record_obstacle` with what happened \
and what fixed it. Obstacles are part of the report, including the ones you couldn't fix.
- For each question call `record_answer` with the value and the exact line of output it came from. \
The quote is checked against the saved command output and rejected if it isn't there or doesn't show \
the value itself (rounding it is fine). Output of `echo` or `printf` doesn't count.
- When a question can't be answered, call `record_no_answer` with a category (`not_verifiable_within_budget`, \
`environment`, `not_in_output` or `other`) and the reason. Never record placeholder text such as \
"no answer" as a value.
- A question marked as read off a figure: run the code that draws it, read the image this run wrote with \
`look_at_figure` (`read_file` can't show you images), and call `record_answer` with `figure` set to that \
image and `quote` saying what was read (which panel, bar or point). An image that came with the \
repository is not accepted.
- Your first action in every run is `write_todos` with a short plan (plan the run with `scoper`, set up \
the environment, run, extract the answers). The person watching the run sees this plan, so mark each step \
done with another `write_todos` call as you finish it.

When every question has an answer or a recorded reason for not having one, reply with a two or three \
sentence summary and stop."""


def build_tools(
    backend: LoggingShellBackend, findings: Findings, agent: str = "main", vision_model: Any = None
) -> dict[str, Any]:
    """The custom tools, bound to the agent that will call them (so events name the right one).

    ``vision_model`` reads figures for ``look_at_figure``; without one that tool says it can't.
    """

    @tool
    def run_experiment(command: str, est_minutes: float, why: str) -> str:
        """Run the command that produces the paper's results. A human approves it before it runs.

        Args:
            command: The shell command, with relative paths (it starts in the workspace directory).
            est_minutes: Your honest estimate of how long it takes, in minutes.
            why: One sentence on what this run produces and which questions it answers.
        """
        allowed, why_not = findings.runs_allowed()
        if not allowed:
            return why_not
        timeout = max(120, int(est_minutes * 60 * 3))
        response = backend.execute(command, timeout=timeout)
        return response.output

    @tool
    def start_background_run(command: str, est_minutes: float, why: str) -> str:
        """Start a long experiment in the background, after human approval, and return at once.

        Use this when the run will take more than a couple of minutes, then follow it with
        `check_background_run` while doing other work.

        Args:
            command: The shell command, with relative paths (it starts in the workspace directory).
            est_minutes: Your honest estimate of how long it takes, in minutes.
            why: One sentence on what this run produces and which questions it answers.
        """
        allowed, why_not = findings.runs_allowed()
        if not allowed:
            return why_not
        run_id = backend.start_background(command, max(120, int(est_minutes * 60 * 3)))
        if not run_id:
            return "Error: the run's time limit is used up; nothing was started."
        return f"Started as {run_id}. It keeps running while you work; call check_background_run('{run_id}') to follow it."

    @tool
    def check_background_run(run_id: str, wait_seconds: int = 0) -> str:
        """Report whether a background run has finished, with the last lines of its output.

        Args:
            run_id: The id `start_background_run` returned, for example "bg1".
            wait_seconds: Wait up to this long (at most 300) for the run to finish before
                reporting. Use this instead of `sleep` commands to wait for a long run.
        """
        state = backend.check_background(run_id)
        if state is None:
            return f"Error: there is no background run '{run_id}'."
        waited_until = time.monotonic() + max(0, min(int(wait_seconds or 0), 300))
        while not state["done"] and time.monotonic() < waited_until:
            time.sleep(min(5.0, max(0.1, waited_until - time.monotonic())))
            state = backend.check_background(run_id) or state
        if not state["done"]:
            return f"Still running after {state['seconds']:.0f} s. Last lines so far:\n{state['tail'] or '<no output yet>'}"
        how = "was stopped at its time limit" if state["timed_out"] else f"finished with exit code {state['exit_code']}"
        return f"The run {how} after {state['seconds']:.0f} s. Full output saved as /{state['log']}. Last lines:\n{state['tail'] or '<no output>'}"

    @tool
    def record_answer(
        question_id: str,
        value: Any,
        quote: str,
        confidence: str,
        figure: str | None = None,
        interval: list[float] | None = None,
    ) -> str:
        """Record the answer to one question, with the evidence that proves it.

        Args:
            question_id: The question's id, for example "q1".
            value: A number for number questions, text for string questions, a list for list questions.
            quote: The exact text from this run's command output that the answer came from. It must show
                the value itself (rounding it is fine). With `figure`: what you read off the image (panel,
                bar or point, and its value).
            confidence: "high", "medium" or "low".
            figure: Only for questions read off a figure: the image this run wrote, as the file
                tools show it (for example /repo/results/fig1.png). Look at it with read_file first.
            interval: Only on a scaled plan, for a number answer: [low, high] of the projection of the full
                run, as printed (with the value) by the script that computed it.
        """
        image = _workspace_file(backend, figure) if figure else None
        return findings.record_answer(question_id, value, quote, confidence, agent, figure=image, interval=interval)

    @tool
    def record_no_answer(question_id: str, category: str, reason: str) -> str:
        """Say why a question has no answer. Use this instead of recording placeholder text as a value.

        Args:
            question_id: The question's id, for example "q1".
            category: "not_verifiable_within_budget" (the plan says the run can't fit the limits),
                "environment" (the code could not be made to run), "not_in_output" (it ran, but the output
                doesn't contain the value) or "other".
            reason: One sentence with the key error text or the projected runtime.
        """
        return findings.record_no_answer(question_id, category, reason, agent)

    @tool
    def record_plan(
        path: str,
        projected_minutes: float | None,
        steps: list[str],
        reason: str,
        missing_steps: list[str] | None = None,
        heavy_settings: list[str] | None = None,
        scale_down: list[dict[str, Any]] | None = None,
        scaled_minutes: float | None = None,
    ) -> str:
        """Record the run's plan, before any experiment: full, scaled or not verifiable within the budget.

        Args:
            path: "full" (the full run fits: at most 60% of the task's limit, leaving time for the answers), "scaled" (it doesn't, but a
                setting can shrink) or "not_verifiable" (nothing can shrink enough).
            projected_minutes: Your estimate of the FULL run's time in minutes, from a probe when the code
                has a heavy setting. May be null only for "not_verifiable".
            steps: The steps that produce the answers, in order.
            reason: Why this path, in one or two sentences, with the probe's numbers when there was one.
            missing_steps: What the instructions leave out that the code needs, each with its fix.
            heavy_settings: The settings that set the runtime, and where each is set.
            scale_down: Only for "scaled": the changes, each {"setting", "original", "scaled", "kind",
                "where"}, kind being "precision", "convergence", "data" or "hardware".
            scaled_minutes: Only for "scaled": the time all the scaled runs together will take, in minutes.
        """
        return findings.record_plan(
            path, projected_minutes, steps, reason, missing_steps, heavy_settings, scale_down, scaled_minutes, agent
        )

    @tool
    def probe_runtime(command: str, seconds: int, why: str) -> str:
        """Time the experiment: run its command for a short while, stop it, and project the full runtime.

        Progress lines in the output (epochs, steps, progress bars) give the share of the work done in
        that time. A human approves the probe first. If the command finishes inside the probe, its
        output counts as the run and can be quoted for answers.

        Args:
            command: The experiment's shell command, with relative paths (it starts in the workspace
                directory). Turn verbose progress output on if the code has an option for it.
            seconds: How long to let it run before stopping it: 30 to 180.
            why: One sentence on what it runs and which heavy setting you want to time.
        """
        cap = probe_cap(seconds)
        run_id = backend.start_background(command, cap)
        if not run_id:
            return "Error: the run's time limit is used up; nothing was started."
        state = backend.check_background(run_id)
        give_up = time.monotonic() + cap + 30
        while state is not None and not state["done"] and time.monotonic() < give_up:
            time.sleep(1.0)
            state = backend.check_background(run_id) or state
        if state is None:
            return "Error: the probe could not be followed."
        output = backend.background_output(run_id)
        finished = bool(state["done"]) and not state["timed_out"]
        if state.get("log") and not (finished and state["exit_code"] == 0):
            # A probe stopped part-way printed numbers from an unfinished run: they can't be answers.
            findings.writer.exclude_from_evidence(state["log"])
        text = describe_probe(output, float(state["seconds"]), finished, state["exit_code"])
        tail = "\n".join(output.splitlines()[-15:]) or "<no output>"
        saved = f" Full output saved as /{state['log']}." if state.get("log") else ""
        return f"{text}{saved}\nLast lines:\n{tail}"

    @tool
    def look_at_figure(path: str, question: str) -> str:
        """Look at an image this run wrote and answer a question about what it shows.

        Use it for questions read off a figure: `read_file` can't show images to you.
        Then record the answer with `record_answer(..., figure=path)`.

        Args:
            path: The image (PNG, JPG, GIF or WEBP), as the file tools show it, for example
                /repo/results/fig1.png. Convert a PDF or SVG figure to PNG first.
            question: What to read, for example "the ACC value of the GRU bar for dataset 1".
        """
        return _read_figure(vision_model, _workspace_file(backend, path), question)

    @tool
    def record_obstacle(stage: str, summary: str, fix: str | None = None, resolved: bool = False) -> str:
        """Record something that got in the way of reproducing the result.

        Args:
            stage: "read", "env", "data", "run", "extract" or "other".
            summary: What went wrong, in one sentence, with the key error text.
            fix: What you did about it, or leave empty if nothing worked.
            resolved: True when the fix worked.
        """
        return findings.record_obstacle(stage, summary, fix, resolved)

    return {
        "run_experiment": run_experiment,
        "start_background_run": start_background_run,
        "check_background_run": check_background_run,
        "record_answer": record_answer,
        "record_no_answer": record_no_answer,
        "look_at_figure": look_at_figure,
        "record_obstacle": record_obstacle,
        "record_plan": record_plan,
        "probe_runtime": probe_runtime,
    }


_IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
_FIGURE_PROMPT = """You are reading a figure that a paper's code just produced. Answer from the image only.
Give the value as precisely as the axis ticks, gridlines, labels or annotations allow, and say how you
read it (which panel, series, bar or point, and against which axis). If several readings are possible,
give the most likely one and the range. If the image doesn't show what is asked, say so.

Question: {question}"""


def _read_figure(model: Any, image: Path, question: str) -> str:
    """Ask the model about an image, sent as a user message (tool results can't carry images)."""
    if model is None or not hasattr(model, "invoke"):
        return "Error: no model that can read images is configured for this run."
    mime = _IMAGE_TYPES.get(image.suffix.lower())
    if not image.is_file():
        return "Error: there is no such image. Give its path as the file tools show it (for example /repo/results/fig1.png)."
    if mime is None:
        return f"Error: {image.name} is not a PNG, JPG, GIF or WEBP image. Convert it first (for example with matplotlib or pdftoppm)."
    data = image.read_bytes()
    if len(data) > 8_000_000:
        return f"Error: {image.name} is {len(data) // 1_000_000} MB; save a smaller PNG (lower dpi) first."
    encoded = base64.b64encode(data).decode("ascii")
    message = HumanMessage(
        content=[
            {"type": "text", "text": _FIGURE_PROMPT.format(question=question)},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
        ]
    )
    try:
        reply = model.invoke([message])
    except Exception as exc:  # noqa: BLE001 - report to the agent, which can try another way
        return f"Error: the figure could not be read ({type(exc).__name__}: {str(exc)[:300]})."
    return _text(reply.content) or "Error: the model returned no reading."


def _workspace_file(backend: LoggingShellBackend, path: str) -> Path:
    """A file-tool path (or a /work/... sandbox path) as a real path inside the workspace."""
    work = Path(backend.cwd).resolve()
    rel = path.strip()
    for prefix in ("/work/", "work/"):
        rel = rel.removeprefix(prefix)
    if rel.startswith("/results/") and not (work / rel.lstrip("/")).exists():
        rel = "repo" + rel  # Code Ocean's /results is linked to repo/results
    target = (work / rel.lstrip("/")).resolve()
    return target if target == work or work in target.parents else work / "__outside_the_workspace__"


def _needs_long_run_approval(request: ToolCallRequest) -> bool:
    """`execute` asks for approval only when the model raises the timeout past the short limit."""
    timeout = (request.tool_call.get("args") or {}).get("timeout")
    return isinstance(timeout, (int, float)) and timeout > SHORT_TIMEOUT_S


_WORKSPACE_NOTE = (
    "File tools see the workspace as `/` (the repository is `/repo`, saved command output is under `/logs`). "
    "Shell commands start in that same directory but need relative paths (`repo/run.py`, not `/repo/run.py`)."
)

SUBAGENTS: list[dict[str, Any]] = [
    {
        "name": "scoper",
        "description": (
            "Plans the run before any experiment: lists the steps that produce each answer, flags missing steps, "
            "finds the settings that set the runtime, times a short probe, and records the plan (full, scaled "
            "or not verifiable within the budget). Call it first in every run."
        ),
        "tools": ["record_plan", "probe_runtime", "record_obstacle"],
        "skills": ["/skills/"],
        "system_prompt": f"""You plan a paper's reproduction before the experiment runs, so the run fits its \
time budget and the result is honest. {_WORKSPACE_NOTE}

1. Read what you were given, the README and any reproduction notes, the Dockerfile or environment files, \
the entry-point scripts and `/paper.md` if it exists. Read `/memories/fixes.md` too: it may hold fixes and \
timings from earlier runs.
2. List the steps that produce every asked value, in order (setup, data preparation, each script).
3. Check for missing steps: anything the code needs that the instructions don't mention, such as an \
undeclared package, a data file or path that doesn't exist, a preprocessing script that must run first, or \
a hard-coded GPU (`cuda`) call. Give each a short fix.
4. Find the settings that set the runtime: epochs, iterations, number of trees, bootstrap or permutation \
counts, MCMC samples, seeds or repetitions, grid sizes, dataset size. Note where each is set.
5. Estimate the full runtime, and record the plan within about the first 8 minutes of the run.
   - No heavy setting (no training loop, no large iteration counts, a small dataset): don't probe. Record a \
"full" plan straight away with an honest estimate; the main agent sets up and runs the code.
   - A heavy setting: measure instead of guessing. Get the environment just far enough to start the code \
(short installs with `execute`), then call `probe_runtime` with the experiment's command and 60 to 180 \
seconds. It runs the command that long, stops it, and projects the total from the progress lines it \
printed. A bare progress bar or step counter gives only a lower bound (it may be one epoch of many): check \
the code for outer loops. If the code finishes inside the probe, that output already counts as the run.
   - Setup taking long: don't wait for it. Estimate from the code (time per step × number of steps), record \
the plan, and say what setup is left; you can probe and call `record_plan` again later to revise it.
6. Call `record_plan` with one path. A full run may take at most 60% of the task's time limit and must leave \
a few minutes after it for the answers; when a plan doesn't fit, `record_plan` says so with the numbers.
   - "full" when the projected runtime fits. Use it for code without a heavy setting, with an honest estimate.
   - "scaled" when it doesn't fit but a setting can shrink. List each change in `scale_down` with its kind: \
"precision" (trees, bootstrap or permutation counts, MCMC samples, repeated seeds: same expected result, more \
noise; plan 3 small runs with different seeds), "convergence" (epochs, iterations: results stay off until \
training ends, so the code must log a learning curve to extrapolate from), "data" (a subsample of rows or \
subjects), "hardware" (GPU code moved to the CPU, always together with one of the others). Shrink as little \
as possible: the smallest change whose runs fit, with margin. Never change the model, the data splits, the \
preprocessing or the metrics. Give `scaled_minutes` for all the scaled runs together.
   - "not_verifiable" when nothing can shrink enough: GPU-only code with no CPU path, data missing from the \
capsule, or a convergence setting with no learning curve to extrapolate. Give the reason.
7. Reply in a few lines: the path, the projected minutes, the steps, the missing steps with their fixes, how \
to start the code, and for a scaled plan exactly how to apply each change (a command-line option or a new \
config file; editing the paper's own files needs a human's approval).

After a probe, add one line to `/memories/fixes.md` with the timing (library, what ran, time per epoch or \
step on this sandbox), so later runs can estimate without a probe. Use `edit_file` for that: the shell \
can't see `/memories`. Record problems you hit with `record_obstacle`.""",
    },
    {
        "name": "paper-reader",
        "description": "Reads the repository and paper text to find which command produces each asked value. Runs nothing.",
        "tools": [],
        "system_prompt": f"""You read a paper's repository to work out how to produce specific values. {_WORKSPACE_NOTE}

Read the README, the entry-point scripts, the dependency files and `/paper.md` if it exists. Do not run anything.

Report, for each question you were given: the exact command that produces the value, what the output \
line or output file looks like, and anything that has to happen first (data to fetch, a config, a seed). \
Then list what the environment needs: language and version hints, dependency files, and anything in \
them that looks unlikely to install today.

If the paper states the value, you may mention it as the published claim, labelled as such. It is \
never the answer: the answer has to come from running the code.""",
    },
    {
        "name": "env-builder",
        "description": "Installs what the repository needs so its code can run, and reports how to start it.",
        "tools": ["record_obstacle"],
        "skills": ["/skills/"],
        "system_prompt": f"""You set up the environment so a paper's code can run. {_WORKSPACE_NOTE}

Before installing anything, read `/memories/fixes.md`: fixes that worked on earlier papers. If one \
matches what the dependency files show, apply it straight away without rediscovering it. After you \
fix something new that would help with another repository, add one line there (symptom, then fix).

For Python, create a virtual environment in the workspace and install into it. Match the Python version \
to the repository's era (a Dockerfile, an environment file, version pins): `uv venv -p 3.X .venv` for 3.8 \
and up, `conda create -y -p ./.pyXY python=3.X` for older ones, `python3 -m venv .venv` when neither tool \
exists. Otherwise try the documented install first. When it fails, read the error and fix the cause with the smallest \
change that works. Never edit files that came with the repository: put relaxed pins in a new \
requirements file and install from that.

`execute` stops a command after {SHORT_TIMEOUT_S} seconds; a longer `timeout` is allowed for slow \
installs and a human approves it first.

Call `record_obstacle` (stage "env" or "data") for each problem you hit, including any you could not \
fix. Finish by reporting the exact way to start the code (for example `.venv/bin/python`) and \
every change you made.""",
    },
    {
        "name": "runner",
        "description": "Runs the experiment command (after human approval) and reports where its output is.",
        "tools": ["run_experiment", "start_background_run", "check_background_run", "record_obstacle"],
        "skills": ["/skills/"],
        "system_prompt": f"""You run a paper's experiment. {_WORKSPACE_NOTE}

Use `run_experiment` for the command that produces the results. A human approves it before it runs, \
so give an honest time estimate. If the approval is rejected, do not retry: report that it was rejected.

When the run will take more than a couple of minutes, use `start_background_run` instead. It returns \
at once; follow it with `check_background_run(run_id, wait_seconds=300)`, which waits for the run to \
finish (don't use `sleep`), and report when it has finished.

If the command fails, report the error text. Don't change the paper's code to get past it; a missing \
package or path is the environment's problem, and the caller decides what to do. Record what went \
wrong with `record_obstacle` (stage "run").

Finish by reporting the exit status, roughly how long it took, and which file under `/logs` holds the output.""",
    },
    {
        "name": "result-judge",
        "description": "Finds each answer in the run's saved output and records it with the line that proves it.",
        "tools": ["record_answer", "record_no_answer", "look_at_figure", "record_obstacle"],
        "system_prompt": f"""You extract answers from the output of a paper's code. {_WORKSPACE_NOTE}

Search `/logs` (every command's output is saved there) and any files the run wrote. For each question \
call `record_answer` with the value and the exact line it came from. The quote is checked against the \
saved output and refused if it isn't there or doesn't show the value. Keep the precision the output \
shows; don't round. If you were told the run was scaled down, each number answer is a projection: \
give `interval=[low, high]` and quote the line where the projection script printed the value and its \
interval. When a question has no answer, call `record_no_answer` with the reason, never a placeholder value.

For a question read off a figure, read the image the run wrote with `look_at_figure` (`read_file` can't \
show you images) and pass it to `record_answer` as `figure`, with `quote` saying what was read (panel, \
bar or point, and its value).

If the paper text states a value, say in your report whether the output agrees with it. The recorded \
answer is always what the run printed. If the output doesn't contain an answer, say so and call \
`record_obstacle` (stage "extract"); never fill a gap from the paper.""",
    },
]


def _writes_into_repo(request: ToolCallRequest) -> bool:
    """File-tool writes under /repo need approval; new files elsewhere in the workspace don't."""
    path = str((request.tool_call.get("args") or {}).get("file_path") or "")
    return ("/" + path.lstrip("/")).startswith("/repo/")


_COMMAND_TOOLS = frozenset({"execute", "run_experiment", "start_background_run", "check_background_run"})
_STRICT_NOTE = """

In this run you don't run commands yourself: `env-builder` sets up the environment, `runner` runs the \
experiment and `result-judge` records the answers. Give each one the paths, commands and question texts \
it needs, and check what they report."""


class DelegateCommands(AgentMiddleware):
    """Hide the command tools from the main agent, so setup and runs go to subagents.

    Their install logs and long outputs then stay in the subagents' own context. Subagents are
    built with their own middleware, so their tools are untouched.
    """

    def wrap_model_call(self, request: ModelRequest, handler: Any) -> ModelResponse:
        tools = [t for t in request.tools if getattr(t, "name", None) not in _COMMAND_TOOLS]
        return handler(request.override(tools=tools))


def delegation_mode() -> str:
    """``REPRO_DELEGATION``: ``auto`` (the main agent may run commands) or ``strict``."""
    mode = (os.environ.get("REPRO_DELEGATION") or "auto").strip().lower()
    return mode if mode in ("auto", "strict") else "auto"


def build_agent(
    model: Any,
    shell: LoggingShellBackend,
    findings: Findings,
    memory_dir: Path,
    skills_dir: Path,
    subagent_model: Any = None,
) -> Any:
    """The deep agent. ``shell`` is the workspace; memory and skills are mounted next to it.

    ``subagent_model`` is an optional cheaper model for the four subagents; by default they
    use the main model.
    """
    strict = delegation_mode() == "strict"
    # Planning is opt-in in deepagents 0.7.38: without TodoListMiddleware there is no `write_todos` tool.
    middleware: list[Any] = [TodoListMiddleware()]
    if strict:
        middleware.append(DelegateCommands())
    decisions: list[DecisionType] = ["approve", "reject"]
    backend = CompositeBackend(
        default=shell,
        routes={
            "/memories/": FilesystemBackend(root_dir=memory_dir, virtual_mode=True),
            "/skills/": FilesystemBackend(root_dir=skills_dir, virtual_mode=True),
        },
    )
    subagents: list[SubAgent] = []
    for spec in SUBAGENTS:
        tools = build_tools(shell, findings, agent=spec["name"], vision_model=subagent_model or model)
        subagent = SubAgent(
            name=spec["name"],
            description=spec["description"],
            system_prompt=spec["system_prompt"],
            tools=[tools[name] for name in spec["tools"]],
        )
        if "skills" in spec:
            subagent["skills"] = spec["skills"]
        if subagent_model is not None:
            subagent["model"] = subagent_model
        subagents.append(subagent)
    # The experiment tools always pause. Without a plan the run loop (agent/runner.py) refuses
    # them at that pause without asking anyone, so a call made in the same turn as the scoper's
    # can't slip through once the plan lands. (A `when` predicate is evaluated before the turn's
    # tools run, and again on resume, so it can't express "a plan exists" safely.)
    interrupt_on: dict[str, bool | InterruptOnConfig] = {
        "run_experiment": {"allowed_decisions": decisions},
        "start_background_run": {"allowed_decisions": decisions},
        "probe_runtime": {"allowed_decisions": decisions},
        "execute": {"allowed_decisions": decisions, "when": _needs_long_run_approval},
        # Changing a file inside the paper's repository pauses for an `edit_source` approval.
        # (`permissions=` would be the deepagents way, but 0.7.38 refuses permissions on a
        # backend that can execute commands.)
        "write_file": {"allowed_decisions": decisions, "when": _writes_into_repo},
        "edit_file": {"allowed_decisions": decisions, "when": _writes_into_repo},
    }
    main_tools = [t for name, t in build_tools(shell, findings, vision_model=model).items() if name not in _SCOPER_ONLY]
    return create_deep_agent(
        model=model,
        tools=main_tools,
        system_prompt=SYSTEM_PROMPT + (_STRICT_NOTE if strict else ""),
        middleware=middleware,
        subagents=subagents,
        skills=["/skills/"],
        memory=[MEMORY_FILE],
        backend=backend,
        # Subagents inherit these, so an approval inside `runner` pauses the whole run.
        interrupt_on=interrupt_on,
        checkpointer=InMemorySaver(),  # interrupts need one; state lives only for this process
        name="repro-bot",
    )


def approval_request(action: dict[str, Any], work: Path, findings: Findings | None = None) -> dict[str, Any]:
    """Turn a paused tool call into the fields of a contract approval request.

    On a scaled plan, the experiment's request also lists the scale-down, so approving the run
    is approving the smaller settings (``extra`` holds optional fields for the request file).
    """
    name = action.get("name")
    args = action.get("args") or {}
    if name in ("write_file", "edit_file"):
        path = str(args.get("file_path") or "")
        summary = f"Change {path} (a file inside the paper's repository)"
        return {"kind": "edit_source", "summary": summary, "command": None, "diff": _diff(name, args, work)}
    command = str(args.get("command") or "")
    extra: dict[str, Any] = {}
    if name == "probe_runtime":
        cap = probe_cap(args.get("seconds"))
        why = f": {args['why']}" if args.get("why") else ""
        summary = f"Time a probe: run {command} for at most {cap} s, then stop it, to measure its speed{why}"
    elif name in ("run_experiment", "start_background_run"):
        minutes = args.get("est_minutes")
        estimate = f" (est. {minutes:g} min)" if isinstance(minutes, (int, float)) else ""
        why = f": {args['why']}" if args.get("why") else ""
        where = " in the background" if name == "start_background_run" else ""
        summary = f"Run {command}{where}{estimate}{why}"
        plan = findings.plan if findings is not None else None
        if plan and plan.get("path") == "scaled":
            summary += f" · scaled down per the plan: {findings.scale_note()}"
            extra["scale_down"] = plan.get("scale_down")
    else:
        summary = f"Run {command} (allowed up to {args.get('timeout')} s)"
    return {"kind": "long_run", "summary": summary, "command": command or None, "diff": None, "extra": extra or None}


def _diff(name: str, args: dict[str, Any], work: Path) -> str:
    """A unified diff of what the file tool would change, for the human who approves it."""
    path = str(args.get("file_path") or "")
    target = work / path.lstrip("/")
    try:
        before = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        before = ""
    if name == "write_file":
        after = str(args.get("content") or "")
    else:
        old, new = str(args.get("old_string") or ""), str(args.get("new_string") or "")
        after = before.replace(old, new) if args.get("replace_all") else before.replace(old, new, 1)
    lines = difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a{path}", tofile=f"b{path}"
    )
    return "".join(lines)[:20000] or "(no textual change)"


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def _one_line(text: str, limit: int = 140) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1] + "…"


# Shown through other events (answer_found, no_answer, plan_recorded, todo_updated, the report).
_QUIET_TOOLS = {"write_todos", "record_answer", "record_obstacle", "record_plan", "record_no_answer"}


class EventMapper:
    """Reads the agent's update stream and appends the matching contract events."""

    def __init__(self, writer: RunWriter, backend: LoggingShellBackend) -> None:
        self.writer = writer
        self.backend = backend
        self.tokens = 0
        self._calls: dict[str, dict[str, Any]] = {}  # tool_call_id -> {name, args, agent}
        self._subagents: list[str] = []  # names of running subagents, newest last
        self._seen_ai: set[str] = set()  # ids of AIMessages already handled

    def current_agent(self) -> str:
        """Who is acting right now: the newest running subagent, else main."""
        return self._subagents[-1] if self._subagents else "main"

    def _agent(self, namespace: tuple[str, ...]) -> str:
        # Updates from inside a subagent arrive under a non-empty namespace.
        return self._subagents[-1] if namespace and self._subagents else "main"

    def handle(self, namespace: tuple[str, ...], chunk: dict[str, Any]) -> None:
        agent = self._agent(namespace)
        if os.environ.get("REPRO_DEBUG"):
            shapes = {node: (sorted(update) if isinstance(update, dict) else type(update).__name__) for node, update in chunk.items()}
            print(f"[stream] ns={namespace} {shapes}", file=sys.stderr)
        for node, update in chunk.items():
            if node == "__interrupt__" or not isinstance(update, dict):
                continue
            messages = update.get("messages")
            messages = getattr(messages, "value", messages)  # unwrap an Overwrite
            if not isinstance(messages, list):
                continue
            for message in messages:
                if isinstance(message, AIMessage):
                    self._on_ai(message, agent)
                elif isinstance(message, ToolMessage):
                    self._on_tool(message, agent)

    def _on_ai(self, message: AIMessage, agent: str) -> None:
        # After an approval, HumanInTheLoopMiddleware.after_model sends the same AIMessage again
        # (with the reviewed tool calls); count its tokens and start its subagents only once.
        if message.id is not None:
            if message.id in self._seen_ai:
                return
            self._seen_ai.add(message.id)
        usage = getattr(message, "usage_metadata", None) or {}
        self.tokens += int(usage.get("total_tokens") or 0)
        for call in message.tool_calls:
            args = call.get("args") or {}
            if call["id"] is not None:  # a ToolMessage is matched to its call by this id
                self._calls[call["id"]] = {"name": call["name"], "args": args, "agent": agent}
            if call["name"] == "task":
                name = str(args.get("subagent_type") or "subagent")
                self._subagents.append(name)
                self.writer.event("subagent_started", {"name": name, "task": _one_line(str(args.get("description", "")), 300)}, agent)

    def _on_tool(self, message: ToolMessage, agent: str) -> None:
        call = self._calls.pop(message.tool_call_id, None) or {"name": message.name or "tool", "args": {}, "agent": agent}
        name, args = call["name"], call["args"]
        text = _text(message.content)
        if name == "write_todos":
            # The plan is taken from the tool call's arguments: the "updates" stream of
            # deepagents 0.7.38 does not carry the `todos` state key.
            todos = args.get("todos")
            if message.status != "error" and isinstance(todos, list):
                clean = [
                    {"content": str(t.get("content", "")), "status": t.get("status", "pending")}
                    for t in todos
                    if isinstance(t, dict)
                ]
                self.writer.event("todo_updated", {"todos": clean}, call["agent"])
                return
        if name in _QUIET_TOOLS and message.status != "error":
            return  # shown through answer_found, todo_updated and the report instead
        if name == "task":
            sub = str(args.get("subagent_type") or "subagent")
            if sub in self._subagents:
                self._subagents.remove(sub)
            self.writer.event("subagent_finished", {"name": sub, "summary": _one_line(text, 400)}, call["agent"])
            return
        ok = message.status != "error" and not text.lstrip().startswith("Error")
        path = str(args.get("file_path") or "")
        if ok and path.startswith("/memories/") and name in ("read_file", "write_file", "edit_file"):
            if name == "read_file":
                count = sum(1 for line in text.splitlines() if "- `" in line[:16] or line.lstrip().startswith("- "))
                note = f"{count} remembered fix{'es' if count != 1 else ''} on file" if count else "Nothing remembered yet"
                self.writer.event("memory_read", {"path": path, "note": note}, call["agent"])
            else:
                added = str(args.get("content") or args.get("new_string") or "")
                lines = [ln.strip().lstrip("-# ").strip() for ln in added.splitlines()]
                lines = [ln for ln in lines if ln and ln != MEMORY_HEADER.strip("# \n")]
                note = _one_line(lines[-1] if lines else "updated", 300)
                self.writer.event("memory_written", {"path": path, "note": note}, call["agent"])
            return
        data: dict[str, Any] = {"tool": name}
        if name == "probe_runtime":
            data["summary"] = _one_line(f"time a probe: {args.get('command', '')}")
            data["detail"] = text[:1800]
        elif name in ("start_background_run", "check_background_run"):
            if name == "start_background_run":
                data["summary"] = _one_line(f"start in the background: {args.get('command', '')}")
            else:
                state = "still running" if text.startswith("Still running") else _one_line(text.split(". ", 1)[0].lower(), 80)
                data["summary"] = f"check {args.get('run_id', '')}: {state}"
                ok = ok and ("exit code" not in state or "exit code 0" in state) and "time limit" not in state
            data["detail"] = text[-1800:]
        elif name in ("execute", "run_experiment"):
            command = str(args.get("command", ""))
            record = self.backend.take_record(command)
            data["summary"] = _one_line(command)
            if record is not None:
                ok = record.exit_code == 0
                tail = record.output[-1800:]
                data["detail"] = f"{tail}\n(full output: {record.log})"
            else:
                ok = False  # the command never ran (rejected, or refused before running)
                data["detail"] = text[:1800]
        else:
            target = args.get("file_path") or args.get("path") or args.get("pattern") or ""
            if name == "grep" and args.get("pattern"):
                target = f"'{args['pattern']}' in {args.get('path') or '/'}"
            data["summary"] = _one_line(str(target) or name)
            if not ok:
                data["detail"] = text[:1800]
        data["ok"] = ok
        self.writer.event("tool_call", data, call["agent"])
