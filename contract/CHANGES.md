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
