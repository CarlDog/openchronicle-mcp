# 0019 — Lowering the cost of cloud LLM use through OpenChronicle: a north star

**Status:** Idea captured, 2026-09-24. **A long-range aspiration, not a
design, not a commitment and not authorization.** It records the operator's
goal and the candidate levers discussed, so they are not lost. Nothing is
scheduled, and each lever keeps its own gates.

**Work-item key:** `CarlDog/openchronicle-mcp#idea-0019-cloud-llm-cost`

## The goal, in the operator's words

> "I would LOVE it if we were able to help improve the efficiency and lower
> the cost of using cloud LLMs through OpenChronicle. It's a big ask, and
> probably not achievable, but shoot for the stars, right?"
>
> "Hence the grab of the FreeToken repo a few weeks ago. I hoped they would
> spawn some ideas on that front."

The question is whether OpenChronicle, which already sits beside every agent
as its memory, can reduce the tokens, money and time spent on cloud LLM calls
across the fleet.

## What has been examined so far, and the gap

- **[0012 — FreeToken review](0012-freetoken-repository-review.md)**
  (2026-09-09) asked a narrower question: could FreeToken serve as OC's
  embedding service or speed up OC's own search? It could not; it serves
  generation, not embeddings. Its one transferable idea was to measure
  repeated query-embedding work (OC-FT-01) before any cache (OC-FT-02). Its
  GPU prefix cache was rejected as a transplant *for memory retrieval*
  (OC-FT-05). **It never examined the operator's actual hope: lowering
  cloud-LLM cost.** That question has not been researched anywhere yet.
- **[0015 — Prompt library](0015-prompt-library.md)** and
  **[0018 — Self-improving prompts](0018-self-improving-prompts.md)** cover
  one lever: reusing and refining prompts, including their token and time
  savings.
- **[0011 — Memory ecosystem review](0011-memory-ecosystem-review.md)** §4
  proposes context retrieval within an explicit budget, which bears
  directly on how many tokens memory costs an agent.

## Candidate levers (hypotheses, unvalidated)

Ordered from "fits OC as it is" to "needs a scope decision".

1. **Measure first.** Nobody currently knows what the fleet spends on
   cloud LLMs per task, or where it goes: re-reading files, rediscovering
   context, drafting prompts, retries. Without a baseline, no lever can be
   shown to save anything. Per-task token and time accounting (0018's
   efficiency record) is the instrument.
2. **Memory instead of rediscovery.** Every session, agents spend tokens
   re-deriving what a previous session already learned: repository layout,
   decisions, conventions, what was tried and rejected. A few recalled
   memories can replace many tokens of file reading and reasoning. OC does
   this today; the lever is doing it deliberately and measuring the savings.
3. **Tight, budgeted context.** Return the fewest, most relevant memories
   in compact form (`top_k`, compact previews, and 0011 §4's explicit
   budget). Every memory returned is input tokens on every later turn.
4. **Self-improving prompts** (0018). Less drafting, fewer attempts, fewer
   corrections.
5. **Cache-friendly surfaces.** Keep OC's tool descriptions and server
   instructions byte-stable, and keep variable content out of them, so the
   clients' provider prompt caches keep hitting (0015 §1). This is a small,
   concrete habit that costs nothing to adopt.
6. **Result reuse (far).** Remember answers to repeated, deterministic
   questions so they are not asked again. It carries staleness and
   correctness risks, so it needs the same identity and invalidation rigour
   as 0012's cache conditions.
7. **Sitting in the request path (farthest; needs a scope decision).** A
   gateway or proxy in front of cloud LLM calls could do routing to cheaper
   or local models, caching, or batching. OC's v3 boundary is memory-only,
   and 0012 rejected adding a generation runtime (OC-FT-06). This would be
   a new component or a separate fleet service, not a change to OC, and it
   needs its own design and ADR.

## Honest framing

- **Accuracy stays first** (operator priority, 2026-09-08). A cheaper answer
  that is wrong costs more in the end. Every lever has to preserve result
  quality.
- **Savings must be measured, not assumed.** Several levers add their own
  cost: fetch calls, extra context, cache misses. Only a baseline comparison
  shows a net saving.
- **OC does not see the LLM calls.** Today it sees only its own tool calls.
  Measuring cost needs cooperation from the clients (reported token counts)
  or a component in the request path (lever 7).

## Research still to do

- A focused pass on the operator's actual question: what memory and context
  layers do to cut LLM token use (context compression, retrieval budgets,
  memory-versus-long-context trade-offs), and what gateway tools do
  (routing, semantic caching, batching).
- A second look at FreeToken with *this* question in mind: which of its
  ideas bear on generation cost, rather than on OC's embedding path?
- How the fleet's clients (Claude Code, Codex, Gemini CLI, and others)
  expose per-request token and cost counts that could feed lever 1.

## Where this is tracked

- [V3_PLAN](../V3_PLAN.md): a trigger-free "north star" note in the backlog
  points here.
- OpenChronicle memory, stable key `CarlDog/openchronicle-mcp#idea-0019-cloud-llm-cost`.
