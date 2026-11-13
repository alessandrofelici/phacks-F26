# ShiftProof: refined spec (cycle C3, 2026-11-09)
Track: Healthcare (fit 3). Sponsor: Photon (SMS/iMessage reminders).

## R1 Facts (checked)
- CMS-2454-IFC (Jun 1 2026): adults 19-64 in expansion; 80 h/month **or $580/month earnings**; exemptions include pregnant/postpartum, Tribal members, veterans with total disability rating, medically frail, caregivers (parents of children under 13; non-resident caregivers need 80 h of caregiving), people meeting SNAP/TANF work rules; short-term hardship. Self-attestation under penalty of perjury allowed **through Dec 31 2027** when no electronic data exists.
- **Oct 29 2026:** a federal court struck the IFR's extra "significantly impairs" test for medical frailty and enjoined it for the plaintiff states for 6 months (multi-state suit). Rules differ by state now.
- Nebraska (live May 1 2026): applicants are checked on **the month before applying**; proof is uploaded at iServe.Nebraska.gov (QR code on the verification letter); school/apprenticeship needs the **Individual Declaration Form**; letters set due dates. Montana and Arkansas started Jul 2026, Michigan Oct 1 2026 for new applicants. California asked for a 6-month delay.

## R3 Prior art (big change)
- **CMS "Emmy" (Eligibility Made Easy)**: an open-source, federally built applicant-facing app (Rails; github.com/DSACMS/iv-cbv-payroll, weekly releases, updated Nov 6 2026) that guides beneficiaries through reporting, connects to payroll/gig data via consent-based verification, and produces an "audit-ready evidence package" for the state. That is ShiftProof's core.
- Vendors: Argyle (gig/payroll CBV for states, criticized for collecting credentials), Equifax Work Number (~$15/report), DiCIT (Digital Public Works). Consumer explainer sites: medicaidworkcheck.com, careroute.ai.
- What's left for us: (1) people in states that haven't adopted Emmy/CBV, (2) cash/informal workers that payroll connectors can't see (screenshots, bank deposits, employer letters), (3) proactive month-by-month tracking + reminders before the look-back month, (4) the exemption screener (now volatile after the Oct 29 ruling).

## R5 Score
Fit 3, pattern 4, feasibility 4, charity 5, **creativity 2** (Emmy), sponsor +1 → **19** (was 21). **Drop from the top 3.** Keep it as a pitch slide fact if building Second Key or Neighbor Call ("benefits paperwork is the next frontier"). If the team wants this space anyway, build *on* Emmy (open source) rather than against it, and say so.
