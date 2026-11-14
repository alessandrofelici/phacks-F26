"""An offline stand-in for the LLM, for the toy task only (``REPRO_MODEL=scripted``).

It plays the main agent and its four subagents through the real deep agent graph, so the
sandbox, subagents, approvals, memory, events and report can be checked without an API key.
The commands really run, and the answers are parsed from their output, never written into
the script. It can't solve anything except ``toy-linreg`` and proves nothing about how a
real model behaves.

The script is a generator: each ``yield`` is one model turn, and the value sent back in is
the conversation of whichever agent is being asked (main or a subagent). Turns happen in
one fixed order, so one generator can speak for all of them.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from collections.abc import Generator, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agent.task import Task

Flow = Generator[AIMessage, list[BaseMessage], None]

FIXES = "/memories/fixes.md"
HEADER = "# Fixes that worked\n"
NUMPY_FIX = (
    "- `numpy==1.19.5` (and other numpy 1.x pins from before 2021) can't be installed on Python 3.10+. "
    "Fix: write a separate requirements file with `numpy>=1.26` and install from that; leave the original untouched.\n"
)


def call(name: str, **args: Any) -> AIMessage:
    """An assistant turn that calls one tool."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:12]}", "type": "tool_call"}],
    )


def say(text: str) -> AIMessage:
    """An assistant turn with plain text, which ends that agent's loop."""
    return AIMessage(content=text)


def last_result(messages: Sequence[BaseMessage], name: str) -> str:
    """Text of the most recent result of tool ``name`` in this agent's conversation."""
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name == name:
            return message.content if isinstance(message.content, str) else str(message.content)
    return ""


class ScriptedChatModel(BaseChatModel):
    """Asks the flow generator for the next assistant turn."""

    flow: Any  # a primed Flow generator

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedChatModel:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            message = self.flow.send(messages)
        except StopIteration:
            message = say("The script has no more steps.")
        return ChatResult(generations=[ChatGeneration(message=message)])


_PLAN = ["Read the task and the repo", "Set up the environment", "Run the experiment", "Extract and check the answers"]


def _todos(done: int) -> AIMessage:
    todos = []
    for i, content in enumerate(_PLAN):
        status = "completed" if i < done else ("in_progress" if i == done else "pending")
        todos.append({"content": content, "status": status})
    return call("write_todos", todos=todos)


