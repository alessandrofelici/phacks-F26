# Harness (Role B)

Everything around the agent: tasks in, results out, and the screen a human uses. It talks to the agent only through `contract/CONTRACT.md`. Python 3.11+ and the standard library only, so there's nothing to install.

## Use it

```
python -m harness.server            # then open http://localhost:8000
```

| Command | What it does |
|---|---|
| `python -m harness.server [--port 8000]` | The web UI: start a run, watch it, approve or reject, read the scored report |
| `python -m harness.corebench list --max-mb 5 --language Python` | Show CORE-Bench (train split) tasks with small downloads |
| `python -m harness.corebench fetch 6460826 4098236 [--level hard]` | Download capsules into `tasks/` and write their answer keys |
| `python -m harness.batch --label "cycle 1"` | Run every task unattended, score it, add a row to `harness/SCOREBOARD.md`, print failures grouped for triage |
| `python -m harness.score runs/<run_id>` | Score one run |
| `python -m harness.fake_agent --task … --run …` | Stand-in agent that replays the golden run (`--scenario crash` or `wrong`, `--speed 0`) |

The real agent is started as `python -m agent.run …` (contract section 3). To point at something else, set `REPRO_AGENT_CMD`.

## Tester script (no terminal needed after the server is up)

Until Role A's agent lands, choose **Demo replay**: it plays back a recorded run of the toy paper and follows the approval protocol for real, but calls no model.

1. Open http://localhost:8000. Under **Start a run**, pick *Toy linear regression* and press **Start run**.
2. Watch **Plan** fill in and **What the agent did** grow: a failed `pip install`, the fix, and a "Remembered for next time" line.
3. A yellow box asks to run a command. Press **Approve**.
4. When it finishes, **Report** shows `0.4555` and `ridge-weak`, each marked *Matches* with the reference, the quoted evidence line (click the file name to see the log), and the problem it fixed.
5. Start the same paper again. This time the timeline says "Checked memory: Found a remembered fix" and there's no failed install.
6. Start it a third time and press **Reject**. The run ends as *Stopped by reviewer* with no answers.

To see the run from the start again, delete `runs/` (it also holds the demo's memory).

## Where things are

| Path | What |
|---|---|
| `common.py` | paths, task lookup, reading events and approvals |
| `runs.py` | starting, watching and stopping agent processes; run status |
| `score.py` | scoring, following CORE-Bench's rules (see its docstring for the one difference) |
| `corebench.py` | CORE-Bench loader |
| `server.py`, `static/index.html` | the web UI |
| `batch.py` | unattended batch runs and the scoreboard |
| `answers/` | answer keys. The agent must never read this folder. Only the toy's key is committed |
| `BACKLOG.md`, `NOTES.md` | this role's loop |
