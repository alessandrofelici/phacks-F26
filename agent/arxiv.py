"""arXiv-link mode: from a paper link to a verdict on each of its numbers.

    python -m agent.arxiv 2409.11363 [--repo https://github.com/o/r] [--claims 5] [--auto-approve]

1. Reads the paper from arXiv (metadata, and the full text from arXiv's HTML version).
2. Finds the code: `--repo`, else a GitHub link in the paper, else a GitHub search by title.
3. Picks up to N numeric claims that the released code should reproduce on a CPU, with a
   model call, and turns each into a question that does not reveal the claimed value.
4. Writes a normal task directory (`tasks/arxiv-<id>/`) and runs the agent on it, exactly
   like a CORE-Bench task. The claimed values go to `harness/answers/arxiv-<id>.json`, which
   the agent never sees, so the harness UI scores the run like any other.
5. Writes `verdicts.json` in the run directory: per claim, *reproduced*, *differs* or *not
   reproduced*, allowing for the claim's rounding and for percent vs fraction.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from agent.run import REPO_ROOT, ensure_dependencies, env_file, load_dotenv

TASKS = REPO_ROOT / "tasks"
ANSWERS = REPO_ROOT / "harness" / "answers"
MAX_REPO_MB = 500
MAX_PAPER_CHARS = 200_000
_UA = {"User-Agent": "repro-bot (research reproduction agent)"}

CLAIMS_PROMPT = """You are choosing which numeric results of a paper to check by running its released code.

Paper: {title}
Code: {repo}

Pick up to {n} numbers the paper reports that running THIS repository's code on a CPU, in under about 20
minutes each, should reproduce. The repository's README and file list are below: only pick a number
when the repository has the script, example or notebook that computes it (a released model, method
or baseline, and the data or a way to get it). Skip numbers whose experiment code isn't in the
repository, numbers that need training large models, GPUs or private data, and numbers that only
summarize other papers. Fewer, checkable numbers are better than many uncheckable ones.

For each, write `question` as an instruction to report the value, naming the exact setting so there is
only one right number, for example "Report the test accuracy of CULP with the AA predictor on the Wine
dataset (Table 3)." The question must NOT contain the reported value. Give `claimed` as the number
exactly as printed in the paper (no % sign), and `where` (table, figure or section).
Set `needs_figure` when the number can only be read off a plot.

Repository files (first {n_files}):
{files}

Repository README:
{readme}

