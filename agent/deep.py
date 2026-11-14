"""The deep agent: prompt, tools, approvals, and the mapping from its stream to contract events."""

from __future__ import annotations

import os
import sys
from typing import Any

from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from agent.rundir import RunWriter
from agent.sandbox import SHORT_TIMEOUT_S, LoggingShellBackend
from agent.task import Findings

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
originals as they are. If nothing works without changing a source file, record that as an obstacle.

Your workspace:
- File tools see the workspace as `/`: the repository is `/repo`, and `/paper.md` exists when the \
task comes with paper text.
- Shell commands start in that same directory, but file-tool paths are not real shell paths. In the \
shell use relative paths (`repo/run.py`, not `/repo/run.py`).
- For Python, create a virtual environment in the workspace (`python3 -m venv .venv`) and install \
into it. Don't install into the system Python.

Running commands:
- `execute` is for setup and inspection. It stops a command after {SHORT_TIMEOUT_S} seconds. Passing \
a longer `timeout` is allowed for slow installs, and a human is asked to approve it first.
- `run_experiment` is for the command that produces the paper's results. A human is asked to approve \
it before it runs, so give an honest time estimate and say what it will do.
- If an approval is rejected, don't retry the same thing. Find another way, or finish with what you have.

Recording results:
- When something fails, read the error, fix the cause, and call `record_obstacle` with what happened \
and what fixed it. Obstacles are part of the report, including the ones you couldn't fix.
- For each question call `record_answer` with the value and the exact line of output it came from. \
The quote is checked against the saved command output and rejected if it isn't there.
- Keep a short plan with `write_todos` (read the task and repo, set up the environment, run, extract \
the answers) and update it as you go.

When every question has an answer or a recorded reason for not having one, reply with a two or three \
sentence summary and stop."""


def build_tools(backend: LoggingShellBackend, findings: Findings) -> list[Any]:
    @tool
    def run_experiment(command: str, est_minutes: float, why: str) -> str:
        """Run the command that produces the paper's results. A human approves it before it runs.

        Args:
            command: The shell command, with relative paths (it starts in the workspace directory).
            est_minutes: Your honest estimate of how long it takes, in minutes.
            why: One sentence on what this run produces and which questions it answers.
        """
        timeout = max(120, int(est_minutes * 60 * 3))
        response = backend.execute(command, timeout=timeout)
        return response.output

    @tool
    def record_answer(question_id: str, value: Any, quote: str, confidence: str) -> str:
        """Record the answer to one question, with the output line that proves it.

        Args:
            question_id: The question's id, for example "q1".
            value: A number for number questions, text for string questions, a list for list questions.
            quote: The exact text from this run's command output that the answer came from.
            confidence: "high", "medium" or "low".
        """
        return findings.record_answer(question_id, value, quote, confidence)

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

    return [run_experiment, record_answer, record_obstacle]


def _needs_long_run_approval(request: Any) -> bool:
    """`execute` asks for approval only when the model raises the timeout past the short limit."""
    timeout = (request.tool_call.get("args") or {}).get("timeout")
    return isinstance(timeout, (int, float)) and timeout > SHORT_TIMEOUT_S


def build_agent(model: Any, backend: LoggingShellBackend, findings: Findings) -> Any:
    decisions = ["approve", "reject"]
    return create_deep_agent(
        model=model,
        tools=build_tools(backend, findings),
        system_prompt=SYSTEM_PROMPT,
        # Planning is opt-in in deepagents 0.7.38: without this there is no `write_todos` tool.
        middleware=[TodoListMiddleware()],
        backend=backend,
        interrupt_on={
            "run_experiment": {"allowed_decisions": decisions},
            "execute": {"allowed_decisions": decisions, "when": _needs_long_run_approval},
        },
        checkpointer=InMemorySaver(),  # interrupts need one; state lives only for this process
        name="repro-bot",
    )


def approval_request(action: dict[str, Any]) -> dict[str, Any]:
    """Turn a paused tool call into the fields of a contract approval request."""
    args = action.get("args") or {}
    command = str(args.get("command") or "")
    if action.get("name") == "run_experiment":
        minutes = args.get("est_minutes")
        estimate = f" (est. {minutes:g} min)" if isinstance(minutes, (int, float)) else ""
        why = f": {args['why']}" if args.get("why") else ""
        summary = f"Run {command}{estimate}{why}"
    else:
        summary = f"Run {command} (allowed up to {args.get('timeout')} s)"
    return {"kind": "long_run", "summary": summary, "command": command or None}


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def _one_line(text: str, limit: int = 140) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1] + "…"


_QUIET_TOOLS = {"write_todos", "record_answer", "record_obstacle"}  # shown through other events


class EventMapper:
    """Reads the agent's update stream and appends the matching contract events."""

    def __init__(self, writer: RunWriter, backend: LoggingShellBackend) -> None:
        self.writer = writer
        self.backend = backend
        self.tokens = 0
        self._calls: dict[str, dict[str, Any]] = {}  # tool_call_id -> {name, args, agent}
        self._subagents: list[str] = []  # names of running subagents, newest last

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
        usage = getattr(message, "usage_metadata", None) or {}
        self.tokens += int(usage.get("total_tokens") or 0)
        for call in message.tool_calls:
            args = call.get("args") or {}
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
        data: dict[str, Any] = {"tool": name}
        if name in ("execute", "run_experiment"):
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
