# Scoreboard

One row per batch run (`python -m harness.batch`). A task counts as reproduced only when every answer matches.

| When (UTC) | Label | Agent | Tasks reproduced | Answers correct | Not finished | Batch |
|---|---|---|---|---|---|---|
| 2026-11-14T14:26:31Z | started from the UI | real | 1/1 | 2/2 | 0 | b-20261114-142611 |
| 2026-11-14T17:43:51Z | cycle 1: Haiku 5.5, medium, full sandbox image (1 crash was a harness podman timeout, since fixed) | real | 10/21 | 25/43 | 9 | b-20261114-160408 |
| 2026-11-14T18:46:53Z | cycle 2: Haiku 5.5, medium, image :2, figure tool, R and prompt fixes. 9 tasks stopped when the OpenRouter account ran out of credit; of the 11 that ran, 9 reproduced (cycle 1: 5 of those 11) | real | 9/21 | 19/45 | 12 | b-20261114-174449 |

## Since plan-first runs

Verifiable within budget: the paper was too big for the limits, and a scaled-down run projected its numbers within ±10%. It never counts as reproduced. Not verifiable within budget: too big, and no scaled run could show it. Neither says the paper is wrong.

| When (UTC) | Label | Agent | Tasks reproduced | Verifiable within budget | Not verifiable within budget | Answers correct | Not finished | Batch |
|---|---|---|---|---|---|---|---|---|
| 2026-11-15T04:51:32Z | plan-first run 1 (8b6a88a) | real | 9/13 | 3 | 1 | 24/30 | 0 | b-20261115-040847 |
| 2026-11-15T05:18:17Z | plan-first run 2 (8b6a88a) | real | 3/6 | 1 | 2 | 12/17 | 1 | b-20261115-045206 |
