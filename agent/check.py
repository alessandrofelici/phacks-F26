"""Check the configuration before spending money on a run.

    python -m agent.check          # what would be used: model, key, sandbox, tracing
    python -m agent.check --call   # also send one tiny request to the model (costs a fraction of a cent)

Exit code 0 when a run could start, 1 otherwise.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

from agent.run import REPO_ROOT, ensure_dependencies, load_dotenv


def _mask(value: str) -> str:
    return f"set ({len(value)} characters, ends in ...{value[-4:]})" if len(value) > 8 else "set"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="python -m agent.check", description="Check Repro Bot's configuration.")
    parser.add_argument("--call", action="store_true", help="send one small request to the model")
    args = parser.parse_args(argv)

    env_file = REPO_ROOT / ".env"
    load_dotenv(env_file)
    ensure_dependencies(argv, module="agent.check")

    from agent import models
    from agent.tracing import (
        available_agents,
        confirm_received,
        destination,
        run_trace,
        tracing_on,
    )

    ok = True
    print(f".env file:      {'found' if env_file.is_file() else 'not found'} ({env_file})")
    name = models.chosen_model()
    print(f"model:          {name}" + ("" if os.environ.get("REPRO_MODEL") else "  (default for the key that is set)"))
    sub = models.chosen_subagent_model()
    print(f"subagent model: {sub or 'same as the main model'}")
    for label, model_name in (("main", name), ("subagents", sub)):
        if not model_name or model_name == "scripted":
            continue
        var = models.missing_key(model_name)
        if var:
            print(f"key:            MISSING for {label}: put {var} in {env_file}")
            ok = False
        else:
            provider = model_name.split(":", 1)[0]
            present = next((v for v in models.KEYS.get(provider, ()) if os.environ.get(v)), None)
            print(f"key:            {present or '(provider needs no known key)'} {_mask(os.environ[present]) if present else ''}".rstrip())
    choice = os.environ.get("REPRO_SANDBOX", "auto").lower()
    have_podman = bool(shutil.which("podman"))
    if choice == "local" or (choice == "auto" and not have_podman):
        print("sandbox:        local shell (no isolation: the paper's code can read this disk)")
    elif have_podman:
        print(f"sandbox:        podman, image {os.environ.get('REPRO_SANDBOX_IMAGE', 'docker.io/library/python:3.12-slim')}")
    else:
        print("sandbox:        REPRO_SANDBOX=podman but podman is not installed")
        ok = False
    tracing = tracing_on()
    if tracing:
        where, problem = destination()
        if problem:
            print(f"LangSmith:      MISCONFIGURED ({where}): {problem}")
            if "AGENT_ID" in problem:
                agents = available_agents()
                shown = ", ".join(agents) or "none yet (create one: Tracing > Connect an agent)"
                print(f"                agent IDs in this workspace: {shown if isinstance(agents, list) else agents}")
            ok = False
        else:
            print(f"LangSmith:      tracing on, {where}")
    else:
        print("LangSmith:      off (trace_url will be null; set LANGSMITH_TRACING=true and LANGSMITH_API_KEY)")

    if args.call and ok and name != "scripted":
        # With tracing on, the test call is itself traced, so the printed link proves LangSmith works.
        with run_trace("agent.check", "check", name) as trace:
            for label, model_name in (("main", name), ("subagents", sub)):
                if not model_name:
                    continue
                try:
                    model = models.make_model(model_name)
                    reply = model.invoke("Reply with the single word: ready")
                    text = reply.content if isinstance(reply.content, str) else str(reply.content)
                    usage = getattr(reply, "usage_metadata", None) or {}
                    tokens = usage.get("total_tokens", "?")
                    print(f"model call:     {label} ({model_name}) answered {text.strip()[:40]!r}, {tokens} tokens")
                except Exception as exc:  # noqa: BLE001 - report any failure as "not ready"
                    print(f"model call:     {label} ({model_name}) FAILED: {type(exc).__name__}: {str(exc)[:300]}")
                    ok = False
        if tracing:
            problem = confirm_received(trace["run_id"]) if trace.get("run_id") else "no trace was started"
            if problem:
                print(f"LangSmith:      trace NOT received ({problem})")
                ok = False
            else:
                print(f"LangSmith:      trace received: {trace['url'] or '(no link)'}")
    elif args.call and name == "scripted":
        print("model call:     skipped (REPRO_MODEL=scripted uses no LLM)")

    print("ready" if ok else "not ready")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
