"""Writes a run directory the way contract v1 describes it (CONTRACT.md section 2).

Standard library only, so it can be tested without the agent's dependencies.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

APPROVAL_TIMEOUT_S = 600.0  # contract 3.1: no decision within 10 minutes is a rejection
POLL_S = 1.0


class RunDirError(RuntimeError):
    """The run directory can't be used (for example it already holds a run)."""


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].strip("-") or "output"


_PRINT_WORDS = {"echo", "printf"}
_HARMLESS_WORDS = {"cd", "true", ":", "export", "sleep", "tee"}
_QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def prints_only(command: str) -> bool:
    """True for a command that only prints text written into it (``cd repo && echo "acc 0.9"``).

    Quoted text is set aside before splitting, so a ``;`` inside an echoed string doesn't hide the
    echo. A command substitution (``$(...)`` or backticks) runs real code, so its output can count.
    """
    if "$(" in command or "`" in command:
        return False
    unquoted = _QUOTED.sub(" '' ", command)
    words = []
    for segment in re.split(r"&&|\|\||;|\||\n", unquoted):
        tokens = segment.strip().lstrip("({ ").split()
        while tokens and _ASSIGNMENT.match(tokens[0]):
            tokens.pop(0)  # VAR=value before the command
        if tokens:
            words.append(tokens[0].rsplit("/", 1)[-1])  # /bin/echo is echo
    return bool(words) and any(w in _PRINT_WORDS for w in words) and all(w in _PRINT_WORDS | _HARMLESS_WORDS for w in words)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class RunWriter:
    """Appends events, saves logs, handles approvals and writes the final report."""

    def __init__(
        self,
        run_dir: Path | str,
        *,
        auto_approve: bool = False,
        approval_timeout_s: float = APPROVAL_TIMEOUT_S,
        poll_s: float = POLL_S,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.auto_approve = auto_approve
        self.approval_timeout_s = approval_timeout_s
        self.poll_s = poll_s
        # The harness normally creates the directory; create it when run by hand.
        self.run_dir.mkdir(parents=True, exist_ok=True)
        events_path = self.run_dir / "events.jsonl"
        if events_path.exists() and events_path.stat().st_size > 0:
            raise RunDirError(f"{events_path} already has events; use a new run directory")
        if (self.run_dir / "report.json").exists():
            raise RunDirError(f"{self.run_dir}/report.json already exists; use a new run directory")
        (self.run_dir / "logs").mkdir(exist_ok=True)
        (self.run_dir / "approvals").mkdir(exist_ok=True)
        self._events = events_path.open("a", encoding="utf-8")
        self._lock = threading.Lock()
        self._seq = 0
        self._log_count = 0
        self._approval_count = 0
        self.logs: list[str] = []  # paths relative to the run directory, oldest first
        self._commands: dict[str, str] = {}  # log path -> the command whose output it holds
        self._not_evidence: set[str] = set()  # logs whose output can't be quoted as an answer

    # -- events -----------------------------------------------------------------

    def event(self, etype: str, data: dict[str, Any], agent: str = "main") -> int:
        """Append one event and flush it, so the harness can tail the file."""
        with self._lock:
            self._seq += 1
            record = {"seq": self._seq, "ts": utc_now(), "type": etype, "agent": agent, "data": data}
            self._events.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._events.flush()
            return self._seq

    # -- logs -------------------------------------------------------------------

    def save_log(self, label: str, text: str) -> str:
        """Save full command output under logs/ and return its path relative to the run dir.

        ``label`` is the command; a log that starts with ``$ <command>`` has that line skipped
        when quotes are looked up, so the command's own text is never evidence.
        """
        with self._lock:
            self._log_count += 1
            rel = f"logs/{self._log_count:02d}-{_slug(label)}.txt"
        (self.run_dir / rel).write_text(text, encoding="utf-8")
        with self._lock:
            # The command is known before the log can be found, so find_quote never sees it half registered.
            self._commands[rel] = label
            self.logs.append(rel)
        return rel

    def exclude_from_evidence(self, rel: str) -> None:
        """Keep a saved log out of evidence (a probe stopped part-way: its numbers aren't the results)."""
        with self._lock:
            self._not_evidence.add(rel)

    def find_quote(self, quote: str) -> str | None:
        """The newest saved log whose output contains ``quote`` exactly, or None.

        Output of commands that only print text they were given (``echo``, ``printf``) and the
        ``$ <command>`` line at the top of a log don't count: they hold what the agent typed.
        """
        with self._lock:
            logs = list(self.logs)
            skip = set(self._not_evidence)
        for rel in reversed(logs):
            if rel in skip:
                continue
            command = self._commands.get(rel)
            if command is not None and prints_only(command):
                continue
            try:
                text = (self.run_dir / rel).read_text(encoding="utf-8")
            except OSError:
                continue
            head = f"$ {command}\n" if command is not None else None
            if head and text.startswith(head):
                text = text[len(head):]
            if quote in text:
                return rel
        return None

    # -- approvals --------------------------------------------------------------

    def request_approval(
        self,
        kind: str,
        summary: str,
        *,
        command: str | None = None,
        diff: str | None = None,
        agent: str = "main",
        deadline: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write the request, wait for the decision and return it (contract 3.1).

        ``deadline`` is a ``time.monotonic()`` value; waiting never goes past it. ``extra`` adds
        optional fields to the request file (for example a scaled plan's ``scale_down``).
        """
        with self._lock:
            self._approval_count += 1
            approval_id = f"a{self._approval_count}"
        adir = self.run_dir / "approvals"
        request = {**(extra or {}), "id": approval_id, "kind": kind, "summary": summary, "command": command, "diff": diff}
        _write_json_atomic(adir / f"{approval_id}.request.json", request)
        self.event("approval_requested", {"id": approval_id, "kind": kind, "summary": summary}, agent)

        decision_path = adir / f"{approval_id}.decision.json"
        if self.auto_approve:
            decision = {"id": approval_id, "decision": "approve", "note": "", "by": "auto"}
            _write_json_atomic(decision_path, decision)
        else:
            decision = self._wait_for_decision(approval_id, decision_path, deadline)
        self.event(
            "approval_resolved",
            {"id": approval_id, "decision": decision["decision"], "by": decision["by"]},
            agent,
        )
        return decision

    def _wait_for_decision(self, approval_id: str, path: Path, deadline: float | None) -> dict[str, Any]:
        give_up = time.monotonic() + self.approval_timeout_s
        if deadline is not None:
            give_up = min(give_up, deadline)
        while True:
            decision = self._read_decision(approval_id, path)
            if decision is not None:
                return decision
            if time.monotonic() >= give_up:
                break
            time.sleep(self.poll_s)
        timed_out = {"id": approval_id, "decision": "reject", "note": "no decision in time", "by": "timeout"}
        try:
            # Exclusive create: if the harness wrote a decision this instant, its answer wins.
            with path.open("x", encoding="utf-8") as handle:
                json.dump(timed_out, handle, indent=2)
                handle.write("\n")
        except FileExistsError:
            late = self._read_decision(approval_id, path)
            if late is not None:
                return late
        return timed_out

    @staticmethod
    def _read_decision(approval_id: str, path: Path) -> dict[str, Any] | None:
        try:
            decision = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None  # not there yet, or the harness is still writing it
        if not isinstance(decision, dict) or decision.get("decision") not in ("approve", "reject"):
            return None
        return {
            "id": approval_id,
            "decision": decision["decision"],
            "note": str(decision.get("note") or ""),
            "by": decision.get("by") if decision.get("by") in ("human", "auto", "timeout") else "human",
        }

    # -- report -----------------------------------------------------------------

    def write_report(self, report: dict[str, Any]) -> None:
        """Write report.json once, atomically (temp file, then rename)."""
        _write_json_atomic(self.run_dir / "report.json", report)

    def close(self) -> None:
        self._events.close()
