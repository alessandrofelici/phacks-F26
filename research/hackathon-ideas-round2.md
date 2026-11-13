# Round 2 ideas (2026-11-13, event day)
These are new ideas to go alongside the 15 in `hackathon-ideas-final.md`. Most of them target the gaps: **Entertainment** and **Science & Discovery** had no ideas, and **Sustainability** only had a weak fit (Bill Rescue).
Inputs: the official Fall '26 track wording and MLH prizes (`prizes/hackprinceton-fall-26-prizes.txt`, fetched today), plus the patterns in `hackprinceton-winners-analysis.md`. Those patterns are iMessage/Photon as the interface, monitor→alert systems for Healthcare, workflow agents for B+E, and geospatial/IoT for Sustainability.

**These are brainstorm ideas, not research.** Nothing here went through the source, prior-art and audience checks used in round 1. Every "Check" line is something to confirm with a few minutes of searching before committing. I left out audience figures on purpose rather than guess them.

Quick score (1-5 each): **Fit** to the track wording, **Demo** wow in 2 minutes, **Build** feasibility for 3 people in about 30 hours, **Gap** (likely fewer competing teams in that track or prize).

| # | Idea | Track | Prize stack | Fit/Demo/Build/Gap | Total |
|---|---|---|---|---|---|
| 1 | Group Chat Game Master | Entertainment | Photon, Gemini | 5/5/4/4 | 18 |
| 2 | Bench Voice | Science & Discovery | Gemini, Tiger Data | 5/4/4/5 | 18 |
| 3 | Retrofit Radar | Sustainability | B+E alt, Tiger Data | 4/4/4/5 | 17 |
| 4 | Office Hours Router | Education | Photon, MongoDB | 5/4/4/4 | 17 |
| 5 | Teach-Back | Education | Gemini | 5/5/4/3 | 17 |
| 6 | Field Ping | Science & Discovery | Photon, MongoDB | 4/5/4/4 | 17 |
| 7 | Shade Map | Sustainability | Gemini | 5/4/3/4 | 16 |
| 8 | Described Live | Entertainment | Gemini, Best Overall | 4/5/3/4 | 16 |
| 9 | Cash Drawer | B+E | Photon, Capital One | 4/4/4/3 | 15 |
| 10 | Wound Check | Healthcare | Photon | 5/4/4/2 | 15 |
| 11 | Air Badge | Healthcare / Hardware | Best Hardware, Tiger Data | 4/4/3/4 | 15 |
| 12 | Repro Bot | Science & Discovery | Vultr | 5/3/2/5 | 15 |

---

## 1. Group Chat Game Master (Entertainment)
- **Idea:** An AI game master that lives in an iMessage group chat (Photon) and runs a weekend-long mystery or improv game. It hands each player a secret role by DM, drops clues in the group, reacts to photos players send ("bring me something red"), and keeps the story consistent through a structured world state rather than raw chat history.
- **Demo moment:** The judges text a number, get pulled into a 3-minute mini-mystery live, and one judge receives a secret DM saying they're the culprit.
- **Why it could win:** It fits the Entertainment wording ("storytelling apps, interactive experiences") directly. The Spring '26 Entertainment winner (Someone Save Us) used Photon. It's also the only idea here whose demo puts the judges inside the product.
- **Build:** Photon spectrum-ts (needs a persistent server), Claude or Gemini to narrate, a JSON world state with a deterministic rules layer for who knows what.
- **Check:** iMessage party-game bots on Devpost. Photon's group-chat support and rate limits.
- **Risk:** Venue Wi-Fi and Apple ID setup. Keep a fallback on a pre-recorded group.

