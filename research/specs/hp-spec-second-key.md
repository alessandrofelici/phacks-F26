# Second Key: refined spec (cycle C2, 2026-11-09)
Track: **Business + Enterprise** (fraud prevention = cybersecurity/fintech, B2B for banks). Sponsor stack: **Capital One Best Financial Hack** (Nessie mock-bank API optional), **Photon** (family co-sign over iMessage).

## R1 Facts for the pitch (checked)
- FTC *Protecting Older Consumers 2025-26* (Oct 2026): adults 60+ reported ~$3B lost in 2025, 5x since 2020; largest losses by bank transfer, then crypto; reports >$100K = 6% of reports but 70% of dollars.
- Regulation is moving toward holds: FINRA filed (Federal Register, Sep 9 2026, SR-FINRA-2026-018) a new **Rule 2166, a temporary delay of up to 5 business days for suspected fraud, for any customer**, plus longer Rule 2165 holds (55 → 145 business days) and "emergency contact" wording for trusted contacts. Still a proposal, not approved as far as I found. Banks rely on state hold laws + the 2024 interagency statement.
- McAfee 2026: 13% of parents have a family codeword.

## R2 Tech
| Need | Choice | Notes |
|---|---|---|
| Call screening | Twilio Voice + ConversationRelay (text stream) → Claude classifier prompt + keyword rules | Same plumbing as Neighbor Call. CallScreenBench's 4B model is optional and unreleased, so skip it. |
| Bank | Capital One **Nessie** (customers, accounts, transfers) for the sponsor prize + our own "hold" layer | api.nessieisreal.com is blocked from this machine (proxy), so it's unverified here; 2026 hackathon tracks still list it. Nessie has no hold concept, so our service sits in front: `POST /transfer` → risk check → `held` → co-sign → forward to Nessie. Fallback: an in-app mock bank. |
| Co-sign | Photon Spectrum iMessage (proactive DM via `im.space.create`) with a reply "YES 4821 / NO" | Twilio SMS fallback. |
| App | Next.js: "Grandma's bank app" (big buttons) + "Family view" + "Bank ops console" (B2B angle) |

## R3 Prior art and the differentiator
- **EverSafe** (AI monitoring of accounts/email, read-only trusted advocates, ~$7.49/mo; Fidelity integration 2026), **Carefull** (Edward Jones partnership Jun 2026; monitoring + caregiver alerts), **True Link** (prepaid card with merchant blocks + real-time purchase alerts), **ElderGuard AI** (hackathon winner 2025: deepfake call detection + family notification), Pixel/iOS call screening.
- All of them either watch the call **or** watch the account, and alert *after* the fact. **Differentiator:** "Second Key links the two: when a pressure call is in progress, the next outgoing transfer is held until a family member co-signs, which is the 'temporary delay + trusted contact' model regulators are writing into FINRA Rule 2166, delivered as an API banks can plug in."
- Creativity 3 → 4 with the call-to-payment link + regulatory hook.

## R4 Design
**Flow:** call arrives on the senior's line (Twilio number) → live transcript → risk score per turn (rules: urgency, secrecy, "don't tell", gift card, crypto ATM, wire, bail, IRS; plus Claude judgment) → risk ≥ threshold: session flagged "pressure call active", family pinged ("Rosa is on a call that looks like a bail scam") → senior opens the bank app and tries a $4,800 transfer → held → family iMessage with amount, payee, call summary → family replies NO → transfer cancelled, senior sees a calm explanation; YES + code → released to Nessie.
**Safe-word step:** during the flagged call the agent (whisper-only to the senior via SMS, or audible if the senior opts in) suggests asking the family question; we won't speak to the caller by default (consent, false positives).

**Data contracts**
```json
// RiskEvent
{"call_id":"c1","senior_id":"s1","turn":3,"score":0.86,"cues":["urgency","bail","secrecy"],"summary":"Caller claims to be grandson in jail, asks for bail money"}
// TransferRequest
{"id":"t1","senior_id":"s1","amount":4800,"payee":"QuickBail LLC","method":"wire","status":"held|released|cancelled","hold_reason":"active pressure call","cosigner":"+1…","expires_at":"…"}
// CoSignDecision
{"transfer_id":"t1","by":"+1…","decision":"deny","code_ok":true,"at":"…"}
```

**2-minute demo script**
- 0:00 "Seniors lost $3B to reported fraud last year, most of it by bank transfer." Three screens visible: grandma's phone, family phone, bank console.
- 0:15 The judge holds "grandma's" phone; a teammate calls as the "grandson in jail". The live transcript scrolls and the risk meter climbs; at turn 3, family gets an iMessage.
- 0:55 The judge (as grandma) taps "Send $4,800" in the bank app → "Held: waiting for Ana".
- 1:10 Family replies "NO". Transfer cancelled; grandma sees "Ana says this isn't real. Call her now."
- 1:25 The bank console shows the held transfer + audit trail: "the FINRA 2166 workflow, automated."
- 1:45 "EverSafe and Carefull alert after the money moves. Second Key stops it while the call is live."

**Fallbacks:** Twilio fails → pre-recorded call audio played into the transcript; Photon fails → SMS; Nessie fails → mock bank.
**Cut list:** safe-word whisper, multiple family co-signers, crypto-ATM/gift-card merchant blocks, Spanish.
**Legal/ethics notes for Q&A:** two-party-consent states mean the screener announces itself; a family override on false positives; there's no credential access, since the senior initiates every transfer.

## R5 Score
Fit 4 → **5** if pitched B2B to banks (enterprise + security), pattern 5, feasibility 3 (telephony + bank + messaging = 3 integrations; mitigated by shared plumbing), charity 5, creativity 4, sponsor +2 → **24**. **New #1.**

## Update 2026-11-09 (HackPrinceton history)
- Prior art at HackPrinceton itself: **NannyCam** (Spring '26, not a winner): "remote eldercare that watches medications, restocks the pantry, and guards finances, all through iMessage." **Flux** (Fall '25): AI-governed approvals for agent payments. Nobody did live-call → payment hold. Say in the pitch: "not monitoring after the fact; a hold *during* the call".
- Sponsor odds: Capital One "Best Financial Hack" = $1,000, **1 winner** (Fall '25: edgecart). Photon prize had **5 winners** in Fall '25. Business + Enterprise winners were workflow agents (Jigsaw, LEGR), consistent with the bank-ops console angle.
- Nessie API verified reachable over HTTPS (port 80 is blocked by the proxy; use https://api.nessieisreal.com). Get a key at nessieisreal.com before the event.
- Citations: CallScreenBench (arXiv 2609.23959) now has 11 citations on OpenAlex (in 7 weeks); still vendor-authored.
