"""Which LLM the agent uses, and which key that needs.

Set in the environment or in `.env` at the repo root (see `agent/.env.example`):

- ``REPRO_MODEL``: a LangChain ``provider:model`` string, or ``scripted`` for the offline toy run.
- ``REPRO_SUBAGENT_MODEL``: optional, a cheaper model for the four subagents.

With ``REPRO_MODEL`` unset, the model follows the key that is present: OpenRouter first,
then Anthropic.
"""

from __future__ import annotations

import os
import sys
from typing import Any

OPENROUTER_DEFAULT = "openrouter:anthropic/claude-opus-5.5"
ANTHROPIC_DEFAULT = "anthropic:claude-opus-5-5"
MAX_TOKENS = 16000

# Any one of the listed variables is enough for that provider.
KEYS: dict[str, tuple[str, ...]] = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


class ModelConfigError(RuntimeError):
    """The model can't be used as configured (unknown provider, missing key or package)."""


def chosen_model() -> str:
    """The main model's name: ``REPRO_MODEL``, else whichever provider has a key."""
    name = (os.environ.get("REPRO_MODEL") or "").strip()
    if name:
        return name
    if os.environ.get("OPENROUTER_API_KEY"):
        return OPENROUTER_DEFAULT
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ANTHROPIC_DEFAULT
    return OPENROUTER_DEFAULT


def chosen_subagent_model() -> str | None:
    return (os.environ.get("REPRO_SUBAGENT_MODEL") or "").strip() or None


def missing_key(name: str) -> str | None:
    """The environment variable ``name`` needs but doesn't have, or None."""
    wanted = KEYS.get(name.split(":", 1)[0], ())
    if wanted and not any(os.environ.get(var) for var in wanted):
        return " or ".join(wanted)
    return None


def make_model(name: str) -> Any:
    """Build the chat model for a ``provider:model`` string, or raise ModelConfigError."""
    if ":" not in name:
        raise ModelConfigError(
            f"REPRO_MODEL '{name}' needs a provider prefix, for example '{OPENROUTER_DEFAULT}' or '{ANTHROPIC_DEFAULT}'."
        )
    var = missing_key(name)
    if var:
        raise ModelConfigError(
            f"{name} needs {var} in the environment or in .env at the repo root (copy agent/.env.example). "
            "Or use REPRO_MODEL=scripted for the offline toy run."
        )
    from langchain.chat_models import init_chat_model

    kwargs: dict[str, Any] = {}
    try:
        # deepagents' per-provider defaults (for OpenRouter: app attribution, no Azure routing).
        from deepagents.profiles.provider.provider_profiles import (
            apply_provider_profile,
        )

        kwargs.update(apply_provider_profile(name))
    except Exception as exc:  # noqa: BLE001 - a beta API; the model works without it
        print(f"agent: provider defaults not applied ({type(exc).__name__}: {exc})", file=sys.stderr)
    # The profile's app_title ("Deep Agents") would override OPENROUTER_APP_TITLE from .env.
    if name.startswith("openrouter:") and os.environ.get("OPENROUTER_APP_TITLE"):
        kwargs["app_title"] = os.environ["OPENROUTER_APP_TITLE"]
    kwargs.setdefault("max_tokens", MAX_TOKENS)
    try:
        return init_chat_model(name, **kwargs)
    except ImportError as exc:
        raise ModelConfigError(
            f"{name} needs a package that isn't installed ({exc}). Run: agent/.venv/bin/pip install -r agent/requirements.txt"
        ) from exc
    except ValueError as exc:
        raise ModelConfigError(f"REPRO_MODEL '{name}' was not accepted: {exc}") from exc
