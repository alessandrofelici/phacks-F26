# LangChain "Best use of deepagents": Repro Bot vs the payment ideas (2026-11-14)
Goal: win LangChain's track only. Its listing says "Teams build a deepagent for any use case they want" and posts no criteria (`prizes/hackprinceton-fall-26-special-tracks.md`). The team notes give three questions judges are likely to ask: **does it need to be automated, did you use all of deep agents, what did you try and fail on**. The general rubric (`judging-criteria.md`: creativity, utility, charity, avidity) is used as the second filter.

Candidates: **Repro Bot** (round 2 §12), **Second Key** (round 1 #3, spec in `specs/hp-spec-second-key.md`) and **Cash Drawer** (round 2 §9, the bookkeeping one). Odyssey (round 3's pick) is included for reference.

## Verdict
**Build Repro Bot, using CORE-Bench tasks as the input set.** It's the only candidate where every deepagents feature does real work rather than being bolted on, it answers all three LangChain questions naturally, and it has a strong local hook: CORE-Bench, the main computational-reproducibility benchmark, comes from Princeton ([arXiv 2409.11363](https://arxiv.org/pdf/2409.11363)). Starting from CORE-Bench capsules fixes the biggest weakness round 2 found (buildability), because each task ships with the code, data and a known answer.

Second Key is the better idea for Best Overall and the Capital One/Photon prizes, but the part that matters (scoring a live call turn by turn) is latency-bound and doesn't fit a deep agent. Cash Drawer is a deterministic ledger with an LLM front end, with very little for an agent to plan.

## Scores
1-5 each. The **LangChain** columns are the three track questions plus a check of which deepagents features the idea actually needs; the **Rubric** columns are the general criteria; **Build** = feasible in ~30 h for 3 people.

| Idea | Needs automation | Uses all of deepagents | Failure story | Creativity | Utility | Charity | Avidity / demo | Build | Total /40 |
|---|---|---|---|---|---|---|---|---|---|
| **Repro Bot** | 5 | 5 | 5 | 4 | 4 | 3 | 4 | 3 (4 with CORE-Bench) | **33-34** |
| Odyssey | 4 | 4 | 3 | 4 | 4 | 5 | 4 | 3 | 31 |
| Second Key | 3 | 3 | 3 | 4 | 4 | 5 | 5 | 3 | 30 |
| Cash Drawer | 2 | 2 | 2 | 2 | 3 | 3 | 3 | 4 | 21 |

### Why these numbers
- **Needs automation.** Repro: reproducing one paper means hours of installs, version pins, data downloads and reruns, which is exactly what people put off. Second Key: the hold and co-sign is a workflow, but the decision belongs to a family member, so the agent assists a human rather than taking over. Cash Drawer: bookkeeping from texts is a parser plus SQL, which needs no autonomy.
- **Uses all of deepagents.** See the feature map below. Repro needs `execute` in a sandbox, async subagents for long runs, and memory across papers; Second Key mostly needs `interrupt_on`; Cash Drawer needs almost none of it.
- **Failure story.** Repro will fail in ways that are well documented (dependency hell, missing data, nondeterminism, the agent "fixing" results by editing the code) and the fixes are agent-design changes, which is the kind of answer that question wants. Second Key's failures are false positives and telephony issues, which aren't about agents.
- **Charity** is Repro's weak spot: it serves research credibility, not a vulnerable group. Pitch it as "science you can trust", since public trust in research rests on results that replicate. Expect a 3, not a 5.

## Feature map: what each deepagents part does
Feature names are from the current docs ([overview](https://docs.langchain.com/oss/python/deepagents/overview)). ✓ = real use, ~ = possible but forced, ✗ = no use.

| deepagents feature | Repro Bot | Second Key | Cash Drawer |
|---|---|---|---|
| `write_todos` planning | ✓ repro plan: read paper → set up env → run → compare, re-planned on failure | ~ investigation checklist after a hold | ✗ |
| Filesystem (`read_file`, `grep`, `glob`, `edit_file`) | ✓ the repo itself: README, configs, requirements, logs | ~ case file | ~ ledger notes |
| `execute` + sandbox backend (Modal / E2B / Daytona / LangSmithSandbox) | ✓ core: runs the code isolated | ✗ | ✗ |
| Large-result offloading (`/large_tool_results/`) and summarization | ✓ build logs and stack traces are huge | ✗ | ✗ |
| Subagents (`task`), context isolation | ✓ paper-reader, env-builder, runner, result-judge; each keeps its mess out of the main context | ✓ call analyst, payee checker (Nessie), family liaison (Photon) | ~ receipt parser |
| Async subagents (`start_async_task` / `check_async_task`) | ✓ a 10-min training run continues while the main agent inspects the next claim | ✗ | ✗ |
| `interrupt_on` (human-in-the-loop) | ✓ approve before GPU spend, before editing source code, before posting the report | ✓ core: transfer release = family approval | ~ confirm a categorization |
| Long-term memory (`AGENTS.md`, StoreBackend `/memories/`) | ✓ "fixes that worked" (e.g. pin numpy for old torch) carry over to the next paper | ~ per-senior baseline | ~ vendor categories |
| Skills (`SKILL.md`) | ✓ "set up an R project", "set up conda from environment.yml", "run a Jupyter notebook headless" | ✗ | ✗ |
| Filesystem permissions | ✓ deny writes to the paper's result files so the agent can't "fix" the numbers | ✗ | ✗ |
| LangSmith tracing | ✓ show the trace in the demo as the "how it thinks" view | ✓ | ✓ |

Repro uses 11 of 11; Second Key 3 real + 3 forced; Cash Drawer 1 real + 4 forced.

## Repro Bot, scoped for this weekend
**One-line pitch:** "Most published code doesn't run on the first try. Repro Bot tries for you and tells you whether the numbers hold up."

**Input:** a CORE-Bench task (a paper's code capsule plus a question about its results, e.g. "what is the test accuracy in Table 2?") or, stretch goal, any arXiv link with a GitHub repo. CORE-Bench has 270 tasks from 90 papers in CS, social science and medicine, Python and R ([paper](https://arxiv.org/pdf/2409.11363)), with an answer key, so every run is scored automatically. Repo: [siegelz/core-bench](https://github.com/siegelz/core-bench).

**Agent design**
- Main agent: plans with `write_todos`, owns the final report.
- `paper-reader` subagent: extracts the claimed numbers and the experiment that produces each one, written to `/claims.json`.
- `env-builder` subagent: reads requirements/Dockerfile/environment.yml, installs in the sandbox, retries with version pins; consults `/memories/fixes.md` first and appends what worked.
- `runner` async subagent: runs the smallest experiment that produces a claimed number; long runs stay in the background.
- `result-judge` subagent: compares output with the claim within a tolerance and labels each one **reproduced / off by X / could not run because Y**, citing the log line.
- `interrupt_on`: GPU jobs over N minutes, any `edit_file` on source code, and publishing the report.
- Permissions: the agent can't write to files that hold expected results.

**Demo (2 min)**
- 0:00 "Princeton's CORE-Bench found AI agents struggle to reproduce published research. Here's ours." Paste a task.
- 0:15 LangSmith trace and todo list fill in; three subagents start; a pip conflict appears and env-builder fixes it with a pin it remembered from an earlier paper (show `/memories/fixes.md`).
- 0:50 An approval prompt: "run the 4-minute experiment on GPU?" A judge clicks approve.
- 1:20 The report: 2 claims reproduced, 1 off by 0.8 points, with the log lines.
- 1:40 "We ran it on 20 CORE-Bench tasks: X solved." The failure slide: what broke and how the agent design changed.

**Answers to the three LangChain questions**
- *Does it need to be automated?* Yes: hours of setup per paper, repeated for every paper a reviewer or student checks.
- *Did you use all of deep agents?* Show the feature map table above, one row per feature with where it appears in the trace.
- *What did you try and fail on?* Keep a running log from hour 1 (`FAILURES.md` in the repo). Expect: one giant agent context blowing up on build logs (fixed with subagents + offloading), the agent editing code to match results (fixed with permissions), runs exceeding the demo window (fixed with async subagents).

**Build plan (3 people)**
- A: agent graph, subagents, memory, permissions.
- B: sandbox (Modal or E2B; pick whichever gives free credits fastest), CORE-Bench loader and scorer, eval run.
- C: report UI (Next.js or Streamlit), LangSmith trace view, pitch and `FAILURES.md`.
- Hour 4: one easy CORE-Bench task end to end. Hour 16: 10 tasks. Hour 26: feature freeze, run the 20-task eval overnight.

**Risks and fallbacks**
- Long runs: only demo tasks that finish in < 5 min; keep a pre-run trace to show if Wi-Fi or the sandbox fails.
- Benchmark claims: CORE-Bench Hard is already saturated by frontier agents ([Life After Benchmark Saturation, arXiv 2606.26158](https://arxiv.org/abs/2606.26158), Jun 2026, which also introduces v1.1 and an OOD suite). Don't pitch "state of the art"; pitch the product (the report, the memory, human approval) and use the benchmark as an honest eval. Using CORE-Bench v1.1 or OOD tasks would avoid the saturation critique (check what they include).
- Prior art: OpenAI's PaperBench ([arXiv 2504.01848](https://arxiv.org/html/2504.01848v3)) replicates papers from scratch (harder, a different task); CORE-Bench's own agents are research baselines, not tools. I found no tool for researchers built on deepagents, but the search was light.
- Sandbox cost: check Modal/E2B/Daytona free tiers before starting. Vultr GPUs (MLH prize) are a possible stack.

## If you'd still pick the payment idea
Second Key is the stronger idea **overall** (charity 5, demo 5, Capital One Nessie $250/person + Photon + Business & Enterprise). To make it a real deep agent: keep the live call scoring as a fast classifier outside the agent, and make the deep agent the **investigator** that wakes on a hold. It gathers evidence with subagents (call transcript analyst, Nessie payee/transaction history, scam-pattern lookup), writes a case file, and the transfer release is an `interrupt_on` decision sent to the family over Photon. That's a fair use of planning, subagents and human-in-the-loop, but `execute`, sandboxes, async subagents and skills go unused, so the "did you use all of deep agents" answer is weaker.

Cash Drawer: don't build it for this track.
