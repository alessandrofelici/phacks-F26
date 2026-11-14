# Autonomous run, 2026-11-14 (15:45-19:00 UTC): review notes

The developer asked for the remaining build plan to be carried out with no human interaction,
assumptions noted here for review afterwards, pushes straight to `main`. This is that note.

## Where each plan item stands

| Item | State |
|---|---|
| Download the two picked CORE-Bench papers and their answer keys | Done (6460826, 4098236; medium and hard) |
| Run one real paper end to end with auto-approve, and score it | Done: CULP 6/6 in 107 s, ART 2/2 in 4 min (Haiku 5.5) |
| Give the sandbox older Pythons, compilers, conda and R | Done: `agent/sandbox-image/` (image `localhost/repro-sandbox:2`) |
| Run the toy and both real papers unattended against the tester script | Done: `python -m harness.tester_check`. Real agent on the toy: 7/7. Replays of the real CULP and ART runs: 16/17 (the recorded ART run kept no plan) |
| Grow the task set from five papers toward twenty | Done: 20 papers (12 Python, 8 R, 8 with figure questions) |
| Evaluate each batch, group failures, improve the agent, repeat | Two cycles, see below. A third is blocked by model credit |
| Record every cycle's score in the scoreboard | Done: `harness/SCOREBOARD.md` (rows annotated) |
| Move from medium to hard once medium passes | **Not run**: task dirs fetched (`tasks/cb-*-hard`), blocked by model credit |
| Compare a paper's first and second runs to confirm memory works | Done: `python -m harness.compare`; second toy run loaded the fix, 1 obstacle fewer, 15% fewer tokens |
| Support questions read off a figure | Done: `look_at_figure`; used for real in three papers, images kept as evidence |
| arXiv-link mode | Done: `python -m agent.arxiv <id>`; tried on arXiv 1810.00717 (CULP) |
| Deep agents feature map, with where each shows in traces | Done: `agent/FEATURES.md` |
| One known-good paper and a recorded fallback run | Done: recordings of CULP (6/6, with plan) and ART (2/2) in `harness/recordings/`; Demo replay plays them |
| Freeze six hours before submission | Rule written down; submission time unknown (assumed Sunday morning ET) |

## Results

| Cycle | Setup | Tasks reproduced | Notes |
|---|---|---|---|
| 1 | Haiku 5.5, medium, image :1 | 10/21 (25/43 answers) | 5 R papers timed out compiling packages; 1 crash was a harness podman timeout |
| 2 | Haiku 5.5, medium, image :2, figure tool, R and prompt fixes | 9/21 on the board; **9 of the 11 that ran to the end** | 9 tasks stopped when the OpenRouter account ran out of credit (18:13 UTC). The same 11 tasks in cycle 1: 5 reproduced |

Remaining genuine misses: three papers that train for longer than 30 minutes on a CPU
(TensorFlow ensemble, a 1000-tree survival forest, a slow training loop) and one R paper that
passed in a separate run but timed out in cycle 2.

arXiv mode on CULP (arXiv 1810.00717): found the authors' repository through a GitHub README that
names the paper, picked claims from Table III, and the agent reported honestly that the released
code has only the library and an Iris example, not the 30-run cross-validation behind the tables
(0/4 reproduced; first attempt wrote its own CV wrapper and got 74.2 vs 98.1 and 95.4 vs 96.6).

## Commits on main

- `5fe5815` cycle 1 fixes: sandbox image, figure tool, background waits, prompts, skills, arXiv
  mode, batch `--parallel`, recordings and run comparison
- `8c5f707` cycle 2 results, strict delegation trial, credit checks, notes and feature map
- the commit with this note: unattended tester script, plan-first prompt, harness README

## Assumptions to review

- Model: all improvement cycles use Haiku 5.5 (the testing model the developer chose). An Opus 5.5
  closing cycle was planned if budget allowed; the credit ran out first.
