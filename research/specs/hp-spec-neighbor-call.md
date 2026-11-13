# Neighbor Call: refined spec (cycle C1, 2026-11-09)
Track: **Healthcare** (public health). Sponsor stack: Photon (iMessage family alerts via Spectrum), Amazon Practical AI (generic).

## R1 Facts for the pitch (checked)
- Maricopa County 2025: **430 heat-related deaths**; AC present in 94% of indoor deaths; people 50+ were **90% of indoor deaths** (Maricopa 2025 Heat Deaths Report, via ABC15/search; PDF not opened, so the 94% vs "AC not working" split is unknown).
- 15.8M Americans 65+ live alone (ACS 2024). Wildfire smoke ~41K deaths/yr (Qiu et al., Nature, Sep 2025).
- CDC/NIA warning signs for older adults: confusion or acting strangely, no sweating, dizziness, nausea, headache, weakness, vomiting, fast/weak pulse; fans don't prevent heat illness in the high 90s (CDPH). These become the deterministic red-flag list.
- No published evaluation of phone check-in programs during heat waves was found. Pitch it as filling a gap, not as "proven".

## R2 Tech (verified via docs/GitHub/search; no live calls, since the proxy blocks the API hosts)
| Need | Choice | Notes |
|---|---|---|
| Trigger | NWS `api.weather.gov/alerts/active?area=AZ` | Free, no key, **must send a User-Agent**. Event names changed Mar 4 2025: "Extreme Heat Warning/Watch" (was "Excessive"); match both. |
| Smoke | AirNow `/aq/observation/current/ziplatlong/` | Free key, 500 req/h. **Old `/zipCode/current` endpoint retired Sep 30 2026**; old tutorials will break. |
| Phone call | Twilio Voice + **ConversationRelay** | Twilio does STT/TTS and sends text over a WebSocket; our server calls Claude. $0.07/min + ~$0.014/min outbound. Starter repos: pBread/twilio-agentic-voice-assistant, rishabkumar7/twilio-cr-gemini-python (swap Gemini for Claude). **Upgrade Twilio** (trial = 5 verified numbers, trial message, 75 min). |
| Family alert | Photon `spectrum-ts` (npm 12.15, MIT, 2.2k★) | Proactive DM works: `im.user("+1…")` then `im.space.create(user)` then `space.send(text)`. Inbound uses a long-running `for await` loop, so host it on a persistent Node process (Railway/Fly/laptop), not Vercel functions. Free $100 credit. |
| LLM | Claude (Haiku-class for live turns, latency) | Conversation only; the escalation decision is deterministic. |
| App | Next.js dashboard + Supabase | Coordinator view: roster, call status, flags. |

## R3 Prior art and the differentiator
- Daily AI check-in call services exist: AloneAssist ($19.99/mo, conversational AI call, alerts after 3 misses), Verocall ($19/mo), iamfine ($14.99, press-1), police "R U OK" programs. NYC "Be a Buddy" uses human volunteers.
- **Differentiator (one sentence):** "Not a daily subscription: a free, event-triggered heat and smoke response that calls only when the weather turns dangerous, asks heat-specific clinical questions, and hands the county a ranked list of who needs a ride to a cooling center *now*."
- Novelty is moderate (3/5); the strength is the public-health framing + the trigger + the coordinator view.

## R4 Design
**Flow:** NWS/AirNow poll (or demo button) → select enrolled seniors in affected zones → Twilio outbound call → ConversationRelay ↔ our WebSocket ↔ Claude (script + free talk) → answers parsed into `CheckIn` → rules engine → status green/yellow/red → red: family iMessage via Photon + dashboard alert + offer cooling-center ride; no answer x2: family + "wellness check" flag.

