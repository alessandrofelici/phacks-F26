---
name: python-old-pins
description: Install a Python repository whose requirements pin versions that no longer install (old numpy, scipy, pandas, torch, tensorflow). Use when pip fails on a pinned version or tries to build a package from source.
---

# Old Python pins

Papers pin the versions the authors had. A few years later those versions have no wheel for
the current Python, so pip either reports no matching distribution or downloads the source
and fails to compile it. Both mean the same thing.

## Order of attempts

1. **Relax the pin, keep the major version.** Copy the requirements into a new file outside
   the repository (for example `requirements.repro.txt`) and replace `==` with a lower bound
   on the failing package only. Leave every pin that installs. Never edit the original file.
2. **If the code needs the old API**, use an older Python instead of patching code. Check
   what is installed (`ls /usr/bin/python3*`, `uv python list` if `uv` exists) and build the
   virtual environment with the newest interpreter that still has wheels for the pin.
3. **Only then** consider a newer major version of the package, and expect API errors when
   the code runs. Report those; don't patch the paper's code to hide them.

## Rough compatibility

| Package | Last version line | Needs Python at most |
|---|---|---|
| numpy 1.19 to 1.21 | 1.21 | 3.9 or 3.10 |
| numpy 1.x | 1.26 | 3.12 |
| scipy 1.5 to 1.7 | 1.7 | 3.9 or 3.10 |
| pandas 1.x | 1.5 | 3.11 |
| tensorflow 1.x | 1.15 | 3.7 |
| torch 1.x | 1.13 | 3.10 or 3.11 |

Treat the table as a starting guess and trust what pip prints.

## Checks

- `pip install --dry-run -r file` shows what would be installed without doing it.
- After installing, import the package and print its version in one command, so the log shows
  what the run really used.
- Numbers can shift slightly between major versions of numpy or a BLAS library. If a result is
  close but not equal to the paper's, say which versions were used.

## What to record

One obstacle per failed pin: the package and version, pip's last error line, and the version
that was installed instead.
