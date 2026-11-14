"""Optional LangSmith tracing: one trace per run, and its link for report.json's ``trace_url``.

On when ``LANGSMITH_TRACING=true`` and ``LANGSMITH_API_KEY`` are set. Tracing must never
break a run, so every failure here ends in "no link".

Where traces go depends on the kind of LangSmith workspace (docs: "Log traces to an agent"):

- agent-based workspace (the current LangSmith Cloud default): ``LANGSMITH_AGENT_ID`` and
  ``LANGSMITH_AGENT_ENVIRONMENT`` (one of local, development, staging, production). Legacy
  project variables must then be unset, or the SDK traces nothing.
- project-based workspace: ``LANGSMITH_PROJECT`` (default ``repro-bot``).
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

DEFAULT_PROJECT = "repro-bot"
_LEGACY_PROJECT_VARS = ("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT", "LANGCHAIN_SESSION")
_AGENT_VARS = ("LANGSMITH_AGENT_ID", "LANGSMITH_AGENT_ENVIRONMENT")
_AGENT_ENVIRONMENTS = ("local", "development", "staging", "production")
# LangSmith's identifier rule: 1-63 characters, starts with a letter, ends with a letter or digit.
_AGENT_ID = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def available_agents() -> list[str] | str:
    """The agent IDs in the key's workspace, or an error text. For hints in `agent.check` only."""
    import warnings

    try:
        from langsmith import Client

        with warnings.catch_warnings():  # the client warns about the very settings being diagnosed
            warnings.simplefilter("ignore")
            return [agent.id for agent in Client().agents.list(page_size=50)]
    except Exception as exc:  # noqa: BLE001 - only a hint
        return f"{type(exc).__name__}: {str(exc)[:200]}"


def tracing_on() -> bool:
    flag = (os.environ.get("LANGSMITH_TRACING") or os.environ.get("LANGCHAIN_TRACING_V2") or "").lower()
    has_key = bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY"))
    return flag in ("1", "true", "yes", "on") and has_key


def destination() -> tuple[str, str | None]:
    """Where traces go: (description, problem or None). Call only when tracing is on."""
    agent_vars = {var: (os.environ.get(var) or "").strip() for var in _AGENT_VARS}
    legacy = [var for var in _LEGACY_PROJECT_VARS if os.environ.get(var)]
    if any(agent_vars.values()):
        agent_id, env = agent_vars["LANGSMITH_AGENT_ID"], agent_vars["LANGSMITH_AGENT_ENVIRONMENT"]
        where = f"agent {agent_id or '?'}, environment {env or '?'}"
        if not (agent_id and env):
            missing = "LANGSMITH_AGENT_ID" if not agent_id else "LANGSMITH_AGENT_ENVIRONMENT"
            return where, f"{missing} is not set; LangSmith needs both agent variables or neither"
        if not _AGENT_ID.fullmatch(agent_id):
            hint = " That looks like a UUID." if _UUID.fullmatch(agent_id) else ""
            return where, (
                f"LANGSMITH_AGENT_ID must be the agent's short ID (lowercase letters, digits and hyphens, "
                f"like 'repro-bot'), shown as ID on the agent's Overview page in LangSmith.{hint}"
            )
        if env.lower() not in _AGENT_ENVIRONMENTS:
            return where, f"LANGSMITH_AGENT_ENVIRONMENT must be one of {', '.join(_AGENT_ENVIRONMENTS)}"
        if legacy:
            return where, f"remove {', '.join(legacy)}: with agent variables set, LangSmith traces nothing"
        return where, None
    return f"project {os.environ.get('LANGSMITH_PROJECT') or DEFAULT_PROJECT}", None


def _prepare_destination() -> str | None:
    """Fill in the default project when no agent is named. Returns a problem, or None."""
    if not any(os.environ.get(var) for var in _AGENT_VARS):
        os.environ.setdefault("LANGSMITH_PROJECT", DEFAULT_PROJECT)
    return destination()[1]


def flush() -> None:
    """Send queued trace data now (it is posted from a background thread)."""
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers

        wait_for_all_tracers()
    except Exception as exc:  # noqa: BLE001 - tracing must never break a run
        print(f"agent.run: could not flush LangSmith traces ({type(exc).__name__}: {exc})", file=sys.stderr)


def confirm_received(run_id: str, attempts: int = 6, wait_s: float = 2.0) -> str | None:
    """Ask LangSmith for the run until it shows up. Returns None when it did, else the last error."""
    import time
    import warnings

    from langsmith import Client
    from langsmith.utils import LangSmithNotFoundError

    error = "not found"
    for attempt in range(attempts):
        try:
            # read_run is deprecated (removed after 2027-01-31); its replacement, the async
            # client.runs.retrieve, needs a project id that agent-based workspaces don't hand us.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                Client().read_run(run_id)
            return None
        except LangSmithNotFoundError as exc:  # ingestion is asynchronous: wait and ask again
            error = f"not found after {attempts * wait_s:g} s ({str(exc)[:200]})"
        except Exception as exc:  # noqa: BLE001 - a bad key or endpoint won't fix itself; stop asking
            return f"{type(exc).__name__}: {str(exc)[:200]}"
        if attempt < attempts - 1:
            time.sleep(wait_s)
    return error


@contextmanager
def run_trace(task_id: str, run_id: str, model: str) -> Generator[dict[str, Any]]:
    """Group everything the agent does in this run under one LangSmith trace.

    Yields a dict whose ``url`` is filled in when the block ends (None when tracing is off
    or the link could not be made). Approvals split a run into several agent invocations;
    the parent trace keeps them together.
    """
    result: dict[str, Any] = {"url": None}
    if not tracing_on():
        yield result
        return
    problem = _prepare_destination()
    if problem:
        print(f"agent.run: LangSmith tracing is off for this run ({problem})", file=sys.stderr)
        yield result
        return
    try:
        import langsmith

        manager = langsmith.trace(
            name=f"repro-bot {task_id}",
            run_type="chain",
            inputs={"task_id": task_id, "run_id": run_id, "model": model},
            metadata={"thread_id": run_id, "task_id": task_id},
        )
        run_tree = manager.__enter__()
    except Exception as exc:  # noqa: BLE001 - bad key, no network, API change: run without a trace
        print(f"agent.run: LangSmith tracing is off for this run ({type(exc).__name__}: {exc})", file=sys.stderr)
        yield result
        return
    result["run_id"] = str(run_tree.id)
    exc_info: tuple[Any, Any, Any] = (None, None, None)
    try:
        yield result
    except BaseException as exc:
        exc_info = (type(exc), exc, exc.__traceback__)  # mark the trace as failed, then re-raise
        raise
    finally:
        try:
            manager.__exit__(*exc_info)
            flush()
            result["url"] = run_tree.get_url()
        except Exception as exc:  # noqa: BLE001
            print(f"agent.run: no LangSmith link for this run ({type(exc).__name__}: {exc})", file=sys.stderr)
