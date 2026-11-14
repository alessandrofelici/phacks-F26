# Role A backlog

Top item first. Done items stay, checked, so a restart can see where the loop is.

- [x] Slice 1: single deep agent, local shell, toy task passes the validator
- [x] Approvals: wait and resume, reject, timeout, `--auto-approve`
- [x] `todo_updated` and `tool_call` events
- [ ] Subagents: paper-reader, env-builder, runner, result-judge, with events attributed to them
- [ ] Isolated sandbox with Podman (answer keys and the rest of the disk out of reach)
- [ ] Memory of fixes across runs (`/memories/fixes.md`, `memory_read` / `memory_written` events)
- [ ] Source files protected: edits need an `edit_source` approval; changed files listed in the report
- [ ] Skills (`SKILL.md` for conda, R, headless notebooks, pinned Python packages)
- [ ] Background runs so a long experiment doesn't block the agent
- [ ] Feature map: which deepagents feature shows where in a run (`FEATURES.md`)

## Needs something this agent doesn't have

- [ ] **Any run with a real model.** Needs a model API key in `.env` (e.g. `ANTHROPIC_API_KEY`).
- [ ] **First CORE-Bench task end to end.** Needs the key, and a task directory made by Role B's
      loader (`tasks/` is local to the machine where the harness ran).
- [ ] **LangSmith trace link in `trace_url`.** Needs `LANGSMITH_API_KEY`.
- [ ] **Hosted sandbox** (Modal, E2B, Daytona, LangSmith). Needs an account; Podman covers
      isolation until then.
- [ ] **Questions with `needs_figure`.** Needs a model that can read images; untested.
