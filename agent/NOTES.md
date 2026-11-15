# Role A notes

Kept by the agent building `agent/`. Newest state first, then decisions, then failures.
Role B doesn't read this; the humans do at checkpoints.

## State

- **2026-11-14 evening (autonomous run, no collaborator changes):** real-model evaluation on 20
  CORE-Bench train papers at medium level plus the toy, scored with `harness.batch`:
  - Cycle 1 (Haiku 5.5, sandbox image :1): 10/21 tasks reproduced, 25/43 answers.
  - Cycle 2 (Haiku 5.5, image :2, figure tool, R and prompt fixes): of the 11 tasks that ran to
    the end, 9 reproduced (cycle 1: 5 of the same 11). The other 9 tasks stopped at 18:13 UTC
    when the OpenRouter account ran out of credit, so they have no cycle 2 result.
  - Not run for the same reason: the hard-level cycle (task dirs `tasks/cb-*-hard` are fetched),
    a strict-delegation cycle, and an Opus closing cycle. Commands are under "Next cycles" below.
- **Where the code is edited:** `/home/claude/repro-agent/agent` on the host, copied into the
  repo clone in CT 120 (`/mnt/vf/hack/hackathon/projects/shared-project`) with
  `/home/claude/repro-agent/tools/sync.sh`. Tests and git run in the CT as user `hack`.
  Experiments that must not disturb a running batch go in a worktree (`/mnt/vf/hack/tmp/wt-dev`).
- **Answer keys:** whoever improves the agent reads scores, never the expected values of real
  tasks, so fixes stay general (prompts, skills, sandbox, tools), not fitted to answers.

### Next cycles (each needs model credit)

```
TASKS=$(ls tasks | grep -E '^cb-.*-medium$' | tr '\n' ',')toy-linreg
python3 -m harness.batch --tasks "$TASKS" --label "cycle 3: Haiku, medium" --parallel 5
TASKS=$(ls tasks | grep -E '^cb-.*-hard$' | tr '\n' ',')toy-linreg
python3 -m harness.batch --tasks "$TASKS" --label "hard 1: Haiku" --parallel 5
REPRO_DELEGATION=strict python3 -m harness.batch --tasks "$TASKS" --label "strict delegation" --parallel 5
REPRO_MODEL=openrouter:anthropic/claude-opus-5.5 python3 -m harness.batch --tasks "$TASKS" --label "Opus" --parallel 3
```

Haiku cost about $0.02-0.25 per paper (80k-2.3M tokens); Opus would be roughly 40 times that.

### What the cycles taught (and what changed)

| Seen in a run | Change |
|---|---|
| R packages compiled from source for 20+ minutes; `Matrix` needs R >= 4.4 | Image :2: CRAN's current R, common packages preinstalled, binary installs from Posit; the R skill says to keep that repository and swap MRAN snapshots for Posit's |
| 18 approvals for `sleep 85` while an install ran in the background | `check_background_run(wait_seconds=...)` |
| The model saw `...` instead of a plotted figure | `look_at_figure` (image as a user message) and figure evidence in `record_answer` |
| A run's output piped through `tail` showed nothing when it hit the time limit | Prompt: estimate run time, start long runs in the background, never pipe through `tail`/`head` |
| The sandbox's Python 3.14 can't install 2018-era pins | Prompt and skills: match the Python of the repository's era with `uv venv -p` or `conda create` |
| Scripts read `/data` and write `/results` (Code Ocean) | `code-ocean-capsule` skill |
| `podman rm` timed out while an image build held the storage lock; the run crashed without a report | Cleanup can't raise any more |
| A rewritten `.pyc` was reported as a changed source file | Bytecode and notebook caches are ignored |
| Haiku never delegates, and one run reached 2.3M tokens | `REPRO_DELEGATION=strict` (on trial: 2 of 3 trial papers ran; it delegated in both) |
| Papers that train for longer than 30 minutes on a CPU (TensorFlow ensemble, survival forest) | Not fixed: needs a longer limit or a GPU |

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

