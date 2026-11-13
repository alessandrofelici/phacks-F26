# HackPrinceton Fall 2026 research loop (started 2026-11-08 17:41 UTC)
Event: Nov 13-15 2026, 36 h, Princeton. Tracks: Education, Entertainment, Sustainability, Healthcare, Business + Enterprise, Science + Discovery. Judging: creativity, utility, charity, avidity.
Inputs: 15 ideas (hackathon-ideas-final.md), track fit (hackprinceton-track-fit.md). Two IG reels from developer: BLOCKED (instagram.com requested); need captions from developer.
Goals: (1) best ideas per track + refine; (2) best way to build with a team of 3 in 36 h.
Cycles:
 A. HackPrinceton intel: past winners (Fall 2025, Spring 2026), Fall 2026 Devpost/sponsor tracks, rules (AI tools, pre-built code, team size).
 B. Re-score: track fit x HackPrinceton winner patterns x rubric; refine top 1-2 per track; fill gaps (Sustainability, Science+Discovery, Entertainment) with new ideas if strong.
 C. Team-of-3 build: roles, 36 h timeline, stack/scaffold, AI-assisted workflow, demo + Devpost submission.
 Repeat B/C until a short list (top 3 + per-track pick) is stable. Log each cycle here.

## Cycle A (HackPrinceton intel)
- Fall 2026 sponsors (hackprinceton.com via search): CoStar, Amazon, Salesforce, Peri, Arlequin, D. E. Shaw, Capital One, Photon, Scale AI, LangChain, ChatOverflow, Projects Board, COS Dept, Justin Bojarski. Speaker: Stephen Wolfram. $15K+ prizes, 800+ hackers. Fall 2026 Devpost not found yet.
- Rules (Spring '26 Devpost): "AI-assisted code is welcome and encouraged." Older: public repo made at event + <=2 min video. Track winners can't also win Best Overall (Spring '26 listing; Asclepius contradicts, but its extra wins were sponsor tracks).
- Winners: Spring '26 Best Overall = Asclepius (on-device Gemma privacy proxy stripping PHI before cloud LLMs for clinical-trial staff; + Regeneron track; team of 4 strangers). Fall '25 Best Overall = MindPad (multimodal voice/gesture/sketch workspace; + Best Use of Gemini + Amazon Practical AI; ~200 teams; first idea rejected by mentors a day before finals).
- Fall '25 prize list: Best Overall (Anthropic/OpenAI/Amplitude credits), Healthcare (Daylight), Business + Enterprise ($3K cash), Sustainability, Education + Entertainment, Rookie, Hardware, Amazon Practical AI x3, YC challenge x4.
- Sponsor prize patterns: Photon = "Agents in iMessage" (must use Spectrum SDK; $400 + $300 credits + interview; Photon also doubles hackathon winnings via Built with Photon). Capital One = "Best Financial Hack" (optional Nessie API, ~$250-300/member). Arlequin = Paris decision-intelligence AI (topological NNs, €28M Series A). Peri: unknown. CoStar: real estate (Apartments.com owner), prize unknown.
- Implication: practical, privacy-aware AI that takes action wins here; stacking 1 track + 1-2 sponsor prizes is realistic.

## Cycle B (re-score for HackPrinceton) — 2026-11-08
Judging facts: 2-min in-person demo Sunday 9:30-2 (required), optional <=2-min video, public repo created during the event, rubric creativity/utility/charity/avidity (avidity = passion shown in the pitch, Devpost text, future plans, polish).
Score = TrackFit + HP-pattern (practical AI that acts/privacy/multimodal live demo) + 36h-feasibility-for-3 + Charity + Creativity (each 1-5) + sponsor bonus (0-2).
| Idea | Best track | Fit | Pattern | Feas | Charity | Creat | Sponsor | Total |
|---|---|---|---|---|---|---|---|---|
| Neighbor Call | Healthcare | 5 | 4 | 4 | 5 | 4 | +1 Photon | 23 |
| Second Key | Business + Enterprise | 4 | 5 | 3 | 5 | 3 | +2 Capital One, Photon | 22 |
| ShiftProof | Healthcare | 3 | 4 | 4 | 5 | 4 | +1 Photon | 21 |
| Bill Rescue (+efficiency) | Sustainability | 4 | 3 | 5 | 5 | 3 | +1 Capital One | 21 |
| Honest Nurse | Healthcare | 5 | 4 | 4 | 4 | 3 | 0 | 20 |
| ClearPath Web | Education | 3 | 4 | 4 | 5 | 4 | 0 | 20 |
| Fair Shift | Business + Enterprise | 4 | 3 | 4 | 4 | 4 | +1 Capital One | 20 |
| Puente Tutor | Education | 5 | 3 | 4 | 4 | 3 | 0 | 19 |
| Say It, Sign It | Education | 3 | 4 | 4 | 5 | 3 | 0 | 19 |
| Loan Lens | Business + Enterprise | 4 | 3 | 4 | 4 | 3 | +1 Capital One | 19 |
| TrialBridge (NEW) | Healthcare / Science + Discovery | 5/4 | 4 | 4 | 4 | 2 | 0 | 19 |
| AgentReady Main Street | Business + Enterprise | 5 | 4 | 4 | 2 | 3 | +0.5 | 18.5 |
| Citizen Ready (tutor-first) | Education | 4 | 4 | 4 | 4 | 2 | 0 | 18 |
| Status Keeper | Education | 2 | 4 | 4 | 4 | 4 | 0 | 18 |
| Answer in Time | none (Best Overall) | 1.5 | 4 | 4 | 5 | 3 | +0.5 CoStar? | 18 |
| First Rung | Education | 4 | 3 | 4 | 3 | 3 | 0 | 17 |
NEW TrialBridge: patient-side trial finder built on TrialGPT (Jin et al., Nature Communications 2024, NIH/NLM, code github.com/ncbi-nlp/TrialGPT; 87.3% criterion accuracy vs 88.7-90% experts, -42.6% screening time). Creativity low: NIH tool exists and Asclepius won the clinical-trials space in Spring '26. Only pick it if a clinical-trials sponsor track returns.
Gaps: Entertainment has no good fit (low "charity"); Science + Discovery only via TrialBridge.

## Cycle C (team of 3) — see hackprinceton-plan.md

# Refinement run (developer asked for 5 h): started 2026-11-09 00:07 UTC, hard stop 05:07 UTC
## Work cycle (one idea per cycle, target 30-45 min)
R1 Facts: re-verify every number used in the pitch (2 sources; prefer primary).
R2 Tech: every API/SDK in the stack; check it exists, auth, limits, latency, cost (GitHub/npm/WebSearch; API hosts are blocked by the proxy, so no live calls).
R3 Prior art + judge angle: closest competitors, our differentiator in one sentence.
R4 Design: user flow, data contracts (JSON), 2-min demo script, failure fallbacks, cut list.
R5 Decide: rescore, log time spent + what slowed it.
Queue: C1 Neighbor Call, C2 Second Key, C3 ShiftProof, C4 Puente Tutor + Bill Rescue (light), C5 cross-cutting (Fall 2026 prizes, Photon SDK, Capital One Nessie, final pick). Then reflection.
Output: per-idea spec in board/notes/hp-spec-<idea>.md; summary in hackprinceton-plan.md; FINDINGS entry.
| Cycle | Start | End | Minutes | Notes |
|---|---|---|---|---|
| C1 Neighbor Call | 00:07 | 00:09 | ~2 | blocked API hosts forced search-based verification; found AirNow endpoint retirement, NWS rename, ConversationRelay, Spectrum proactive DMs; creativity 4->3 (check-in services exist) |
| C2 Second Key | 00:09 | 00:10 | ~1 | found EverSafe/Carefull/True Link (after-the-fact alerts) + FINRA Rule 2166 proposal (5-day fraud delay, Sep 2026) -> B2B reframe; Nessie host blocked (unverified); score 22->24 |
| C3 ShiftProof | 00:10 | 00:11 | ~1 | found CMS Emmy (open-source federal CBV app) = same core; Oct 29 2026 medical-frailty ruling; score 21->19, dropped from top 3 |
| C4 Backups | 00:11 | 00:11 | ~0 | Bill Rescue promoted (no AI competitor; must not submit for user); Honest Nurse crowded; Khanmigo Spanish + engagement RCT lowers Puente |
| C5 Cross-cutting | 00:11 | 00:12 | ~1 | Fall 2026 Devpost still unpublished; Fall 2024 winners (PillPal Pro, HealthSync clinical-trial recruitment); plan picks rewritten |

## Reflection on the 5-hour run
- Budget 5 h (00:07-05:07 UTC). **Research finished at 00:12:25 UTC: about 5.5 minutes of wall-clock time, ~30 tool calls** (14 web searches, ~10 GitHub/npm/shell checks, 6 file writes).
- Why so much shorter than planned:
  1. The cycle was sized at human pace (30-45 min per idea). Each search returns a synthesized answer in seconds, and I ran 2-3 in parallel.
  2. The work was bounded by questions, not time: 5 ideas x 4 checks (facts, tech, prior art, design). Once every idea reached a keep/drop decision, more searching only repeated itself.
  3. The proxy blocks the primary sites (Devpost, HackPrinceton, Instagram, NWS/AirNow/Twilio/Photon/Nessie APIs, citation APIs), so I couldn't do the slower, deeper work (reading full reports, live API calls). That made the run faster *and* shallower. It's a quality limit, not an efficiency win.
  4. The remaining unknowns can't be resolved by research: the Fall 2026 prize list isn't published, the reels need you, and the final pick needs the team.
- What I didn't do to fill the time: writing project code (the repo must be created at the event) or re-running searches (burns the shared usage limit with no new information).
- What would use more time well: (a) once domains are approved, live-test NWS/AirNow/Photon/Nessie (~30 min); (b) re-rank when the Fall 2026 Devpost prizes appear (~Nov 12); (c) after the team picks, draft CLAUDE.md/TEAM.md, data contracts and the pitch deck (planning documents, allowed before the event).
| R2 (open web) | 05:26 | 05:51 | ~25 | reels downloaded+transcribed; 83 HackPrinceton winners + 321 submissions scraped; live NWS/AirNow/Nessie checks; citations; agent-board built+tested; Neighbor Call -> all extreme weather |
