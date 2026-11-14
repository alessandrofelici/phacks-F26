# Repro Bot build plan: two roles, one contract, continuous loops (2026-11-14)
Plan only. **Nothing is built yet.** Idea and rationale: `langchain-deepagents-eval.md`.

Shape of the plan:
- **Two roles**, each a coding agent with a human owner, each running its own continuous build loop.
- **One frozen contract** between them. Each role knows exactly what the other is building from the contract, and neither follows the other's progress while building.
- **MVP a human can test at T+14 h.** After that the loops don't stop: they switch from "build the MVP" to "run the task set, fix the top failure, repeat".

Hours are relative to kickoff (T+0). *Check:* the submission deadline and demo time, then set the freeze hour in the last section.

---

## 1. The two roles
The split is along the one boundary that's cleanest in this product: the agent on one side, everything that feeds it and shows its work on the other.

| | **Role A: Agent** | **Role B: Harness** |
|---|---|---|
| Builds | The deep agent that reproduces a paper | Everything around the agent: tasks in, results out, the screen a human uses |
| Owns (only this role writes here) | `agent/` | `harness/` |
| Consumes | A task directory (contract §3.1) | A run directory (contract §3.2) |
| Produces | A run directory | Task directories, scores, the UI, the batch runner |
| Scope | `deepagents` graph, subagents (paper-reader, env-builder, runner, result-judge), sandbox + `execute`, approvals via `interrupt_on`, memory of fixes, skills, file permissions | CORE-Bench loader, answer key and scorer, web UI (start a run, live timeline, approve/reject, report), batch eval runner, scoreboard, failure grouping |
| Tests itself with | The toy task fixture, no UI needed | The golden run fixture and a fake agent, no real agent needed |
| Never does | Read `harness/`, see the answer key, build UI | Read `agent/`, call the LLM for reproduction, change agent prompts |

The third teammate (if there is one) owns the checkpoints, the pitch and `FAILURES.md`, and is the tester at T+14.

## 2. How the two stay in sync without status updates
Three things are shared, and nothing else:

1. **`contract/CONTRACT.md`**: the interface in §3, frozen at kickoff.
2. **`contract/fixtures/`**: one toy task and one golden run that both roles validate against (§3.4).
3. **`contract/CHANGES.md`**: the only channel between the roles while building. A role that needs the contract changed writes a proposal there and keeps working.