- Level order: medium first (Dockerfile and REPRODUCING.md kept), hard after medium passes, as the
  build plan and harness/TASKS.md say.
- Task set: 20 CORE-Bench train capsules picked by me for CPU-only, small downloads, a mix of
  Python (12) and R (8), 8 with figure questions. Skipped GPU/TensorFlow-heavy ones and the
  Python 2.7 one. Picks: 6460826 4098236 2011424 0940461 5975162 5286757 0238624 3894632 9370340
  2916503 1906954 6133093 6746514 3497606 5496369 1108125 3137115 9168639 1324693 2061060.
- Answer keys: I (the developer agent) never open harness/answers/* for real tasks, and summaries
  hide the expected values, so prompt/skill changes stay general and don't fit specific answers.
- Role boundaries: with no collaborator changes expected, I edit harness/ as well as agent/
  (batch --parallel, recorded-run replay, run comparison).
- Sandbox: a local Podman image (localhost/repro-sandbox:2) built from agent/sandbox-image/; not
  pushed to a registry. Teammates build it with agent/sandbox-image/build.sh.
- Parallel batch runs share one memory file (agent/.memory/fixes.md); simultaneous writes can lose
  a line. Accepted for now.
- Code changes are not synced into the main checkout while a batch is running, so every task in a
  cycle runs the same agent code. New work is tried in a separate worktree (/mnt/vf/hack/tmp/wt-dev).
- Figure questions: answers are read by the same model through a `look_at_figure` tool (image sent
  as a user message), because OpenRouter's OpenAI-style API drops images inside tool results.
- arXiv-link mode: verdict tolerance is half a unit of the claim's last printed digit or 1% of
  its value, whichever is larger, and percent vs fraction counts as the same number.
- Freeze rule: submission time unknown; assumed Sunday 2026-11-15 morning (ET).
- cb-0238624 (stacked TensorFlow ensemble, 150 epochs) is slower than the 30-minute task limit on
  this CPU. I kept the harness's 30-minute limit rather than raising it per task.
- Sandbox image :2 moves R from Ubuntu's 4.3 to CRAN's current R and preinstalls the common R
  packages, because current CRAN packages (Matrix) need R >= 4.4.
- cb-4098236 crashed in cycle 1 only because my image build held Podman's storage lock while the
  run cleaned up its container (fixed: cleanup can no longer crash a run). I count it as a harness
  failure, not an agent one.
- **Blocker (18:13 UTC): the OpenRouter account ran out of credit** ($14.95 of $15 used; this key
  used $3.14 of it, so the rest went elsewhere on the account). Every model call since fails with
  PaymentRequired. I did not add credit (payment) and did not switch to OpenRouter's free models
  (different data-retention terms for the papers' code and our prompts). Cycle 2 runs that ended
  on that error are counted as "not run", not as agent failures. The hard-level cycle and an Opus
  closing cycle are prepared but not run.

## What needs the developer

1. **OpenRouter credit.** The account has about $0.03 left (`python -m agent.check` shows it).
   Everything below needs it.
2. Then, in CT 120 as `hack` from the repo root, the next cycles (also in `agent/NOTES.md`):
   ```
   TASKS=$(ls tasks | grep -E '^cb-.*-medium$' | tr '\n' ',')toy-linreg
   python3 -m harness.batch --tasks "$TASKS" --label "cycle 3: Haiku, medium" --parallel 5
   TASKS=$(ls tasks | grep -E '^cb-.*-hard$' | tr '\n' ',')toy-linreg
   python3 -m harness.batch --tasks "$TASKS" --label "hard 1: Haiku" --parallel 5
   ```
   Haiku cost $0.02-0.25 per paper. An Opus cycle is roughly 40 times that.
3. Decide whether `REPRO_DELEGATION=strict` becomes the default (Haiku only uses subagents in that
   mode; one more cycle in each mode would settle it).
4. Untested because the credit ran out: the plan-first prompt change (Haiku kept a plan in only
   10 of 21 cycle 1 runs).
