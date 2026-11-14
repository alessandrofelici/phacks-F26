"""The changed-source check ignores caches that running the code rewrites."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

HAVE_DEPS = importlib.util.find_spec("deepagents") is not None


@unittest.skipUnless(HAVE_DEPS, "needs the agent's dependencies (agent/.venv)")
class Snapshot(unittest.TestCase):
    def test_rewritten_bytecode_is_not_a_source_change(self) -> None:
        from agent.sandbox import changed_files, snapshot

        repo = Path(tempfile.mkdtemp())
        try:
            (repo / "code" / "__pycache__").mkdir(parents=True)
            (repo / "code" / "model.py").write_text("x = 1\n", encoding="utf-8")
            (repo / "code" / "__pycache__" / "model.cpython-39.pyc").write_bytes(b"old")
            before = snapshot(repo)
            (repo / "code" / "__pycache__" / "model.cpython-39.pyc").write_bytes(b"new")
            self.assertEqual(changed_files(repo, before), [])
            (repo / "code" / "model.py").write_text("x = 2\n", encoding="utf-8")
            self.assertEqual(changed_files(repo, before), [{"path": "repo/code/model.py", "change": "modified"}])
        finally:
            shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
