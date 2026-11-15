# Demo path (checked 15 November 2026, 05:45 UTC)

Two runs, about 3 minutes in all, then the scoreboard. Rehearsed on commit `cd6a2d8` through the web UI's own API, with every approval clicked as a presenter would.

## Before you start

- Start the UI: `python3 -m harness.server --port 8000` in the repo root, then open http://localhost:8000. On the team server, `tools/ui.sh` on the host starts it in CT 120, and a laptop reaches it with `ssh -N -L 8000:127.0.0.1:8000 claude@pve`.
- `python -m agent.check` must say `ready` and show OpenRouter credit (a live run costs about 9 cents).
- An approval left unanswered for 10 minutes counts as a rejection.

## 1. Live: a paper reproduced end to end (about 2 minutes)

1. Paper: **ExPSO Package: Exponential Particle Swarm Optimization for Global Optimization** (`cb-5975162-medium`). Agent: **Real**. **Start run**.
2. The **Plan** panel fills first: the `scoper` subagent's plan (full run, about 1 minute of 30), the steps, and the missing step it found (the code needs `PYTHONPATH=repo/src`).
3. Two approvals: the install, then the experiment. Approve both.
4. **Report**: 2 of 2 answers match the reference, **Reproduced**, each with the output line it came from (click the log name to open it). The rehearsal took 1 min 29 s.

## 2. Replay: a paper too big for 30 minutes on a CPU (about 1 minute)

1. Paper: **A University Admission Prediction System using Stacked Ensemble Learning** (`cb-0238624-medium`). Agent: **Demo replay** (a recorded real run, no model). **Start run**.
2. Approve the probe: the scoper times the training for up to 180 s.
3. The plan turns **scaled**: the full run would take about 80 minutes, so epochs go from 150 to 8.
4. The next approval card says *"Scaled down from the paper's settings (approving this approves the smaller run): epochs: 150 → 8 (convergence)"*. Approve it.
5. **Report**: **Verifiable within budget**. Each answer is a projection with its interval (0.88, 0.875 to 0.885) marked **In range** of the reference; a scaled answer never counts as reproduced.

## 3. Scoreboard

The **Scoreboard** button: every batch, with the two budget columns, and the latest batch paper by paper with each run's plan.

## If something fails

- No network or no credit: run part 1 as a **Demo replay** too. Recordings exist for `cb-0238624-medium` (plan-first, scaled), `cb-6460826-medium` and `cb-4098236-medium` (both reproduced, from before the planning step).
- Figures for slides: `research/eval-2026-11-14/images/` (figures 1 to 7) and `research/eval-2026-11-15-plan-first/images/` (8 and 9), each in light and dark.
