"""Compare two runs of the same task, to show what memory changed. Standard library only.

    python -m harness.compare runs/<first> runs/<second>

Prints, side by side: fixes read from memory, fixes written, failed commands,
obstacles, approvals, time, tokens and the score.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .common import read_events, read_json
from .score import score_run


def summary(rdir: Path) -> dict:
    events = read_events(rdir)
    report = read_json(rdir / "report.json", {}) or {}
    score = score_run(rdir)
    usage = report.get("usage") or {}
    cmds = [e for e in events if e["type"] == "tool_call" and e["data"].get("tool") in ("execute", "run_experiment")]
    return {
        "task": report.get("task_id", "?"),
        "status": report.get("status", "?"),
        "memory read": next((e["data"].get("note", "") for e in events if e["type"] == "memory_read"), "-"),
        "fixes remembered": sum(1 for e in events if e["type"] == "memory_written"),
        "commands": len(cmds),
        "failed commands": sum(1 for e in cmds if not e["data"].get("ok")),
        "obstacles": len(report.get("obstacles") or []),
        "approvals": sum(1 for e in events if e["type"] == "approval_requested"),
        "wall seconds": usage.get("wall_seconds"),
        "tokens": usage.get("tokens"),
        "score": f"{score['correct']}/{score['total']}" if score else "no answer key",
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m harness.compare runs/<first> runs/<second>", file=sys.stderr)
        return 2
    a, b = summary(Path(args[0])), summary(Path(args[1]))
    if a["task"] != b["task"]:
        print(f"note: different tasks ({a['task']} vs {b['task']})")
    width = max(len(k) for k in a)
    print(f"{'':<{width}}  {'first run':<40}  second run")
    for key in a:
        print(f"{key:<{width}}  {str(a[key])[:40]:<40}  {str(b[key])[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
