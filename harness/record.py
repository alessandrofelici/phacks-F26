"""Save a finished real run as the demo's fallback recording. Standard library only.

    python -m harness.record runs/<run_id>

Copies the run (events, report, logs, figures, approval requests) to
harness/recordings/<task_id>/. Demo replay then plays it back for that task
without a model, with the approval asked for real.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .common import ROOT, read_json

RECORDINGS = ROOT / "harness" / "recordings"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    src = Path(args[0])
    report = read_json(src / "report.json")
    if not isinstance(report, dict) or report.get("status") != "completed":
        print(f"{src}: only a completed run can be a recording", file=sys.stderr)
        return 2
    dest = RECORDINGS / report["task_id"]
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in ("events.jsonl", "report.json"):
        shutil.copy2(src / name, dest / name)
    for sub in ("logs", "figures"):
        if (src / sub).is_dir():
            shutil.copytree(src / sub, dest / sub)
    (dest / "approvals").mkdir()
    for req in (src / "approvals").glob("*.request.json"):
        shutil.copy2(req, dest / "approvals" / req.name)
    print(f"saved {src} as the recording for {report['task_id']} ({dest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
