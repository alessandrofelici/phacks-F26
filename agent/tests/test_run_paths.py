"""A linked git worktree borrows the main checkout's .env (standard library only)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent import run


@unittest.skipUnless(shutil.which("git"), "needs git")
class WorktreeEnv(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.main = self.tmp / "main"
        self.main.mkdir()
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "init", "-q"], cwd=self.main, check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "start"], cwd=self.main, check=True)
        self.worktree = self.tmp / "wt"
        subprocess.run([*git, "worktree", "add", "-q", "--detach", str(self.worktree)], cwd=self.main, check=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_main_checkout_is_found_from_a_worktree(self) -> None:
        self.assertEqual(run.main_checkout(self.worktree), self.main.resolve())
        self.assertIsNone(run.main_checkout(self.main))

    def test_a_worktree_without_env_uses_the_main_one(self) -> None:
        (self.main / ".env").write_text("X=1\n", encoding="utf-8")
        with mock.patch.object(run, "REPO_ROOT", self.worktree):
            self.assertEqual(run.env_file(), self.main.resolve() / ".env")
            (self.worktree / ".env").write_text("X=2\n", encoding="utf-8")
            self.assertEqual(run.env_file(), self.worktree / ".env")  # its own .env wins


if __name__ == "__main__":
    unittest.main()