def _toy_flow() -> Flow:
    yield  # primed by scripted_model_for; the first send() delivers the first conversation

    # --- main: plan, then hand the reading to paper-reader
    yield _todos(0)
    yield call(
        "task",
        subagent_type="paper-reader",
        description="Find which command and output line answer: q1 'Report the test R^2 printed by run.py.' "
        "and q2 'Report the name of the selected model.' The task says: run run.py with seed 0. "
        "Also report what the environment needs.",
    )
    yield call("read_file", file_path="/repo/README.md")
    yield call("read_file", file_path="/repo/requirements.txt")
    yield call("read_file", file_path="/repo/run.py")
    yield say(
        "Both answers are printed by `python run.py --seed 0` run inside repo/: the line starting 'test r2:' "
        "answers q1 and the line starting 'best model:' answers q2. The only dependency is numpy, pinned to "
        "1.19.5 in repo/requirements.txt, which is too old for a current Python."
    )

    # --- main: environment
    yield _todos(1)
    yield call(
        "task",
        subagent_type="env-builder",
        description="Create .venv in the workspace and install repo/requirements.txt (numpy==1.19.5, likely too old). "
        "Report how to start Python.",
    )
    if os.environ.get("REPRO_SCRIPT_PROBE"):
        # Test switch: try to read a file outside the workspace. A real sandbox makes this fail.
        yield call("execute", command=f"cat {os.environ['REPRO_SCRIPT_PROBE']}")
    if os.environ.get("REPRO_SCRIPT_BIG_OUTPUT"):
        # Probe: a command with a very large output, to see what the model is handed back.
        messages = yield call("execute", command="python3 -c \"print('a line of build log output\\n' * 60000)\"")
        text = last_result(messages, "execute")
        print(f"[scripted] big output: model received {len(text)} characters; start: {text[:300]!r}", file=sys.stderr)
    if os.environ.get("REPRO_SCRIPT_TAMPER"):
        # Test switch: change one of the paper's files with a shell command, behind the file tools' back.
        yield call("execute", command="echo '# touched' >> repo/run.py")
    messages = yield call("read_file", file_path=FIXES)
    remembered = "numpy==1.19.5" in last_result(messages, "read_file")
    if remembered:
        # A fix from an earlier run applies: skip the install that is known to fail.
        yield call("write_file", file_path="/requirements.repro.txt", content="numpy>=1.26\n")
        yield call("execute", command="python3 -m venv .venv && .venv/bin/pip install -r requirements.repro.txt")
        yield say(
            "Environment ready: start the code with .venv/bin/python. I used the remembered fix for the numpy "
            "pin (installed numpy>=1.26 from requirements.repro.txt) without trying the original pin first."
        )
    else:
        messages = yield call("execute", command="python3 -m venv .venv && .venv/bin/pip install -r repo/requirements.txt")
        code = re.search(r"Exit code: (\d+)", last_result(messages, "execute"))
        if os.environ.get("REPRO_SCRIPT_EDIT_SOURCE"):
            # Test switch: first try to change the paper's own file, which must ask for approval.
            yield call("edit_file", file_path="/repo/requirements.txt", old_string="numpy==1.19.5", new_string="numpy>=1.26")
        yield call("write_file", file_path="/requirements.repro.txt", content="numpy>=1.26\n")
        yield call("execute", command=".venv/bin/pip install -r requirements.repro.txt")
        yield call(
            "record_obstacle",
            stage="env",
            summary="pip install -r requirements.txt fails"
            + (f" (pip exit code {code.group(1)})" if code else "")
            + ": numpy==1.19.5 has no build for this Python version",
            fix="Installed numpy>=1.26 from a separate requirements.repro.txt; the original file is untouched",
            resolved=True,
        )
        yield call("edit_file", file_path=FIXES, old_string=HEADER, new_string=HEADER + "\n" + NUMPY_FIX)
        yield say(
            "Environment ready: start the code with .venv/bin/python. One fix: the numpy pin (1.19.5) can't be "
            "installed on this Python, so I installed numpy>=1.26 from requirements.repro.txt and saved the fix."
        )

    # --- main: run
    yield _todos(2)
    yield call(
        "task",
        subagent_type="runner",
        description="Run `cd repo && ../.venv/bin/python run.py --seed 0` with run_experiment and report where the output is.",
    )
    if os.environ.get("REPRO_SCRIPT_BACKGROUND"):
        # Test switch: run the experiment in the background (made slow on purpose) and poll it.
        messages = yield call(
            "start_background_run",
            command="cd repo && sleep 3 && ../.venv/bin/python run.py --seed 0",
            est_minutes=1,
            why="prints the selected model and its test R^2 (q1, q2)",
        )
        ran = False
        if last_result(messages, "start_background_run").startswith("Started as"):
            for _ in range(30):
                messages = yield call("check_background_run", run_id="bg1")
                state = last_result(messages, "check_background_run")
                if not state.startswith("Still running"):
                    ran = "exit code 0" in state
                    break
                yield call("execute", command="sleep 1")
    else:
        messages = yield call(
            "run_experiment",
            command="cd repo && ../.venv/bin/python run.py --seed 0",
            est_minutes=1,
            why="prints the selected model and its test R^2 (q1, q2)",
        )
        ran = bool(re.search(r"^test r2:", last_result(messages, "run_experiment"), flags=re.M))
    if not ran:
        yield say("The experiment was not run: the approval was rejected, so there is no output.")
        yield say("The run stopped because the experiment was not approved. No question could be answered.")
        return
    yield say("The command exited with status 0 in about a second. Its output is saved under /logs.")

    # --- main: answers
    yield _todos(3)
    yield call(
        "task",
        subagent_type="result-judge",
        description="Record q1 (test R^2 printed by run.py, a number) and q2 (name of the selected model, a string) "
        "from the saved output under /logs. Lines start with 'test r2:' and 'best model:'.",
    )
    # The grep tool matches literal text, so each line gets its own search.
    messages = yield call("grep", pattern="test r2:", path="/logs", output_mode="content")
    r2 = re.search(r"test r2: *(-?[0-9.]+)", last_result(messages, "grep"))
    messages = yield call("grep", pattern="best model:", path="/logs", output_mode="content")
    best = re.search(r"best model: *([\w.-]+)", last_result(messages, "grep"))
    if r2:
        yield call("record_answer", question_id="q1", value=float(r2.group(1)), quote=r2.group(0), confidence="high")
    if best:
        yield call("record_answer", question_id="q2", value=best.group(1), quote=best.group(0), confidence="high")
    yield say("Both answers are in the run's output. The note's abstract says 0.46, which agrees with the printed 0.4555 after rounding.")

    yield _todos(4)
    yield say("Ran run.py with seed 0 after relaxing the numpy pin. Both answers come from its output.")


def scripted_model_for(task: Task) -> ScriptedChatModel:
    if task.task_id != "toy-linreg":
        raise RuntimeError(
            f"REPRO_MODEL=scripted only knows the toy-linreg fixture, not '{task.task_id}'. Use a real model."
        )
    flow = _toy_flow()
    next(flow)  # run to the first bare yield, so send() works from the first model call
    return ScriptedChatModel(flow=flow)
