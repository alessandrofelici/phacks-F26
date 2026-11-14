# Repro Bot contract, v1 (frozen 2026-11-14)

The only interface between **Role A (Agent, owns `agent/`)** and **Role B (Harness, owns `harness/`)**.
Plan and reasons: `research/repro-bot-build-plan.md`.

Rules:
- Build against this file and `contract/fixtures/`, not against the other role's code.
- Don't edit this file while building. Propose changes in `contract/CHANGES.md`; they're adopted only at checkpoints.
- Between checkpoints you may **add optional fields and new event types**. The reader must ignore anything it doesn't know.
- `python contract/validate.py` is the referee. If the validator and this text disagree, raise it in `CHANGES.md`.

All paths are relative to the repo root, which is also the working directory of every command.

---

## 1. Task directory (B writes, A reads)

```
<task_dir>/
  task.json
  repo/        # the paper's code and data, as published
  paper.md     # optional: paper text or abstract
```

Task directories live in `contract/fixtures/tasks/<task_id>/` (fixtures) or `tasks/<task_id>/` (made by B's loaders, gitignored).

```json
{
  "contract_version": 1,
  "task_id": "toy-linreg",
  "title": "Toy linear regression",
  "source": "fixture",
  "paper_url": null,
  "instructions": "Run run.py with seed 0.",
  "questions": [
    {"id": "q1", "text": "Report the test R^2 printed by run.py.", "type": "number"},
    {"id": "q2", "text": "Report the name of the selected model.", "type": "string"}
  ],
  "limits": {"max_minutes": 15, "gpu": false, "network": true}
}
```

| Field | Required | Notes |
|---|---|---|
| `contract_version` | yes | `1` |
| `task_id` | yes | `[a-z0-9][a-z0-9-]*`, equals the directory name |
| `title` | yes | shown in the UI |
| `source` | yes | `fixture`, `core-bench` or `arxiv` |
| `paper_url` | yes | string or `null` |
| `instructions` | yes | string or `null`. What to run, if the task says (CORE-Bench's task prompt). `null` = work it out from the repo |
| `questions[]` | yes | at least one. `id` unique in the task; `type` is `number`, `string` or `list` |
| `questions[].needs_figure` | no | `true` when the answer has to be read off a plot the code produces |
| `limits.max_minutes` | yes | wall-clock budget for the whole run; A stops and reports `timeout` when it's exceeded |
| `limits.gpu`, `limits.network` | yes | booleans: whether the task may use them |

Guarantees:
- **The answer key is never inside a task directory.** B keeps it in `harness/answers/`, which A must not read.
- A treats the task directory as **read-only**. It copies `repo/` into its sandbox and works there.

## 2. Run directory (A writes, B reads)

```
<run_dir>/
  events.jsonl                  # append-only, one JSON object per line, flushed after each line
  report.json                   # written once, at the end, atomically (write a temp file, then rename)
  approvals/<id>.request.json   # A writes
  approvals/<id>.decision.json  # B writes (A writes it itself under --auto-approve)
  logs/                         # optional: full command output, any file names
  .harness/                     # B's private notes about the run; A never touches it
```

B creates `<run_dir>` (and `.harness/`) before starting A. A creates everything else.

### 2.1 events.jsonl

```json
{"seq": 12, "ts": "2026-11-14T03:10:22Z", "type": "tool_call", "agent": "env-builder", "data": {"tool": "execute", "summary": "pip install -r requirements.txt", "ok": false, "detail": "No matching distribution found for numpy==1.19.5"}}
```

- `seq`: integer, starts at 1, increases by 1.
- `ts`: UTC, ISO 8601, ending in `Z`.
- `agent`: who did it. `main` for the top-level agent, otherwise the subagent's name.
- `data`: an object; its shape depends on `type`.

| `type` | `data` | When |
|---|---|---|
| `run_started` | `{"task_id", "run_id", "model"?}` | first event |
| `todo_updated` | `{"todos": [{"content", "status"}]}` with status `pending`, `in_progress` or `completed`. Always the **whole** list | every plan change |
| `subagent_started` | `{"name", "task"}` | the main agent delegates |
| `subagent_finished` | `{"name", "summary"}` | the subagent returns |
| `tool_call` | `{"tool", "summary", "ok", "detail"?}`. `summary` is one line for the timeline; `detail` is at most ~2,000 characters, with full output in `logs/` | after each tool call worth showing |
| `approval_requested` | `{"id", "kind", "summary"}` | same moment the request file is written |
| `approval_resolved` | `{"id", "decision", "by"}` | after A reads the decision |
| `memory_read` | `{"path", "note"}` | A used something remembered from an earlier run |
| `memory_written` | `{"path", "note"}` | A saved something for later runs |
| `answer_found` | `{"question_id", "value"}` | an answer is settled |
| `error` | `{"message", "fatal"}` | something went wrong; `fatal: true` means the run is ending |
| `run_finished` | `{"status"}`, same value as `report.json` | last event |

### 2.2 report.json

```json
{
  "contract_version": 1,
  "task_id": "toy-linreg",
  "run_id": "r-20261114-031000-ab12",
  "status": "completed",
  "answers": [
    {"question_id": "q1", "value": 0.4555, "evidence": {"file": "logs/run.txt", "quote": "test r2: 0.4555"}, "confidence": "high"}
  ],
  "obstacles": [
    {"stage": "env", "summary": "numpy==1.19.5 has no wheel for this Python", "fix": "installed numpy>=1.26 instead", "resolved": true}
  ],
  "usage": {"wall_seconds": 212, "tokens": 48000},
  "trace_url": null
}
```

- `status`: `completed` (the agent finished; answers may still be wrong or null), `failed` (it gave up), `timeout` (over `limits.max_minutes`), `rejected` (a human rejected an approval the run couldn't continue without).
- `answers`: **one entry per question in `task.json`, always.** If there's no answer, `value` is `null`, `evidence` is `null`, and `obstacles` says why. `value` is a number, string or list matching the question's `type`.
- `evidence.file` is relative to the run directory; `evidence.quote` is the exact text the answer came from.
- `confidence`: `high`, `medium` or `low`.
- `obstacles[].stage`: `read`, `env`, `data`, `run`, `extract` or `other`. `fix` is a string or `null`.
- `usage.tokens` and `trace_url` may be `null`.

## 3. The command

```
python -m agent.run --task <task_dir> --run <run_dir> [--auto-approve]
```

- **Exit code 0** means `report.json` was written, whatever its status. **Non-zero** means a crash; B shows the run as crashed.
- Stdout and stderr are free-form; B saves them to `.harness/process.log`.
- Secrets (API keys) come from the environment or a `.env` file in the repo root, which is gitignored.
- B may stop a run by sending SIGTERM. A doesn't need to write a report in that case.

### 3.1 Approvals

When the agent reaches a gated action it:
1. writes `approvals/<id>.request.json`,
2. appends `approval_requested`,
3. polls for `approvals/<id>.decision.json` (about once a second),
4. appends `approval_resolved` and continues, or handles the rejection.

No decision within **10 minutes** counts as a rejection (`"by": "timeout"`).

```json
{"id": "a1", "kind": "long_run", "summary": "Run python run.py --seed 0 (est. 1 min)", "command": "python run.py --seed 0", "diff": null}
```
```json
{"id": "a1", "decision": "approve", "note": "", "by": "human"}
```

- `id`: `[a-z0-9-]+`, unique in the run.
- `kind`: `long_run` (a command expected to take more than about a minute, or any GPU use), `edit_source` (changing a file that came with the paper's repo; `diff` holds the change), `publish` (sending anything outside the sandbox).
- `command` and `diff` are strings or `null`.
- `decision`: `approve` or `reject`. `by`: `human`, `auto` or `timeout`.
- With `--auto-approve`, A still writes the request, then writes the decision itself with `"by": "auto"`, so the record of what was gated stays complete.

## 4. Fixtures

- `contract/fixtures/tasks/toy-linreg/`: runs in about a second once installed. `requirements.txt` pins `numpy==1.19.5`, which can't be installed on Python 3.10 or later, so even the toy needs one fix. Correct answers: q1 = `0.4555`, q2 = `ridge-weak` (seed 0; any recent numpy).
- `contract/fixtures/runs/golden/`: a hand-made valid run of the toy task, with one approval, one obstacle and one memory write.

## 5. Validator

```
python contract/validate.py task <task_dir>
python contract/validate.py run  <run_dir> [--task <task_dir>] [--partial]
```

`--task` also checks that the answers cover the task's questions. `--partial` accepts a run that's still going (no `report.json` yet). Exit code 0 = valid; otherwise it prints one line per problem. Python standard library only.
