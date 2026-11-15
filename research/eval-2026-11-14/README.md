# Evaluation of the 2026-11-14 CORE-Bench runs

Results of the autonomous run described in `research/autonomous-run-2026-11-14.md`: two cycles on 20 medium-level CORE-Bench papers, Haiku 5.5 via OpenRouter, repo at 9d1a400.

Open `index.html` in a browser for the full report: metrics, the 7 figures, a per-paper table, root causes of failed runs and fixes ranked by benefit for cost.

## Headline numbers

- 14 of 20 papers reproduced in at least one run (95% CI 48–85%).
- The 11 papers that ran to the end in both cycles: 4 reproduced in cycle 1, 8 in cycle 2 (mostly the new sandbox image fixing R).
- 52 of 54 recorded answers were right. Failed runs left questions blank (23 of 26) instead of guessing.
- 9 cycle 2 papers were not run: the OpenRouter credit ran out.
- Runs that ended at the 30-minute limit used 61% of all tokens.

## Files

| Path | What it is |
|---|---|
| `index.html` | The report page (light and dark) |
| `images/` | 7 figures, each as `-light.png` and `-dark.png` |
| `data/runs.json` | One row per run: outcome, model, tools, approvals, obstacles |
| `data/questions.json` | One row per scored question: answered, correct, confidence |
| `data/metrics.json` | Everything the report and the figures are drawn from |
| `scripts/` | `build_dataset.py` → `metrics.py` → `render.py` (matplotlib) |

## Answer keys

Nothing here contains expected values or anything they can be worked out from: per-question rows keep only right/wrong, not the error size. `build_dataset.py` reads the keys through `harness/score.py`, so whoever works on `agent/` should not run it.

## Caveats

Only Haiku 5.5 at medium level was tested on CORE-Bench, most papers ran once or twice, and the root cause of each failed run was assigned by hand (`CAUSE` in `scripts/metrics.py`). The fix-priority figure is an estimate, not a measurement.
