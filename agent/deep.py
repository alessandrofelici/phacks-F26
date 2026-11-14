"""The deep agent: prompt, tools, approvals, and the mapping from its stream to contract events."""

from __future__ import annotations

import difflib
import os
import sys
from pathlib import Path
from typing import Any

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend
from langchain.agents.middleware import (
    InterruptOnConfig,
    TodoListMiddleware,
    ToolCallRequest,
)
from langchain.agents.middleware.human_in_the_loop import DecisionType
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from agent.rundir import RunWriter
from agent.sandbox import SHORT_TIMEOUT_S, LoggingShellBackend
from agent.task import Findings

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
MEMORY_FILE = "/memories/fixes.md"
MEMORY_HEADER = "# Fixes that worked\n"

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
- For Python, create a virtual environment in the workspace (`python3 -m venv .venv`) and install \
into it. Don't install into the system Python.

Running commands:
- `execute` is for setup and inspection. It stops a command after {SHORT_TIMEOUT_S} seconds. Passing \
a longer `timeout` is allowed for slow installs, and a human is asked to approve it first.
- `run_experiment` is for the command that produces the paper's results. A human is asked to approve \
it before it runs, so give an honest time estimate and say what it will do.
- `start_background_run` is for an experiment that takes more than a couple of minutes. It is \
approved the same way, returns at once, and `check_background_run` reports on it. Use the wait for \
work that doesn't depend on the result, and don't check in a tight loop (`sleep 30` through \
`execute` is a fine way to wait).
- If an approval is rejected, don't retry the same thing. Find another way, or finish with what you have.

How to split the work (each helper starts with only the message you give it, so include the \
file paths, commands and question texts it needs):
- `paper-reader` first: it finds which command produces each asked value and what the repository \
needs to run. It reads and never runs anything.
- `env-builder`: it gets the environment installed and tells you how to start the code.
- `runner`: it runs the experiment through `run_experiment` and reports where the output is.
- `result-judge`: it finds each answer in the output and records it with its evidence.
For a small repository you may do a step yourself when delegating would only add a round trip.

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
The quote is checked against the saved command output and rejected if it isn't there.
- Keep a short plan with `write_todos` (read the task and repo, set up the environment, run, extract \
the answers) and update it as you go.

When every question has an answer or a recorded reason for not having one, reply with a two or three \
sentence summary and stop."""


def build_tools(backend: LoggingShellBackend, findings: Findings, agent: str = "main") -> dict[str, Any]:
    """The custom tools, bound to the agent that will call them (so events name the right one)."""

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
    def start_background_run(command: str, est_minutes: float, why: str) -> str:
        """Start a long experiment in the background, after human approval, and return at once.

        Use this when the run will take more than a couple of minutes, then follow it with
        `check_background_run` while doing other work.

        Args:
            command: The shell command, with relative paths (it starts in the workspace directory).
            est_minutes: Your honest estimate of how long it takes, in minutes.
            why: One sentence on what this run produces and which questions it answers.
        """
        run_id = backend.start_background(command, max(120, int(est_minutes * 60 * 3)))
        if not run_id:
            return "Error: the run's time limit is used up; nothing was started."
        return f"Started as {run_id}. It keeps running while you work; call check_background_run('{run_id}') to follow it."

    @tool
    def check_background_run(run_id: str) -> str:
        """Report whether a background run has finished, with the last lines of its output.

        Args:
            run_id: The id `start_background_run` returned, for example "bg1".
        """
        state = backend.check_background(run_id)
        if state is None:
            return f"Error: there is no background run '{run_id}'."
        if not state["done"]:
            return f"Still running after {state['seconds']:.0f} s. Last lines so far:\n{state['tail'] or '<no output yet>'}"
        how = "was stopped at its time limit" if state["timed_out"] else f"finished with exit code {state['exit_code']}"
        return f"The run {how} after {state['seconds']:.0f} s. Full output saved as /{state['log']}. Last lines:\n{state['tail'] or '<no output>'}"

    @tool
    def record_answer(question_id: str, value: Any, quote: str, confidence: str) -> str:
        """Record the answer to one question, with the output line that proves it.

        Args:
            question_id: The question's id, for example "q1".
            value: A number for number questions, text for string questions, a list for list questions.
            quote: The exact text from this run's command output that the answer came from.
            confidence: "high", "medium" or "low".
        """
        return findings.record_answer(question_id, value, quote, confidence, agent)

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
        "record_obstacle": record_obstacle,
    }


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

For Python, create a virtual environment in the workspace (`python3 -m venv .venv`) and install into it. \
Otherwise try the documented install first. When it fails, read the error and fix the cause with the smallest \
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
at once; follow it with `check_background_run`, waiting between checks (`sleep 30` through `execute`), \
and report when it has finished.

If the command fails, report the error text. Don't change the paper's code to get past it; a missing \
package or path is the environment's problem, and the caller decides what to do. Record what went \
wrong with `record_obstacle` (stage "run").

Finish by reporting the exit status, roughly how long it took, and which file under `/logs` holds the output.""",
    },
    {
        "name": "result-judge",
        "description": "Finds each answer in the run's saved output and records it with the line that proves it.",
        "tools": ["record_answer", "record_obstacle"],
        "system_prompt": f"""You extract answers from the output of a paper's code. {_WORKSPACE_NOTE}

Search `/logs` (every command's output is saved there) and any files the run wrote. For each question \
call `record_answer` with the value and the exact line it came from. The quote is checked against the \
saved output and refused if it isn't there. Keep the precision the output shows; don't round.

If the paper text states a value, say in your report whether the output agrees with it. The recorded \
answer is always what the run printed. If the output doesn't contain an answer, say so and call \
`record_obstacle` (stage "extract"); never fill a gap from the paper.""",
    },
]


