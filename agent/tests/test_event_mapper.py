"""EventMapper: the agent's update stream becomes contract events, once per model turn."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

HAVE_DEPS = importlib.util.find_spec("deepagents") is not None


@unittest.skipUnless(HAVE_DEPS, "needs the agent's dependencies (agent/.venv)")
class RepeatedMessages(unittest.TestCase):
    def setUp(self) -> None:
        from agent.deep import EventMapper
        from agent.rundir import RunWriter

        self.tmp = Path(tempfile.mkdtemp())
        self.writer = RunWriter(self.tmp / "run", auto_approve=True, approval_timeout_s=1)
        unused_backend: Any = None  # only tool results read the backend; these tests send none
        self.mapper = EventMapper(self.writer, backend=unused_backend)

    def tearDown(self) -> None:
        self.writer.close()

    def events(self) -> list[dict]:
        lines = (self.tmp / "run" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def test_a_turn_resent_after_an_approval_counts_once(self) -> None:
        from langchain_core.messages import AIMessage

        turn = AIMessage(
            content="",
            id="msg-1",
            tool_calls=[{"name": "task", "args": {"subagent_type": "runner", "description": "run it"}, "id": "c1"}],
            usage_metadata={"input_tokens": 900, "output_tokens": 100, "total_tokens": 1000},
        )
        # The model node emits the turn; HumanInTheLoopMiddleware.after_model emits it again
        # once the approval is resolved.
        self.mapper.handle((), {"model": {"messages": [turn]}})
        self.mapper.handle((), {"HumanInTheLoopMiddleware.after_model": {"messages": [turn]}})

        self.assertEqual(self.mapper.tokens, 1000)
        started = [e for e in self.events() if e["type"] == "subagent_started"]
        self.assertEqual(len(started), 1)

    def test_turns_without_ids_are_still_counted(self) -> None:
        from langchain_core.messages import AIMessage

        for _ in range(2):
            turn = AIMessage(content="ok", usage_metadata={"input_tokens": 5, "output_tokens": 5, "total_tokens": 10})
            self.mapper.handle((), {"model": {"messages": [turn]}})
        self.assertEqual(self.mapper.tokens, 20)


if __name__ == "__main__":
    unittest.main()
