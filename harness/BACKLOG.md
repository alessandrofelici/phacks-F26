# Harness backlog (Role B)

Top item first. Re-read `contract/CONTRACT.md` and `contract/CHANGES.md` before picking.

## Next
1. **Look at the UI in a real browser.** Still not seen by anyone from this role (the API behind it is tested; the page's JavaScript only passed a syntax check). The owner said it looks fine after the first build; the Scoreboard view added since is unseen.
2. Checkpoint 1 prep: run Role A's agent on the toy task through the UI as soon as `agent/run.py` exists.
3. Run the two MVP tasks (`TASKS.md`) with the real agent at medium level; adjust `limits.max_minutes` from what's measured.
4. Side-by-side "run 1 vs run 2" to show memory working.
5. `needs_figure` questions: show the figure the agent read next to the answer.

## Later
- arXiv loader (paper link → task directory) for the stretch mode.
- Demo path: one known-good task plus a recorded run as the fallback.
- More tasks toward 20: triage the R capsules and the rest of the Python ones.

## Done
- 2026-11-14: contract v1, fixtures, validator (kickoff).
- 2026-11-14: fake agent, scorer, CORE-Bench loader, run manager, web UI, batch runner.
- 2026-11-14: Scoreboard view with "Run all papers" and failure groups; opened output sections and the log panel now stay open during live runs; MVP task triage (`TASKS.md`); loader removes saved outputs that leak answers.
