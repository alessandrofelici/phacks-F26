# Harness backlog (Role B)

Top item first. Re-read `contract/CONTRACT.md` and `contract/CHANGES.md` before picking.

## Next
1. **Look at the UI in a real browser.** It hasn't been seen by anyone yet (the API behind it is tested; the page's JavaScript only passed a syntax check). Fix whatever looks wrong.
2. Timeline: keep an opened "output" section open while a run is live (the page re-renders every second and closes it).
3. Pick the 2 real MVP tasks: fetch the small Python capsules, and check by hand which run in under 5 minutes on CPU. Candidates so far: 6460826, 4098236, 0940461, 5975162, 2011424.
4. Checkpoint 1 prep: run Role A's agent on the toy task through the UI as soon as `agent/run.py` exists.
5. Failure view in the UI: obstacles grouped by stage across runs (the batch runner already prints this).
6. Scoreboard page in the UI (reads `harness/SCOREBOARD.md` / `runs/.batches/`).

## Later
- Side-by-side "run 1 vs run 2" to show memory working.
- `needs_figure` questions: show the figure the agent read next to the answer.
- arXiv loader (paper link → task directory) for the stretch mode.
- Demo path: one known-good task plus a recorded run as the fallback.

## Done
- 2026-11-14: contract v1, fixtures, validator (kickoff).
- 2026-11-14: fake agent, scorer, CORE-Bench loader, run manager, web UI, batch runner.
