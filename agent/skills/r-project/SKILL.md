---
name: r-project
description: Run a repository written in R (.R or .Rmd files, renv.lock, DESCRIPTION, install.packages calls). Use when the paper's code is R or the task mentions Rscript or knitr.
---

# R projects

## First look

- `Rscript --version` tells you whether R is installed. If it isn't, that is an obstacle
  (stage "env"): report it; installing R needs system packages this workspace may not allow.
- Find what the code needs: `renv.lock`, a `DESCRIPTION` file, an `environment/Dockerfile`
  (Code Ocean), or `library(...)` and `require(...)` calls. One command lists them:
  `grep -rhoE "(library|require|p_load)\(['\"]?[A-Za-z0-9.]+" repo --include=*.R --include=*.Rmd | sort -u`

## Installing packages

In this sandbox R is current, the common packages (tidyverse, rmarkdown, knitr, lme4,
data.table, remotes, devtools, BiocManager, car, psych, broom, here) are already installed, and
`install.packages` gets **prebuilt binaries** from Posit Package Manager, so the rest take
seconds. Install everything missing in one command:

```
Rscript -e 'install.packages(c("corrplot","pastecs"))'
```

**Don't set `repos` to `cloud.r-project.org` or the URL in the paper's Dockerfile**: that
switches to source packages, which compile for minutes and often fail. Microsoft's MRAN
snapshots (`mran.microsoft.com/snapshot/DATE`, common in Code Ocean Dockerfiles) are gone;
the same date on Posit works and serves binaries:
`https://packagemanager.posit.co/cran/__linux__/noble/DATE`.

- Old code that breaks on current packages: install from a dated snapshot of CRAN that
  matches the paper's era (Dockerfile dates, file dates, `R.version` hints), for example
  `options(repos=c(CRAN="https://packagemanager.posit.co/cran/__linux__/noble/2021-06-01"))`
  before `install.packages`. Dated snapshots also serve binaries.
- A single old version: `remotes::install_version("pkg", "1.2.3")` (install `remotes` first).
- Bioconductor packages: `install.packages("BiocManager"); BiocManager::install("limma")`.
- A package that fails to compile names a missing system library in its last lines (for
  example `libgsl`). Record that as the obstacle; most common ones are already installed.
- With `renv.lock`, `renv::restore()` reproduces exact versions but often fails on old ones.
  A dated snapshot with the same packages is the usual fallback; say so in the report.

## Running

- Scripts: `Rscript repo/analysis.R`, from the directory the script expects. Many scripts
  call `setwd()` with the author's path or read data by relative path; run from the
  repository root first, then from the script's folder. Code Ocean scripts expect `/data`
  and `/results` (see the code-ocean-capsule skill).
- R Markdown: `Rscript -e 'rmarkdown::render("repo/paper.Rmd", output_dir="/work/out")'`
  (install `rmarkdown` and `knitr`; PDF output also needs LaTeX, so prefer
  `output_format="html_document"`). The numbers are in the rendered file: print the value
  with a command (for example `grep` on the HTML, or run the chunk with `Rscript -e`), so
  the answer's quote comes from command output, without editing the original file.
- Figures: R writes PNG with `png("plot.png")` ... `dev.off()`; ggplot2 with `ggsave`.
  Read a figure with `look_at_figure`.
- `set.seed()` in the script is what makes the numbers repeat. If there is none, results can
  differ between runs: report that along with the value.
