# Role A backlog

Top item first. Done items stay, checked, so a restart can see where the loop is.

## Built before the first real model

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

## Done with a real model (2026-11-14 afternoon)

- [x] Real model runs (OpenRouter; Opus 5.5 for demos, Haiku 5.5 for test cycles)
- [x] LangSmith: one trace per run, `trace_url`, agent-based workspaces (`LANGSMITH_AGENT_ID`)
- [x] CORE-Bench tasks end to end: 20 train papers at medium level, scored in batches
      (`harness/SCOREBOARD.md`)
- [x] A fuller sandbox image (`agent/sandbox-image/`: conda, uv, compilers, current R with
      binary packages, pandoc, nbconvert)
- [x] Questions with `needs_figure`: `look_at_figure` + `record_answer(figure=...)`
- [x] arXiv-link mode (`python -m agent.arxiv <id>`): find the code, pick checkable claims,
      run, verdict per claim
- [x] Waiting for background runs without `sleep` commands (`check_background_run(wait_seconds=)`)

## Next

- [ ] **Hard level** (Dockerfile, REPRODUCING.md and run scripts removed): a cycle on the same 20 papers.
- [ ] **Subagents on Haiku.** Haiku does every step itself despite the prompt; long install logs then
      pile up in one context (up to 2.3M tokens a run). `REPRO_DELEGATION=strict` hides the command
      tools from the main agent so setup and runs go to `env-builder` and `runner`; compare it with
      the default over a whole cycle before making it the default.
- [ ] **Runs longer than 30 minutes on a CPU** (TensorFlow ensembles, 1000-tree survival forests).
      Either a longer per-task limit for scored runs or a GPU sandbox (hosted).
- [ ] **One memory file shared by parallel runs.** Simultaneous writes can lose a line; give each
      batch worker a lock or merge after the batch.
- [ ] **Hosted sandbox** (Modal, E2B, Daytona, LangSmith). Needs an account; Podman covers
      isolation until then.
- [ ] **Tokens spent by `look_at_figure`** are not counted in `usage.tokens` (they are in LangSmith).
