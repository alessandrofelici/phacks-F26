# HackPrinceton research summary

## 2026-11-07: Hackathon ideas, 15 researched and scored
**Answer:** 15 ideas passed 4 research/brainstorm/review cycles (score >= 26/35, no criterion below 3, 13 lanes). The top 5 are ShiftProof (Medicaid work-requirement proof for gig workers), ClearPath Web (verified, shared accessibility fixes for blind users), Second Key (family co-sign before an older adult moves money under scam pressure), Honest Nurse (anti-sycophancy caregiver copilot) and Status Keeper (tracking changing rules for 1.18M international students). Full list in the format you asked for: `board/notes/hackathon-ideas-final.md`; log and sources: `board/notes/hackathon-ideas.md`.

- What wins (2024-26): accessibility grand prizes (Shepherd, TreeHacks 2026), agents that act (FaceTimeOS, Cal Hacks 12; CrossBeam, Opus 4.6 hackathon), named groups with paperwork pain (Kava, HackMIT 2025). Generic chatbots are penalized. Sources: Stanford Daily, claude.com winners posts, LA Hacks, Devpost (via search).
- Key sources: FTC Protecting Older Consumers (Oct 2026, $3B lost by 60+ in 2025); CBO/KFF (18.5M subject to Medicaid work req); Nebraska early data (KFF, Georgetown CCF Sep 2026); WebAIM Million 2026 (95.9% fail WCAG); AARP/NAC 2025 (63M caregivers); Stanford "Canaries" Aug 2026 (-19% young workers in AI-exposed jobs); NEADA Feb 2026 (21.5M households behind on energy bills); arXiv 2608.06027, 2608.24913, 2609.23959, 2610.14360, 2605.30589 (checked directly).
- Dropped after prior-art checks: health-insurance appeal bots (Counterforce, Claimable), FEMA appeals (Kava, HackMIT 2025), LEP medical interpreter (Opalite, LanguageLine, No Barrier).
- Policy watch: the F-1 "duration of status" rule was enjoined on Sep 14 2026, so Status Keeper is pitched as a rule-change tracker. Medicaid work requirements are still on for Jan 1 2027 (no state delay approved as of Oct 7). Student-loan garnishment is paused but being prepared to restart.

**Not verified:** devpost.com, stanforddaily.com, ftc.gov, kff.org, webaim.org and other primary sites are blocked by the proxy (requested in ALLOW_REQUESTS), so most figures come from search summaries cross-checked in a second source. Scores are my judgment. Devpost prior-art checks used search only, so a similar project may exist that search didn't surface.

## 2026-11-07: How reliable the papers behind the 15 hackathon ideas are
**Answer:** I added a "motivating paper(s)" field to every idea in `board/notes/hackathon-ideas-final.md`. Strongest to build on: FareShare (CSCW 2026 Best Paper Honorable Mention, field-tested) for Fair Shift; the Nature 2025 smoke-mortality study for Neighbor Call; Kestin et al. (Sci. Reports 2025) + the World Bank RCT for Puente Tutor; the verified-repair paper (ACM ICMI 2026 companion, code released) for ClearPath Web. Weakest: ImmigrationQA (single author, unaffiliated) for Citizen Ready; CallScreenBench (vendor preprint, 41 test scenarios) for Second Key.

- 4 ideas rest on policy/specs rather than papers: AgentReady (WebMCP/MCP specs), Bill Rescue (NEADA), Loan Lens (statute/ED), Status Keeper (Federal Register + injunction).
- Venue/affiliation checked via arXiv metadata and PDFs (Stanford, JHU, EPFL, Autodesk Research, IBM Research, ARTPARK/IISc, Scam.ai).

**Not verified:** citation counts. api.semanticscholar.org, api.openalex.org, Crossref and Google Scholar are blocked by the proxy (requested in ALLOW_REQUESTS). Most papers are from 2026, so counts would be near zero anyway.

## 2026-11-07: Mapping the hackathon ideas to HackPrinceton Fall 2026 tracks
**Answer:** The Fall 2026 tracks are Education, Entertainment, Sustainability, Healthcare, Business + Enterprise and Science + Discovery. Strong fits: Honest Nurse and Neighbor Call (Healthcare), Puente Tutor (Education), AgentReady Main Street (Business + Enterprise). There is no civic/legal track, so Answer in Time can only compete for Best Overall. No idea fits Entertainment or Science + Discovery. Table: `board/notes/hackprinceton-track-fit.md`.

