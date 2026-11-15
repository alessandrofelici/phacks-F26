# Overnight, 15 November: UI review and a README for judges (branch `overnight-ui`)

**Recommendation: safe to merge before the 08:00 EST deadline.** Docs, CSS and two small display changes; no API, agent or harness code. Merge with `git merge --ff-only overnight-ui` from `main`.

## What changed

- **`README.md`:** rewritten for judges. One-line pitch, results on 20 CORE-Bench papers (17 reproduced in at least one run, no wrong exact number in 98 recorded answers, a median of 9.3 minutes per reproduced run), how it works, how to try it with and without a model key, and honest limitations. The hackathon research list is kept at the end. Every number comes from `research/eval-2026-11-14/` and `research/eval-2026-11-15-plan-first/`.
- **`harness/static/index.html`:**
  - At phone width, long code words in the timeline (`requirements.repro.txt`) pushed the page 11 px wider than the screen. They now wrap, and the timeline puts time and agent on one line with the step below.
  - The scoreboard's tables were 169 px too wide on a phone. They now scroll inside their panel, and the narrow layout column can shrink (`minmax(0, 1fr)`).
  - A not-verifiable plan showed its reason three times. It now shows it once.
  - The to-do list's empty state said "didn't publish a plan" right under the scoper's plan. It now says "to-do list".
  - "Problems it hit" repeated each no-answer reason already shown on that answer. Those lines are now skipped; other problems still show.
  - A run with no scaled answers said "0 of 2 answers in range of a scaled run". It now says none of the answers could be shown within the run's limits.

## How it was checked

- **Screenshots:** headless Chromium 156 (`chromium-headless-shell`, installed in CT 120 for the review, then removed to free the disk). Pages at 1280 px and 390 px wide, light and dark, of every state:
  - reproduced
  - verifiable within budget
  - not verifiable
  - partly
  - an approval waiting, with its scale-down list
  - the scoreboard
- **Result:** no page errors, and no horizontal overflow after the fixes.
- The branch's UI ran on port 8010 from its own worktree. The demo server on port 8000 was not touched.
- **Toy paper only:** the screens used the toy paper's demo scenarios (`harness/fake_agent.py --scenario scaled | not_verifiable | wrong`). No CORE-Bench answer key was opened or shown, because the same night's agent work must not see expected values.
- **Syntax:** `node --check` passes on the page script.

## Not done

- **The paper-style evaluation doc** (claude.ai, "Repro Bot on CORE-Bench: Evaluation of the First Two Cycles") is still unfinished: Limitations, Conclusion, the appendices and the figures. The docs connector was unreachable all night.
- **The two overnight sessions:** they were meant to run separately, but the desktop app didn't answer, so both workstreams ran in one session, one after the other.
