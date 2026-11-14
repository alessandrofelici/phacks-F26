"""Turn CORE-Bench tasks into contract task directories. Standard library only.

    python -m harness.corebench list [--max-mb 5] [--language Python]
    python -m harness.corebench fetch <capsule_id> [<capsule_id> ...] [--level hard]

CORE-Bench (Siegel et al., Princeton, arXiv 2409.11363) publishes the task
list on GitHub and the code "capsules" on corebench.cs.princeton.edu. This
uses the open **train** split (45 tasks). The test split is encrypted on
purpose to keep it out of model training data, so it isn't used or stored.

For each capsule this writes:
    tasks/cb-<id>-<level>/task.json, repo/      (what the agent sees)
    harness/answers/cb-<id>-<level>.json        (what it must never see)

Levels follow the benchmark:
    easy    everything, including the authors' saved results
    medium  results removed; Dockerfile and REPRODUCING.md kept
    hard    results, Dockerfile, REPRODUCING.md and run scripts removed
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

from .common import ANSWERS, TASKS, read_json, write_json_atomic

DATASET_URL = "https://raw.githubusercontent.com/siegelz/core-bench/main/benchmark/dataset/core_train.json"
CAPSULE_URL = "https://corebench.cs.princeton.edu/capsules/{cid}.tar.gz"
CACHE = TASKS / ".cache"
LEVELS = ("easy", "medium", "hard")
LAYOUT_NOTE = (
    " The repo is a Code Ocean capsule: the code is in code/, the inputs are in data/, and the scripts may"
    " expect to run from /code, read from /data (or ../data) and write to /results (or ../results)."
)


def load_dataset(refresh: bool = False) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "core_train.json"
    if refresh or not path.exists():
        with urllib.request.urlopen(DATASET_URL, timeout=60) as resp:
            path.write_bytes(resp.read())
    return json.loads(path.read_text(encoding="utf-8"))


def capsule_size_mb(cid: str) -> float | None:
    req = urllib.request.Request(CAPSULE_URL.format(cid=cid), method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return int(resp.headers.get("Content-Length", 0)) / 1e6
    except Exception:
        return None


def normalize_id(raw: str) -> str:
    raw = raw.strip()
    return raw if raw.startswith("capsule-") else f"capsule-{raw}"


def question_type(value) -> str:
    if isinstance(value, list):
        return "list"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return "string"


def download(cid: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{cid}.tar.gz"
    if not path.exists():
        tmp = path.with_suffix(".part")
        with urllib.request.urlopen(CAPSULE_URL.format(cid=cid), timeout=120) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out)
        tmp.rename(path)
    return path


def extract(archive: Path, dest: Path) -> Path:
    """Extract with the 'data' filter (no absolute paths, links out, or devices)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")
    inner = [p for p in dest.iterdir() if p.is_dir()]
    return inner[0] if len(inner) == 1 else dest


def apply_level(capsule: Path, level: str) -> None:
    """Same removals as CORE-Bench's benchmark.py."""
    if level != "easy":
        shutil.rmtree(capsule / "results", ignore_errors=True)
        (capsule / "results").mkdir(exist_ok=True)
    if level != "medium":
        (capsule / "REPRODUCING.md").unlink(missing_ok=True)
        shutil.rmtree(capsule / "environment", ignore_errors=True)
        for name in ("run.sh", "run"):
            (capsule / "code" / name).unlink(missing_ok=True)
    for junk in capsule.rglob(".DS_Store"):
        junk.unlink()


def build_task(entry: dict, level: str) -> str:
    cid = entry["capsule_id"]
    task_id = f"cb-{cid.split('-', 1)[1]}-{level}"
    tdir = TASKS / task_id

    staging = CACHE / f"extract-{task_id}"
    capsule = extract(download(cid), staging)
    apply_level(capsule, level)
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    shutil.move(str(capsule), str(tdir / "repo"))
    shutil.rmtree(staging, ignore_errors=True)

    runs = entry["results"]
    questions, key = [], {}
    for i, (text, first) in enumerate(runs[0].items(), start=1):
        qid = f"q{i}"
        qtype = question_type(first)
        needs_figure = text.strip().lower().startswith("fig ")
        q = {"id": qid, "text": text[4:].strip() if needs_figure else text, "type": qtype}
        if needs_figure:
            q["needs_figure"] = True
        questions.append(q)
        key[qid] = {"type": qtype, "values": [r[text] for r in runs if text in r], "text": text}

    task = {
        "contract_version": 1,
        "task_id": task_id,
        "title": entry["capsule_title"],
        "source": "core-bench",
        "paper_url": entry.get("capsule_doi"),
        "instructions": entry["task_prompt"].strip() + LAYOUT_NOTE,
        "questions": questions,
        "limits": {"max_minutes": 30, "gpu": False, "network": True},
        "core_bench": {"capsule_id": cid, "level": level, "field": entry.get("field"), "language": entry.get("language")},
    }
    write_json_atomic(tdir / "task.json", task)
    write_json_atomic(ANSWERS / f"{task_id}.json", {"task_id": task_id, "questions": key})
    return task_id


def cmd_list(args) -> int:
    data = load_dataset(args.refresh)
    rows = []
    for entry in data:
        if args.language and entry["language"].lower() != args.language.lower():
            continue
        figs = sum(1 for q in entry["results"][0] if q.strip().lower().startswith("fig "))
        rows.append((entry, len(entry["results"][0]), figs))
    print(f"{'capsule':<17}{'MB':>8}  {'lang':<7}{'q':>2} {'fig':>3}  title")
    for entry, nq, figs in rows:
        size = capsule_size_mb(entry["capsule_id"]) if not args.no_size else None
        if args.max_mb is not None and (size is None or size > args.max_mb):
            continue
        size_txt = f"{size:8.2f}" if size is not None else "       ?"
        print(f"{entry['capsule_id']:<17}{size_txt}  {entry['language']:<7}{nq:>2} {figs:>3}  {entry['capsule_title'][:70]}")
    return 0


def cmd_fetch(args) -> int:
    data = {e["capsule_id"]: e for e in load_dataset(args.refresh)}
    status = 0
    for raw in args.capsule_ids:
        cid = normalize_id(raw)
        if cid not in data:
            print(f"{cid}: not in the CORE-Bench train split", file=sys.stderr)
            status = 1
            continue
        task_id = build_task(data[cid], args.level)
        print(f"{task_id}: {len(data[cid]['results'][0])} question(s) -> tasks/{task_id}")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CORE-Bench (train split) -> task directories.")
    parser.add_argument("--refresh", action="store_true", help="re-download the task list")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="show tasks and capsule sizes")
    p_list.add_argument("--max-mb", type=float, default=None)
    p_list.add_argument("--language", default=None)
    p_list.add_argument("--no-size", action="store_true", help="skip the size lookup (faster)")
    p_fetch = sub.add_parser("fetch", help="download capsules and write task directories")
    p_fetch.add_argument("capsule_ids", nargs="+")
    p_fetch.add_argument("--level", choices=LEVELS, default="hard")
    args = parser.parse_args(argv)
    return cmd_list(args) if args.cmd == "list" else cmd_fetch(args)


if __name__ == "__main__":
    sys.exit(main())
