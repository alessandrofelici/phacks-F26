# Role A backlog

Top item first. Done items stay, checked, so a restart can see where the loop is.

- [x] Slice 1: single deep agent, local shell, toy task passes the validator
- [x] Approvals: wait and resume, reject, timeout, `--auto-approve`
- [x] `todo_updated` and `tool_call` events
- [x] Subagents: paper-reader, env-builder, runner, result-judge, with events attributed to them
- [x] Isolated sandbox with Podman (answer keys and the rest of the disk out of reach)
- [x] Memory of fixes across runs (`/memories/fixes.md`, `memory_read` / `memory_written` events)
- [x] Source files protected: edits through file tools need an `edit_source` approval
- [x] Files changed by shell commands are listed in the report
- [x] Skills (`SKILL.md` for conda, R, headless notebooks, pinned Python packages)
- [x] Background runs so a long experiment doesn't block the agent
- [x] Feature map: which deepagents feature shows where in a run (`FEATURES.md`)

Everything above is done and pushed. Nothing else can be built or checked without the items below.

## Needs something this agent doesn't have

- [ ] **Any run with a real model.** Needs `OPENROUTER_API_KEY` in `.env` (see `agent/.env.example`;
      check it with `python -m agent.check --call`).
      First thing to do with a key: `python -m agent.run --task contract/fixtures/tasks/toy-linreg
      --run runs/real-1 --auto-approve`, then read the timeline. Expect to tune the prompts in
      `agent/deep.py`: they have only ever been read by the scripted stand-in.
- [ ] **First CORE-Bench task end to end.** Needs the key, and a task directory made by Role B's
      loader (`tasks/` is local to the machine where the harness ran).
- [ ] **LangSmith trace link in `trace_url`.** Wired, but never tried with a real `LANGSMITH_API_KEY`.
- [ ] **Hosted sandbox** (Modal, E2B, Daytona, LangSmith). Needs an account; Podman covers
      isolation until then.
- [ ] **A fuller sandbox image.** `python:3.12-slim` has no compiler, R or conda. Pick one when a
      real task shows what is missing (`REPRO_SANDBOX_IMAGE`).
- [ ] **Questions with `needs_figure`.** Needs a model that can read images; untested.
