# Plan: Hackathon idea research (15 ideas)

Status: DONE 2026-11-07 16:21 UTC (started 16:01). Result: hackathon-ideas-final.md (4 cycles).
Output file: `board/notes/hackathon-ideas.md` (working doc). Summaries go to `board/FINDINGS.md`.

## Goal
Produce 15 solid hackathon ideas. Each idea must be:
1. Based on recent research or articles: published within ~2 years (since ~Nov 2024). For agentic/LLM-agent topics, prefer the last ~12 months (since ~Nov 2025).
2. Aimed at a defined, sizeable group that judges (engineers) and college students understand: e.g. immigrants/globalization, US citizens/voters, college students, older adults, small businesses, gig workers, rural residents, people with disabilities, non-English speakers, patients/caregivers, K-12 teachers. Size should be backed by a number with a source (Census, BLS, Pew, WHO, etc.).

Final format per idea (exactly this order):
1. Name
2. Target Audience (with size estimate + source)
3. Solution
4. Relevance (the paper/article it builds on, with link and date, and why now)
5. One line pitch
6. Tech stack

## Phase 0: Ground truth on what wins (1 pass, before any brainstorming)
Use the `research` skill. Sources to check:
- Devpost winners pages for large hackathons 2024-2026: TreeHacks, HackMIT, PennApps, CalHacks, HackTheNorth, MHacks, LA Hacks, HackPrinceton, plus AI-sponsored ones (Anthropic, OpenAI, Google/Gemini, AWS, Microsoft) and MLH "Best of".
- Write-ups / blog posts on "what judges look for", and recaps of winning projects.
Record, in a table in the notes: project name, event, year, category, target group, core tech, why it won (if stated).
Then extract patterns: common target groups, track/prize categories, demo style (live demo > slides), scope that fits 24-48h, what tech was rewarded (agents, voice, vision, on-device, MCP/tool use, browser automation), and what got overused/penalized (generic chatbots, thin GPT wrappers).
Output: "Winning patterns" section, 10-15 bullets. Add a short FINDINGS.md entry.

## Phase 1: Research recent sources (seed pool)
Collect ~30-40 candidate sources across these lanes, ~4-6 each:
- Agentic AI: computer-use / browser agents, MCP and tool use, multi-agent systems, agent evaluation and safety, long-horizon agents, voice agents (arXiv cs.AI/cs.CL/cs.HC, Anthropic/OpenAI/Google/DeepMind blogs, HF papers).
- Accessibility and assistive tech (CHI/ASSETS 2025-2026 papers).
- Health and caregiving (NEJM AI, npj Digital Medicine, health AI news).
- Civic tech, government services, voting, legal aid (Pew, Code for America, GovTech).
- Education and college students (learning science + LLM tutoring studies).
- Globalization, migration, language access, remittances (World Bank, UN, MPI).
- Climate, energy, disaster response.
- Work and economy: gig workers, small businesses, job displacement by AI (BLS, Brookings, Anthropic Economic Index, etc.).
- Security, scams and fraud targeting specific groups (FTC data, deepfake/voice-clone research).
For each source: title, link, date, 1-2 line key finding, which group it affects. Reject anything older than the date window.

## Cycle (repeat until 15 ideas pass the bar; expect 2-3 cycles)
Each cycle:
1. **Research**: fill gaps from the previous review (weak lanes, ideas that lacked a source, unclear audience size).
2. **Brainstorm 10-15 ideas**: combine (recent finding) x (defined group) x (winning pattern). Draft each in the 6-field format. Keep a backlog of rejected ideas with the reason.
3. **Refine**: sharpen the audience (narrow enough to demo, big enough to matter), tighten the pitch to one line, pick a concrete demo moment, pick a stack that a 2-4 person team can ship in 24-48h.
4. **Review implementation effects and outcomes**, score each idea 1-5 on:
   - Source recency and strength (peer-reviewed or credible outlet, within window)
   - Audience clarity and size (has a number + source)
   - Feasibility in a hackathon (APIs available, no data we can't get, no hardware we lack)
   - Demo-ability (a clear "wow" moment in 2-3 min)
   - Novelty vs past winners (not a clone of a Phase 0 winner, not a generic chatbot)
   - Impact and risk (real outcome for users; privacy, safety, legal, misuse concerns noted)
   - Judge appeal (fits common prize tracks)
   Pass bar: total >= 25/35 and no score below 3. Keep passing ideas, drop or rework the rest.
5. **Log**: append the cycle's results to `board/notes/hackathon-ideas.md` (cycle number, ideas kept, dropped and why, open gaps), so a later session can continue.
Stop when 15 ideas pass, with spread across at least 6 lanes and at most 3 ideas per lane. Cap at 4 cycles; if still short, report what is missing.

## Final deliverable
- `board/notes/hackathon-ideas.md`: 15 ideas in the 6-field format, ranked by score, each with source links; then the scoring table; then the winning-patterns summary.
- `board/FINDINGS.md`: dated entry with the top 5 one-liners and a pointer to the full file. State what was not verified (e.g. audience numbers taken from secondary sources).
- Push notification when finished.

## Budget rules (Pro plan, shared limits)
- Work inline; no subagent fan-out. At most 1 helper agent (Sonnet) if a lane needs bulk reading.
- Skim abstracts and summaries, not full papers. Fetch full text only for the final 15 sources.
- Save notes after every phase so work survives a usage limit.
- Blocked domains go to `ALLOW_REQUESTS.md`; use another source.
