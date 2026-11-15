"""Project a long run's total time from the first minutes of its output.

Used by the ``probe_runtime`` tool: the paper's command runs for a short, capped time, and
the progress lines it printed (``Epoch 3/150``, a tqdm or Keras progress bar, ``tree 40 of
1000``) give the share of the work done. Standard library only.

The projection includes start-up time (imports, data loading) in the measured part, so it
leans high, which is the safe side for deciding whether a run fits.
"""

from __future__ import annotations

import re
from typing import Any

_EPOCH = re.compile(r"(?i)\bepoch\b\s*[:#=]?\s*(\d+)\s*(?:/|of)\s*(\d+)")
_TQDM = re.compile(r"(\d+)/(\d+)\s*\[(\d+(?::\d+){1,2})<(\d+(?::\d+){1,2}|\?)")
_BAR = re.compile(r"^\s*(\d+)/(\d+)\s*\[[=>.\-#\s]*\]")  # Keras: " 12/250 [=>....] - ETA: ..."
_STEP = re.compile(
    r"(?i)\b(iteration|iter|step|fold|trees?|rep|replicate|repetition|simulation|sim|round|permutation|"
    r"bootstrap|sample|chain|run)\b\s*[:#=]?\s*(\d+)\s*(?:/|of|out of)\s*(\d+)"
)


def _clock(text: str) -> float | None:
    """Seconds in a tqdm clock such as 01:23 or 1:02:03."""
    try:
        parts = [int(p) for p in text.split(":")]
    except ValueError:
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return float(seconds)


def _lines(output: str) -> list[str]:
    # Progress bars rewrite their line with \r; each rewrite counts as a line here.
    return [line for line in re.split(r"[\r\n]+", output or "") if line.strip()]


def project(output: str, elapsed_s: float) -> dict[str, Any] | None:
    """Estimate the full run from ``elapsed_s`` seconds of ``output``.

    Returns ``{"progress", "line", "projected_minutes"}`` (``projected_minutes`` may be None
    when the progress seen is too early to extrapolate), or None when no progress line was found.
    """
    lines = _lines(output)
    if elapsed_s <= 0 or not lines:
        return None

    # 1. Epochs, refined by the progress bar inside the current epoch when there is one.
    for i in range(len(lines) - 1, -1, -1):
        match = _EPOCH.search(lines[i])
        if not match:
            continue
        current, total = int(match.group(1)), int(match.group(2))
        if total <= 0 or current > total:
            break
        inner = None
        for later in lines[i + 1:]:
            bar = _TQDM.search(later) or _BAR.search(later)
            if bar and int(bar.group(2)) > 0 and int(bar.group(1)) <= int(bar.group(2)):
                inner = int(bar.group(1)) / int(bar.group(2))
        if inner is not None:
            done = (current - 1) + inner
        else:
            # "Epoch k/N" is printed at the start of epoch k by most libraries: k - 1 are done.
            done = current - 0.5 if current > 1 else 0.0
        result = {"progress": f"epoch {current} of {total}", "line": lines[i].strip()[:200]}
        result["projected_minutes"] = round(elapsed_s * total / done / 60, 1) if done > 0 else None
        return result

    # 2. A tqdm bar states its own remaining time.
    for line in reversed(lines):
        match = _TQDM.search(line)
        if not match:
            continue
        current, total = int(match.group(1)), int(match.group(2))
        remaining = _clock(match.group(4)) if match.group(4) != "?" else None
        result = {"progress": f"{current} of {total} steps", "line": line.strip()[:200]}
        if remaining is not None:
            result["projected_minutes"] = round((elapsed_s + remaining) / 60, 1)
        elif current > 0 and total > 0:
            result["projected_minutes"] = round(elapsed_s * total / current / 60, 1)
        else:
            result["projected_minutes"] = None
        return result

    # 3. Any "<unit> k of N" counter.
    for line in reversed(lines):
        match = _STEP.search(line)
        if not match:
            continue
        unit, current, total = match.group(1).lower(), int(match.group(2)), int(match.group(3))
        if total <= 0 or current > total:
            continue
        done = current - 0.5 if current > 1 else 0.0
        result = {"progress": f"{unit} {current} of {total}", "line": line.strip()[:200]}
        result["projected_minutes"] = round(elapsed_s * total / done / 60, 1) if done > 0 else None
        return result
    return None


def describe(output: str, elapsed_s: float, finished: bool, exit_code: int | None) -> str:
    """The probe's result in a few sentences for the model."""
    if finished and exit_code == 0:
        return (
            f"The command finished in {elapsed_s:.0f} s with exit code 0: the full run fits, no scaling needed. "
            "Its output is saved under /logs, so answers can be taken from it."
        )
    if finished:
        return (
            f"The command stopped after {elapsed_s:.0f} s with exit code {exit_code}, before the probe's cap: it "
            "failed. Fix the error before estimating the runtime."
        )
    estimate = project(output, elapsed_s)
    if estimate is None:
        return (
            f"The probe was stopped after {elapsed_s:.0f} s and printed no progress line (epoch, step or "
            "progress bar). Estimate from the code instead: time per loop × number of loops, or probe a "
            "command that prints progress (for example with verbose output on)."
        )
    if estimate["projected_minutes"] is None:
        return (
            f"The probe was stopped after {elapsed_s:.0f} s at {estimate['progress']} ('{estimate['line']}'), "
            "too early to extrapolate. Probe again for longer (up to 180 s)."
        )
    return (
        f"The probe was stopped after {elapsed_s:.0f} s at {estimate['progress']} ('{estimate['line']}'). "
        f"At that pace the full run takes about {estimate['projected_minutes']:g} min. This includes start-up "
        "time, so it leans high."
    )
