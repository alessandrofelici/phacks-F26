# Role A notes

Kept by the agent building `agent/`. Newest state first, then decisions, then failures.
Role B doesn't read this; the humans do at checkpoints.

## State

- **Who:** Alessandro's Claude Code session on the Proxmox host, started as Role A on
  2026-11-14 at about 12:25 UTC (T+9 h; kickoff commit was 03:17 UTC). Told to carry out the
  agent half of the plan without asking questions and to write decisions here.
- **Where the code is edited:** `/home/claude/repro-agent/agent` on the host, copied into the
  repo clone in CT 120 (`/mnt/vf/hack/hackathon/projects/shared-project`) with
  `/home/claude/repro-agent/tools/sync.sh`. Tests and git run in the CT as user `hack`.
- **Verified:** see "What is verified" at the bottom. Updated after every slice.
- **Not possible yet:** any run with a real model. There is no model API key in CT 120, and no
  account for a hosted sandbox. Everything below was checked with the scripted stand-in model.

## Decisions

Each line is a decision made while building, with the reason. Change them at a checkpoint if
they're wrong.

### Open decisions the kickoff left to Role A

1. **deepagents pin: 0.7.38**, with langchain 1.5.0, langgraph 1.2.21, langchain-anthropic 1.7.10.
   It is the latest release on PyPI today and the one already proven on this machine.
2. **Model: `anthropic:claude-opus-5-5` by default, set with `REPRO_MODEL`.** Any LangChain
   `provider:model` string works. Untested live (no key). Reason for Opus: the task is long,
   multi-step debugging, and it is Anthropic's current default model at $4/$20 per million tokens.
3. **Sandbox: local shell first, then rootless Podman; hosted providers not used.** Modal, E2B,
   Daytona and LangSmith sandboxes all need an account nobody has made. `LocalShellBackend` ships
   with deepagents and needs nothing, so slice 1 uses it. It has no isolation, so the next step is
   a Podman container (already installed in CT 120, no signup, works the same with Docker on a
   laptop). A hosted backend can replace either later without touching the rest: only
   `agent/sandbox.py` knows where commands run.

### Contract and run directory

4. **`agent/run.py` imports only the standard library and re-runs itself with `agent/.venv`**
   when the calling Python lacks deepagents. The contract says B starts `python -m agent.run` but
   not which Python has A's dependencies. Proposal filed in `contract/CHANGES.md`.
5. **Exit code 2 before any event is written** when the run can't start (no key, bad task,
   run directory already used). Exit 0 always means a report exists, as the contract says. Any
   error after the first event becomes a `failed` report, not a crash.
6. **`run_id` is the run directory's name.** B creates the directory, so it already chose the id.
7. **A used run directory is refused.** `events.jsonl` is append-only and `seq` starts at 1, so
   a second run in the same directory would break both.
8. **On an approval timeout A writes the decision file itself** (`"by": "timeout"`), created
   exclusively so a decision B writes at the same instant wins. This keeps the record complete,
   the same way `--auto-approve` does.
9. **Status mapping.** `completed`: the agent finished with at least one answer. `failed`: it
   finished with none, or an error stopped it. `rejected`: an approval was rejected and at least
   one question is unanswered. `timeout`: over `limits.max_minutes`.
10. **The time limit covers everything**, including waiting for approvals. Each command's
    timeout is capped at the time left, and the limit is checked after every agent step.

### Agent design

11. **Planning is switched on explicitly** with `TodoListMiddleware`. In deepagents 0.7.38
    `create_deep_agent` no longer adds `write_todos` by itself.
12. **Events come from the agent's `updates` stream** (`subgraphs=True`): tool calls from the
    assistant message, results from the tool message. `todo_updated` is built from the
    `write_todos` call's arguments, because the stream doesn't carry the `todos` state key.
13. **Every command's full output is saved by the backend itself** (`LoggingShellBackend.execute`),
    not by the model. So `logs/` is complete even if the model never asks for it, and the
    `tool_call` event's `ok` is the real exit code.
14. **An answer needs a quote that is found in saved command output.** `record_answer` looks the
    quote up in `logs/` and fills in `evidence.file` itself; if the quote isn't there the tool
    refuses. The model can't report a number the run didn't print (for example the paper's
    rounded 0.46 in place of the printed 0.4555).
15. **Two ways to run a command.** `execute` for setup, stopped after 90 s
    (`REPRO_SHORT_TIMEOUT`); asking for a longer timeout needs approval. `run_experiment` for the
    command that produces the results, which always needs approval. Both use kind `long_run`.
    Reason: the contract gates commands "expected to take more than about a minute", but the toy
    runs in a second and checkpoint 1 needs a human to click approve on it. Gating the experiment
    itself makes approvals show up in every run, and the rule is easy to explain in the demo:
    setup is free, running the paper's experiment needs a go-ahead.
16. **A rejection is told to the model as a rejection** and it may try another way. The run is
    only `rejected` if answers are still missing at the end.
17. **The agent works on a private copy outside this repository** (`REPRO_WORK_ROOT`, default the
    system temp dir), with only `repo/` and `paper.md` in it. The task directory stays read-only,
    and the fixtures that contain the toy answers aren't in the workspace.
18. **Commands get a small environment**: PATH, a private HOME, proxy variables. API keys are not
    passed, so the paper's code can't read them.

## Failures and what changed

For `FAILURES.md` (the "what did you try and fail on" question).

- **The plan never appeared in the timeline.** The first run passed the validator with correct
  answers but had no `todo_updated` events. Cause: `write_todos` didn't exist (decision 11), the
  calls came back as tool errors, and the event mapper hid errors from "quiet" tools. Fixed by
  adding the middleware and by always showing a failed tool call. Lesson: a validator-clean run
  can still be missing a whole feature; check the timeline against the golden run, not only the
  validator.
- **The toy's install fails differently than the golden run says.** On Python 3.13 pip doesn't
  print "No matching distribution" for `numpy==1.19.5`; it downloads the source and fails to
  build it, with a long traceback. Anything that matches one specific error text is brittle;
  the fix has to come from reading the output.

## What is verified (scripted model, CT 120, 2026-11-14)

- `python -m agent.run` on the toy task writes a run directory that `contract/validate.py`
  accepts, with q1 = 0.4555 and q2 = ridge-weak parsed from the real output of `run.py`.
- Approval paths: auto-approve, a human approve, a human reject (status `rejected`, null
  answers), no decision (rejected by timeout).
- Run over `limits.max_minutes` ends with status `timeout`.
- 11 tests: 6 on the writer and findings (standard library), 5 end-to-end.