Paper text:
{text}"""


# -- fetching -----------------------------------------------------------------------------


def arxiv_id(raw: str) -> str:
    """The bare identifier from an id or an abs/pdf/html URL (version suffix kept if given)."""
    match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)", raw)
    if not match:
        raise ValueError(f"'{raw}' doesn't look like an arXiv id or link")
    return match.group(1)


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout) as resp:
        return resp.read()


def metadata(aid: str) -> dict[str, Any]:
    xml = _get(f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(xml).find("a:entry", ns)
    if entry is None or entry.findtext("a:title", default="", namespaces=ns).strip() in ("", "Error"):
        raise ValueError(f"arXiv has no paper {aid}")
    clean = lambda s: " ".join((s or "").split())  # noqa: E731
    return {
        "id": aid,
        "title": clean(entry.findtext("a:title", namespaces=ns)),
        "abstract": clean(entry.findtext("a:summary", namespaces=ns)),
        "url": f"https://arxiv.org/abs/{aid}",
    }


class _TextOfHtml(HTMLParser):
    """Visible text of arXiv's HTML paper, with table cells kept apart."""

    SKIP = {"script", "style", "nav", "header", "footer", "math"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip += 1
        if tag == "a" and not self._skip:  # links in the page's header and footer aren't the paper's
            href = dict(attrs).get("href") or ""
            if href.startswith("http"):
                self.links.append(href)
        if tag in ("td", "th"):
            self.parts.append(" | ")
        if tag in ("p", "tr", "div", "section", "h1", "h2", "h3", "h4", "li", "figcaption", "br"):
            self.parts.append("\n")
        if tag == "math":  # keep the alt text of formulas, which holds numbers in tables
            alt = dict(attrs).get("alttext")
            if alt:
                self.parts.append(f" {alt} ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        joined = re.sub(r"[ \t]+", " ", joined)
        return re.sub(r"\n\s*\n+", "\n\n", joined).strip()


def paper_text(aid: str) -> tuple[str, list[str]]:
    """Full text and outbound links from arXiv's HTML version; empty when there is none."""
    try:
        html = _get(f"https://arxiv.org/html/{aid}").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - many older papers have no HTML version
        return "", []
    parser = _TextOfHtml()
    parser.feed(html)
    return parser.text()[:MAX_PAPER_CHARS], parser.links


# GitHub accounts linked from arXiv's HTML pages themselves, and GitHub's own pages.
_NOT_CODE_OWNERS = {"arxiv", "ar5iv", "brucemiller", "latexml", "features", "orgs", "topics", "sponsors", "login"}
_GITHUB = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def find_repo(meta: dict[str, Any], text: str, links: list[str]) -> tuple[str | None, str]:
    """The paper's code repository and how it was found."""
    sources = (
        ("a link in the paper", links),
        ("the paper text", [m.group(0) for m in _GITHUB.finditer(text)]),
        ("the abstract", [m.group(0) for m in _GITHUB.finditer(meta["abstract"])]),
    )
    for source, candidates in sources:
        for url in candidates:
            match = _GITHUB.match(url)
            if match and match.group(1).lower() not in _NOT_CODE_OWNERS:
                owner, repo = match.group(1), match.group(2).rstrip(".").removesuffix(".git")
                return f"https://github.com/{owner}/{repo}", f"found in {source}"
    try:  # Hugging Face's paper pages record the code repository for many recent papers
        hf = json.loads(_get(f"https://huggingface.co/api/papers/{urllib.parse.quote(meta['id'])}", timeout=20))
        if isinstance(hf, dict) and _GITHUB.match(str(hf.get("githubRepo") or "")):
            return str(hf["githubRepo"]).rstrip("/"), "listed on the paper's Hugging Face page"
    except Exception:  # noqa: BLE001,S110 - not every paper is there
        pass
    title = meta["title"]
    query = urllib.parse.quote(f'"{title[:200]}" in:readme,description')
    try:
        found = json.loads(_get(f"https://api.github.com/search/repositories?q={query}&per_page=5"))
    except Exception as exc:  # noqa: BLE001
        return None, f"no link in the paper and the GitHub search failed ({type(exc).__name__})"
    wanted = (title.lower(), meta["id"].split("v")[0])
    for item in found.get("items") or []:
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{item['full_name']}/readme",
                headers={**_UA, "Accept": "application/vnd.github.raw"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                readme = " ".join(resp.read().decode("utf-8", "replace").split()).lower()
        except Exception:  # noqa: BLE001
            continue
        if any(w in readme for w in wanted):
            return item["html_url"], "a GitHub repository whose README names the paper (check it is the authors' code)"
    return None, "no link in the paper, none on Hugging Face, and no GitHub README names the paper"


def clone(repo_url: str, dest: Path) -> None:
    """Shallow-clone the repository, refusing very large ones."""
    match = _GITHUB.match(repo_url)
    if match:
        try:
            info = json.loads(_get(f"https://api.github.com/repos/{match.group(1)}/{match.group(2)}"))
            if info.get("size", 0) / 1024 > MAX_REPO_MB:
                raise ValueError(f"{repo_url} is {info['size'] // 1024} MB, over the {MAX_REPO_MB} MB limit")
        except ValueError:
            raise
        except Exception:  # noqa: BLE001,S110 - size check is best effort
            pass
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", repo_url, str(dest)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git clone {repo_url} failed: {result.stderr.strip()[-300:]}")
    shutil.rmtree(dest / ".git", ignore_errors=True)


# -- claims -------------------------------------------------------------------------------


def repo_overview(repo_dir: Path, max_files: int = 300) -> tuple[list[str], str]:
    """The repository's file list and README text, for picking claims it can check."""
    files = sorted(str(p.relative_to(repo_dir)) for p in repo_dir.rglob("*") if p.is_file())[:max_files]
    readme = ""
    for name in ("README.md", "README.rst", "README.txt", "README", "readme.md"):
        if (repo_dir / name).is_file():
            readme = (repo_dir / name).read_text(encoding="utf-8", errors="replace")[:12_000]
            break
    return files, readme


def extract_claims(meta: dict[str, Any], repo: str, text: str, n: int, repo_dir: Path | None = None) -> list[dict[str, Any]]:
    """Ask the model for up to n checkable numeric claims."""
    from pydantic import BaseModel, Field

    from agent import models

    class Claim(BaseModel):
        question: str = Field(description="Instruction to report the value; must not contain it")
        claimed: float = Field(description="The value as printed in the paper, without % sign")
        where: str = Field(description="Table, figure or section the value is in")
        needs_figure: bool = Field(default=False, description="True if the value can only be read off a plot")

    class Claims(BaseModel):
        claims: list[Claim]

    model = models.make_model(models.chosen_model())
    files, readme = repo_overview(repo_dir) if repo_dir is not None else ([], "")
    prompt = CLAIMS_PROMPT.format(
        title=meta["title"], repo=repo, n=n, text=text or meta["abstract"],
        n_files=len(files), files="\n".join(files) or "(not available)", readme=readme or "(none)",
    )
    result = model.with_structured_output(Claims).invoke(prompt)
    claims = result.claims if isinstance(result, Claims) else Claims.model_validate(result).claims
    out = []
    for claim in claims[:n]:
        shown = f"{claim.claimed:g}"
        if shown in claim.question:  # the value must not leak into the question
            continue
        out.append(claim.model_dump())
    return out


# -- verdicts -----------------------------------------------------------------------------


def _decimals(value: float) -> int:
    text = f"{value:.10g}"
    return len(text.split(".")[1]) if "." in text and "e" not in text else 0


def verdict(claimed: float, answer: Any) -> dict[str, Any]:
    """Does the run's value agree with the paper's, allowing for rounding and percent scaling?"""
    if answer is None:
        return {"verdict": "not reproduced", "why": "the run produced no value"}
    try:
        value = float(answer)
    except (TypeError, ValueError):
        return {"verdict": "differs", "why": f"the run produced {answer!r}, not a number"}
    if math.isnan(value):
        return {"verdict": "differs", "why": "the run produced NaN"}
    tol = max(0.5 * 10 ** -_decimals(claimed), abs(claimed) * 0.01)
    for scale, how in ((1, ""), (100, " (as a percentage)"), (0.01, " (as a fraction)")):
        if abs(value * scale - claimed) <= tol:
            return {"verdict": "reproduced", "why": f"{value:g}{how} matches {claimed:g} within ±{tol:g}"}
    return {"verdict": "differs", "why": f"{value:g} vs claimed {claimed:g} (allowed ±{tol:g})"}


# -- command ------------------------------------------------------------------------------


def build_task(raw: str, repo: str | None, n: int, refresh: bool = False) -> Path:
    """Create tasks/arxiv-<id>/ and its answer key. Returns the task directory."""
    aid = arxiv_id(raw)
    task_id = "arxiv-" + re.sub(r"[^a-z0-9]+", "-", aid.lower()).strip("-")
    task_dir = TASKS / task_id
    if task_dir.exists() and not refresh:
        print(f"{task_id}: reusing {task_dir} (pass --refresh to rebuild)")
        return task_dir
    meta = metadata(aid)
    print(f"paper:  {meta['title']} ({meta['url']})")
    text, links = paper_text(aid)
    print(f"text:   {len(text):,} characters from arXiv's HTML version" if text else "text:   no HTML version; using the abstract only")
    how = "given with --repo"
    if repo is None:
        repo, how = find_repo(meta, text, links)
    if repo is None:
        raise ValueError(f"no code repository found: {how}. Pass --repo.")
    print(f"code:   {repo} ({how})")
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)
    clone(repo, task_dir / "repo")
    claims = extract_claims(meta, repo, text, n, task_dir / "repo")
    if not claims:
        shutil.rmtree(task_dir)
        raise ValueError("no numeric claims that this repository's code could reproduce on a CPU were found")
    for i, c in enumerate(claims, 1):
        print(f"claim {i}: {c['question']}  [paper: {c['claimed']:g}, {c['where']}]")
    paper = f"# {meta['title']}\n\n{meta['url']}\n\n## Abstract\n\n{meta['abstract']}\n\n{text}\n"
    (task_dir / "paper.md").write_text(paper, encoding="utf-8")
    questions = []
    for i, c in enumerate(claims, 1):
        q: dict[str, Any] = {"id": f"q{i}", "text": c["question"], "type": "number"}
        if c.get("needs_figure"):
            q["needs_figure"] = True
        questions.append(q)
    task = {
        "contract_version": 1,
        "task_id": task_id,
        "title": meta["title"],
        "source": "arxiv",
        "paper_url": meta["url"],
        "instructions": (
            "Find and run the code in this repository that produces each number asked about. Use the smallest "
            "configuration the paper used for that number (the README and the paper text in paper.md say how). "
            f"The code was {how}."
        ),
        "questions": questions,
        "limits": {"max_minutes": 45, "gpu": False, "network": True},
    }
    (task_dir / "task.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    key = {
        "task_id": task_id,
        "questions": {f"q{i}": {"type": "number", "values": [c["claimed"]]} for i, c in enumerate(claims, 1)},
        "claims": claims,
        "repo": repo,
        "repo_found": how,
    }
    ANSWERS.mkdir(parents=True, exist_ok=True)
    (ANSWERS / f"{task_id}.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    print(f"task:   {task_dir} ({len(questions)} questions); claimed values kept in harness/answers/, out of the agent's reach")
    return task_dir


def write_verdicts(task_dir: Path, run_dir: Path) -> list[dict[str, Any]]:
    key = json.loads((ANSWERS / f"{task_dir.name}.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    answers = {a["question_id"]: a for a in report.get("answers", [])}
    rows = []
    for i, claim in enumerate(key["claims"], 1):
        qid = f"q{i}"
        answer = answers.get(qid) or {}
        row = {"question_id": qid, "question": claim["question"], "where": claim["where"], "claimed": claim["claimed"],
               "reproduced_value": answer.get("value"), "evidence": answer.get("evidence"),
               **verdict(claim["claimed"], answer.get("value"))}
        rows.append(row)
    (run_dir / "verdicts.json").write_text(json.dumps({"paper": report.get("task_id"), "claims": rows}, indent=2) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="python -m agent.arxiv", description="Check an arXiv paper's numbers by running its code.")
    parser.add_argument("paper", help="arXiv id or link, for example 2409.11363 or https://arxiv.org/abs/2409.11363")
    parser.add_argument("--repo", help="the code's git URL, when the paper doesn't link it")
    parser.add_argument("--claims", type=int, default=5, help="how many numbers to check (default 5)")
    parser.add_argument("--run", type=Path, help="run directory (default runs/arxiv-<id>-<n>)")
    parser.add_argument("--auto-approve", action="store_true", help="approve every gated action")
    parser.add_argument("--refresh", action="store_true", help="rebuild the task even if it exists")
    parser.add_argument("--prepare-only", action="store_true", help="build the task directory and stop")
    args = parser.parse_args(argv)

    load_dotenv(env_file())
    ensure_dependencies(argv, module="agent.arxiv")
    try:
        task_dir = build_task(args.paper, args.repo, args.claims, args.refresh)
    except (ValueError, OSError) as exc:
        print(f"agent.arxiv: {exc}", file=sys.stderr)
        return 2
    if args.prepare_only:
        return 0
    run_dir = args.run
    if run_dir is None:
        n = 1
        while (REPO_ROOT / "runs" / f"{task_dir.name}-{n}").exists():
            n += 1
        run_dir = REPO_ROOT / "runs" / f"{task_dir.name}-{n}"

    from agent.rundir import RunDirError
    from agent.runner import ConfigError, run_task
    from agent.task import TaskError

    try:
        run_task(task_dir, run_dir, auto_approve=args.auto_approve)
    except (ConfigError, TaskError, RunDirError) as exc:
        print(f"agent.arxiv: {exc}", file=sys.stderr)
        return 2
    rows = write_verdicts(task_dir, run_dir)
    print("\nVerdicts:")
    for row in rows:
        print(f"  {row['question_id']} {row['verdict'].upper():<15} {row['why']}  — {row['question'][:90]}")
    counts = {v: sum(r["verdict"] == v for r in rows) for v in ("reproduced", "differs", "not reproduced")}
    print(f"\n{counts['reproduced']}/{len(rows)} claims reproduced, {counts['differs']} differ, {counts['not reproduced']} not reproduced. "
          f"Details: {run_dir}/verdicts.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