## 2. Bench Voice (Science & Discovery)
- **Idea:** A hands-free voice assistant for wet-lab work (gloves on, can't touch a screen). It loads a protocol (PDF or protocols.io), walks through it step by step, runs the timers, and logs every deviation by voice ("added 55 µL, not 50") with timestamps into a structured lab notebook entry. At the end it flags any step that went out of spec.
- **Demo moment:** A teammate "runs" a protocol at the table using only their voice, and a clean, timestamped notebook entry with one flagged deviation appears on screen.
- **Why it could win:** It matches "tools to aid scientific processes and methods" word for word, and Princeton judges include researchers. The Science & Discovery track probably gets few strong entries (the round-1 list had none).
- **Build:** Browser speech (Web Speech API or streaming STT), an LLM that parses the protocol into steps, Tiger Data/Postgres for the timestamped event log.
- **Check:** Existing lab voice assistants (e.g. LabTwin, HelixAI) and whether any are free or open. Bring a real protocol from a Princeton lab if a teammate has one.
- **Risk:** Mic noise in the venue. Use a headset.

## 3. Retrofit Radar (Sustainability, alt B+E)
- **Idea:** Building-performance laws (e.g. NYC Local Law 97) fine large buildings that exceed carbon limits. Retrofit Radar takes a building address, pulls the city's public energy-benchmarking data, estimates the carbon gap and the fine exposure by year, and drafts a ranked retrofit plan (heat pumps, LED, envelope) with payback periods and the incentives that apply.
- **Demo moment:** Type a real NYC address and get "projected fine: $X/yr from 2030" plus a three-step plan that brings the fine to zero.
- **Why it could win:** It's geospatial and data-driven (the pattern Sustainability winners follow) and has a B+E angle (property owners, and CoStar was a listed Fall 2026 sponsor). It also uses real public data rather than a mock.
- **Build:** NYC Open Data benchmarking dataset (Socrata API), LL97 emission factors and limits as a rules table, LLM for the plan narrative, a map view.
- **Check:** The current LL97 limits and fine rate ($/ton) from the law text. Existing tools (several consultancies offer LL97 calculators), so the hook is the full plan plus incentives, not the fine calculation alone.
- **Risk:** Getting the emissions math wrong in front of judges. Keep it as deterministic code and show the formula.

## 4. Office Hours Router (Education)
- **Idea:** For large CS courses: students describe their bug in the office-hours queue, the agent groups students stuck on the same issue into small group sessions, answers conceptual questions from the course materials without giving away solutions, and shows TAs a live board of "what the class is stuck on."
- **Demo moment:** 20 queued questions collapse into 4 clusters, one TA takes a group of 6, and the dashboard shows "62% stuck on the same pointer bug."
- **Why it could win:** Every judge has stood in an OH queue, and it's personalized and scalable learning. The team knows COS courses first-hand.
- **Build:** Next.js queue, embeddings + clustering, LLM with course-material retrieval and a "no solutions" guardrail, MongoDB Atlas (MLH prize).
- **Check:** Existing tools (e.g. Princeton's own queue tools, Ed, the course-assistant pilots at Harvard and Stanford).
- **Risk:** Academic-integrity questions. Show the guardrail explicitly in the demo.

## 5. Teach-Back (Education)
- **Idea:** You learn by teaching. The AI plays a curious, slightly confused student. You explain a concept out loud, it asks the questions a real novice would, catches gaps and wrong statements, and ends with a short report: what you explained well, what you got wrong, what to review.
- **Demo moment:** A judge explains a concept by voice, and the AI catches a subtle mistake with "wait, but then why does…".
- **Why it could win:** It's interactive and personal, a fresh take on AI tutors (they usually explain *to* you), and the learning-by-teaching effect is well established.
- **Build:** Realtime voice (Gemini Live or OpenAI Realtime), a concept rubric generated per topic, a misconception checker.
- **Check:** Prior art. This exists in some form (e.g. "Feynman technique" apps), so the hook must be voice plus the misconception report.
- **Risk:** Crowded Education track. Gap score is only 3.

## 6. Field Ping (Science & Discovery)
- **Idea:** Citizen science over iMessage. Text a photo of a plant, insect or bird, and the agent identifies it, asks one follow-up question that makes the record scientifically useful (location, count, behavior), then logs a research-grade observation and tells you what scientists are tracking in your area ("you're the 3rd to report this invasive species this week").
- **Demo moment:** Text a photo of a leaf from the venue and get back an ID, a follow-up question, and a map pin among other reports.
- **Why it could win:** It turns curiosity into discovery, which is the track wording. It also stacks with Photon.
- **Build:** Photon, a vision LLM (Gemini qualifies for the MLH prize), MongoDB for observations, Leaflet map. Optionally export to iNaturalist format.
- **Check:** iNaturalist's own app does ID well, so the hook is zero-install texting plus the data-quality follow-up questions. Check the iNaturalist API terms.
- **Risk:** It reads as "Seek over text" if the follow-up questions aren't clearly smart.

## 7. Shade Map (Sustainability)
- **Idea:** For city planners and neighborhood groups: combine satellite land-surface temperature, tree canopy and sidewalk or bus-stop locations to rank where new trees or shade structures would cool the most people. Then auto-draft the grant application or 311 request for the top site.
- **Demo moment:** A heat map of Trenton, click the hottest bus stop, and a "plant 4 trees here, est. −X°F" card plus a drafted grant paragraph appear.
- **Why it could win:** Geospatial work matches the TerraLink and Watt's Up wins. It also connects to Neighbor Call's heat story if the team pivots.
- **Build:** Landsat LST via Google Earth Engine or precomputed tiles, a canopy layer, OSM bus stops, a scoring formula, LLM for the drafting.
- **Check:** The American Forests Tree Equity Score already ranks neighborhoods, so the hook is block-level siting plus the drafted application.
- **Risk:** Earth Engine setup time. Precompute one city.

## 8. Described Live (Entertainment)
- **Idea:** Live audio description for blind and low-vision viewers of content that has none (livestreams, sports clips, short-form video). A vision model watches the stream and speaks short descriptions in natural pauses in the dialogue, without talking over it.
- **Demo moment:** Play a silent-action clip with the screen off, then turn the screen on and show how much the description captured.
- **Why it could win:** Accessibility grand prizes keep winning (round-1 finding), and media accessibility fits "creatively integrate entertainment and media."
- **Build:** Frame sampling, Gemini video understanding, voice-activity detection to find gaps, TTS.
- **Check:** YouTube and Netflix AD coverage, and existing AI audio-description startups.
- **Risk:** Latency. Demo on a short clip with a buffer rather than a fully live stream.

## 9. Cash Drawer (B+E)
- **Idea:** Bookkeeping over iMessage for cash-heavy micro-businesses (food trucks, barbers, street vendors). Text receipt photos and voice notes ("sold 40 tacos, $3 each"), and it keeps a running P&L, separates personal from business spending, and produces a tax-ready Schedule C summary.
- **Demo moment:** Three texts (receipt photo, voice note, "how'd I do this week?") return a weekly P&L chart.
- **Why it could win:** It's a workflow agent (the B+E pattern) and stacks Photon with Capital One (Nessie for mock accounts) if those prizes are announced.
- **Build:** Photon, vision LLM for receipts, a deterministic ledger, Nessie for the bank feed.
- **Check:** Crowded (QuickBooks, Wave, many hackathon receipt apps). The hook must be voice and no app at all.
- **Risk:** Generic-chatbot penalty. Gap score is 3.

## 10. Wound Check (Healthcare)
- **Idea:** After surgery, patients get a daily iMessage asking for a photo of the incision and three symptom questions. The agent compares today's photo with earlier ones, tracks a trend, and escalates to the care team only on red flags (spreading redness, fever plus pain), with the photo series attached.
- **Demo moment:** Four days of photos with a worsening trend trigger a nurse alert containing the side-by-side images.
- **Why it could win:** It's a monitor→alert system (the VITAL pattern) and Photon-native.
- **Build:** Photon, vision LLM with a structured rubric, a nurse dashboard.
- **Check:** Prior art. Several remote post-op monitoring products exist (Gap score 2), so it needs a sharper hook before committing.
- **Risk:** Medical-claim scrutiny. Pitch it as triage support, not diagnosis.

## 11. Air Badge (Healthcare, Best Hardware)
- **Idea:** A clip-on air-quality badge (CO2 and PM2.5 sensors on an ESP32) for people with asthma or for classrooms. It streams to a time-series database, learns your personal exposure pattern, and texts you before you walk into a bad-air situation ("your 2pm room hit 1800 ppm yesterday, open a window").
- **Demo moment:** Breathe on the badge, the CO2 reading spikes on a live chart, and a text arrives.
- **Why it could win:** It's the only idea here that qualifies for Best Hardware Hack. Tiger Data's prize literally names "real-time IoT monitoring". The MongoDB prize is an M5Stack kit, which hints at an IoT crowd.
- **Build:** ESP32 + SCD40/PMS5003 (needs hardware from the venue or bought ahead), Tiger Data continuous aggregates, Twilio or Photon alerts.
- **Check:** What hardware the hardware lab has. Without a CO2 sensor this idea is dead.
- **Risk:** Hardware lead time on event day.

## 12. Repro Bot (Science & Discovery)
- **Idea:** Paste an arXiv link. The agent finds the paper's code, sets up the environment in a cloud sandbox, runs the smallest experiment, and reports "headline number reproduced / off by X / couldn't run because Y", with the log.
- **Demo moment:** A paper's Table 1 number is reproduced live on a Vultr GPU.
- **Why it could win:** "Research accelerators" is the track wording, and it stacks with the Vultr prize. Low competition is likely because it's hard.
- **Build:** Agent with shell tools in a container on Vultr, arXiv API plus Papers with Code links.
- **Check:** Existing efforts (several reproducibility-agent benchmarks exist). Pick 2-3 demo papers known to run quickly.
- **Risk:** Lowest buildability here. Only attempt it if a teammate has done agent + Docker work before.

---

## Takeaways from today's Devpost page
- **Photon and Capital One are not listed yet.** Only MLH prizes are up. Ask at the opening ceremony or Discord whether sponsor prizes are coming before building around them. If they don't appear, the Photon-based ideas (1, 6, 9, 10) lose their prize stack, though iMessage still works as a demo interface.
- **Cheap stacks:** Gemini (any idea using Gemini for vision or voice), MongoDB or Tiger Data (whichever database you'd use anyway), and GoDaddy domain name (register a fun domain). These cost almost nothing to add.
- **SpaceXSI raffle** requires Cursor plus a Grok Bot, and the team plans to use Claude Code. Skip it unless someone already uses Cursor.
- **Best Hardware Hack** is a separate award. Only Air Badge (#11) targets it.

## Suggested shortlist with Second Key and Neighbor Call
1. Keep **Second Key** or **Neighbor Call** as the main bet if Photon/Capital One prizes are confirmed.
2. If sponsor prizes don't appear, **Bench Voice** (Science & Discovery) and **Group Chat Game Master** (Entertainment) target the two tracks the team had no entry for, where competition is likely thinnest.
3. Before committing, run any of these through `event-day-brainstorm-prompt.md` with the final prize list.
