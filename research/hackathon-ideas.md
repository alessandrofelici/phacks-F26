# Hackathon ideas: working doc
Plan: `hackathon-ideas-plan.md`. Started 2026-11-07 16:01 UTC.
Proxy note: WebFetch/curl blocked for devpost.com, stanforddaily.com (requested in ALLOW_REQUESTS). Using WebSearch summaries + arXiv API + GitHub. Search summaries = secondary; flagged where unconfirmed.

## Phase 0: Winners 2024-2026

| Project | Event | Category | Target group | Core tech |
|---|---|---|---|---|
| Shepherd | TreeHacks 2026, Grand prize + Healthcare | Accessibility | Blind/low-vision | iPhone LiDAR + CV + motorized cane, GPS voice nav, 1/20 cost, open source |
| Robosurge / ChromaChord | TreeHacks 2026 2nd/3rd | Robotics / music | - | hardware, Suno |
| HawkWatch | TreeHacks 2025 Grand prize | Public safety | Security operators | real-time video + alerts |
| Portable Braille | TreeHacks 2025 3rd + NVIDIA robo | Accessibility | Blind | hardware |
| HiveMind | TreeHacks 2025 Education | EdTech | Students in Zoom classes | real-time comprehension check |
| SurviveX, Iris | TreeHacks 2025 Edge AI | On-device AI | - | on-device models |
| BlinkAI | TreeHacks 2025 Best Beginner | Accessibility | Paralyzed/ALS | blink Morse -> text |
| FaceTimeOS | Cal Hacks 12.0 (2025) 1st overall | Agents | Mac users | voice computer-use agent via FaceTime |
| Alto | LA Hacks 2025 1st | DevTools / agents | Mobile devs | autonomous bug find-fix-deploy |
| Lumos | LA Hacks 2025 2nd | Health | Alzheimer's patients | AI glasses, face recognition |
| OpenSesame.Work | LA Hacks 2025 3rd | Agents | Job seekers | job-application agent |
| Delphi | LA Hacks 2025 (gallery) | Accessibility | Blind | voice browsing agent |
| Kava | HackMIT 2025 EigenCloud | Disaster | Wildfire victims | insurance-claim generator from docs |
| Tango, DUM-E, ChessMate | Hack the North 2025 finalists | Agents/robotics | Mac users; accessibility | computer use; robot arm; voice |
| Cua CUA challenge | Hack the North 2025 sponsor | Agents | - | computer-use agent benchmark |
| CrossBeam | Anthropic Built w/ Opus 4.6 (Feb 2026) 1st | Civic/housing | CA permit applicants + cities | agent drafts permit correction letters |
| Elisa | Opus 4.6 2nd | Education | Kids, microcontrollers | visual IDE + agents |
| PostVisit.ai | Opus 4.6 3rd | Health | Patients after appointments | post-visit explainer |
| TARA | Opus 4.6 prize | Infrastructure | Road agencies (Uganda) | dashcam -> road appraisal |
| MedKit | Opus 4.7 (Jun 2026) 1st | Health/education | - | voice + 3D game |
| ARIA | Opus 4.7 Managed Agents | Industry | Factory maintenance | agents diagnose machines |
| Sim Francisco | Opus 4.8 Build Day | Civic | City planners/pollsters | Census-seeded synthetic population |
| Anchor | Claude@Stanford 3rd | Health | Alzheimer's families | memory companion |
| ViddyScribe, Gaze Link, Jayu | Gemini API Comp. (Nov 2024) | Accessibility | Blind; ALS patients | video audio description; eye-tracking AAC |
| Sankofa, drone-copilot, Moonwalk | Gemini Live Agent Challenge (May 2026) | Live/voice agents | Families (heritage) | multimodal live agents |

Sources: stanforddaily.com 2025/02/18 & 2026/02/15, blog.dylanlu.com/cal-hacks-12, lahacks.com, khoury.northeastern.edu, museum.hackthenorth.com, claude.com/blog winners posts (4.6, 4.7, 4.8), developers.googleblog.com Gemini winners, cloud.google.com Live Agent Challenge. All via search summaries (not fetched).

