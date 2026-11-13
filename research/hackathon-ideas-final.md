# 15 Hackathon Ideas (research 2026-11-07)
Method: `hackathon-ideas-plan.md`. Working log and all sources: `hackathon-ideas.md`.
Ranked by score (7 criteria x 5 = 35). Every idea: source <= 2 years old (agentic ones <= 12 months), audience sized with a cited number.
Field 7 = motivating paper(s), citations and how reliable they are to build on. Citation counts: Semantic Scholar/OpenAlex/Scholar are blocked (requested); papers from 2026 are <6 months old, so counts are ~0 and venue, authors, code and evaluation size are used instead.
Caveat: devpost/ftc/kff etc. are blocked by the proxy, so most figures come from search summaries cross-checked in a 2nd source; arXiv papers were checked directly.

---

## 1. ShiftProof (32/35)
1. **Name:** ShiftProof
2. **Target audience:** ~18.5M Medicaid expansion adults (19-64) who must prove 80 h/month of work, school or volunteering (or $580/month earnings) from Jan 1 2027 (CBO via KFF). The sharp end is gig, self-employed and cash workers, who are missing from state wage records, so automatic checks miss them (CBPP; SpruceID Nov 2026).
3. **Solution:** A phone-first agent for people the state's data can't see. It imports gig-app earnings exports, bank/Venmo deposits, pay stubs and class schedules (photo or file), totals hours and the $580 income test, checks every exemption (caregiver, disability, student, pregnancy, etc.) against the state's rules, and produces a consent-based, user-reviewed verification report + pre-filled state submission before the 30-day response window closes. The human confirms every submission; self-attestation is allowed through 2027, documents are needed from 2028.
4. **Relevance:** H.R.1 (Jul 2025) + CMS interim final rule (Jun 2026). CBO: 4.8-5M+ more uninsured by 2034; CMS: 2.3M disenrolled in FY2027. Nebraska went live May 2026: 14% of applicants subject to the rule were denied, >=1,090 lost or were denied coverage by Sep 30 2026, and up to 28K of 70K had to submit proof; 97% of passing renewals cleared via the $580 income match (KFF; Georgetown CCF Sep 2026). Montana (Jul 2026) and Iowa (Dec 1 2026) also start early; as of Oct 7 2026 no state had a CMS good-faith delay approved (CMS expects ~2 approvals). Nationwide, first losses come Apr 1 2027. Past work requirements (Arkansas) cut coverage via paperwork, not jobs (CBPP). FormBharo (arXiv 2608.06027, Aug 2026) shows LLM + rule-based validation works for form filling.
5. **Pitch:** "Millions will lose Medicaid over paperwork, not work. ShiftProof turns your pay stubs into proof in 60 seconds."
6. **Tech stack:** Expo/React Native; Claude (vision for stubs, tool use for rules); deterministic rules engine (JSON per state, from CMS-2454-IFC); Supabase (Postgres + storage, row-level security); Twilio SMS reminders; Playwright demo against a mock state portal.
7. **Motivating paper(s) and reliability:** *FormBharo* (arXiv 2608.06027, Aug 2026; ARTPARK/IISc, live pilot with the NGO ARMMAN; companion paper at a NeurIPS 2026 workshop; open eval framework github.com/artpark-sahai-org/calibrate, 24★). Preprint, not peer-reviewed, ~3 months old, so citations are ~0. The need is backed by primary policy data (CBO via KFF, CMS-2454-IFC, Nebraska data in KFF/Georgetown CCF). **Implementation reliability: medium-high.** LLM extraction plus deterministic rule validation is a proven pattern, and the eligibility rules come from the CMS rule text, not the paper.
- Demo moment: snap 3 DoorDash screenshots + a class schedule -> "82 hours: compliant" -> report filled.
- Risks: wrong attestation = fraud exposure, so the user reviews and signs every report. State rules differ, so demo Nebraska + 1 state.
- Prior art: consumer explainer/check sites (careroute.ai, medicaidworkcheck.com) and B2G consent-based-verification vendors (CBPP vendor landscape). No consumer agent for gig workers was found; novelty 4.