Rules:
- A role doesn't read the other's folder, commits or notes. It builds against the contract and the fixtures.
- Contract changes take effect **only at checkpoints** (§5), when both humans agree. Between checkpoints a role may only add optional fields; the other side must ignore fields it doesn't know.
- Both roles commit to `main` in their own folder, so there are no merge conflicts and no need to coordinate pushes.
- Each role keeps `agent/NOTES.md` or `harness/NOTES.md` for its own loop (what it's on, what failed). The other role doesn't read it; the humans do at checkpoints.

## 3. The contract (v1)
The boundary is **files on disk plus one command**. That keeps the roles independent (either side can be faked with a folder of files), and a human can inspect every run by opening the folder.

### 3.1 Task directory (B writes, A reads)
```
tasks/<task_id>/
  task.json
  repo/            # the paper's code and data, as published
  paper.md         # optional: paper text or abstract
```
```json
// task.json
{
  "contract_version": 1,
  "task_id": "toy-linreg",
  "title": "Toy linear regression",
  "source": "fixture | core-bench | arxiv",
  "paper_url": null,
  "questions": [
    {"id": "q1", "text": "What is the test R^2 reported by run.py?", "type": "number"},
    {"id": "q2", "text": "Which optimizer does the best model use?", "type": "string"}
  ],
  "limits": {"max_minutes": 15, "gpu": false, "network": true}
}
```
The answer key is **never** in the task directory. B keeps it in `harness/answers/<task_id>.json`, outside anything the agent can read.

### 3.2 Run directory (A writes, B reads)
```
runs/<run_id>/
  events.jsonl                 # append-only, one JSON object per line
  report.json                  # written once, at the end
  approvals/<id>.request.json  # A writes
  approvals/<id>.decision.json # B writes
  logs/                        # optional: full command output
```
```json
// one line of events.jsonl
{"seq": 12, "ts": "2026-11-14T03:10:22Z", "type": "tool_call", "agent": "env-builder", "data": {"tool": "execute", "summary": "pip install -r requirements.txt", "ok": false}}
```
Event types (B must ignore unknown ones): `run_started`, `todo_updated` (data = the full todo list), `subagent_started`, `subagent_finished`, `tool_call`, `approval_requested`, `approval_resolved`, `memory_written`, `answer_found`, `error`, `run_finished`.

```json
// report.json
{
  "contract_version": 1,
  "task_id": "toy-linreg",
  "run_id": "r-0001",
  "status": "completed | failed | timeout | rejected",
  "answers": [
    {"question_id": "q1", "value": 0.91, "evidence": {"file": "logs/run.txt", "quote": "test r2: 0.91"}, "confidence": "high | medium | low"}
  ],
  "obstacles": [
    {"stage": "env", "summary": "numpy 2 breaks old sklearn", "fix": "pinned numpy<2", "resolved": true}
  ],
  "usage": {"wall_seconds": 212, "tokens": 48000},
  "trace_url": null
}
```
A question the agent couldn't answer still appears, with `"value": null` and the reason in `obstacles`.

### 3.3 The command, and approvals
```
python -m agent.run --task tasks/<task_id> --run runs/<run_id> [--auto-approve]
```
- Exit code 0 = `report.json` was written (whatever its status); non-zero = crash, and B shows the run as crashed.
- **Approvals:** when the agent hits a gated action it writes `approvals/<id>.request.json`, emits `approval_requested`, and waits. B's UI shows it; the human's click writes `approvals/<id>.decision.json`. A resumes. No decision within 10 minutes = reject.
```json
// request
{"id": "a1", "kind": "long_run | edit_source | publish", "summary": "Run train.py (est. 6 min)", "command": "python train.py", "diff": null}
// decision
{"id": "a1", "decision": "approve | reject", "note": "", "by": "human"}
```
- `--auto-approve` is for B's batch runs.

### 3.4 Fixtures (made together at kickoff, then frozen)
- `contract/fixtures/tasks/toy-linreg/`: a 30-line script with a requirements file that has one deliberate version conflict, so even the toy needs a fix. Runs in under a minute.
- `contract/fixtures/runs/golden/`: a hand-written, valid run directory for the toy task, including one approval and one obstacle.
- `contract/validate.py`: checks any task or run directory against v1. Both roles run it in their loop. *It's the only code written before the roles split.*

## 4. The loop each role runs
Same loop for both roles, run continuously from the end of kickoff until freeze:

1. **Read** `contract/CONTRACT.md` and `contract/CHANGES.md` (in case a checkpoint changed something), then the role's own `BACKLOG.md`.
2. **Pick** the top backlog item. Cut it to a slice that can be finished and checked in about 45 minutes.
3. **Build** it, in the role's own folder only.
4. **Check** against the fixture, never against the other role's code:
   - A: run the toy task for real → `validate.py` on the run directory → is the answer right?
   - B: point the UI/scorer/batch runner at the golden run (or the fake agent that replays it) → does it show and score correctly?
5. **Commit and push** if the check passes. If it fails twice, write the failure into `NOTES.md` and `FAILURES.md` (the LangChain "what did you fail on" answer), and take a smaller slice.
6. **Blocked by the contract?** Write a proposal in `contract/CHANGES.md`, work around it with an optional field, move to the next item. Don't wait.
7. Go to 1.

The loop never asks "what is the other role doing?". It only asks "does my side still satisfy the contract?".

## 5. Timeline to the MVP (T+14)
Checkpoints are the only moments the two sides meet. Each is a 15-20 minute, human-run integration: real agent, real harness, fix or log what breaks, adopt or reject `CHANGES.md` proposals.

| Hours | Role A: Agent | Role B: Harness |
|---|---|---|
| **T+0 to 1: kickoff (together)** | Freeze contract v1, write the two fixtures and `validate.py`, choose the sandbox provider, get API keys, set up LangSmith tracing | same |
| T+1 to 6 | Single deep agent with `execute` in a sandbox solves the toy task and writes a valid run directory; then the approval wait/resume; then `todo_updated` and `tool_call` events | CORE-Bench loader → 3 real task directories + answer key; scorer; UI on the golden run: timeline, todo list, approval buttons, report view |
| **T+6: checkpoint 1** | Real agent runs the toy task, watched in the real UI, with a human clicking approve | |
| T+6 to 10 | Split into subagents (env-builder, runner, result-judge); large logs offloaded; first easy CORE-Bench task | "Start run" button that launches the command; live tail of `events.jsonl`; batch runner with `--auto-approve`; scoreboard |
| **T+10: checkpoint 2** | One real CORE-Bench task end to end, scored | |
| T+10 to 13 | Memory of fixes across runs; file permissions so the agent can't edit result files; reliability on the 3 tasks | Failure view (obstacles grouped by stage); crashed/timeout states; a one-page tester script |
| T+13 to 14 | Stabilize only, no new features | Stabilize only |
| **T+14: MVP test** | A human who didn't build it follows the tester script | |

### What "human testable" means at T+14
A teammate who built neither side can do all of this from the UI, with no terminal:
1. Pick one of 3 tasks (the toy and 2 real CORE-Bench tasks) and start a run.
2. Watch the plan and the subagents' steps appear live.
3. Get an approval prompt, and both approve and reject work.
4. Read a report with an answer per question, the evidence quote, and the obstacles hit.
5. See the score against the answer key (which the agent never saw).
6. Start the same task again and see the agent reuse a remembered fix.

If something on this list is missing at T+12, cut 6 first, then the second real task. Never cut 3 or 5: approvals and honest scoring are the pitch.

## 6. After the MVP: the loops keep running
From T+14 the two build loops stay exactly as in §4, but the backlog is now fed by an **improvement cycle** of about 3 hours:

1. **Run:** B's batch runner runs the whole task set unattended (start with 5 tasks, grow toward 20).
2. **Read:** the scoreboard and failure view group what went wrong.
3. **Triage** (humans, 10 minutes): each failure group goes to one role's backlog. Agent behaviour (wrong fix, gave up, bad answer extraction) → A. Harness problems (bad task conversion, scorer too strict, UI unclear) → B.
4. **Build:** both roles loop on their backlog until the next run.
5. Record the score for the cycle in `SCOREBOARD.md`. The score over cycles is the demo's closing slide.

Standing backlog when triage produces nothing urgent, in this order:
- A: async subagents so long runs continue in the background → skills (`SKILL.md` for conda, R, headless notebooks) → harder CORE-Bench levels → arXiv-link mode (find the repo, extract the claimed numbers, verdict per claim).
- B: more tasks → side-by-side "run 1 vs run 2" to show memory working → LangSmith trace link per run → the demo path (one known-good task, one pre-recorded run as fallback).

Each feature A adds from that list is another row in the "did you use all of deep agents" table, so keep `langchain-deepagents-eval.md`'s feature map updated with where it shows in the trace.

**Freeze:** 6 hours before submission, both loops switch to bugs on the demo path only. The last improvement cycle's score is the one that goes in the pitch.

## 7. Risks to settle at kickoff
- **Sandbox provider:** pick the one with working free credits in the first 30 minutes (Modal, E2B, Daytona or LangSmith sandboxes are the documented backends). *Check* before T+1; this is A's biggest unknown.
- **CORE-Bench access:** the dataset has easy, medium and hard levels, and tasks are large code capsules. *Check* at kickoff: how to download and decrypt the task file, capsule sizes, and which tasks run in under 5 minutes without a GPU. Pick the 3 MVP tasks from those. This is B's biggest unknown.
- **Where runs execute:** contract v1 assumes the agent process and the harness share a disk (one laptop or one small VM). If that changes, only the transport changes, not the file formats.
- **deepagents version:** pin it at kickoff. Planning (`write_todos`) and several features are opt-in or version-gated in current releases.
- **Rules:** the code repo must be created during the event. This repo was (Nov 13), so build here or in a new repo made now.
