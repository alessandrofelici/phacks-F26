"""Optional LangSmith tracing: one trace per run, and its link for report.json's ``trace_url``.

On when ``LANGSMITH_TRACING=true`` and ``LANGSMITH_API_KEY`` are set. Tracing must never
break a run, so every failure here ends in "no link".
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def tracing_on() -> bool:
    flag = (os.environ.get("LANGSMITH_TRACING") or os.environ.get("LANGCHAIN_TRACING_V2") or "").lower()
    return flag in ("1", "true", "yes", "on") and bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY"))


@contextmanager
def run_trace(task_id: str, run_id: str, model: str) -> Iterator[dict[str, Any]]:
    """Group everything the agent does in this run under one LangSmith trace.

    Yields a dict whose ``url`` is filled in when the block ends (None when tracing is off
    or the link could not be made). Approvals split a run into several agent invocations;
    the parent trace keeps them together.
    """
    result: dict[str, Any] = {"url": None}
    if not tracing_on():
        yield result
        return
    os.environ.setdefault("LANGSMITH_PROJECT", "repro-bot")
    try:
        import langsmith

        manager = langsmith.trace(
            name=f"repro-bot {task_id}",
            run_type="chain",
            inputs={"task_id": task_id, "run_id": run_id, "model": model},
            metadata={"thread_id": run_id, "task_id": task_id},
        )
        run_tree = manager.__enter__()
    except Exception as exc:  # bad key, no network, API change: run without a trace
        print(f"agent.run: LangSmith tracing is off for this run ({type(exc).__name__}: {exc})", file=sys.stderr)
        yield result
        return
    try:
        yield result
    finally:
        try:
            manager.__exit__(None, None, None)
            result["url"] = run_tree.get_url()
        except Exception as exc:
            print(f"agent.run: no LangSmith link for this run ({type(exc).__name__}: {exc})", file=sys.stderr)