### Subagents, memory, skills, source protection (slice 2)

19. **Four subagents, as the plan names them**: `paper-reader` (no custom tools, told to run
    nothing), `env-builder` (`record_obstacle`), `runner` (`run_experiment`, `record_obstacle`),
    `result-judge` (`record_answer`, `record_obstacle`). The main agent keeps every tool and may
    do a step itself on a small repository; forcing four round trips on a toy wastes tokens.
20. **Custom tools are created once per agent**, so `answer_found` and other events name the
    agent that acted. Steps inside a subagent are attributed through the stream's namespace.
21. **An approval inside a subagent pauses the whole run.** Subagents inherit `interrupt_on`.
    The same interrupt can surface at more than one level of the stream, so interrupts are
    de-duplicated by id before any request file is written.
22. **Command output is saved twice**: in the run directory's `logs/` (for the harness and the
    evidence) and under `/logs` in the workspace (so `result-judge` can search it with file tools).
23. **Memory is one Markdown file, `/memories/fixes.md`**, kept in `REPRO_MEMORY_DIR` (default
    `agent/.memory`, gitignored) and mounted with a `CompositeBackend` route. It is loaded into
    the main agent's instructions with deepagents' `memory=` option, and `env-builder` reads it
    before installing and adds a line after a new fix. Events: `memory_read` at the start of a
    run when there is something remembered and on every read, `memory_written` on every write.
    Two batch runs writing at the same moment could lose a line; accepted for now.
24. **Skills are `SKILL.md` files in `agent/skills/`** (old Python pins, conda environment
    files, R projects, headless notebooks), mounted at `/skills` from a per-run copy so the
    agent can't change the ones in the repository.
25. **Edits to the paper's files go through `interrupt_on`, not `permissions=`.** A `when` rule
    on `write_file` and `edit_file` pauses any write under `/repo` for an `edit_source` approval
    whose `diff` is a unified diff of the change. deepagents 0.7.38 raises `NotImplementedError`
    when `permissions=` is combined with a backend that can run commands, so the permissions
    feature can't be used with a sandbox at all in this version.
26. **No deepagents async subagents.** `AsyncSubAgent` talks to an Agent Protocol server
    (LangGraph Platform or self-hosted). A one-shot command has no such server, so long runs in
    the background are done with the agent's own tools instead.
27. **The scripted model is one generator that speaks for the main agent and all subagents.**
    Their turns happen in a fixed order, so one script with normal `if` branches covers the
    remembered-fix path, the rejected-approval path and the edit-source test switch.

### Sandbox and source check (slice 3)

28. **The default sandbox is a rootless Podman container** (`REPRO_SANDBOX=auto` uses it when
    `podman` is installed). Only the workspace is mounted, at `/work`. The paper's code can't
    read this repository, so not `harness/answers/` either, nor other files or API keys. With
    the local shell any command could `cat` the answer key, which would make every score
    worthless. Docker-compatible, so it should behave the same on a laptop; untested there.
29. **`limits.network: false` is enforced** by starting the container with `--network none`.
    `limits.gpu` needs nothing: no GPU device is passed in.
30. **Image: `python:3.12-slim`**, set with `REPRO_SANDBOX_IMAGE`. Small enough to pull over a
    bad connection. It has no compiler, R or conda, so real CORE-Bench capsules will need a
    fuller image; that choice is left until there is a real task to try.
31. **If Podman can't start in `auto` mode the run falls back to the local shell** and says so
    in a non-fatal `error` event. With `REPRO_SANDBOX=podman` the same failure stops the run
    before it starts (exit 2), for batch runs where an unisolated run must not be scored.
32. **Command timeouts are enforced inside the container** (`timeout -k 5 N sh -c ...`), with
    a slightly longer guard on the `podman exec` call itself.
