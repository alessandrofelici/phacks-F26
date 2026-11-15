# Harness notes (Role B)

Role B's own log. Role A doesn't need to read it.

## 2026-11-14, loop 1 (kickoff + first build)
- Wrote contract v1 alone because Role A hadn't started; the choices that go beyond the plan are listed in `contract/CHANGES.md` for A to object to.
- Tested with the fake agent: approve, reject, wrong answer, crash, and the remembered-fix second run all produce run directories that pass `contract/validate.py`, and the server reports the right status for each.
- **Not verified:** the web page in a browser. Chrome wasn't reachable from this session.
- CORE-Bench: using the open train split (45 tasks). The test split is encrypted to keep it out of training data, so it isn't decrypted or stored here. Several capsules are under 1 MB.
- Scoring follows CORE-Bench (95% prediction interval over its 3 reference runs) plus 0.5% slack, because many tasks have three identical reference values, which would otherwise demand an exact float match.
- Capsules assume Code Ocean's layout (`/code`, `/data`, `/results`). The loader says so in `instructions`; whether that's enough for the agent is something checkpoint 2 will show.
- cb-4098236 has no `data/` folder at all; its script may generate or download data. Check before making it an MVP task.

## 2026-11-14, loop 2
- Role A still hasn't started (no `agent/`, nothing new in `contract/CHANGES.md`).
- Triage of 8 small Python capsules by reading them: see `TASKS.md`. Picks: 6460826 and 4098236.
- Found an answer leak: capsule-2011424 ships `code/results/output.txt` with the answer in it, and CORE-Bench's own level rules only empty the top-level `results/`. The loader now removes nested `results` folders at medium and hard and records it in `task.json` under `core_bench.saved_outputs_removed`. This is stricter than the benchmark, so scores on that task aren't comparable with published ones.
- I didn't run any capsule code on this machine: it's third-party code, and running it belongs in the agent's sandbox.
- Scoreboard view tested through the API only (start, refuse a second batch, results and failure groups). Not seen in a browser.

## 2026-11-14, plan-first runs (branch `plan-first`)

- `harness/score.py` gives every run one outcome, the weakest across its answers: `reproduced`, `partly`,
  `verifiable` (verifiable within budget), `not_verifiable` (not verifiable within budget) or
  `not_reproduced`. A scaled answer (`answers[].scaled`) is never correct; a number one is verifiable
  when the reference value lies inside its `interval` and the half-width is at most 10% of the value
  (`INTERVAL_CAP`). A run with a `not_verifiable` plan, or a question with a `not_verifiable_within_budget`
  no-answer, is not verifiable.
- `harness/batch.py`: results carry `outcome`, `verifiable` and the plan; SCOREBOARD.md gets a new table
  with two budget columns (older rows keep their own header); failure groups name the budget outcomes.
- UI: the plan (path, projected minutes, scale-down, missing steps) in the Plan panel; outcome chips;
  projections with their interval and verdict; no-answer reasons; the scale-down on approval cards; two
  budget columns and a Plan column on the scoreboard. "Not verifiable" is neutral, never red.
- Fake agent: `--scenario scaled` and `--scenario not_verifiable` (or `REPRO_FAKE_SCENARIO` for runs
  started from the UI) play both new paths on the toy task, for demos without a model.
- Tests: `python3 -m unittest discover -s harness/tests -t .` (made-up key, plus both fake scenarios
  through the validator).
