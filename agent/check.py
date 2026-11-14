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
    from agent.tracing import tracing_on

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
    print(f"LangSmith:      {'tracing on, project ' + os.environ.get('LANGSMITH_PROJECT', 'repro-bot') if tracing_on() else 'off (trace_url will be null)'}")

    if args.call and ok and name != "scripted":
        for label, model_name in (("main", name), ("subagents", sub)):
            if not model_name:
                continue
            try:
                model = models.make_model(model_name)
                reply = model.invoke("Reply with the single word: ready")
                text = reply.content if isinstance(reply.content, str) else str(reply.content)
                usage = getattr(reply, "usage_metadata", None) or {}
                print(f"model call:     {label} ({model_name}) answered {text.strip()[:40]!r}, {usage.get('total_tokens', '?')} tokens")
            except Exception as exc:
                print(f"model call:     {label} ({model_name}) FAILED: {type(exc).__name__}: {str(exc)[:300]}")
                ok = False
    elif args.call and name == "scripted":
        print("model call:     skipped (REPRO_MODEL=scripted uses no LLM)")

    print("ready" if ok else "not ready")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
