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
        """Save full command output under logs/ and return its path relative to the run dir."""
        with self._lock:
            self._log_count += 1
            rel = f"logs/{self._log_count:02d}-{_slug(label)}.txt"
        (self.run_dir / rel).write_text(text, encoding="utf-8")
        self.logs.append(rel)
        return rel

    def find_quote(self, quote: str) -> str | None:
        """The newest saved log that contains ``quote`` exactly, or None."""
        for rel in reversed(self.logs):
            try:
                if quote in (self.run_dir / rel).read_text(encoding="utf-8"):
                    return rel
            except OSError:
                continue
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
    ) -> dict[str, Any]:
        """Write the request, wait for the decision and return it (contract 3.1).

        ``deadline`` is a ``time.monotonic()`` value; waiting never goes past it.
        """
        with self._lock:
            self._approval_count += 1
            approval_id = f"a{self._approval_count}"
        adir = self.run_dir / "approvals"
        request = {"id": approval_id, "kind": kind, "summary": summary, "command": command, "diff": diff}
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