33. **Files that came with the repository are fingerprinted before the run and compared after
    it.** File-tool edits need an approval (decision 25), but a shell command can still change
    a file. Changed originals go into the report as `source_changes` (path, modified or
    deleted, approved or not), and unapproved ones add an obstacle. The wording is neutral:
    some code rewrites an output file that shipped with the repository, which is not cheating.
34. **Fields beyond contract v1**, all optional and listed in `contract/CHANGES.md`:
    `run_started.data.sandbox`, `report.sandbox`, `report.source_changes`, and the event type
    `source_changed`.

### Background runs and the feature map (slice 4)

35. **Long experiments run detached in the sandbox** through two tools the agent owns:
    `start_background_run` (approved like `run_experiment`, kind `long_run`) and
    `check_background_run`. The command's output goes to a file in the workspace; when it has
    finished, the output is saved to `logs/` like any other command, so answers can cite it.
    This replaces deepagents' async subagents (decision 26). The run is still bounded by the
    time left in `limits.max_minutes`, and anything still running is killed when the run ends.
36. **Large outputs are left to deepagents.** A probe with a 1.5 MB output showed the model
    gets a short pointer to `/large_tool_results/...`. The backend keeps up to 1 MB per command
    in `logs/`. No extra code was needed.
37. **`FEATURES.md` is the answer to "did you use all of deep agents?"**: one row per feature,
    where it shows in a run, and how far it was checked. Two features could not be used as the
    plan assumed (permissions, async subagents); it says what replaced them.
38. **Test switches live in the scripted model**, not in the agent: `REPRO_SCRIPT_EDIT_SOURCE`,
    `REPRO_SCRIPT_TAMPER`, `REPRO_SCRIPT_PROBE`, `REPRO_SCRIPT_BACKGROUND`,
    `REPRO_SCRIPT_BIG_OUTPUT`. They only change what the stand-in model does.

### Keys and model choice (slice 5, after Alessandro said he will add an OpenRouter key)

39. **OpenRouter through `langchain-openrouter` 0.2.9**, the provider `init_chat_model` and
    deepagents already know (`openrouter:<vendor>/<model>`). Not an OpenAI-compatible base URL:
    deepagents ships an OpenRouter profile (app attribution, no routing through Azure) that
    only applies to the real provider.
