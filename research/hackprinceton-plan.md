# HackPrinceton Fall 2026: picks + build plan for a team of 3
Event: Nov 13-15 2026, 36 h, Princeton (JRR Building). Log: `hackprinceton-loop.md`. Track fit: `hackprinceton-track-fit.md`.
Rules that shape the plan: public repo **created during the event**; **2-min live demo Sunday** 9:30-2 (required), optional <=2-min video; AI-assisted code "welcome and encouraged"; rubric = creativity, utility, charity, avidity; track winners can't also win Best Overall.
Instagram reels from the developer: not read (instagram.com blocked). Paste captions/what they say and I'll fold them in.

## 1. Picks (refined again 2026-11-09 with Devpost winner data, live APIs and the two reels)
| Rank | Idea | Track | Sponsor prizes to stack | Spec |
|---|---|---|---|---|
| 1 | **Second Key** (bank-side hold during a live scam call) | Business + Enterprise | Capital One Best Financial Hack ($1,000, 1 winner), Photon (5 winners last fall) | hp-spec-second-key.md |
| 2 | **Neighbor Call** (now: heat, cold and smoke check-ins) | Healthcare | Photon; Amazon Practical AI (3 winners) | hp-spec-neighbor-call.md |
| 3 | Team's choice: ClearPath Web (Education, accessibility) or Bill Rescue with an energy-burden map (Sustainability) | | | hp-spec-backups.md |
Why: see `hackprinceton-winners-analysis.md`. Past HackPrinceton winners: Healthcare = monitor→alert (VITAL), B+E = workflow agents (LEGR, Jigsaw), Sustainability = geospatial/IoT. **Photon/iMessage shows up in many winners' stacks**, so make iMessage the user interface either way.
Neighbor Call's live demo: November has no heat alerts but does have live winter-storm alerts. Cold killed ~2,520 Americans in 2023 vs heat 2,391 in 2024, so the scope is now all extreme weather, demoed with real NWS alerts from that weekend.
Dropped: ShiftProof (CMS Emmy exists). Prior art seen at HackPrinceton: NannyCam (S26, eldercare finances via iMessage), Guardian (falls), Lume (won Education F25, seniors).

## 2. Event strategy (from the reels + winner data)
- Friday night: run `event-day-brainstorm-prompt.md` against the real prize list (~1 h). Prefer the stack with less competition (sponsor prizes with several winners: Photon, Amazon).
- In the first 3 hours, spend ~20 min at the chosen sponsors' booths and ask what would wow them; design the demo's first 30 seconds around that.
- Judges see ~2-3 minutes: one live moment (a phone rings / a transfer freezes), a visible agent-to-agent conversation on screen, then the architecture slide.

## 3. Team of 3: roles
| Role | Owns | Typical files |
|---|---|---|
| A. Agent/voice lead | LLM prompts, tool calls, Twilio/Photon, rules engine, red-flag logic | `server/agent/*`, `server/telephony/*` |
| B. Product/UI lead | Next.js screens, dashboard, demo "simulate" controls, visual polish | `app/*`, `components/*` |
| C. Data/integration + pitch lead | External APIs (NWS/AirNow or Nessie), DB schema, seed data, deploy, Devpost text, slides, demo script | `lib/data/*`, `db/*`, `README`, pitch |
Hosting: Next.js UI on Vercel; one persistent Node service (Railway/Fly or a laptop + tunnel) for the Twilio WebSocket and the Photon loop.
Everyone codes with Claude Code (AI help is allowed). Coordination: the **agent board** (projects/agent-board: a pinned GitHub issue; agents post when done and `board wait` for @mentions; ownership table in CLAUDE.md). Tested 2026-11-09. Each person runs 1-2 sessions in their own git worktree on their own folder. Merge to main every ~2 h, each owner merging only their own branch after reading `git diff`.

## 4. Stack (one repo, one language, few moving parts)
- Next.js (App Router, TypeScript) on Vercel; API routes for the agent; Supabase (Postgres + auth) or SQLite for speed.
- Claude API (tool use) for reasoning; deterministic TypeScript for rules/red flags (judges trust "the LLM never decides alone").
- Voice: Twilio Voice + Media Streams with a realtime speech model, or simpler: Twilio `<Gather>` speech + TTS (more reliable in 36 h).
- Messaging: Photon Spectrum SDK (iMessage/SMS) for the sponsor prize; Twilio SMS fallback.
- Twilio: **upgrade before the event (~$20)**. Trial accounts only call 5 verified numbers, play a trial message, allow 1 conference, and include 75 voice / 30 Media Streams minutes. That breaks a live judge demo.

## 5. Before the event (no code, since the repo must be created at the event)
- Pick the idea + a backup by Wed Nov 11; write the 1-page spec, data contracts (JSON shapes), the demo script and the 2-min pitch outline.
- Accounts + keys: Anthropic, Twilio (upgraded, number bought), Photon (free $100 credit), Vercel, Supabase, NWS (no key, needs User-Agent) / AirNow key or Capital One Nessie key.
- Extra keys found necessary (2026-11-09): AirNow API key (free, docs.airnowapi.org), Capital One Nessie key (nessieisreal.com; use **https**), Photon project ID/secret (app.photon.codes, $100 free credit).
- The agent-board script is a pre-existing tool, like a library: keep it in its own repo, not in the hackathon repo. If unsure, ask an organizer Friday.
- Each person reads the docs for their part (Photon Spectrum, Twilio Media Streams, NWS alerts API).
- Prepare a `CLAUDE.md` + `TEAM.md` text (owners, contracts, "don't touch others' folders") to paste in at hour 0.

## 6. 36-hour timeline (Fri evening -> Sun 9:30 judging)
| Hours | Goal |
|---|---|
| 0-2 | Create repo, paste CLAUDE.md/TEAM.md, scaffold, deploy "hello" to Vercel, agree on contracts |
| 2-6 | Each role builds its vertical slice against mocked contracts |
| 6 | **Mentor check** (MindPad's first idea was rejected; get feedback early) |
| 6-12 | **Integration #1: ugly end-to-end demo works** (call -> agent -> dashboard) |
| 12-20 | Sleep in staggered 3-4 h shifts (always 2 awake); polish the main path; sponsor integrations |
| 20-26 | Integration #2; edge cases that appear in the demo only; seed realistic data |
| 26 | **Feature freeze.** Record the backup video (optional upload, but have it in case live telephony fails) |
| 26-32 | Devpost write-up (problem, data, how built, future plans = "avidity"), slides, README |
| 32-35 | Rehearse the 2-min demo 5+ times with a timer; bug fixes only |
| 35-36 | Submit Devpost + repo link; test the demo on venue Wi-Fi + hotspot |

## 7. Demo/pitch rules (2 minutes)
0:00-0:15 the number (e.g. "41,000 Americans die from smoke each year; 15.8M seniors live alone"). 0:15-1:30 live demo of one path, no menus. 1:30-1:50 how it works (agent + deterministic safety). 1:50-2:00 what's next + who it's for. Have the video ready if the phone network fails.

## 8. Risks
- Telephony on venue networks: keep a hotspot + prerecorded fallback.
- Over-scoping: one user, one city/state, one happy path + one failure path.
- Usage limits: Claude Code on a Pro plan can hit limits mid-hackathon, so stagger heavy sessions and keep model calls in the app cheap (Haiku/Sonnet for runtime).