**Data contracts**
```json
// Senior
{"id":"s1","name":"Rosa M.","phone":"+1602…","zip":"85008","lang":"es","family":[{"name":"Ana","phone":"+1…","channel":"imessage"}],"meds_affect_heat":true,"has_ac":true}
// Alert
{"id":"nws-…","type":"Extreme Heat Warning|AQI","zones":["AZZ537"],"zips":["85008"],"starts":"…","ends":"…","severity":"Extreme"}
// CheckIn (written by the agent via a tool call)
{"senior_id":"s1","alert_id":"…","answered":true,"ac_working":false,"indoor_temp_hot":true,"water_ok":true,"symptoms":["dizziness"],"confused":false,"wants_ride":true,"transcript_url":"…"}
// Triage (deterministic)
{"senior_id":"s1","level":"red","reasons":["AC not working","symptom: dizziness"],"actions":["family_imessage","coordinator_alert","offer_ride"]}
```
**Red flags (deterministic):** any of confusion, no sweating, fainting, vomiting, chest pain → "tell them to call 911 now + family + coordinator". AC broken/off, or indoor hot + meds affecting heat → red (ride). Dizziness/headache/nausea/weakness → yellow (call back in 1 h + family). No answer after 2 tries → red (wellness check).

**2-minute demo script**
- 0:00 "Last year Maricopa County lost 430 people to heat; 9 in 10 indoor deaths were 50+." Show the dashboard with 6 seniors in Phoenix.
- 0:15 Click "Simulate NWS Extreme Heat Warning." The judge's phone rings (judge = "Rosa").
- 0:20-1:10 The agent asks 4 questions in ~40 s; the judge says "my AC broke, I feel a bit dizzy". The dashboard turns Rosa red live; the family phone (teammate) gets an iMessage: "Rosa's AC is out and she's dizzy. Cooling center at … 1.2 mi; ride requested."
- 1:10-1:35 Show the no-answer case (pre-run) → wellness-check flag.
- 1:35-1:55 "Claude talks; rules decide. Every red flag is from CDC guidance." Architecture slide.
- 1:55-2:00 "Free for counties; Area Agencies on Aging run it."

**Fallbacks:** Twilio fails → browser WebRTC call (ConversationRelay WebRTC demo repo) or a recorded run. Photon fails → Twilio SMS. NWS down → cached alert JSON.
**Cut list (in this order if behind):** smoke/AirNow, Spanish, ride booking (link only), multi-county, auth.

## R5 Score
Fit 5, pattern 4, feasibility 4 (ConversationRelay removes the hardest part), charity 5, creativity 3 (down from 4: check-in services exist), sponsor +1 → **22** (was 23). Still a top pick for the Healthcare track.

## Update 2026-11-09 (live data + HackPrinceton winners)
- **Scope change: all extreme weather, not just heat.** HackPrinceton is Nov 13-15: no heat alerts in November (live NWS check 05:5x UTC: 0 Extreme Heat Warnings), but there were live Winter Storm Warnings/Watches and Winter Weather Advisories. Cold is as deadly: **~2,520 US deaths with hypothermia as a cause in 2023** (provisional CDC via KFF Health News) vs **2,391 heat-related deaths in 2024** (CDC MMWR QuickStats); adults 65+ have the highest cold death rates. Pitch: "Heat and cold kill ~5,000 Americans a year, mostly older adults alone at home."
- Demo uses **real alerts from that weekend**: query `api.weather.gov/alerts/active?event=...` live on stage (verified working from CT 120 with a User-Agent; it returned real AZ Flood Warnings).
- Question script per hazard: heat (AC, water, symptoms), cold (heat source working, power, warm room, symptoms of hypothermia: shivering, confusion, slurred speech), smoke (windows closed, air filter, breathing).
- HackPrinceton fit: the Spring '26 Healthcare winner **VITAL** was a "monitor, detect deterioration, alert family" system using Photon, the same shape as this. Family/caregiver updates via **Photon iMessage** targets Photon's recurring prize (5 winners in Fall '25).
- AirNow API reachable (401 without key) → get a free key before the event.
