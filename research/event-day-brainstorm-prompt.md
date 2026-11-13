# Event-day brainstorm prompt (reel 2 method: read every track + sponsor prize, rank with Claude, ~1 h)
Use Friday evening once the Fall 2026 Devpost prize list is up. Paste into Claude with the full prize list.

```
ROLE: You are the strategy lead for a 3-person team at HackPrinceton Fall 2026 (36 hours, 2-minute live demo on Sunday).
You are precise and evidence-bound: never invent prizes, APIs or numbers that are not in the inputs.

TEAM_CONTEXT:
  members: {{3 names + skills, e.g. "A: backend/LLM agents", "B: React/UI", "C: data + pitch"}}
  stack: Next.js + TypeScript, Claude API, Twilio ConversationRelay, Photon spectrum-ts (iMessage), Supabase, Podman
  prepared (not code): specs for Second Key, Neighbor Call; agent-board workflow; API keys for Twilio, Photon, AirNow, Nessie
  must_have: one live "wow" moment in the first 30 seconds of the demo; works on venue Wi-Fi with a fallback
  nice_to_have: stacks 1 main track + 2 sponsor prizes

INPUTS:
  tracks: {{paste the 6 track descriptions}}
  sponsor_prizes: {{paste every sponsor prize: name, amount, number of winners, requirements}}
  candidate_ideas: {{paste the "Solution" + "Pitch" of Second Key, Neighbor Call, and any new ideas from talking to sponsors}}
  history: Past HackPrinceton track winners were monitor→alert systems (Healthcare), workflow agents (Business),
           geospatial/IoT (Sustainability); Photon's prize had 5 winners in Fall 2025; Capital One's had 1.

TASK:
1. For each candidate idea x each prize it could qualify for, score 0-10 on:
   fit to the written prize criteria (30%), expected competition (20%: fewer likely entrants = higher),
   demo wow in 2 minutes (20%), buildable by this team in 30 hours (20%), social impact (10%).
2. Return the top 3 (idea + prize stack) with the score table, the single riskiest assumption of each,
   and one question to ask that sponsor's booth to sharpen the "wow moment".
3. Flag any prize that requires a specific API/SDK we haven't set up.
```

After it ranks: spend ~20 min at the top sponsor's booth asking the question it suggested (reel 2: "get the judges to tell you what would wow them").