## 2. ClearPath Web (32/35)
1. **Name:** ClearPath Web
2. **Target audience:** ~8.5M Americans who are blind or have low vision (ACS 2024; 2026 Disability Statistics Compendium); 1 in 4 US adults has a disability (CDC).
3. **Solution:** A browser extension where a user-side agent repairs broken pages live (missing labels, empty buttons, unlabeled images, low contrast), checks every fix with axe-core, and rolls it back if it doesn't reduce violations. Verified fixes go into a shared registry, so the next blind user on that page gets the fix immediately, and the site owner gets an auto-generated issue/PR with the patch.
4. **Relevance:** WebAIM Million 2026 (Mar 2026): 95.9% of top home pages fail WCAG, first worsening in 6 years. "From Blind Edits to Verified Repair" (arXiv 2608.24913, Jul 2026); MCP accessibility tree for screen-reader agents (arXiv 2608.24898); Interface Quilt (arXiv 2611.01891, Nov 2026). Shepherd (blind cane) won TreeHacks 2026 grand prize.
5. **Pitch:** "Fix an inaccessible website once, and it stays fixed for every blind user."
6. **Tech stack:** Chrome MV3 extension; axe-core; Claude (or local Ollama model for privacy); Cloudflare Workers + D1/KV for the patch registry (keyed by URL + DOM hash); GitHub API for upstream issues; NVDA/VoiceOver for the live demo.
7. **Motivating paper(s) and reliability:** *From Blind Edits to Verified Repair* (arXiv 2608.24913; accepted to the ACM ICMI 2026 companion proceedings, i.e. peer-reviewed but short; code and benchmark on figshare). Its key finding: unverified LLM fixes helped and hurt about equally (24 vs 20), while the verify loop caught 57/57 seeded violations and rejected 126/126 harmful patches. *Interface Quilt* (arXiv 2611.01891, Autodesk Research, under review). WebAIM Million is an established annual report. Citations ~0 (all 2026). **Implementation reliability: medium-high.** Released code plus axe-core gives a working base, and the paper itself shows why verification is mandatory.
- Demo: screen reader reads "button, button, unlabeled image" -> toggle -> "Add to cart, Search, Photo of red sneakers".
- Risks: overlays have a bad reputation (UserWay lawsuit), so pitch it as user-controlled and verified, not a compliance claim. Registry poisoning means patches must be re-verified on load.
- Prior art: Accessify (2026 Devpost winner, AI summaries/captions), Accessize (TreeHacks, LLM DOM cleanup), Open Accessibility (MadHacks 2023). None verifies fixes or shares them across users, which is the hook.

## 3. Second Key (30/35)
1. **Name:** Second Key
2. **Target audience:** 61.2M Americans aged 65+ (Census Vintage 2024, CB25-99), focusing on the 15.8M aged 65+ who live alone (ACS 2024), and their adult children.
3. **Solution:** A "two-person rule" for money under pressure. Calls to a landline or mobile forward through an AI screener. When it detects scam patterns (urgency, secrecy, gift cards, crypto, wire), it asks the caller a family safe-word question and pings a designated family member, who can join the call. A companion browser/phone layer pauses wire, crypto-ATM and gift-card checkouts until the "second key" holder approves.
4. **Relevance:** FTC "Protecting Older Consumers 2025-2026" (Oct 2026): 60+ reported ~$3B lost in 2025 (5x since 2020); biggest losses via bank transfers and crypto. FBI IC3: $893M AI-linked fraud 2025 (secondary). McAfee 2026: only 13% of parents have a family codeword. CallScreenBench (arXiv 2609.23959, Sep 2026): a 4B model screens per turn with AUROC .974. Gap: Pixel and iOS warn the victim on-device. Prior art: ElderGuard AI (listed as a "Top Overall" winner of the Production Agents Hackathon, Devpost, Nov 21 2025, 172 participants) did deepfake detection + family notification, so lead with the payment co-sign and caller safe-word challenge, not detection.
5. **Pitch:** "Scammers can fool one person. They can't fool two."
6. **Tech stack:** Twilio Voice (call forwarding + conference); streaming STT (Deepgram/Whisper); small fine-tuned classifier (Qwen3-4B LoRA, per CallScreenBench) + Claude for explanations; React Native family app with push; Chrome extension for checkout pausing.
7. **Motivating paper(s) and reliability:** *CallScreenBench / Open-Jev* (arXiv 2609.23959 v2, Oct 2026). It comes from Scam.ai, a vendor (conflict of interest). AUROC .974 on only 41 held-out scenarios (577 turns); no code link found. FTC *Protecting Older Consumers 2025-26* is a primary government report. Citations ~0. **Implementation reliability: medium.** Treat the classifier numbers as optimistic. The product's core (family co-sign, safe-word challenge, payment pause) doesn't depend on detection accuracy.
- Demo: teammate plays "grandson in jail" -> screener flags at turn 3 -> family phone buzzes -> joins call.
- Risks: call-recording consent laws (2-party states), so announce screening. False positives on real emergencies, so family can override instantly.

