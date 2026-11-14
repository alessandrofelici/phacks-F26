---
name: code-ocean-capsule
description: Run a Code Ocean capsule (CORE-Bench task) - a repository with code/, data/, results/ and often environment/Dockerfile and REPRODUCING.md. Use when the repository has that layout or the scripts read /data or write /results.
---

# Code Ocean capsules

Code Ocean ran each capsule in a container built from `environment/Dockerfile`, with the
code at `/code`, the inputs at `/data` and outputs written to `/results`, starting from
`code/run` or `code/run.sh`. Recreate that, and most "file not found" errors disappear.

## 1. Recreate the paths (in the sandbox shell, which runs as root)

```
ln -sfn /work/repo/code /code
ln -sfn /work/repo/data /data          # only if repo/data exists
mkdir -p /work/repo/results && ln -sfn /work/repo/results /results
```

`/results` then lands inside the workspace, so file tools can read it at `/repo/results`.
New files there are outputs, not changes to the paper's files.

## 2. Recreate the environment from the Dockerfile

`environment/Dockerfile` (kept at the medium level, removed at hard) names the base image
and the exact packages. Read it before installing anything:

- `FROM registry.codeocean.com/codeocean/miniconda3:4.x-python3.6-...` or `python3.6`
  in the tag: the code expects that Python. Make it with conda, inside the workspace:
  `conda create -y -p ./.py36 python=3.6` then `./.py36/bin/pip install ...`.
  For Python 3.8 and newer, `uv venv -p 3.8 .venv` is faster.
- `pip install -U --no-cache-dir name==version ...` lines: install those versions first.
  Old versions often have wheels only for the old Python, which is why matching the
  Python matters more than anything else.
- `conda install -y name==version` lines: use `conda install -p ./.py36 -c conda-forge ...`.
- `apt-get install` lines: most build tools are already in this sandbox; skip the rest
  unless an error asks for them.
- R capsules: the Dockerfile often pins an MRAN snapshot or `cloud.r-project.org`. Don't copy
  that repository setting; follow the r-project skill (binaries from Posit, dated snapshot if
  old versions are needed).
- Long installs: start them with `start_background_run` and wait with
  `check_background_run(run_id, wait_seconds=300)`, not with `sleep` commands.

Without a Dockerfile (hard level), infer the era from the imports and any version hints
(README, metadata/metadata.yml, file dates), and start from the python-old-pins skill.

## 3. Run what the task says

The task's instructions name the scripts. `code/run` or `code/run.sh` (if present) shows
the order and arguments the authors used. Run from `/code` (`cd /code && ...`) when the
scripts use relative paths like `../data`.

## 4. Find the answers

Results are printed or written under `/results` (figures, CSV, text). Every answer must come
from what this run printed or wrote, never from the paper or a saved copy.
