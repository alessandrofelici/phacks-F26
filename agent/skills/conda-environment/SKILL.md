---
name: conda-environment
description: Set up a repository that ships a conda environment.yml (or environment.yaml) when conda may not be installed. Use when the README says "conda env create" or the only dependency file is a conda environment file.
---

# Conda environment files

## If conda or mamba is installed

Create the environment inside the workspace, not in the user's home:

```
conda env create -f repo/environment.yml -p ./.conda-env
./.conda-env/bin/python repo/script.py
```

Solving can take several minutes. That is a long command, so pass a longer `timeout` and
expect an approval request.

Exported environment files often list exact builds (`numpy=1.19.2=py38h54aff64_0`) that only
exist for one platform. When the solver says packages are not found, write a copy outside the
repository with the build strings removed (keep `name=version`), and try again. If that also
fails, drop the versions of the packages that fail and keep the rest.

## If conda is not installed

Don't install conda just for this. Most environment files are a Python version plus packages
that pip also has:

1. Read the file. Note the `python=` line, the `dependencies:` list and any nested `pip:` list.
2. Build a virtual environment with the closest Python available.
3. Write a `requirements.repro.txt` outside the repository from both lists. Conda names mostly
   match pip names; common differences are `pytorch` (pip: `torch`), `opencv` (`opencv-python`),
   `scikit-learn` (same), `pillow` (same), `tensorflow-gpu` (`tensorflow`).
4. Skip entries that aren't Python packages (`cudatoolkit`, `mkl`, `libgcc`, `ca-certificates`,
   `_libgcc_mutex`, anything starting with `lib`). If the code later needs one of them, that is
   an obstacle to report.

## What to record

Say that the environment was rebuilt with pip from the conda file, which entries were skipped,
and any version that had to change.