## 4. Honest Nurse (30/35)
1. **Name:** Honest Nurse
2. **Target audience:** 63M US family caregivers (AARP/NAC, Jul 2025), 1 in 4 adults; over half do medical/nursing tasks, but only 20% are trained.
3. **Solution:** A camera + voice copilot for home care tasks. It scans every pill bottle to build a med list and flag interactions/duplicates, coaches wound care and injections step by step, and keeps a shared log for siblings. It is built to push back: if the caregiver prefers a clinically worse option ("skip the antibiotic, she hates it"), it says so and escalates to the nurse line instead of agreeing.
4. **Relevance:** "When Pleasing the User Compromises Care: AI Sycophancy in Caregiver-Mediated Healthcare" (arXiv 2610.14360, Oct 2026); "Inform, Coach, Relate, Listen" (arXiv 2605.29473, May 2026); AI in polypharmacy scoping review (Cureus, Aug 2025). Anchor (Alzheimer's families) placed at Claude@Stanford; Lumos (LA Hacks 2025, 2nd) shows judges reward caregiving.
5. **Pitch:** "The AI that tells caregivers what the patient needs, not what they want to hear."
6. **Tech stack:** Expo; Claude vision (label OCR) + RxNorm/openFDA APIs for interactions; anti-sycophancy guard (second-pass check on care-affecting answers, scored on the arXiv 2610.14360 benchmark style); Supabase shared family log; Twilio escalation.
7. **Motivating paper(s) and reliability:** *When Pleasing the User Compromises Care* (arXiv 2610.14360, Oct 2026, Stanford + Texas A&M, 58 pp). Preprint; the benchmark release wasn't found in the PDF. *Inform, Coach, Relate, Listen* (arXiv 2605.29473 v2; UIUC, UMass, Indiana). Preprint. AARP/NAC 2025 is a large national survey (~7,000 caregivers). Citations ~0. **Implementation reliability: medium.** The papers give a solid evaluation method, but the anti-sycophancy guard is our own design and untested. Build a small eval set modeled on the paper's setup.
- Risks: medical advice, so it is limited to label-grounded facts plus escalation and is evaluated on a sycophancy benchmark during the hackathon (a great slide).
- Prior art: pill-bottle scanners are common on Devpost (MedSNAP 2026, pill.ai LA Hacks 2024, Medisafe). Lead with the anti-sycophancy guard and live benchmark score, not the scanner.

## 5. Status Keeper (30/35)
1. **Name:** Status Keeper
2. **Target audience:** ~1.18M international students in the US (Open Doors 2025: 1,177,766 in 2024/25, incl. 294K on OPT); new international enrollment fell 17% in fall 2025.
3. **Solution:** Upload your I-20, I-94 and EAD. The agent keeps a live "rules in force today" model and computes your deadlines under it: grace period, OPT unemployment days, CPT eligibility, travel-signature validity, and, if the D/S rule is revived, your fixed Admit Until Date and extension-of-stay window. It watches the Federal Register, SEVP broadcasts and the court docket. When a rule changes or an injunction lifts, it re-runs your timeline, tells you what changed for you, and drafts the email to your DSO. Nothing is filed without the DSO.
4. **Relevance:** DHS final rule ending "duration of status" (Federal Register 2026-14439, Jul 17 2026): fixed admission up to the I-20 end date, max 4 years; grace cut from 60 to 30 days; transfer limits. A nationwide preliminary injunction blocked it on Sep 14 2026 (Presidents' Alliance v. DHS, D. Mass. 1:26-cv-13799), but the case is ongoing and an appeal could revive it. SEVP's Aug 2026 CPT guidance (restricting Day-1 CPT) still applies (Seyfarth, Auburn, globalimmigrationblog Sep 2026). Students face rules that flip within weeks, and that is the agent's job. DAR deontic reasoning with agentic harnesses (arXiv 2606.05009, Jun 2026) supplies the rules-to-facts pattern.
5. **Pitch:** "The rules for 1.2 million international students changed three times since July. Status Keeper tells you, personally, what each change means for you."
6. **Tech stack:** Next.js PWA; Claude vision for I-20/I-94/EAD parsing; versioned deterministic rules engine (rule sets: current D/S, enjoined fixed-period rule, CPT guidance) with unit tests; Federal Register API + CourtListener docket alerts + SEVP page watchers, with Claude summarizing diffs; Resend/Twilio alerts; local-first storage (immigration data is sensitive).
7. **Motivating paper(s) and reliability:** These are primary legal documents, not papers: Federal Register 2026-14439 (final rule) and the Sep 14 2026 preliminary injunction (Presidents' Alliance v. DHS). *DAR: Deontic Reasoning with Agentic Harnesses* (arXiv 2606.05009, Jun 2026, Johns Hopkins, Van Durme group). Preprint, citations ~0. **Implementation reliability: high for the rules engine** (deterministic code from the rule text), **low for stability** (the litigation can flip it). The paper is optional support.
- Demo: load a sample student -> toggle "injunction lifted" -> timeline re-computes: "Admit Until May 2028; your planned 2nd master's is now barred; you have 30 days of grace, not 60."
- Risks: immigration advice -> information + DSO handoff; legal status changes fast, so every alert cites the source document and date.
- Prior art: no student-facing tool found (searched Nov 7); schools are only updating their DSO software (ISMS).

## 6. Answer in Time (29/35)
1. **Name:** Answer in Time
2. **Target audience:** Renters facing eviction: ~2.7M households get an eviction filing each year (PNAS/Eviction Lab); tenants have lawyers ~3-14% of the time vs landlords 80-92%.
3. **Solution:** Photo of the summons -> agent extracts court, case number and the response deadline (state-specific and short: California is 10 court days since AB 2347, Jan 2025; in Texas the trial date matters more than a written answer), screens for defenses (notice defects, repairs, retaliation, rent paid) with a guided interview, fills the state's answer form, books the nearest legal aid / right-to-counsel intake, and adds hearing reminders.
4. **Relevance:** Eviction Lab (Apr 2026): 1.23M filings in tracked areas in 2025, rising in places like Austin (+27%). Federal pro se filings 11% -> 16.8% in FY2025, linked to AI (Shah & Levy). "Legal Reasoning Is Not Lawyering" (arXiv 2606.23716, Jun 2026): models must handle messy pro se input, which is the design target. In one city dashboard, 4% of represented vs 42% of unrepresented tenants got an eviction record.
5. **Pitch:** "Most tenants lose eviction cases by missing a deadline. We make sure they answer in time."
6. **Tech stack:** Next.js; Claude vision (summons OCR) + structured output; Docassemble (or PDF-lib) for court forms; Legal Services Corp / LawHelp directory data; Google Calendar API; Twilio SMS.
7. **Motivating paper(s) and reliability:** *Legal Reasoning Is Not Lawyering* (arXiv 2606.23716; ICML 2026 AI4Law workshop, a peer-reviewed position paper). It warns that legal benchmarks overstate performance on messy pro se input. Shah & Levy, *AI and pro se filings*, is a working paper whose causal claim Georgetown disputes. Eviction counts come from PNAS + Eviction Lab (high). Citations ~0. **Implementation reliability: medium.** The research argues for exactly this design (guided interview, court forms, lawyer handoff) rather than free-form legal advice.
- Risks: unauthorized practice of law, so frame it as legal information + form prep with a legal-aid handoff. Partner with an existing Docassemble interview (e.g., Michigan Legal Help) for accuracy.
- Prior art: Devpost has TenantGuard, EVITA (Philly), Patch, Echo Legal (no confirmed wins). Differentiate with the deadline + court-form filing + right-to-counsel booking loop.

## 7. AgentReady Main Street (29/35)
1. **Name:** AgentReady Main Street
2. **Target audience:** 36.2M US small businesses (SBA Advocacy, Jun 2025); only ~8.8% use AI (Census BTOS, Sep 2025). Focus: local shops, restaurants and salons with a simple site or social page.
3. **Solution:** Paste your website or Google Business profile. The agent crawls it, builds a menu/catalog/booking schema, generates WebMCP tools + llms.txt + MCP server config, and deploys them via a Cloudflare Worker with no code. Then it runs a live "AI shopper test" where Claude's browser-use tool tries to order or book, before vs after.
4. **Relevance:** WebMCP (Chrome preview Feb 2026, docs May 2026, origin trial); MCP 2026-07-28 spec with MCP Apps; agent payments (Google AP2, Stripe/x402, Visa TAP, Shopify WebMCP checkout, Walmart MCP gateway, all H1 2026); Claude computer-use GA + browser-use tool (Aug 2026). Dev tools exist (web-mcp CLI, webmcpify), but nothing for non-technical owners.
5. **Pitch:** "AI agents are the new shoppers. We make sure they can find and buy from your corner bakery."
6. **Tech stack:** Next.js dashboard; Playwright crawler; Claude for schema extraction + tool generation; Cloudflare Workers (inject WebMCP/llms.txt at the edge); Stripe test mode / x402 for agent checkout; Claude browser-use for the before/after test.
7. **Motivating paper(s) and reliability:** No research paper. It rests on specs: WebMCP (W3C Community Group draft; Chrome origin trial, docs May 2026), MCP spec 2026-07-28, and agent payment protocols (AP2, x402, Visa TAP). Audience data from SBA Advocacy / Census BTOS (high). **Implementation reliability: medium.** The specs are real and have reference code (GoogleChromeLabs/webmcp-tools, Cloudflare demo), but the API surface is still changing, so ship a schema.org/llms.txt fallback.
- Risk: WebMCP is still an origin trial, so also ship plain schema.org + llms.txt.
- Prior art: OpenAI's WebMCP Challenge on Devpost (Aug-Sep 2026, 7,042 participants) had storefront entries (CartPilot, Sodium). Differentiate with no-code onboarding for non-technical owners + the before/after agent shopper test; avoid pitching at a WebMCP-themed event.

## 8. Bill Rescue (29/35)
1. **Name:** Bill Rescue
2. **Target audience:** 21.5M US households (1 in 6) behind on energy bills, $25B owed, up to 4M disconnections (NEADA, Feb 2026); LIHEAP reaches only ~17% of eligible households.
3. **Solution:** Snap your utility bill. The agent reads usage and rate plan, checks eligibility for LIHEAP, utility discount programs, budget billing, medical-certificate shutoff protection and weatherization, pre-fills the applications, and simulates a cheaper rate plan from your usage. It warns you 10 days before a shutoff date and drafts a payment-plan request.
4. **Relevance:** NEADA Energy Hardship Report (Feb 2026); LIHEAP cut from $6.1B (2023) to ~$4.0B (2026). The President's FY2027 budget proposes eliminating it, but the House committee bill keeps ~$4.055B and ACF released $3.63B early on Oct 9 2026 under the CR (APPA, AGA), so help exists and is front-loaded this winter; avg electric bill $121 -> $156 (2021-2025). Heat makes cooling a health issue (Yale Nov 2025: heat deaths +50% over two decades).
5. **Pitch:** "One photo of your power bill finds every dollar of help you qualify for, before the lights go out."
6. **Tech stack:** Expo; Claude vision for bill parsing; eligibility rules from state LIHEAP tables (JSON); OpenEI Utility Rate Database API for rate-plan simulation; PDF-lib for applications; Twilio reminders.
7. **Motivating paper(s) and reliability:** No academic paper. NEADA Energy Hardship Report (Feb 2026) is a report from an advocacy group (state LIHEAP directors) built on EIA/utility data, so credible but advocacy-framed. LIHEAP funding facts come from ACF/APPA (primary). The DOE LEAD tool provides energy-burden data. **Implementation reliability: high** for the build (bill OCR + eligibility tables + OpenEI rate data are all standard). The weak spot is state-by-state rule coverage.
- Risk: program rules vary by state and utility, so demo one state + 2 utilities.

## 9. Neighbor Call (29/35)
1. **Name:** Neighbor Call
2. **Target audience:** 15.8M Americans 65+ living alone (ACS 2024), with the highest risk in AZ/NV heat and West Coast smoke regions.
3. **Solution:** When the NWS issues heat alerts or AirNow AQI turns unhealthy, a warm voice agent calls each enrolled senior (landline OK): it asks about symptoms, AC status and water, gives tailored advice, offers a ride to a cooling center, and escalates to family or 211 if answers are worrying or no one picks up after 2 tries. Volunteers and Area Agencies on Aging get a live map.
4. **Relevance:** Wildfire smoke already kills ~41K Americans a year, projected 71K by 2050 (Nature, Sep 2025); heat deaths up >50% over two decades (Yale, Nov 2025); persistence of heat matters more than intensity (PLOS Climate, Aug 2025). Voice agents for health gaps (arXiv 2507.16229).
5. **Pitch:** "When the heat or smoke hits, every senior who lives alone gets a call, and nobody gets missed."
6. **Tech stack:** NWS alerts API (api.weather.gov) + NWS/CDC HeatRisk (ArcGIS ImageServer, experimental) + AirNow API (free key); Twilio Voice + realtime voice model; Claude for triage summary + risk rubric (deterministic red flags); Supabase; Mapbox dashboard for volunteers.
7. **Motivating paper(s) and reliability:** Qiu et al., *Nature* (Sep 2025; Stony Brook + Stanford, Burke lab), on wildfire-smoke mortality, peer-reviewed in a top journal. It is 14 months old and widely covered (NPR, WaPo, Grist); the citation count couldn't be retrieved. Yale heat-mortality study (Nov 2025) and PLOS Climate (Aug 2025) are peer-reviewed. *Voice-based AI Agents* (arXiv 2507.16229, IBM Research, IEEE ICDH 2025) is a conference perspective paper, not an evaluation. **Implementation reliability: high** for the evidence and the APIs (NWS, AirNow). The voice-triage safety is our own rubric and needs a clinician's review.
- Risk: medical triage, so it uses a rule-based red-flag list (confusion, no AC above 95°F, chest pain) that triggers a human/911 prompt.

## 10. First Rung (28/35)
1. **Name:** First Rung
2. **Target audience:** New grads and college students: ages 22-25 in AI-exposed jobs have 19% lower employment than peers (Stanford Digital Economy Lab, Aug 2026); ~1.97M bachelor's degrees a year (NCES 2022-23).
3. **Solution:** The agent maps a student's target role to tasks AI automates vs augments (Anthropic Economic Index open data + O*NET), then picks a real "good first issue" or open dataset problem that exercises the augment-side skills. It coaches the student through shipping it, with no ghostwriting enforced by commit-level checks, and compiles a verified portfolio card for recruiters.
4. **Relevance:** "Canaries in the Coal Mine?" (Brynjolfsson et al., rev. Aug 12 2026): decline comes from reduced hiring, concentrated where AI substitutes; complementary roles are flat or rising. "Helping People Choose Careers in the Age of AI" (arXiv 2607.15506, Jul 2026); SAFI skill-automation index (arXiv 2604.06906); Anthropic Economic Index Jun 2026 release (HF dataset, MIT).
5. **Pitch:** "AI took the first rung of the career ladder. We help students build a new one, with proof."
6. **Tech stack:** Next.js; Anthropic/EconomicIndex HF dataset + O*NET API; GitHub API (issue search, PR verification); Claude as coach (Socratic mode, no code writing); Postgres.
7. **Motivating paper(s) and reliability:** *Canaries in the Coal Mine?* (Brynjolfsson, Chandar, Chen; Stanford Digital Economy Lab working paper, Aug 2025, revised Nov 2025 and Aug 2026; ADP payroll microdata). Not peer-reviewed but very influential: presented at the Bank of England and World Bank and used as the empirical anchor by other papers. It is contested: a UCLA study and CPS-based analyses find small or no effects. *Helping People Choose Careers in the Age of AI* (arXiv 2607.15506; American U. + CU Boulder; data at github.com/jensteele1/careers-ai-data). Preprint. Anthropic Economic Index (MIT-licensed open dataset). **Implementation reliability: medium-high.** Motivation is strong if contested, and the build uses open datasets plus the GitHub API.
- Risk: it can't promise jobs, so measure "verified merged PRs" instead.
- Prior art: AEI-based "career AI risk" analyzers exist (e.g. career-analyzer-ten.vercel.app). The hook is the verified proof-of-work, not the risk score.

## 11. Fair Shift (28/35)
1. **Name:** Fair Shift
2. **Target audience:** App-based gig workers (rideshare/delivery): Pew 16% of US adults have done platform gig work; DoorDash alone had 7M+ US Dashers in 2024, averaging <4 h/week (DoorDash 2024 Economic Impact Report; 8M globally per FY2024 10-K).
3. **Solution:** Upload the platform data export. The agent computes true hourly pay including waiting time, mileage and expenses, detects pay-algorithm changes over time, and on deactivation drafts a jurisdiction-aware appeal (Seattle ordinance, MN/WA rules) with an evidence timeline and lost-wage estimate.
4. **Relevance:** HRW "The Gig Trap" (May 2025): Texas workers earned $5.12/h with waiting time counted; ~1/3 deactivated at least once. FareShare (arXiv 2505.08904): WA platforms overturn 80% of deactivations on appeal. The Ninth Circuit upheld Seattle's deactivation ordinance (Mar 2026); MN law gives 30-day appeals + a free advocate.
5. **Pitch:** "Know what you really earn, and fight back when an algorithm fires you."
6. **Tech stack:** Python/FastAPI; pandas for trip-data parsing (Uber/Lyft/DoorDash export formats); Claude for appeal drafting + rule lookup; Streamlit or Next.js; IRS mileage rate + fuel price API.
7. **Motivating paper(s) and reliability:** *FareShare* (arXiv 2505.08904; published in PACM HCI / **CSCW 2026, Best Paper Honorable Mention**; Princeton CITP; 6-month partnership with Washington's largest rideshare union, 178 users in a 3-month field deployment, >95% faster lost-wage calculation). The strongest paper on this list. Human Rights Watch *The Gig Trap* (May 2025) is a rigorous NGO report but its 127-worker Texas sample isn't representative. **Implementation reliability: high.** The FareShare method is published and validated in the field; extend it with LLM appeal drafting.
- Risk: platform ToS on scraping, so only use user-downloaded exports.
- Prior art: Gridwise (500K drivers) already tracks gross $/hour but has no appeal tool, and its old "Gridwise Protection" product looks discontinued. The hook is net pay incl. waiting time + a jurisdiction-aware appeal; DoorDash added in-app appeals in Mar 2026.

## 12. Citizen Ready (28/35)
1. **Name:** Citizen Ready
2. **Target audience:** ~8.7M green-card holders eligible to naturalize (DHS OHSS, Jan 2024), plus 813K people with pending N-400s (Aug 2026).
3. **Solution:** A source-grounded document agent (plus a voice civics/interview tutor). It checks travel history, tax and address gaps that trigger RFEs, builds the evidence packet, and tracks case status. Answers always cite the USCIS Policy Manual/8 CFR passage.
4. **Relevance:** Naturalization approvals fell 76% YoY (Q2 2026) and the approval rate dropped 91% -> 82%; median wait 9.5 months (USCIS data via Newsweek/immigration-analytics, 2026). ImmigrationQA (arXiv 2605.30589, May 2026): 17K source-grounded QA pairs, a 3B model fine-tuned for unrepresented petitioners.
5. **Pitch:** "Your path to citizenship, in your language, with every answer backed by the law."
6. **Tech stack:** Next.js PWA; realtime voice (Gemini Live / OpenAI Realtime) for the test interview; RAG over USCIS Policy Manual + 8 CFR (pgvector); optional ImmigrationQA-tuned Llama 3.2 3B for on-device answers; USCIS case-status lookup (mock).
7. **Motivating paper(s) and reliability:** *ImmigrationQA* (arXiv 2605.30589, May 2026). Single author, no affiliation listed, not peer-reviewed. Dataset, model and code released (github.com/nshportun/usa-immigration, 2★; HF dataset + Llama-3.2-3B model). Backlog data from USCIS via Newsweek and immigration-analytics (secondary). **Implementation reliability: low-medium.** Reuse the idea (source-grounded RAG over the USCIS Policy Manual + 8 CFR) but don't rely on the released model's accuracy without your own checks.
- Risks: legal advice / UPL, so it gives information only, refers complex cases (criminal history, long trips) to DOJ-accredited reps, and keeps data local because immigration data is sensitive.
- Prior art: AI civics tutors already exist (CivixApp, CivicFlare, PassTheCivics, a high-schooler's bilingual tutor for Erie House, Oct 2026). Lead with the RFE-risk/evidence checker; the tutor is a side feature.

## 13. Say It, Sign It (28/35)
1. **Name:** Say It, Sign It
2. **Target audience:** ~58.9M US adults (28%) at or below PIAAC Level 1 literacy (PIAAC 2023, released Dec 2024; ProLiteracy).
3. **Solution:** Point the camera at any paper or PDF form (benefits, school enrollment, lease, clinic intake). The agent reads it aloud in plain language and your language, asks the questions conversationally, validates answers with rules (dates, SSN format, required fields), and produces a filled PDF to sign, plus an audio recap of what you agreed to.
4. **Relevance:** FormBharo (arXiv 2608.06027, Aug 2026): a voice agent that fills forms for low-literacy users with LLM + deterministic validation, piloted with ARMMAN. PIAAC 2023: US adults at Level 1 or below rose from 19% to 28% since 2017.
5. **Pitch:** "If you can talk, you can fill out any form."
6. **Tech stack:** Expo; Claude vision for form field detection; pdf.js + PDF-lib (AcroForm filling); realtime voice (STT/TTS) in 10+ languages; JSON-schema validators.
7. **Motivating paper(s) and reliability:** *FormBharo* (arXiv 2608.06027; ARTPARK/IISc; NGO pilot; NeurIPS 2026 workshop companion). Preprint, citations ~0. PIAAC 2023 (OECD/NCES) is the gold-standard literacy survey. **Implementation reliability: medium-high.** The paper documents the exact architecture (STT → LLM extraction → rule validation) and its model/latency trade-offs, but it was tested in Hindi over phone calls, not on US paper forms.
- Overlap note: the generic engine for #1; pitch separately if needed, or merge.

## 14. Loan Lens (27/35)
1. **Name:** Loan Lens
2. **Target audience:** ~7M former SAVE borrowers forced to switch plans (90-day notices Jul-Aug 2026), within 42M federal borrowers; ~10-12M delinquent or in default.
3. **Solution:** Upload your servicer notice or bill. The agent recomputes your payment under RAP, Tiered Standard and IBR from your AGI and family size, flags billing errors, explains Parent PLUS ineligibility, drafts a correction request to the servicer and a CFPB complaint if needed, and pre-fills the IDR form (paper version added RAP Oct 2026).
4. **Relevance:** SAVE ended (court order Mar 10 2026); RAP live Jul 1 2026 under OBBBA; the Education Dept found IDR/RAP calculation errors and sent reapply notices (CollegeLens Sep 2026); TCF: 530K pending IDR apps, servicer billing errors. 7.7M borrowers were in default at the start of 2026. Garnishment (up to 15% of pay, no court order) was paused on Jan 16 2026, and Forbes/Yahoo (Oct 2026) report ED and Treasury are preparing to restart collections. Treasury took over defaulted-loan collection in Mar 2026.
5. **Pitch:** "Your loan servicer got the math wrong. We catch it in 30 seconds."
6. **Tech stack:** Next.js; Claude vision for letter parsing; deterministic RAP/IBR calculators (TypeScript, unit-tested against ED formulas); PDF-lib for the IDR form; no data storage (privacy).
7. **Motivating paper(s) and reliability:** No research paper. It rests on law and agency facts: the OBBBA statute (RAP formula), the Mar 10 2026 court order ending SAVE, Education Department notices, and reporting from TCF, Forbes and NPR (secondary). **Implementation reliability: medium.** The calculator is deterministic and testable against the statute, but agency rules and servicer behavior are changing (garnishment restart is pending).
- Risk: formulas change, so publish the formula version and cite the statute.

## 15. Puente Tutor (26/35)
1. **Name:** Puente Tutor
2. **Target audience:** 5.3M K-12 English learners (10.6% of public school students, NCES fall 2021, latest), plus their teachers.
3. **Solution:** A guardrailed Socratic math/science tutor that scaffolds in the student's home language and gradually shifts to English (translanguaging). It never gives answers. Teachers get a misconception dashboard and a built-in fairness audit that replays the same session as different student personas and flags quality gaps.
4. **Relevance:** Harvard physics RCT (Sci. Reports, Jun 2025): a guardrailed AI tutor gave >2x learning gains; World Bank Nigeria RCT (May 2025): 0.31 SD in 6 weeks at $48/student; EduFair-Bench (arXiv 2609.12949, Sep 2026): tutoring quality varies by immigration background and first language; unrestricted chatbots hurt exam performance (UMD 2026 trial).
5. **Pitch:** "The tutor that explains in Spanish, tests in English, and proves it treats every kid fairly."
6. **Tech stack:** Next.js; Claude with a strict tutoring system prompt + answer-leak checker; KaTeX; EduFair-style persona replay harness; Supabase (FERPA-minded, no PII in prompts).
7. **Motivating paper(s) and reliability:** Kestin et al., *Scientific Reports* (Jun 2025; Harvard; crossover RCT, n=194). Peer-reviewed and widely cited in follow-on AI-tutor work (several 2025-26 arXiv papers cite it). A critique notes unexplained attrition (142 vs 174 scored tests) and only 2 topics. De Simone et al., *From Chalkboards to Chatbots* (World Bank Policy Research WP 11125, May 2025; RCT, n≈657; reproducibility package published). Not peer-reviewed. *EduFair-Bench* (arXiv 2609.12949; EPFL; data + code released). Preprint. **Implementation reliability: high-medium.** Two RCTs agree that guardrailed tutors work (unrestricted chatbots don't), and the fairness benchmark is reusable.
- Risk: crowded EdTech space (HiveMind won TreeHacks 2025 Education), so lead with the fairness audit.

---

## Scoring table (Src/Aud/Feas/Demo/Nov/Impact/Judge)
| # | Idea | Lane | Scores | Total |
|---|---|---|---|---|
| 1 | ShiftProof | Benefits | 5/5/4/5/4/5/4 | 32 |
| 2 | ClearPath Web | Accessibility | 5/5/4/5/4/4/5 | 32 |
| 3 | Second Key | Fraud/older adults | 5/5/3/5/3/5/4 | 30 |
| 4 | Honest Nurse | Health/caregiving | 5/5/4/4/3/5/4 | 30 |
| 5 | Status Keeper | Immigration/students | 5/4/4/4/4/4/5 | 30 |
| 6 | Answer in Time | Legal/housing | 4/4/4/4/3/5/5 | 29 |
| 7 | AgentReady Main Street | Small biz/agentic commerce | 5/5/4/4/3/3/5 | 29 |
| 8 | Bill Rescue | Energy | 4/5/4/4/4/4/4 | 29 |
| 9 | Neighbor Call | Climate-health | 4/4/4/4/4/5/4 | 29 |
| 10 | First Rung | Work/new grads | 5/5/4/3/4/3/4 | 28 |
| 11 | Fair Shift | Work/gig | 5/4/4/3/4/4/4 | 28 |
| 12 | Citizen Ready | Immigration | 5/4/4/4/3/4/4 | 28 |
| 13 | Say It, Sign It | Literacy | 5/5/4/5/3/3/3 | 28 |
| 14 | Loan Lens | Finance/students | 5/5/4/3/3/4/3 | 27 |
| 15 | Puente Tutor | Education | 5/4/4/3/3/4/3 | 26 |
Ties have no further ordering rule. Say It, Sign It overlaps #1 (it is ShiftProof's generic engine).
Lanes: 13 distinct, max 2 per lane (Work: First Rung + Fair Shift; Immigration: Status Keeper + Citizen Ready).

## Dropped (with reason)
- Health insurance appeal agent: Counterforce Health, Claimable, Fight Health Insurance already exist.
- FEMA appeal agent: Kava won HackMIT 2025 with a near-identical idea.
- Scam-baiting bots: legal/ethics risk; O2 "Daisy" exists.
- Prompt-injection firewall for AI browsers: audience not definable for judges.
- VA claim organizer: weak recent source; VA backlog fell 57% in FY2025.
- Lingo Bridge Care (LEP phone interpreter): crowded. Opalite Health (YC), No Barrier, LanguageLine automated interpreter, AI Call, open-source Twilio+Realtime interpreters (CHCF report Mar 2026). Replaced by Status Keeper.

## Picking one
- General collegiate hackathon (TreeHacks/Cal Hacks style): ClearPath Web or Second Key, because accessibility and live voice demos win grand prizes.
- AI/agents-sponsored event (Claude, Gemini): ShiftProof or Status Keeper. Both are agents that act on documents and changing rules, the CrossBeam pattern.
- Health track: Honest Nurse. Civic/social-good track: ShiftProof, Answer in Time or Bill Rescue. Climate track: Neighbor Call.
- Starter code: The verified-repair extension (arXiv 2608.24913, ACM doi 10.1145/3776591.3833866) releases its code and benchmark at figshare.com/s/baec720691de58f99f92, a good starter for ClearPath Web. No code link found for CallScreenBench (arXiv 2609.23959; authors linked to scam.ai/trustable.ai). ImmigrationQA and FormBharo only match unrelated hobby repos.
