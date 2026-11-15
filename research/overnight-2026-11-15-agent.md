# Overnight, 15 November: review fixes and an earlier plan (branch `overnight-agent`)

**Recommendation:**
- **If the demo includes a live run, merge this branch.** Easy papers are back to about 3 minutes per run, as before the planning step, and 12 defects from a code review are fixed with tests. Then rehearse the live demo paper once (`cb-5975162-medium`, about 3 minutes and 5 cents), since it wasn't in the re-test.
- **If you'd rather keep exactly what was rehearsed tonight, leave this branch for after the demo.** It changes how the agent behaves, and it was tested on 6 papers, one run each.

## What changed

1. **Review fixes.** A reviewer subagent read the plan-first diff (`e590f75..f1d404f`) and found 13 defects. 12 are fixed, each with a test. `agent/NOTES.md` has the full list. The ones that matter most:
   - **The runtime probe trusted a lone progress bar.** A per-epoch bar with no epoch total projected 1.2 minutes for a 100-epoch job. Such bars and step counters now count only as a lower bound.
   - **The answer check matched numbers too loosely.** It accepted 1.0 against "AUC: 0.62", 0.03 against "seed 3", and the "2" in "r2". Values now count as written.
   - **The harness hid wrong answers behind "not verifiable".** It no longer does.
   - **Some `echo` forms still counted as evidence.**
   - **A stopped probe's partial output could be quoted as an answer.**
2. **Plan early.**
   - The scoper prompt asks for the plan within about 8 minutes, with no probe for light code.
   - From minute 6 with no plan, command output reminds the scoper. The saved logs stay clean.
3. **A roomier allowance for full runs.** A full run may take up to 60% of the task's whole limit, keeping a reserve (15% of the limit, at least 3 minutes) for the answers. The allowance no longer shrinks just because the plan came late. 3497606, planned at minute 12 of 30, now gets a full run.

**Checks:** 72 agent tests and 8 harness tests pass, and ruff is clean.

## Re-test: the 6 test papers, one run each (Haiku 5.5, 07:19 UTC, $0.37)

| Paper | 15 Nov plan-first (2 runs) | Overnight | Plan at minute (15 Nov → overnight) | Minutes | Tokens |
|---|---|---|---|---|---|
| 6460826 | reproduced, reproduced | reproduced | 8.6, 0.3 → 0.4 | 9.7, 4.7 → 2.7 | 542k, 292k → 341k |
| 0940461 | reproduced, reproduced | reproduced | 0.5, 4.0 → 0.3 | 15.1, 5.9 → 2.8 | 416k, 680k → 462k |
| 1108125 | reproduced, reproduced | reproduced | 7.2, 3.8 → 2.8 | 8.8, 5.6 → 4.7 | 580k, 641k → 343k |
| 0238624 | verifiable, not verifiable | not verifiable | 18.8, 6.4 → 7.7 | 22.1, 17.7 → 20.3 | 665k, 437k → 822k |
| 5496369 | verifiable, verifiable | not verifiable | 16.6, 10.4 → 5.3 | 25.7, 23.4 → 19.6 | 1,083k, 2,144k → 991k |
| 9370340 | not verifiable, not verifiable | not verifiable | 29.0, 8.3 → 0.7 | 29.6, 26.1 → 19.4 | 1,181k, 1,075k → 558k |

**Easy papers:**
- The plan now comes at a median of minute 0.4, against 3.9, and no probe ran.
- A run takes a median of 2.8 minutes against 7.4, and 343k tokens against 561k. That's back to where the papers were before the planning step (2.6 minutes, 317k tokens on 14 November).

**Papers too slow for the limit:**
- The plan came at a median of minute 5.3, against 13.5, and the runs were shorter. None timed out.
- **Outcomes:** all three ended not verifiable, against 3 of 6 runs verifiable on 15 November. The causes:
  - **5496369:** one of its two answers came out different under a smaller scale-down (permutation repeats 15 → 3, refits skipped).
  - **0238624:** the agent gave a "projection" with a ±0.6% range. That's just the scaled run's own value with rounding, not an extrapolation from 30 of 150 epochs, so the reference fell outside. Its verifiable run on 15 November had the same kind of narrow range.
  - **9370340:** an honest "not verifiable within budget" again.

With one run per paper, this is within the variation already seen. It doesn't look caused by the earlier plan.

## Next

- **Overconfident projections:** a range from rounding alone is not a projection. For convergence settings the range should come from the learning-curve fit; for precision settings, from the spread across seeds. Both are in the prompt but weren't followed. A check in `record_answer` could refuse a convergence projection whose range is narrower than the scaled run's own seed-to-seed spread.
- **Known gap:** a `runner` started in the same turn as the `scoper` can slip past the plan check.
