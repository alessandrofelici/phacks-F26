---
name: r-project
description: Run a repository written in R (.R or .Rmd files, renv.lock, DESCRIPTION, install.packages calls). Use when the paper's code is R or the task mentions Rscript or knitr.
---

# R projects

## First look

- `Rscript --version` tells you whether R is installed. If it isn't, that is an obstacle
  (stage "env"): report it; installing R needs system packages this workspace may not allow.
- Find what the code needs: `renv.lock`, a `DESCRIPTION` file, or `library(...)` and
  `require(...)` calls. One command lists them:
  `grep -rhoE "(library|require)\(['\"]?[A-Za-z0-9.]+" repo --include=*.R --include=*.Rmd | sort -u`

## Installing packages

Install into a library inside the workspace so nothing touches the system:

```
mkdir -p .rlib
R_LIBS_USER=$PWD/.rlib Rscript -e 'install.packages(c("dplyr","ggplot2"), repos="https://cloud.r-project.org", lib=Sys.getenv("R_LIBS_USER"))'
```

- Packages compile from source on Linux, so installs are slow. Ask for a longer `timeout`.
- A package that fails to compile usually names a missing system library in its last lines
  (for example `libcurl`, `libxml2`). Record that as the obstacle.
- With `renv.lock`, `renv::restore()` reproduces exact versions but often fails on old ones.
  Installing current versions of the same packages is the usual fallback; say so in the report.

## Running

- Scripts: `R_LIBS_USER=$PWD/.rlib Rscript repo/analysis.R`, from the directory the script
  expects. Many scripts call `setwd()` with the author's path or read data by relative path;
  run from the repository root first, then from the script's folder.
- R Markdown: `Rscript -e 'rmarkdown::render("repo/paper.Rmd", output_format="html_document")'`.
  The numbers are in the rendered file, so the answer's evidence has to come from output the
  command prints. Add a step that prints the value, for example by running the relevant chunk
  with `Rscript -e`, without editing the original file.
- `set.seed()` in the script is what makes the numbers repeat. If there is none, results can
  differ between runs: report that along with the value.
