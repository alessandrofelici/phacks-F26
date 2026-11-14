# Harness notes (Role B)

Role B's own log. Role A doesn't need to read it.

## 2026-11-14, loop 1 (kickoff + first build)
- Wrote contract v1 alone because Role A hadn't started; the choices that go beyond the plan are listed in `contract/CHANGES.md` for A to object to.
- Tested with the fake agent: approve, reject, wrong answer, crash, and the remembered-fix second run all produce run directories that pass `contract/validate.py`, and the server reports the right status for each.
- **Not verified:** the web page in a browser. Chrome wasn't reachable from this session.
- CORE-Bench: using the open train split (45 tasks). The test split is encrypted to keep it out of training data, so it isn't decrypted or stored here. Several capsules are under 1 MB.
- Scoring follows CORE-Bench (95% prediction interval over its 3 reference runs) plus 0.5% slack, because many tasks have three identical reference values, which would otherwise demand an exact float match.
- Capsules assume Code Ocean's layout (`/code`, `/data`, `/results`). The loader says so in `instructions`; whether that's enough for the agent is something checkpoint 2 will show.
- cb-4098236 has no `data/` folder at all; its script may generate or download data. Check before making it an MVP task.
