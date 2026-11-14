# deepagents features: what is used, and where it shows in a run

For the LangChain question "did you use all of deep agents?". Each row says what the feature
does here, what a person sees in the run directory, the UI or the LangSmith trace, and how far it
has been checked. deepagents 0.7.38. "Real runs" means Haiku 5.5 or Opus 5.5 through OpenRouter on
the toy task and 20 CORE-Bench papers (2026-11-14, `harness/SCOREBOARD.md`).

| deepagents feature | What it does in Repro Bot | Where it shows | Checked |
|---|---|---|---|
| Planning (`write_todos`, `TodoListMiddleware`) | The main agent keeps a plan: read, set up, run, extract | `todo_updated` events; the Plan panel in the UI | Real runs |
| Filesystem tools (`read_file`, `ls`, `glob`, `grep`, `write_file`, `edit_file`) | Read the paper's repo and Dockerfile, write fix files outside it, search saved output | `tool_call` events named after the tool | Real runs |
| `execute` with a sandbox backend | Every command runs in a rootless Podman container that only holds the workspace (`PodmanShellBackend`, built on `LocalShellBackend`), on an image with conda, uv, compilers and R (`agent/sandbox-image/`) | `tool_call` with the real exit code in `ok`; full output in `logs/`; `run_started.data.sandbox` | Real runs |
| Large tool results offloaded | A 1.5 MB command output reached the model as a pointer to `/large_tool_results/...`; the full text stays in `logs/` | The `logs/` file; the model's context stays small | Probe |
| Subagents (`task`) | `paper-reader`, `env-builder`, `runner`, `result-judge`, each with its own instructions and tools | `subagent_started` / `subagent_finished`; the `agent` field on every step; `lc_agent_name` in LangSmith | Real runs **in strict mode only**: Haiku does every step itself by default. With `REPRO_DELEGATION=strict` (a `wrap_model_call` middleware that hides the command tools from the main agent) it delegates to all three working subagents |
| Middleware (`wrap_model_call`) | `DelegateCommands`: dynamic tool selection for the main agent only, so long install logs stay in subagent contexts | Subagent steps in the timeline; fewer tokens in the main context | Real runs (strict mode) |
| Human in the loop (`interrupt_on` with `when` predicates) | Pauses before the experiment, before a background run, before a command with a long timeout, and before any write inside the paper's repo | `approvals/<id>.request.json`, `approval_requested` / `approval_resolved`, kinds `long_run` and `edit_source` | Real runs: approved over the harness API and with `--auto-approve`; approve and reject clicked in the UI on scripted runs; timeout with the scripted model |
| Long-term memory (`memory=`, a `CompositeBackend` route) | `/memories/fixes.md` keeps fixes that worked; loaded into the main agent's instructions | `memory_read` / `memory_written`; `python -m harness.compare` on two runs | Real runs: the second toy run loaded the first one's fix, 1 obstacle fewer, 15% fewer tokens |
| Skills (`SKILL.md`) | Five how-to notes: Code Ocean capsules, old Python pins, conda files, R projects, headless notebooks | `read_file` of `/skills/.../SKILL.md` at the start of real runs | Real runs: the agent reads `code-ocean-capsule` first on CORE-Bench tasks |
| Custom tools | `run_experiment`, `start_background_run`, `check_background_run(wait_seconds)`, `record_answer`, `record_obstacle`, `look_at_figure` | `tool_call` events; `answer_found`; `figures/` | Real runs |
| Summarization, prompt caching | deepagents' defaults, left on | Nothing visible | On; not measured |
| LangSmith tracing | One parent trace per run (`langsmith.trace`), agent-based workspaces (`LANGSMITH_AGENT_ID`), flushed before exit | `report.json` `trace_url`; `python -m agent.check --call` reads the trace back | Real runs: every run is one trace with each model call, tool call and subagent inside |

## Two features we could not use as planned

| deepagents feature | What happened | What we did instead |
|---|---|---|
| Filesystem permissions (`permissions=`) | 0.7.38 raises `NotImplementedError` when permissions are combined with a backend that can run commands | An `interrupt_on` rule on `write_file` / `edit_file` for paths under `/repo` (an `edit_source` approval with a diff), plus a before/after fingerprint of the paper's files, reported as `source_changes` |
| Async subagents (`AsyncSubAgent`) | They talk to an Agent Protocol server (LangGraph Platform or self-hosted); a one-shot command has none | The agent's own tools `start_background_run` and `check_background_run`: the experiment runs detached in the sandbox, the agent gets control back and waits with `wait_seconds` |

## Images in tool results

`read_file` returns images as multimodal content blocks, but through OpenRouter's OpenAI-style API
the model only saw `...`: tool results there can't carry images. `look_at_figure` sends the image
as a user message to the same model and returns the reading as text; `record_answer(figure=...)`
keeps that image as the evidence (`figures/` in the run directory).

## Not wired

| Feature | Why |
|---|---|
| A hosted sandbox (Modal, E2B, Daytona, LangSmith) | Needs an account. Only `agent/sandbox.py` would change |

## One thing that isn't a deepagents feature but belongs in the pitch

An answer is only accepted with evidence from this run: a quote found in this run's saved command
output, or, for a figure question, an image this run wrote (images that came with the repository
are refused). The agent can't report the paper's number in place of what the code produced.
