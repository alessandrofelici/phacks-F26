# Contract change proposals

The only channel between Role A and Role B while building. Add a proposal at the bottom and keep working; proposals are decided at checkpoints (T+6, T+10) by the humans.

Format:

```
## <date> <role> — <short title>
Status: proposed | adopted in v<N> | rejected
Problem: what the current contract makes hard.
Proposal: the exact change to CONTRACT.md.
Workaround until then: the optional field or event type being used in the meantime.
```

---

## 2026-11-14 B — decisions made while writing v1
Status: adopted in v1

These go beyond section 3 of the build plan. They were settled by Role B at kickoff because Role A hadn't started yet; A should object here if any of them is a problem.

- `task.json` has a required `instructions` field (CORE-Bench tasks come with a prompt saying what to run) and an optional per-question `needs_figure`.
- Two memory event types, `memory_read` and `memory_written`, so the UI can show a remembered fix being reused.
- Under `--auto-approve`, A writes the request **and** the decision (`"by": "auto"`) rather than skipping both.
- `.harness/` inside each run directory is B's private space.
- `report.json` is written atomically, and `events.jsonl` is flushed line by line, because B reads both while A is still running.
- The toy task's answers are q1 = 0.4555 and q2 = ridge-weak.

## 2026-11-14 A — which Python runs `agent.run`
Status: proposed
Problem: section 3 says B starts `python -m agent.run`, but not which interpreter. The agent needs `deepagents` and its dependencies; `contract/validate.py` and anything else that only needs the standard library doesn't. If B's `python` lacks them, every run crashes on import.
Proposal: add to section 3: "A's dependencies are listed in `agent/requirements.txt` and installed into `agent/.venv` (gitignored). B may start the command with any Python 3.11+; `agent/run.py` starts with the standard library only and switches to `agent/.venv` itself."
Workaround until then: already built that way. Set up once with `python3 -m venv agent/.venv && agent/.venv/bin/pip install -r agent/requirements.txt`. If the venv is missing, the command exits with code 2 and prints that line.

## 2026-11-14 A — notes for B, no contract change needed
Status: proposed (information only)
- Exit code 2 means the run could not start (no model key, unreadable task, run directory already has events). Nothing is written in that case, so B sees a crash with the reason in `.harness/process.log`.
- A refuses a run directory that already has `events.jsonl` content or a `report.json`. An empty directory, with or without `.harness/`, is fine.
- When no decision arrives in 10 minutes, A writes `approvals/<id>.decision.json` itself with `"by": "timeout"`. It creates the file exclusively, so a decision B writes at the same moment wins.
- Every run asks for one `long_run` approval before the experiment command, even when it is short, so the approve button is exercised on the toy task. Setup commands under 90 seconds don't ask.
- `evidence.file` always points into `logs/`; A fills it in after finding the quote in saved command output.

## 2026-11-14 A — optional fields A now writes
Status: proposed (information only; all optional, nothing to adopt)
- `run_started.data.sandbox` and `report.sandbox`: where commands ran, e.g. `podman (python:3.12-slim, network on)` or `local`. A run with `local` had no isolation, so the paper's code could read anything on the disk, answer keys included. B may want to show or exclude those runs on the scoreboard.
- `report.source_changes`: files that came with the task's repo and were modified or deleted during the run, as `[{"path": "repo/run.py", "change": "modified", "approved": false}]`. `approved` is true when a human approved that edit through an `edit_source` request. Empty list when nothing changed.
- Event type `source_changed` with `data.files` (same list), emitted just before `run_finished` when the list has unapproved entries. The same information is also in `obstacles`.
- Approvals can now come from a subagent: the `agent` field of `approval_requested` / `approval_resolved` is the subagent's name (`runner`, `env-builder`), not always `main`.
- A run can raise more than one approval (`a1`, `a2`, ...): `edit_source` when the agent wants to change a file inside the paper's repo (the request's `diff` is a unified diff), then `long_run` before the experiment.

## 2026-11-14 A+B — plan-first runs and budget outcomes
Status: proposed (all additive: optional fields and new event types, which v1 readers ignore)
Problem: papers too big for the limits (30 minutes, CPU only) used to run until the time limit and score as plain failures; 6 of the 15 failed runs on 14 November were compute walls, not agent mistakes. There was also no way to record why a question has no answer, so a run once recorded the text "no answer" as a value.
Proposal (from research doc "Repro Bot: Plan-First Runs and Budget-Scaled Verification"):
- `report.plan` (A writes): `{"path": "full" | "scaled" | "not_verifiable", "projected_minutes", "minutes_left", "steps", "missing_steps", "heavy_settings", "reason", "revision"}`, plus `"scale_down": [{"setting", "original", "scaled", "kind", "where"}]` and `"scaled_minutes"` on a scaled plan. `kind` is `precision`, `convergence`, `data` or `hardware`.
- `answers[].scaled: true` on answers from a scaled run, and `answers[].interval: [low, high]` on a scaled number answer: the value is then a projection of the full run, printed with its interval by a script in the run.
- `answers[].no_answer: {"category", "reason"}` next to `value: null`; categories `not_verifiable_within_budget`, `environment`, `not_in_output`, `other`.
- Event types `plan_recorded` (`{"path", "projected_minutes", "minutes_left", "summary"}`) and `no_answer` (`{"question_id", "category", "reason"}`).
- `approvals/<id>.request.json` may carry `scale_down` (same list as the plan) on the experiment's `long_run` request: approving that run approves the smaller settings. No new approval kind.
- B scores a scaled answer as never correct; it is "verifiable" when the reference value lies inside its interval and the half-width is at most 10% of the value. Each run gets one outcome, the weakest across its answers: `reproduced`, `partly`, `verifiable`, `not_verifiable`, `not_reproduced` (`harness/score.py`).
Workaround until then: already built that way on branch `plan-first`; `contract/validate.py` checks the new fields' shapes only when they are present.