- Tracks from the [QAI listing](https://qai.io/events/128a4c2e-d5fa-48d4-a59a-961eb5793388); track descriptions from the [Spring 2026](https://hackprinceton-spring-26.devpost.com/) and [Fall 2025](https://hackprinceton-fall-2025.devpost.com/) Devpost pages (via search).

**Not verified:** hackprinceton.com is blocked by the proxy (requested). I found no description of Science + Discovery, and no Fall 2026 sponsor tracks.

## 2026-11-08: HackPrinceton Fall 2026, best ideas and a build plan for a team of 3
**Answer:** Top picks are Neighbor Call (Healthcare, + Photon), Second Key (Business + Enterprise, + Capital One Best Financial Hack + Photon) and ShiftProof (Healthcare). The plan covers roles (agent/voice, UI, data+pitch), one Next.js repo built in parallel worktrees with Claude Code, integration by hour 12, feature freeze at hour 26, and rehearsing the 2-min demo. Full plan: `board/notes/hackprinceton-plan.md`; scoring log: `board/notes/hackprinceton-loop.md`.

- Rules: the repo must be created during the event; a 2-min live demo is required; AI-assisted code is allowed ([Spring '26 Devpost](https://hackprinceton-spring-26.devpost.com/), via search).
- Recent winners: Asclepius (on-device privacy proxy for clinical-trial AI, Spring '26) and MindPad (multimodal workspace, Fall '25; [Illinois news](https://siebelschool.illinois.edu/news/golcha-hackprinceton)).
- Fall 2026 sponsors include Capital One, Photon, Amazon, LangChain, Scale AI, CoStar ([hackprinceton.com](https://www.hackprinceton.com/) via search). Photon's usual prize is "Agents in iMessage" (Spectrum SDK).
- Twilio trial accounts can't support a live judge demo (5 verified numbers, trial message, 1 conference), so upgrade before the event.

**Not verified:** Fall 2026 sponsor prize list (no Devpost page yet); the two Instagram reels (instagram.com blocked, requested).

## 2026-11-09: HackPrinceton ideas refined: Second Key now #1, ShiftProof dropped
**Answer:** After a 5-cycle refinement, the picks are Second Key (Business + Enterprise, pitched to banks; score 24), Neighbor Call (Healthcare, 22) and Bill Rescue (Sustainability, 22). ShiftProof is dropped because CMS already builds "Emmy", an open-source app that does the same Medicaid work reporting. Specs with data contracts and 2-min demo scripts: `board/notes/hp-spec-*.md`; plan: `hackprinceton-plan.md`.

- Second Key: EverSafe/Carefull/True Link alert after money moves; FINRA's proposed Rule 2166 ([Federal Register, Sep 2026](https://www.federalregister.gov/documents/2026/09/09/2026-18293/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-of-a)) adds a 5-business-day fraud delay, so "hold during a live scam call" fits where regulation is going.
- Neighbor Call: daily AI check-in services exist (AloneAssist, Verocall); pitch it as event-triggered public health. Maricopa had 430 heat deaths in 2025. AirNow's `/zipCode/current` endpoint was retired Sep 30 2026.
- ShiftProof: [CMS Emmy](https://github.com/DSACMS/iv-cbv-payroll) does applicant reporting + consent-based verification; a federal court struck the medical-frailty test on Oct 29 2026.
- Photon `spectrum-ts` (npm 12.15, MIT) supports proactive iMessage DMs; its inbound loop needs a persistent server.
- The research took ~5.5 minutes of the 5-hour budget; reasons are in `hackprinceton-loop.md`.

**Not verified:** Fall 2026 prize list (unpublished), Nessie and the other APIs live (hosts blocked), the Instagram reels.
- 2026-11-09 update: the matching method changed at the developer's request (commit 728dd42, local, not pushed yet). Only payments whose description mentions Zelle are considered. A purchase must be within 7 days of the payment, before or after. The $50 minimum is gone. An exact share wins, otherwise the purchase closest in date. 117 tests pass. Not verified: how Citizens writes Zelle payments in Plaid's description.

## 2026-11-09: Reels, HackPrinceton winner data, and a tested agent-board workflow
**Answer:** The two reels are workflow and strategy advice, not ideas: (1) coordinate teammates' coding agents through one pinned GitHub issue with @mentions and folder ownership; (2) rank every track and sponsor prize with Claude, target less-crowded sponsor prizes, and ask sponsors what would wow them. Devpost data from the last two HackPrinceton events (83 winning projects, 321 submissions) supports Second Key (B+E + Capital One + Photon) and Neighbor Call (Healthcare + Photon), the latter now covering cold as well as heat so it can demo on live November alerts. I built and tested `projects/agent-board` (the reel-1 workflow).

- Reels: downloaded with yt-dlp, transcribed locally (faster-whisper), frames inspected; takeaways in `board/notes/reels-takeaways.md`.
- Winners: Photon's prize had 5 winners in Fall '25 and Photon/iMessage appears in many winning stacks; Healthcare winners are monitor→alert systems (VITAL S26); B+E winners are workflow agents (LEGR, Jigsaw); Sustainability winners are geospatial/IoT. Details: `board/notes/hackprinceton-winners-analysis.md` ([Fall '25](https://hackprinceton-fall-2025.devpost.com/project-gallery), [Spring '26](https://hackprinceton-spring-26.devpost.com/project-gallery)).
- Live checks: NWS alerts API works (no heat alerts in November; winter storm alerts active). AirNow needs a free key. Nessie works over HTTPS only.
- Cold vs heat: ~2,520 deaths with hypothermia as a cause (2023, CDC provisional via KFF Health News) vs 2,391 heat deaths (2024, [CDC MMWR](https://www.cdc.gov/mmwr/volumes/75/wr/mm7534a3.htm)).
- Citations (OpenAlex/Semantic Scholar): TrialGPT 319, Kestin AI-tutor RCT 239, CallScreenBench 11, FareShare 7, most 2026 papers 0.
- agent-board: tested on a temporary issue in the private repo hackagent-write-test (#2, now closed): tagging, read-once inbox and blocking `wait` all worked.

**Not verified:** Fall 2026 sponsor prizes (Devpost page not live yet: 404/403); Photon's dashboard (app.photon.codes didn't respond); whether HackPrinceton counts a pre-built helper script as pre-existing code.

