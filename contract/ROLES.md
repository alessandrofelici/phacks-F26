# Who builds what

| Role | Folder | Who | Status |
|---|---|---|---|
| **B: Harness** | `harness/` | virkahmed's agent (started first, also did the kickoff in `contract/`) | MVP pieces built and tested with a fake agent; see `harness/README.md` |
| **A: Agent** | `agent/` | the second agent to start | **open: start here** |

## Starting as Role A
1. Read `contract/CONTRACT.md` (the interface) and `research/repro-bot-build-plan.md` sections 1, 4 and 5 (your scope, your loop, your timeline).
2. Your job: make this command work, writing a valid run directory:
   ```
   python -m agent.run --task contract/fixtures/tasks/toy-linreg --run runs/my-first-run
   python contract/validate.py run runs/my-first-run --task contract/fixtures/tasks/toy-linreg
   ```
   Correct answers for the toy: q1 = 0.4555, q2 = ridge-weak. `contract/fixtures/runs/golden/` shows what a good run looks like.
3. Only write inside `agent/`. Don't read `harness/` (it holds the answer keys) and don't wait for it: the validator is your check.
4. Need the contract changed? Write it in `contract/CHANGES.md` and keep going.
5. LangChain docs are wired in as MCP servers (`.mcp.json`): `docs-langchain` and `reference-langchain`.

Open decisions that are yours: the sandbox provider, the `deepagents` version pin, the model.
