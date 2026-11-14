# shared-project

## Repro Bot (the build)

An agent that runs a paper's code and checks whether the published numbers hold up. Built for LangChain's deepagents track.

- [contract/CONTRACT.md](contract/CONTRACT.md): the interface between the two halves, frozen. [contract/ROLES.md](contract/ROLES.md) says who builds which half and how to start as Role A.
- [harness/](harness/README.md): task loaders, scoring, web UI, batch runner (Role B). Try it: `python -m harness.server`, open http://localhost:8000, choose Demo replay.
- [agent/](agent/README.md): the deep agent (Role A). Results so far: [harness/SCOREBOARD.md](harness/SCOREBOARD.md); review notes of the autonomous run: [research/autonomous-run-2026-11-14.md](research/autonomous-run-2026-11-14.md).
- Plan: [research/repro-bot-build-plan.md](research/repro-bot-build-plan.md)

## Research

HackPrinceton research.

- [research/judging-criteria.md](research/judging-criteria.md): the four official judging criteria (creativity, utility, charity, avidity). Check ideas, scope and features against these
- [research/prizes/hackprinceton-fall-26-special-tracks.md](research/prizes/hackprinceton-fall-26-special-tracks.md): Fall 2026 sponsor tracks with their own criteria and prizes (CoStar, Amazon, Peri, LangChain, Arlequin AI, Capital One, Photon, ChatOverflow, Physical AI)
- [research/SUMMARY.md](research/SUMMARY.md): dated summary of the findings, newest conclusions last (Second Key ranked #1, ShiftProof dropped)
- [research/hackathon-ideas-final.md](research/hackathon-ideas-final.md): the 15 researched and scored ideas
- [research/hackathon-ideas-round2.md](research/hackathon-ideas-round2.md): 12 new event-day ideas (brainstorm, not researched), covering Entertainment, Science & Discovery and Sustainability
- [research/hackathon-ideas-round3-deepagents.md](research/hackathon-ideas-round3-deepagents.md): best Deep Agents fit among round 2, plus 3 new researched ideas (Odyssey, Council Thread, IEP Case File)
- [research/langchain-deepagents-eval.md](research/langchain-deepagents-eval.md): LangChain deepagents track only: Repro Bot vs Second Key vs Cash Drawer, scored on the track questions + rubric; pick is Repro Bot on CORE-Bench tasks
- [research/repro-bot-build-plan.md](research/repro-bot-build-plan.md): build plan for Repro Bot (plan only, nothing built): two roles (Agent, Harness), a frozen file-based contract between them, continuous loops, MVP human-testable at T+14 h
- [research/hackprinceton-plan.md](research/hackprinceton-plan.md): build plan for a team of 3
- [research/specs/](research/specs/): specs for Second Key, Neighbor Call, ShiftProof and backups
- [research/prizes/](research/prizes/): prize lists from Fall 2025, Spring 2026 and Fall 2026 (tracks and MLH prizes; the sponsor tracks are in the special-tracks file above)
- [research/hackprinceton-winners-analysis.md](research/hackprinceton-winners-analysis.md): what past winners built
- research/hackprinceton-materials.html: everything above as one page (download and open in a browser)
