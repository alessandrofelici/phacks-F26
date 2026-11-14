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