40. **Default model `openrouter:anthropic/claude-opus-5.5`** ($4 / $20 per million tokens on
    OpenRouter today; the id was read from OpenRouter's model list, not guessed). With
    `REPRO_MODEL` unset the model follows the key that is set: OpenRouter first, then Anthropic.
41. **`REPRO_SUBAGENT_MODEL` is optional and empty by default.** Subagents use the main model
    unless someone decides to trade quality for cost; that is a human's call after a real run.
42. **`agent/.env.example` lives in `agent/`** because Role A only writes there, but it is
    copied to `.env` in the repo root, where the contract says secrets go.
43. **`python -m agent.check`** prints what a run would use (model, key present or not, sandbox,
    tracing) and with `--call` sends one tiny request. A wrong key, no credit or a mistyped
    model id is the likeliest first failure, and this finds it without starting a run.
44. **LangSmith tracing wraps the whole run in one parent trace** (`langsmith.trace`), because
    approvals split a run into several agent invocations. `trace_url` is that trace's link.
    Any tracing failure ends in `trace_url: null`, never in a failed run. Checked with tracing
    off and with a fake key; **not checked with a real LangSmith key**.

### Plan-first runs and budget outcomes (branch `plan-first`, 2026-11-14 evening)

Asked for in the research doc "Repro Bot: Plan-First Runs and Budget-Scaled Verification" after the
evaluation of the 14 November runs (`research/eval-2026-11-14/`): 6 of 15 failed runs were compute walls.

- **The plan is enforced in code, not the prompt.** Only `scoper` has `record_plan` and
  `probe_runtime`; `run_experiment` and `start_background_run` refuse without a plan. The refusal
  happens at the approval pause in `runner._drive`, without asking a human. A `when` predicate
  can't do it: it is evaluated before the turn's tools run and again on resume, so a call made in
  the same turn as the scoper's would slip through unapproved once the plan landed.
- **Full runs may use 60% of the minutes left** (`FULL_RUN_SHARE`). `record_plan` checks the path
  against the numbers and refuses inconsistent plans (a scaled plan that would fit in full, a scaled
  run that still doesn't fit, a hardware-only "scale-down").
- **No new approval kind.** The scaled experiment's own `long_run` request lists the scale-down in
  its summary and in an optional `scale_down` field, so approving the run approves the smaller
  settings. `contract/validate.py` would reject an unknown kind, and this needs none.
- **The probe projects from progress lines** (`agent/probe.py`): Keras/tqdm bars, `Epoch k/N`,
  `tree k of N` and similar. Start-up time counts as work done, so projections lean high, the safe
  side. A command that finishes inside the probe is simply the run.
- **Projections must be printed by code.** On a scaled plan a number answer needs
  `interval=[low, high]`, and the quote must show the value and both bounds (bounds at least as
  precise as the value), so the projection comes from a script in the run, not the model's arithmetic.
- **The harness judges the range**, never the agent, which still never sees expected values:
  in range and at most ±10% wide → verifiable within budget (`harness/score.py`).
- **Evidence tightened.** The quote must show the value (rounding and fraction/percent allowed);
  output of commands that only `echo`/`printf` and the `$ command` line at the top of a log no
  longer count. Replayed over every recorded answer in the 14 November runs: all 92 non-figure
  answers still pass, and the two "no answer" values from run d657 are refused.
- **Known gap:** `execute` with a long timeout is not gated by the plan (it is how long installs
  run), so a model could still start an experiment that way. The prompt says experiments go through
  `run_experiment`. Short `execute` calls (90 s) can run the code before the plan, which works as a
  free probe for quick scripts.
- **One real-model check** (Haiku 5.5, toy task, run dir `/mnt/vf/hack/tmp/pf-toy-034528` in CT 120,
  the last of the OpenRouter credit): the main agent handed the task to `scoper` first without being
  refused; the plan was full (0.1 min of 14.6 left) with the numpy pin flagged as a missing step; the
  experiment's approval came after the plan; 2/2 correct in 57 s. It used 367k tokens against about
  80-110k for the toy before: the scoper set up the environment and timed the script with `execute`,
  then the main agent read the repository again. The prompt now tells the main agent to build on the
  scoper's report, and the scoper to write memory with `edit_file` (it tried `echo >> /memories/...`,
  which the shell can't reach). Neither tweak has run on a real model yet.

### Overnight review and scoper fixes (branch `overnight-agent`, 15 November)

A reviewer subagent read the plan-first diff (`e590f75..f1d404f`) and found 13 defects; 12 are fixed here, each with a test.

- **The probe no longer trusts a lone progress bar.** A bar or a `step k/N` counter may be one loop of
  many (one epoch, one split): `agent/probe.py` now reports it as a lower bound and says to check the
  code for outer loops. A finished bar is ignored (a probe stopped during preprocessing said "1 minute"),
  and zero-based `Epoch 0/150` counters work.
- **Number checks are strict about what the value says.** A value counts as written (1.0 allows ±0.05,
  not ±0.5); fraction/percentage conversions apply only to numbers written with a decimal point or `%`,
  and never to zero; a number glued to a word (`r2`) or a range's second half (`0.44-0.46`) is read
  correctly; comma groups are read both as one number and as a list. Infinity and NaN are refused.
- **Echo evidence:** quoted text is set aside before splitting a command, so `echo "a; b"`, `| tee`,
  `(echo ...)`, `/bin/echo` and `X=1 echo` are all print-only, while `$(...)` runs real code and counts.
- **A stopped probe's output is not evidence** (its numbers come from an unfinished run).
- **A placeholder word can be a real answer** ("none") when the quote shows it.
- **Background runs started in parallel get distinct ids** (a lock), and a log is registered with its
  command before it can be searched.
- **An honest budget finish wins over a rejected approval** (a probe approval that timed out no longer
  turns a not-verifiable run into `rejected`).
- **The probe's time cap is computed once** (`probe_cap`), so its approval and its run agree.
- **Harness:** `classify` no longer hides a wrong or unexplained answer behind "not verifiable": any such
  answer makes the run partly reproduced or not reproduced.
- **Not fixed, known gap:** if the main agent starts `scoper` and `runner` in the same turn, the runner's
  experiment is checked after the scoper's plan lands, so a command written before the plan can run.

The three fixes the 15 November runs asked for:

- **Plan early.** The scoper prompt says to record the plan within about 8 minutes, to skip the probe for
  code with no heavy setting, and to estimate from the code instead of waiting for a slow setup. From
  minute 6 without a plan (a quarter of a short task's limit), every command's output to the model ends
  with a reminder (`Findings.plan_reminder`, `LoggingShellBackend.reminder`); the saved log, and so the
  evidence, stays clean.
- **The 60% rule counts from the task's limit, not the minutes left.** A full run may take at most 60% of
  the task's whole limit and must leave a reserve (15% of the limit, at least 3 minutes) for the answers
  (`Findings.full_run_allowance`). 3497606 (12.5 minutes projected, plan at minute 12 of 30) now gets a
  full run: the old rule allowed 10.8 minutes, the new one 13.5.

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

- **`permissions=` can't be used together with `execute`.** The feature map promised "deny
  writes to the paper's result files" through filesystem permissions. deepagents 0.7.38 refuses
  the combination outright. Replaced by an approval rule on the file tools (decision 25) plus a
  check at the end of the run for files that changed anyway.
- **The time limit ended runs as `failed`, not `timeout`.** The seconds left were rounded down,
  so with 0.7 s left every command was refused, the agent "finished" at once with no answers,
  and the report said `failed`. Now the remainder is rounded up and a refused command marks the
  run as out of time.
- **The result-judge found nothing and the run still validated.** The file `grep` tool matches
  literal text, so the pattern `test r2:|best model:` matched no line. No answer was recorded,
  the report was valid, the status was `failed`. Two lessons: search for one literal at a time,
  and a valid run directory says nothing about whether the questions got answered.

- **Turning tracing on emptied the scripted model.** With `LANGSMITH_TRACING=true` the run
  ended at once with no answers. The tracer serializes the model's fields, and one field was the
  script's generator, which got consumed before the first turn. Only the stand-in was affected
  (a real model has no such field), but it was found only because a test ran with a fake
  LangSmith key. The generator is now a private attribute.

## What is verified (scripted model, CT 120, 2026-11-14)

- `python -m agent.run` on the toy task writes a run directory that `contract/validate.py`
  accepts, with q1 = 0.4555 and q2 = ridge-weak parsed from the real output of `run.py`.
- The four subagents run in order, and every step is attributed to the subagent that did it.
- Approval paths: auto-approve, a human approve, a human reject (status `rejected`, null
  answers), no decision (rejected by timeout), and an approval raised inside a subagent.
- A write into `/repo` raises an `edit_source` approval with the diff; rejecting it is not fatal.
- A second run reads the remembered numpy fix and skips the install that fails (16 s down to 10 s).
- An approved edit is listed as approved; a file changed by a shell command is reported.
- In the Podman sandbox the toy reproduces, a file outside the workspace can't be read, and the
  container is gone afterwards.
- A background run returns control to the agent, is polled, and its output is cited as
  evidence, in the local shell and in Podman.
- A 1.5 MB command output is offloaded by deepagents and saved in `logs/`.
- Run over `limits.max_minutes` ends with status `timeout`.
- The model follows the key that is set; a missing key is named; `python -m agent.check` reports it.
- A fake LangSmith key does not break a run.
- 24 tests: 6 on the writer and findings, 5 on model selection, 13 end-to-end.

None of this says how a real model behaves with these prompts. That needs a key.
