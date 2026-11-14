"""An offline stand-in for the LLM, for the toy task only (``REPRO_MODEL=scripted``).

It replays a fixed sequence of tool calls through the real deep agent graph, so the
sandbox, approvals, events and report can be checked without an API key. The commands
really run, and the answers are parsed from their output, never written into the script.
It can't solve anything except ``toy-linreg`` and proves nothing about a real model.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agent.task import Task

Step = AIMessage | Callable[[list[BaseMessage]], AIMessage]


def call(name: str, **args: Any) -> AIMessage:
    """An assistant turn that calls one tool."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:12]}", "type": "tool_call"}],
    )


def say(text: str) -> AIMessage:
    """An assistant turn with plain text, which ends the agent loop."""
    return AIMessage(content=text)


def tool_text(messages: Sequence[BaseMessage], name: str) -> str:
    """Text of the most recent result of tool ``name``."""
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name == name:
            return message.content if isinstance(message.content, str) else str(message.content)
    return ""


class ScriptedChatModel(BaseChatModel):
    """Replays ``script`` one step per model call."""

    script: list[Any]
    cursor: int = 0
    bound_tools: list[str] = Field(default_factory=list)

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
        if self.cursor >= len(self.script):
            return ChatResult(generations=[ChatGeneration(message=say("The script has no more steps."))])
        step = self.script[self.cursor]
        self.cursor += 1
        message = step(messages) if callable(step) else step
        return ChatResult(generations=[ChatGeneration(message=message)])


_PLAN = ["Read the task and the repo", "Set up the environment", "Run the experiment", "Extract and check the answers"]


def _todos(done: int, active: bool = True) -> AIMessage:
    todos = []
    for i, content in enumerate(_PLAN):
        status = "completed" if i < done else ("in_progress" if i == done and active else "pending")
        todos.append({"content": content, "status": status})
    return call("write_todos", todos=todos)


def _toy_script() -> list[Step]:
    def note_install_failure(messages: list[BaseMessage]) -> AIMessage:
        # The install failure is the older of the two `execute` results by now.
        failed = next(
            (
                m.content
                for m in messages
                if isinstance(m, ToolMessage) and m.name == "execute" and "Exit code:" in str(m.content)
            ),
            "",
        )
        code = re.search(r"Exit code: (\d+)", str(failed))
        detail = f" (pip exit code {code.group(1)})" if code else ""
        return call(
            "record_obstacle",
            stage="env",
            summary=f"pip install -r requirements.txt fails{detail}: numpy==1.19.5 has no build for this Python version",
            fix="Installed numpy>=1.26 from a separate requirements.repro.txt; the original file is untouched",
            resolved=True,
        )

    def after_run(messages: list[BaseMessage]) -> AIMessage:
        output = tool_text(messages, "run_experiment")
        if not re.search(r"^test r2:", output, flags=re.M):
            return say("The experiment did not run, so there is nothing to report.")
        return _todos(3)

    def answer(question_id: str, prefix: str, number: bool) -> Callable[[list[BaseMessage]], AIMessage]:
        def step(messages: list[BaseMessage]) -> AIMessage:
            output = tool_text(messages, "run_experiment")
            line = next((ln.strip() for ln in output.splitlines() if ln.strip().startswith(prefix)), "")
            raw = line[len(prefix) :].strip()
            return call(
                "record_answer",
                question_id=question_id,
                value=float(raw) if number and raw else raw,
                quote=line,
                confidence="high",
            )

        return step

    return [
        _todos(0),
        call("read_file", file_path="/repo/README.md"),
        call("read_file", file_path="/repo/requirements.txt"),
        call("read_file", file_path="/repo/run.py"),
        _todos(1),
        call("execute", command="python3 -m venv .venv && .venv/bin/pip install -r repo/requirements.txt"),
        call("write_file", file_path="/requirements.repro.txt", content="numpy>=1.26\n"),
        call("execute", command=".venv/bin/pip install -r requirements.repro.txt"),
        note_install_failure,
        _todos(2),
        call(
            "run_experiment",
            command="cd repo && ../.venv/bin/python run.py --seed 0",
            est_minutes=1,
            why="prints the selected model and its test R^2 (q1, q2)",
        ),
        after_run,
        answer("q1", "test r2:", number=True),
        answer("q2", "best model:", number=False),
        _todos(4),
        say("Ran run.py with seed 0 after relaxing the numpy pin. Both answers come from its output."),
    ]


def scripted_model_for(task: Task) -> ScriptedChatModel:
    if task.task_id != "toy-linreg":
        raise RuntimeError(
            f"REPRO_MODEL=scripted only knows the toy-linreg fixture, not '{task.task_id}'. Use a real model."
        )
    return ScriptedChatModel(script=_toy_script())
