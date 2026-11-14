# deepagents features: what is used, and where it shows in a run

For the LangChain question "did you use all of deep agents?". Each row says what the feature
does here, what a person sees in the run directory or the UI, and how far it has been checked.
Everything was checked with the offline scripted model (deepagents 0.7.38, 2026-11-14). No row
has been tried with a real model yet.

| deepagents feature | What it does in Repro Bot | Where it shows | Checked |
|---|---|---|---|
| Planning (`write_todos`, `TodoListMiddleware`) | The main agent keeps a four-step plan: read, set up, run, extract | `todo_updated` events with the whole list | Yes |
| Filesystem tools (`read_file`, `write_file`, `edit_file`, `grep`) | Read the paper's repo, write fix files outside it, search saved output | `tool_call` events named after the tool | Yes |
| `execute` with a sandbox backend | Every command runs in a rootless Podman container that only holds the workspace (`PodmanShellBackend`, built on `LocalShellBackend`) | `tool_call` with the real exit code in `ok`; full output in `logs/`; `run_started.data.sandbox` | Yes |
| Large tool results offloaded | A 1.5 MB command output reached the model as a 963-character pointer to `/large_tool_results/...`; the full text stays in `logs/` | The `logs/` file; the model's context stays small | Yes (probe) |
| Subagents (`task`) | `paper-reader`, `env-builder`, `runner`, `result-judge`, each with its own instructions and tools | `subagent_started` / `subagent_finished`; the `agent` field on every step | Yes |
| Human in the loop (`interrupt_on`) | Pauses before the experiment, before a background run, before a command with a long timeout, and before any write inside the paper's repo | `approvals/<id>.request.json`, `approval_requested` / `approval_resolved`, kinds `long_run` and `edit_source` | Yes: approve, reject, timeout, from inside a subagent |
| Long-term memory (`memory=`, a `CompositeBackend` route) | `/memories/fixes.md` keeps fixes that worked; it is loaded into the main agent's instructions and read by `env-builder` before installing | `memory_read` / `memory_written`; the second run of the toy skips the install that fails | Yes |
| Skills (`SKILL.md`) | Four how-to notes: old Python pins, conda files, R projects, headless notebooks | Nothing in the timeline; they sit in the agent's context | Loads without error. Whether a model uses them is unknown |
| Summarization, prompt caching | deepagents' defaults, left on | Nothing visible | Not exercised: the toy is too short |

## Two features we could not use as planned

| deepagents feature | What happened | What we did instead |
|---|---|---|
| Filesystem permissions (`permissions=`) | 0.7.38 raises `NotImplementedError` when permissions are combined with a backend that can run commands | An `interrupt_on` rule on `write_file` / `edit_file` for paths under `/repo` (an `edit_source` approval with a diff), plus a before/after fingerprint of the paper's files, reported as `source_changes` |
| Async subagents (`AsyncSubAgent`) | They talk to an Agent Protocol server (LangGraph Platform or self-hosted); a one-shot command has none | The agent's own tools `start_background_run` and `check_background_run`: the experiment runs detached in the sandbox, the agent gets control back and polls |

## Not wired yet

| Feature | Why |
|---|---|
| LangSmith tracing (`trace_url`) | Wired: one parent trace per run, linked from `trace_url`. Needs `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true`; never tried with a real key |
| A hosted sandbox (Modal, E2B, Daytona, LangSmith) | Needs an account. Only `agent/sandbox.py` would change |

## One thing that isn't a deepagents feature but belongs in the pitch

An answer is only accepted with a quote that is found in this run's saved command output.
`record_answer` looks the quote up and refuses if it isn't there, so the agent can't report the
paper's number in place of what the code printed.