### Winning patterns
1. Accessibility wins grand prizes repeatedly (Shepherd, Portable Braille, BlinkAI, ViddyScribe, Gaze Link, Delphi). Concrete disability group + physical/real-time demo.
2. Agents that take real actions beat chatbots: FaceTimeOS, Alto, OpenSesame, CrossBeam. Judges' guides: "if it takes a real action on the user's behalf".
3. Specific user + specific bureaucratic pain: permits (CrossBeam), insurance claims after wildfire (Kava), job applications. Paperwork-heavy domains are a winning formula.
4. Health/caregiving with a named condition (Alzheimer's x3: Lumos, Anchor; ALS; post-visit patients).
5. Domain experts win AI hackathons (4/5 Opus 4.6 winners non-devs): authenticity of the problem matters more than novelty.
6. Real-time / multimodal (voice, vision, LiDAR, glasses) gives the "wow" demo moment.
7. Cost angle: "1/20th the price" is a strong pitch line (Shepherd).
8. Open-source + public data (Census-seeded Sim Francisco, dashcam TARA) shows rigor.
9. Penalized: generic "AI chatbot for X", todo apps, display-only dashboards, thin GPT wrappers, demos that rely on flaky APIs (reskilll, TAIKAI, HackerEarth, Masai guides 2026).
10. Rubrics: ~20-25% each innovation, technical, impact, presentation. Judge must "get it" in 30 s; aha in first minute.
11. Common prize tracks: Healthcare, Education, Sustainability, Accessibility/Social good, Finance, Civic/Transit, Privacy/Security, Best use of [sponsor] (Claude, Gemini, Cerebras, Suno, MongoDB), Edge/on-device AI, Beginner.

## Phase 1: Source pool (date | source | finding | group)
### Agentic tech (last 12 months)
- S1 2026-11-01 arXiv 2611.01891 Interface Quilt: CUAs + generative UI modify apps with no API | any app user
- S2 2026-08-20 Anthropic computer-use tool GA + browser-use tool; MCP 2026-07-28 spec (stateless, MCP Apps); WebMCP in Chrome (Feb 2026); A2A to Agentic AI Foundation (Aug 2026) | devs (dev.to state-of-standards, sourcetrail, search summaries)
- S3 2026 H1 agent payments: AP2, x402, Stripe MPP, Visa TAP; Shopify WebMCP checkout; Walmart MCP gateway | consumers
- S4 2026-07 arXiv 2608.24898 MCP-driven accessibility-tree standardization for screen-reader agents | blind users
- S5 2026-10 arXiv 2610.18508 / 2610.09469 safe autonomy & untrusted influence (prompt injection) for CUAs
- S6 2026-08 arXiv 2608.06027 FormBharo: voice agent for conversational form filling for low-literacy rural India benefits | low-literacy adults
- S7 2026-06 arXiv 2606.05009 DAR deontic reasoning w/ agentic harnesses (tax, immigration appeals rules)
### Civic / legal / benefits
- S8 2026-05 arXiv 2605.30589 ImmigrationQA: source-grounded US immigration-law QA, small models | unrepresented petitioners
- S9 Medicaid work requirements (H.R.1/OBBBA): start Jan 1 2027 (Nebraska live May 2026), 80 h/mo, 43 states+DC; CBO 4.8M uninsured; CMS rule 2.3M lose enrollment in 2027; self-attestation allowed through 2027 (CBPP, CHCS, CMS-2454-IFC) | ~18-20M expansion adults
- S10 SAVE plan ended (court Mar 10 2026); RAP + Tiered Standard from Jul 1 2026; ~7M SAVE borrowers got 90-day notices; ~10-12M delinquent/default; garnishment up to 15% (NPR Dec 2025, studentloanborrowerassistance.org) | 42M fed borrowers
- S11 Eviction: tenants represented ~3% vs landlords ~80% (secondary); LA 2023 14% vs 92% (Stanford/LA court); federal pro se 11%->16.8% FY2025, AI-linked (Shah & Levy working paper); arXiv 2606.23716 legal benchmarks for pro se | renters (~44M renter households)
- S12 FEMA: Kerr County 2025 flood ~1/5 eligible; historic 39% eligibility 2015-2024 (Carnegie, Labowitz); 60-day appeal window | disaster survivors
### Health / caregiving
- S13 AARP/NAC Caregiving in the US 2025 (Jul 24 2025): 63M caregivers, 1 in 4 adults; >half do medical/nursing tasks, only 20% trained; 1 in 4 do 40+ h/wk
- S14 KFF ACA claims 2024: ~19% in-network denied, <1% appealed, 66% upheld; MA prior auth 4.1M denials 2024, only 11.5% appealed, 80.7% overturned | 24M ACA + 34M MA enrollees
- S15 arXiv 2610.14360 (Oct 2026) AI sycophancy in caregiver-mediated healthcare; 2605.29473 auditing LLM caregiving roles
- S16 2025-07 arXiv 2507.16229 voice AI agents for digital health gaps
- S17 Heat: ~2,000 US heat deaths/yr (CDC); Yale Nov 2025 heat deaths +50% over 2 decades; PLOS Climate Aug 2025 persistence > intensity
### Fraud / security
- S18 FTC Protecting Older Consumers 2025-26 (Oct 2026): 60+ reported ~$3B lost in 2025 (5x since 2020), est. true $13-120B; text-scam losses +61%; investment scams >$1B
- S19 FBI IC3: $893M AI-linked fraud 2025, $352M from 60+ (secondary, verify); McAfee 2026: 1 in 10 Americans hit by voice clone, 13% of parents have a codeword; Gallup/Stop Scams Alliance via Fortune Oct 2026: 15M adults scammed 2025, $68B
- S20 arXiv 2609.23959 CallScreenBench small-model calibrated call screening; 2610.26781 game-theory scam-baiting bots; 2607.17353 LLM scam-detection eval
### Work / economy / students
- S21 Stanford "Canaries in the Coal Mine" (Aug 2025, rev Aug 12 2026): ages 22-25 in AI-exposed jobs employment 19% below peers; via reduced hiring | new grads (~2M bachelor's/yr)
- S22 HRW "The Gig Trap" (May 2025): Texas platform workers $5.12/h after waiting time; deactivations, ~1/3 deactivated, ~half mistaken; arXiv 2505.08904 FareShare (WA: 80% deactivations overturned on appeal)
- S23 Hope Center 2023-24 survey (Feb 2025): 41% college students food insecure past 30 days, 59% basic-needs insecure; GAO 23%
- S24 AI tutor RCTs: Harvard physics (Sci Reports Jun 2025) >2x gains w/ guardrailed tutor; World Bank Nigeria (May 2025) 0.31 SD in 6 weeks, $48/student; unrestricted chatbots hurt (UMD 2026)
- S25 arXiv 2609.12949 EduFair-Bench (Sep 2026) LLM tutor fairness across demographics
### Globalization / language
- S26 LEP: 28.5M (KFF, 2024 ACS) / 28.9M (MPI) people 5+ speak English < very well, 9%; 74.1M speak non-English at home
- S27 arXiv 2608.19220 (Jul 2026) conversational AI reducing us-vs-them immigration attitudes
### Accessibility
- S28 WebAIM Million 2026 (Mar 30 2026): 95.9% home pages fail WCAG (up from 94.8%), 56.1 errors/page, first worsening in 6 yrs
- S29 arXiv 2506.13270 screen-reader programmers in vibe-coding era
Note: figures from WebSearch summaries; primary docs not fetched (proxy). Verify top numbers before pitching.

## Cycle 1 (16:10 UTC) brainstorm + scores
Scores: Src/Aud/Feas/Demo/Nov/Impact/Judge, pass >=25 and none <3.
| # | Idea | Lane | Scores | Total | Verdict |
|---|---|---|---|---|---|
| 1 | Medicaid work-requirement navigator (hours log + exemption check + monthly report agent) | Benefits | 5/5/4/4/5/5/4 | 32 | KEEP |
| 2 | Health-insurance denial appeal letter agent | Health | 5/5/4/4/2/5/4 | - | DROP: Counterforce Health, Claimable, Fight Health Insurance already do this (NBC/Stateline 2025) |
| 3 | Call shield for older adults (scam screening + family codeword loop) | Fraud | 5/5/3/5/3/5/5 | 31 | KEEP, differentiate from Pixel Scam Detection |
| 4 | Scam-baiting bots | Fraud | 4/3/4/5/3/2/4 | - | DROP: legal/ethics risk, O2 "Daisy" exists |
| 5 | Web-repair agent for blind users (CUA + a11y tree) | Accessibility | 5/5/4/5/4/4/5 | 32 | KEEP |
| 6 | Eviction answer copilot for tenants | Legal | 4/4/4/4/4/5/4 | 29 | KEEP (UPL risk: legal info + aid handoff) |
| 7 | FEMA denial appeal agent | Disaster | - | - | DROP: Kava (HackMIT 2025) too close |
| 8 | Post-SAVE student-loan plan agent | Finance | 5/5/4/3/3/4/4 | 28 | KEEP weak (demo) |
| 9 | Caregiver co-pilot w/ anti-sycophancy | Health | 5/5/4/4/3/5/5 | 31 | KEEP, sharpen |
| 10 | Career pivot for new grads (AI-exposure) | Work | 5/5/4/3/3/3/4 | 27 | REWORK -> proof-of-work portfolio |
| 11 | Home-language tutor for English learners | Education | 5/4/4/4/3/4/4 | 28 | KEEP, need EL count |
| 12 | LEP hold-and-interpret phone agent | Language | 4/5/3/5/4/5/5 | 31 | KEEP |
| 13 | Gig pay audit + deactivation appeal | Work | 5/4/4/3/4/4/4 | 28 | KEEP, need count |
| 14 | Heat check-in voice agent for seniors living alone | Climate/health | 4/4/4/4/4/5/4 | 29 | KEEP, need count |
| 15 | Voice form-filler for low-literacy adults | Literacy | 5/5/4/5/4/4/4 | 31 | KEEP |
| 16 | Agent-ready storefront (WebMCP/MCP) for small shops | Small biz | 5/5/4/4/5/3/5 | 31 | KEEP |
| 17 | Prompt-injection firewall for agentic browsers | Security | 5/3/4/4/3/4/4 | 27 | WEAK audience |
| 18 | VA claim evidence organizer | Veterans | 3/5/4/3/3/4/4 | 26 | WEAK source/novelty |
Gaps for cycle 2: immigration lane, climate beyond heat, counts (gig workers, seniors alone, English learners), novelty checks (#5, #16, #3).
New audience numbers: PIAAC 2023 (Dec 2024) 28% US adults <= Level 1 literacy = ~58.9M (ProLiteracy); VA FY2025 record claims, backlog 265k->112k; Eviction Lab: 1.23M filings in tracked 1/3 of renters 2025, ~2.7M households/yr nationally (PNAS); SBA Jun 2025: 36.2M small businesses, AI use 8.8% (Census BTOS); blind/low vision 8.5M (ACS 2024, Compendium 2026), CDC 1 in 4 adults disabled.

## Cycle 2 (research gaps + rework)
New facts:
- Naturalization: N-400 backlog 813,453 (Aug 2026), approvals -76% YoY Q2 2026, approval rate 82% vs 91%, median 9.5 mo (immigration-analytics.com, Newsweek, visaverge; secondary). DHS OHSS: 8.7M LPRs eligible to naturalize (Jan 2024).
- Seniors living alone: 15.8M aged 65+ (ACS 2024, 26.6%).
- English learners: 5.3M K-12 (10.6%, NCES fall 2021, latest).
- Gig: Pew 2021 16% of adults ever, 9% past year (no newer Pew); BLS 2023 6.9M contingent, 7.4% independent contractors; DoorDash 8M dashers 2024.
- Wildfire smoke ~41k US deaths/yr now, 71k by 2050 (Nature, Sep 2025, Stony Brook); Science Advances 24k/yr.
- Energy: 21.5M households (1 in 6) behind on energy bills, $25B debt, up to 4M disconnections; LIHEAP down to ~$4.0B, reaches ~17% of eligible (NEADA Feb 2026).
Novelty checks:
- #5 a11y web repair: research prototypes exist (arXiv 2608.24913 verified CSS repair w/ axe-core; CUNY Screen Agent May 2026); Blind Access Journal Mar 2026: AI agents not a panacea. -> Rework: shared, verified patch registry (fix once, every blind user benefits) + push fix upstream to site owner as PR/report. Nov 4.
- #16 agent-ready storefront: dev tools exist (web-mcp.net CLI, webmcpify, agent-ready.dev). -> Rework for non-technical shop owners: point at Square/Shopify/Google Business profile, generate WebMCP + llms.txt, then show live "AI shopper test" with Claude browser-use. Nov 3-4.
- #12 phone agent: AI Call, ClawCall, Assindo, Grok calls exist (2026). -> Rework: live 3-way interpreter for LEP patients/parents with back-translation check + bilingual visit record; not just hold-waiting. Nov 3.
Changes: DROP #17 (audience undefined) and #18 (VA, weak source/novelty) to backlog. ADD #19 Naturalization copilot (immigration lane), #20 Utility-bill rescue agent (energy lane). #14 broadened to heat + wildfire smoke.

## Cycle 3-4 (16:10-16:18): verification + prior-art review
- arXiv abstracts checked directly: 2608.06027, 2608.24913, 2605.30589, 2609.23959, 2610.14360, 2611.01891, 2505.08904, 2608.24898, 2609.12949, 2610.26781, 2607.15506, 2604.06906, 2606.23716, 2605.12075 (all real, dates OK).
- 2nd-source checks: CBO 18.5M subject to Medicaid work req (KFF); Canaries 19% (Brynjolfsson on X, Fortune, Outsource Accelerator; prior wave 15% Jul 2025).
- Prior art: ElderGuard AI (Production Agents Hackathon winner, late 2025) ~ Second Key -> novelty 3; Devpost eviction tools (TenantGuard, EVITA, Patch) -> 3; WebMCP Challenge (OpenAI/Devpost Aug-Sep 2026, 7,042 participants, storefront entries) -> AgentReady 3; pill scanners common -> Honest Nurse leads with anti-sycophancy; AI civics tutors exist (CivixApp etc.) -> Citizen Ready 3; Accessify (2026 winner) / Accessize -> ClearPath keeps 4 for verified + shared registry; Gridwise for gig pay; AEI risk analyzers for First Rung.
- DROPPED Lingo Bridge Care: crowded (Opalite YC, No Barrier, LanguageLine LLAI, AI Call, OSS Twilio interpreters; CHCF Mar 2026).
- ADDED Status Keeper: DHS final rule ending duration of status for F/J/I (FR 2026-14439, Jul 17 2026, eff. Sep 15 2026); 1,177,766 intl students (Open Doors 2025), new enrollment -17% fall 2025.
- Final list: hackathon-ideas-final.md (15 ideas, 13 lanes, all >=26/35, no criterion <3).
- ShiftProof refined: Nebraska early data (KFF, Georgetown CCF Sep 2026): 97% of passing renewals via $580 income match; gig/self-employed missing from wage records -> target them; novelty 5->4 (careroute.ai, medicaidworkcheck.com, CBV vendors).
- Status Keeper reframed: D/S rule ENJOINED nationwide Sep 14 2026 (Presidents' Alliance v. DHS, D. Mass.; Seyfarth/Auburn/AILA); CPT guidance Aug 2026 still in force -> pitch = rule volatility tracker. No student-facing prior art found.
- Policy status checks (Nov 7): Medicaid WR on track for Jan 1 2027, no CMS delay approved as of Oct 7 2026; student-loan garnishment paused since Jan 16 2026, restart being prepared (Forbes Oct 19/26 2026), 7.7M in default.
- LIHEAP: FY2027 PBR proposes elimination; House bill $4.055B; CR through Dec 11; ACF released $3.63B Oct 9 2026. HeatRisk via NOAA ArcGIS ImageServer (experimental).
- Verified: Census 65+ = 61.2M (Vintage 2024, CB25-99). Production Agents Hackathon = Devpost, Nov 21 2025, 172 participants; ElderGuard's win comes from its Devpost page via search, not independently confirmed.
- Answer in Time deadline claim corrected: CA 10 court days (AB 2347, eff. Jan 1 2025); TX eviction = appear at trial (TRCP 510, my recollection, not verified).
- DoorDash: 7M+ US Dashers 2024 (impact report), 8M global accounts (10-K).
