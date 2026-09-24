# 0018 — Self-improving prompts: the operator's vision

**Status:** Idea captured, 2026-09-24. **Not a design and not authorization
to implement.** It records the operator's intent and the concepts
discussed, so they are not lost. It extends
[0015 — Prompt Library](0015-prompt-library.md), which remains the research
record. Nothing is scheduled.

**Work-item key:** `CarlDog/openchronicle-mcp#idea-0018-self-improving-prompts`

## The idea, in the operator's words

The original request (2026-09-22, recorded in 0015) was "LLM prompt caching".
On 2026-09-24 the operator gave the intent behind it:

> "The additional context that I had for the prompt caching is that it
> would be continually improving somehow. As prompts pass through OC to our
> agents, we would track success and failures, what parts worked well, and
> what didn't so the prompts (hopefully) would continue to improve every
> time we used them. It wouldn't be a static library of ancient prompts that
> would gather dust."

So the goal is not a store of saved prompts. It is prompts that **get better
the more they are used**, with OpenChronicle carrying the memory of what
worked.

## How this changes 0015

0015 designed a curated, versioned library and treated feedback as optional:

- its gap table lists "Outcome or usage signal: none, by design", after the
  earlier decision to drop telemetry from v3 (V3_PLAN open question 8);
- an append-only `prompt_feedback` outcome log appears only as a Stage 2
  follow-on;
- its open question 6 asks: "Add `prompt_feedback` … or rely on human
  curation only?"

The operator's intent answers question 6: **outcome signals are the core
of the feature, not an add-on.** The consequences, if the proposal is
pursued:

- For this feature, the v3 decision to record no usage or outcome data is
  deliberately revisited.
- The outcome log belongs in the first built stage, not a later one.
- Stage 0 should test the improvement loop, not only reuse (see the
  proposed revision below).

The rest of 0015 still applies: the terminology (this is procedural memory,
not provider-side prefix caching), the trust gate, the write-time checks,
keeping prompts out of `memory_search` ranking, and the staged, gated path.

## Concepts

### The improvement loop

1. **A prompt is used.** An agent fetches a specific version for a task.
2. **The outcome is recorded against that version.** Record:
   - which version ran, from which client and model, for what task;
   - the result: success, partial or failure;
   - notes on what worked and what did not, ideally tied to specific parts
     of the prompt;
   - where possible, a *checkable* signal (tests passed, the operator
     accepted the result, a follow-up correction was needed) rather than
     the agent's own opinion.
3. **Improvements are proposed as small edits.** A new version records its
   parent and the change, typically a targeted change to the part that
   failed. It is never a wholesale rewrite.
4. **Versions compete on real outcomes.** A proposed version earns its place
   by doing better than the current one on actual use, not by looking
   better.
5. **Promotion is a human decision backed by evidence.** OpenChronicle
   presents the outcome history and the diff, and the operator approves.
6. **Nothing gathers dust.** Prompts that go unused, or whose outcomes
   decline, are flagged for review or retirement.

### What the research says (from 0015 §3.3)

The evidence supports the idea and names its failure modes:

- **Outcome-driven refinement works.**
  - ExpeL up- and down-votes stored insights from real runs and retires them
    at zero: ALFWorld 59.0% against 40.3%.
  - ACE refines a playbook with small edits and helpful/harmful counters.
  - Voyager keeps a skill only after a self-check passes; removing the check
    cut discoveries by 73%.
- **Unguarded self-improvement goes wrong.**
  - Skills that agents generated for themselves scored *below having no
    skills at all* on all three SkillsBench setups; curated skills added
    16.6 percentage points.
  - ACE warns of *context collapse*: repeated whole rewrites shrank one
    context from 18,282 tokens to 122.
  - Agent Workflow Memory's online mode, which kept workflows an LLM grader
    judged successful, can learn wrong workflows.

Hence the concepts above: small edits, checkable outcomes, versions that
compete on evidence, and human promotion.

### Honest limits

- **Self-grading is biased.** An agent judging its own run is a weak signal;
  prefer checkable outcomes and the operator's verdict.
- **Small numbers.** Personal-scale use means few runs per prompt, so
  "better" will often be anecdotal before it is statistical. The record
  should show counts, not just rates.
- **Attribution.** An outcome depends on the model, the task and the context
  as well as the prompt; record enough of each to compare like with like.
- **Privacy.** Outcome notes can carry task content or secrets; they need
  the same care as memories.

### Trust

A prompt that is replayed as instructions, with the operator's authority,
and that changes itself from feedback, is exactly the poisoning path 0015's
risk register warns about. It is sharper here because production auth is
intentionally disabled, so any LAN client can write. Feedback and proposed
versions can be accepted from agents, but **promotion to the version that
gets served stays a human act** that no agent can perform.

## The open architectural fork

Who writes the improved version?

1. **The agents that use the prompt propose edits; OpenChronicle only
   records.** OC stores versions, outcomes and diffs, presents the
   evidence, and stays model-free, as v3 is today. *Recommended in
   discussion; not decided.*
2. **OpenChronicle runs its own improver model.** For example, the NAS
   Ollama rewrites prompts from accumulated feedback. This would reintroduce
   an LLM into OC, which v3 deliberately removed. It would need an ADR, and
   the NAS's CPU-only limits would apply.

## Proposed revision to Stage 0 (not yet adopted)

0015's Stage 0 is operator-run and needs no code: save candidate prompts
for about two weeks and note reuse. To test this idea as well, for each
prompt reused, note:

- whether it worked, and what failed or needed correcting;
- what changed in the next use, and whether that helped.

**Exit:** evidence that recorded outcomes actually led to better prompts, or
an honest "they did not", which is a result worth recording.

## Research still to do

The operator asked for research on this in 2026-09. 0015 covered storage,
the MCP prompt primitive, trust and procedural memory. Not yet covered:

- **Automated prompt optimizers:** DSPy (including GEPA), TextGrad, OPRO:
  how they use feedback, and what carries over to a model-free store.
- **Prompt-management tools that tie outcomes to versions:** Langfuse,
  PromptLayer, Humanloop's successors. How they link runs, scores and
  versions, and how they decide a version is better.
- **Evaluation at small N:** how to compare two prompt versions honestly
  with few runs, and which checkable signals agents can report.

## Where this is tracked

- [V3_PLAN](../V3_PLAN.md) active queue item 10 (the prompt library)
  points here.
- 0015's open question 6 is marked answered by this record.
- OpenChronicle memory, stable key
  `CarlDog/openchronicle-mcp#idea-0018-self-improving-prompts`.
