# agent/ (Role A)

The deep agent that runs a paper's code and answers the task's questions. It reads a task
directory and writes a run directory, as `contract/CONTRACT.md` describes.

## Set up (once)

From the repo root:

```
python3 -m venv agent/.venv && agent/.venv/bin/pip install -r agent/requirements.txt
```

or `uv venv agent/.venv && uv pip install -p agent/.venv -r agent/requirements.txt`.

## Keys

Copy the example and fill in one key:

```
cp agent/.env.example .env        # .env lives in the repo root and is gitignored
python -m agent.check             # shows the model, key, sandbox and tracing that would be used
python -m agent.check --call      # also sends one tiny request to the model
```

| Key | Needed? | What for |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes (or `ANTHROPIC_API_KEY`) | The model. Default `openrouter:anthropic/claude-opus-5.5` |
| `ANTHROPIC_API_KEY` | Only when `REPRO_MODEL` starts with `anthropic:` | Anthropic's API directly |
| `LANGSMITH_API_KEY` + `LANGSMITH_TRACING=true` | Optional | One LangSmith trace per run, linked from `trace_url` |
| `LANGSMITH_AGENT_ID` + `LANGSMITH_AGENT_ENVIRONMENT` | In an agent-based LangSmith workspace | Which LangSmith agent receives the traces. Leave `LANGSMITH_PROJECT` unset then; `.env.example` explains both workspace kinds |

Nothing else needs a key: the sandbox is local Podman, and the docs MCP servers are public.
A linked git worktree has no `.env` or `agent/.venv` of its own; it uses the main checkout's.
Keys stay in the agent's own process. Commands in the sandbox never see them.

## Run

```
python -m agent.run --task contract/fixtures/tasks/toy-linreg --run runs/my-first-run
python contract/validate.py run runs/my-first-run --task contract/fixtures/tasks/toy-linreg
```

Any `python` works: `agent/run.py` only needs the standard library to start and switches to
`agent/.venv` by itself. Without `--auto-approve` the run waits for
`approvals/<id>.decision.json`, which the harness UI writes.

No API key? `REPRO_MODEL=scripted` replays a fixed sequence of tool calls for the toy task
through the real agent graph. The commands really run and the answers are parsed from their
output, but no LLM is involved, so it only proves the plumbing.

## Settings (environment or `.env`)

| Variable | Default | Meaning |
|---|---|---|
| `REPRO_MODEL` | `openrouter:anthropic/claude-opus-5.5` (or `anthropic:claude-opus-5-5` when only that key is set) | Any LangChain `provider:model` string, or `scripted` |
| `REPRO_SUBAGENT_MODEL` | same as `REPRO_MODEL` | A cheaper model for the four subagents |
| `REPRO_SANDBOX` | `auto` | `podman`, `local`, or `auto` (Podman when it's installed, else the local shell) |
| `REPRO_SANDBOX_IMAGE` | `docker.io/library/python:3.12-slim` | Container image for the Podman sandbox |
| `REPRO_WORK_ROOT` | system temp dir | Where the private copy of the task's repo is made |
| `REPRO_KEEP_WORK` | unset | Set to keep that copy after the run, for debugging |
| `REPRO_MEMORY_DIR` | `agent/.memory` | Where fixes remembered across runs are kept (gitignored) |
| `REPRO_SHORT_TIMEOUT` | `90` | Seconds a command may run without an approval |
| `REPRO_APPROVAL_TIMEOUT` | `600` | Seconds to wait for a decision (contract: 10 minutes) |
| `REPRO_DEBUG` | unset | Print the agent's raw stream updates to stderr |

The local shell has no isolation: the paper's code can read anything this user can, including
the harness's answer keys. Use it for plumbing only; scored runs should use Podman.

## Exit codes

- `0`: `report.json` was written (status `completed`, `failed`, `timeout` or `rejected`).
- `2`: the run could not start (no model key, unreadable task, run directory already used, `REPRO_SANDBOX=podman` but Podman didn't start).
  Nothing is written in that case.
- anything else: a crash.

## Tests

```
python3 -m unittest discover -s agent/tests -t .               # writer and findings, standard library only
agent/.venv/bin/python -m unittest discover -s agent/tests -t .  # plus end-to-end scripted runs (needs network)
```

## Files

- `run.py`: the command. `runner.py`: one run from start to report. `check.py`: configuration check.
- `models.py`: which model and key. `tracing.py`: the optional LangSmith trace link.
- `.env.example`: every setting, with comments.
- `deep.py`: prompts, tools, subagents, approvals, stream-to-events mapping.
- `sandbox.py`: where commands run. `rundir.py`: events, logs, approvals, report.
- `task.py`: task loading, answers, obstacles. `scripted.py`: the offline stand-in model.
- `skills/`: how-to notes the agent loads when a setup matches (old pins, conda, R, notebooks).
- `NOTES.md`: decisions and failures. `BACKLOG.md`: what's next. `FEATURES.md`: which deepagents
  features are used and where they show in a run.
