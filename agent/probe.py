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

    Returns ``{"progress", "line", "projected_minutes", "lower_bound"}`` (``projected_minutes`` is None
    when the progress seen is too early to extrapolate), or None when no progress line was found.
    ``lower_bound`` is True when the counter may be one of several loops (a bare progress bar, a
    step counter): the run takes at least that long, maybe much longer.
    """
    lines = _lines(output)
    if elapsed_s <= 0 or not lines:
        return None

    # 1. Epochs with a total, refined by the progress bar inside the current epoch when there is one.
    hits = [(i, int(m.group(1)), int(m.group(2))) for i, line in enumerate(lines) for m in [_EPOCH.search(line)] if m]
    if hits:
        zero_based = min(current for _, current, _ in hits) == 0  # "Epoch 0/150" counts from zero
        i, current, total = hits[-1]
        if 0 < total and current <= total:
            inner = None
            for later in lines[i + 1:]:
                bar = _TQDM.search(later) or _BAR.search(later)
                if bar and int(bar.group(2)) > 0 and int(bar.group(1)) <= int(bar.group(2)):
                    inner = int(bar.group(1)) / int(bar.group(2))
            finished = current if zero_based else current - 1  # epochs done before the current one
            if inner is not None:
                done = finished + inner
            else:
                # The epoch line is usually printed when the epoch starts: count it as half done.
                done = finished + 0.5 if finished >= 1 else 0.0
            projected = round(elapsed_s * total / done / 60, 1) if done > 0 else None
            return {"progress": f"epoch {current} of {total}", "line": lines[i].strip()[:200],
                    "projected_minutes": projected, "lower_bound": False}

    # 2. An unfinished tqdm bar states its own remaining time. It may be one of several loops (one epoch,
    #    one data split), so it only gives a lower bound. A finished bar says nothing about what is left.
    for line in reversed(lines):
        match = _TQDM.search(line)
        if not match:
            continue
        current, total = int(match.group(1)), int(match.group(2))
        if total <= 0 or current >= total:
            continue
        remaining = _clock(match.group(4)) if match.group(4) != "?" else None
        if remaining is not None:
            projected = round((elapsed_s + remaining) / 60, 1)
        else:
            projected = round(elapsed_s * total / current / 60, 1) if current > 0 else None
        return {"progress": f"{current} of {total} steps", "line": line.strip()[:200],
                "projected_minutes": projected, "lower_bound": True}

    # 3. Any "<unit> k of N" counter: also a lower bound, it may be an inner loop or a pipeline step.
    for line in reversed(lines):
        match = _STEP.search(line)
        if not match:
            continue
        unit, current, total = match.group(1).lower(), int(match.group(2)), int(match.group(3))
        if total <= 0 or current > total:
            continue
        done = current - 0.5 if current > 1 else 0.0
        projected = round(elapsed_s * total / done / 60, 1) if done > 0 else None
        return {"progress": f"{unit} {current} of {total}", "line": line.strip()[:200],
                "projected_minutes": projected, "lower_bound": True}
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
    if estimate.get("lower_bound"):
        return (
            f"The probe was stopped after {elapsed_s:.0f} s at {estimate['progress']} ('{estimate['line']}'). "
            f"That counter alone would take about {estimate['projected_minutes']:g} min, but it may be one of "
            "several loops (one epoch, one data split, one pipeline step): treat it as a lower bound and check "
            "the code for outer loops before trusting it."
        )
    return (
        f"The probe was stopped after {elapsed_s:.0f} s at {estimate['progress']} ('{estimate['line']}'). "
        f"At that pace the full run takes about {estimate['projected_minutes']:g} min. This includes start-up "
        "time, so it leans high."
    )