def _writes_into_repo(request: ToolCallRequest) -> bool:
    """File-tool writes under /repo need approval; new files elsewhere in the workspace don't."""
    path = str((request.tool_call.get("args") or {}).get("file_path") or "")
    return ("/" + path.lstrip("/")).startswith("/repo/")


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
        tools = build_tools(shell, findings, agent=spec["name"])
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
    interrupt_on: dict[str, bool | InterruptOnConfig] = {
        "run_experiment": {"allowed_decisions": decisions},
        "start_background_run": {"allowed_decisions": decisions},
        "execute": {"allowed_decisions": decisions, "when": _needs_long_run_approval},
        # Changing a file inside the paper's repository pauses for an `edit_source` approval.
        # (`permissions=` would be the deepagents way, but 0.7.38 refuses permissions on a
        # backend that can execute commands.)
        "write_file": {"allowed_decisions": decisions, "when": _writes_into_repo},
        "edit_file": {"allowed_decisions": decisions, "when": _writes_into_repo},
    }
    return create_deep_agent(
        model=model,
        tools=list(build_tools(shell, findings).values()),
        system_prompt=SYSTEM_PROMPT,
        # Planning is opt-in in deepagents 0.7.38: without this there is no `write_todos` tool.
        middleware=[TodoListMiddleware()],
        subagents=subagents,
        skills=["/skills/"],
        memory=[MEMORY_FILE],
        backend=backend,
        # Subagents inherit these, so an approval inside `runner` pauses the whole run.
        interrupt_on=interrupt_on,
        checkpointer=InMemorySaver(),  # interrupts need one; state lives only for this process
        name="repro-bot",
    )


def approval_request(action: dict[str, Any], work: Path) -> dict[str, Any]:
    """Turn a paused tool call into the fields of a contract approval request."""
    name = action.get("name")
    args = action.get("args") or {}
    if name in ("write_file", "edit_file"):
        path = str(args.get("file_path") or "")
        summary = f"Change {path} (a file inside the paper's repository)"
        return {"kind": "edit_source", "summary": summary, "command": None, "diff": _diff(name, args, work)}
    command = str(args.get("command") or "")
    if name in ("run_experiment", "start_background_run"):
        minutes = args.get("est_minutes")
        estimate = f" (est. {minutes:g} min)" if isinstance(minutes, (int, float)) else ""
        why = f": {args['why']}" if args.get("why") else ""
        where = " in the background" if name == "start_background_run" else ""
        summary = f"Run {command}{where}{estimate}{why}"
    else:
        summary = f"Run {command} (allowed up to {args.get('timeout')} s)"
    return {"kind": "long_run", "summary": summary, "command": command or None, "diff": None}


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


_QUIET_TOOLS = {"write_todos", "record_answer", "record_obstacle"}  # shown through other events


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
        if name in ("start_background_run", "check_background_run"):
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
