"""Model selection from the environment. Needs the agent's dependencies only for make_model.

    agent/.venv/bin/python -m unittest discover -s agent/tests -t .
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from agent import models

REPO_ROOT = Path(__file__).resolve().parents[2]
HAVE_DEPS = importlib.util.find_spec("langchain_openrouter") is not None
CLEAN = {name: "" for name in ("REPRO_MODEL", "REPRO_SUBAGENT_MODEL", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")}


class ChooseModel(unittest.TestCase):
    def choose(self, **env: str) -> str:
        with mock.patch.dict(os.environ, {**CLEAN, **env}):
            return models.chosen_model()

    def test_the_model_follows_the_key_that_is_set(self) -> None:
        self.assertEqual(self.choose(OPENROUTER_API_KEY="k"), "openrouter:anthropic/claude-opus-5.5")
        self.assertEqual(self.choose(ANTHROPIC_API_KEY="k"), "anthropic:claude-opus-5-5")
        self.assertEqual(self.choose(OPENROUTER_API_KEY="k", ANTHROPIC_API_KEY="k"), "openrouter:anthropic/claude-opus-5.5")
        self.assertEqual(self.choose(), "openrouter:anthropic/claude-opus-5.5")

    def test_repro_model_wins(self) -> None:
        chosen = self.choose(OPENROUTER_API_KEY="k", REPRO_MODEL="openrouter:anthropic/claude-sonnet-5.5")
        self.assertEqual(chosen, "openrouter:anthropic/claude-sonnet-5.5")

    def test_missing_key_names_the_variable(self) -> None:
        with mock.patch.dict(os.environ, CLEAN):
            self.assertEqual(models.missing_key("openrouter:anthropic/claude-opus-5.5"), "OPENROUTER_API_KEY")
            with self.assertRaises(models.ModelConfigError) as caught:
                models.make_model("openrouter:anthropic/claude-opus-5.5")
            self.assertIn("OPENROUTER_API_KEY", str(caught.exception))
            with self.assertRaises(models.ModelConfigError):
                models.make_model("claude-opus-5.5")  # no provider prefix

    @unittest.skipUnless(HAVE_DEPS, "needs langchain-openrouter")
    def test_openrouter_model_is_built_from_the_key(self) -> None:
        with mock.patch.dict(os.environ, {**CLEAN, "OPENROUTER_API_KEY": "sk-or-test"}):
            model = models.make_model("openrouter:anthropic/claude-opus-5.5")
        self.assertEqual(type(model).__name__, "ChatOpenRouter")
        self.assertEqual(model.model_name, "anthropic/claude-opus-5.5")
        self.assertEqual(model.max_tokens, models.MAX_TOKENS)

    def test_check_command_reports_a_missing_key(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agent.check"],
            cwd=REPO_ROOT,
            env={**os.environ, **CLEAN, "REPRO_MODEL": "openrouter:anthropic/claude-opus-5.5"},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if (REPO_ROOT / ".env").is_file() and "MISSING" not in result.stdout:
            self.skipTest("a real key is configured in .env")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("OPENROUTER_API_KEY", result.stdout)
        self.assertIn("not ready", result.stdout)


if __name__ == "__main__":
    unittest.main()
