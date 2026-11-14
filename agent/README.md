# agent/ (Role A)

The deep agent that runs a paper's code and answers the task's questions. It reads a task
directory and writes a run directory, as `contract/CONTRACT.md` describes.

## Set up (once)

From the repo root:

```
python3 -m venv agent/.venv && agent/.venv/bin/pip install -r agent/requirements.txt
```

or `uv venv agent/.venv && uv pip install -p agent/.venv -r agent/requirements.txt`.

Put the model key in `.env` at the repo root (gitignored), for example `ANTHROPIC_API_KEY=...`.

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
| `REPRO_MODEL` | `anthropic:claude-opus-5-5` | Any LangChain `provider:model` string, or `scripted` |
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

- `run.py`: the command. `runner.py`: one run from start to report.
- `deep.py`: prompts, tools, subagents, approvals, stream-to-events mapping.
- `sandbox.py`: where commands run. `rundir.py`: events, logs, approvals, report.
- `task.py`: task loading, answers, obstacles. `scripted.py`: the offline stand-in model.
- `skills/`: how-to notes the agent loads when a setup matches (old pins, conda, R, notebooks).
- `NOTES.md`: decisions and failures. `BACKLOG.md`: what's next. `FEATURES.md`: which deepagents
  features are used and where they show in a run.
