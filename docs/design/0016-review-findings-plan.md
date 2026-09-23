# 0016 — Plan for the 2026-09-23 review findings

**Status:** Adversarially reviewed. Track 1 entered `main` through
[PR #34](https://github.com/CarlDog/openchronicle-mcp/pull/34) (merge `7ffc277c`);
track 3 entered `main` through
[PR #35](https://github.com/CarlDog/openchronicle-mcp/pull/35) (merge `77ea0173`).
Tracks 2, 4 and 5 remain proposed or gated. No track is released or deployed
by this document.
**Baseline:** `main` at
`c7f36a7c`; production remains the tag-pinned v3.3.0 image. This plan covers the four findings in the
2026-09-23 adversarial review and the pre-existing `created_at` ordering
defect in [V3_PLAN items 8, 10–12](../V3_PLAN.md#post-cutover-follow-ups-tech-debt).
The prompt-library Stage 1 and a production compose replacement remain
separate, gated decisions.

## Desired result and boundaries

1. A semantic query is never knowingly scored against vectors stamped with a
   different model revision. Hybrid search retains its keyword fallback;
   semantic-only search reports a failure when no safe vector result is
   available.
2. Chronological queries order by instants, including offset-bearing
   `created_at` values from `onboard_git`, with an explicit policy for naive
   timestamps. Existing memory content, IDs, tags, project links and embedding
   identity remain intact.
3. A future adoption of the repository's NAS compose preserves the operator's
   LAN REST Host allowlist. The current detached stack remains on its stored
   compose until the separate reconciliation decision.
4. Candidate prompts in Stage 0 cannot enter routine unscoped memory recall;
   the pilot records actual reuse or an honest no-reuse outcome.
5. The release version, stability-policy exception, metrics evidence and
   deployment path are decided and verified before any tag or `OC_TAG` change.

Each track is a small, reviewable change. The plan leaves the unmerged Gemini
branch, runtime metrics, the live stack, and prompt-library Stage 1 at their
current decision gates.

The tracks have different gates. The query-race fix passed PR CI and merged to
`main`, but still needs a separately authorized tagged release.
Timestamp migration has a separate data
review and release decision; do not bundle it into v3.4.0 by default and
delay the production revision fix. Compose reconciliation is independent
of the env-only release. The prompt pilot is independent of both.

## Sequence and acceptance evidence

### 1. Close the query-revision race

In [`_semantic_search`](../../src/openchronicle/core/application/services/embedding_service.py),
read one `RevisionSnapshot` before `_embed_single`. Read it again immediately
after embedding. Compare `(known, value)`, not the complete dataclass: a
successful re-probe of the *same* digest changes `verified_at` without
changing the embedding space. If the identities differ, discard that query
vector and retry once using the newly observed identity. If the second
attempt also changes identity, do not score it: hybrid returns keyword results;
semantic-only returns a typed, actionable error. If a request opened with a
known identity, a later unknown snapshot must fail closed even when the
second attempt stays unknown: revision-agnostic matching could mix spaces.
A revision change is not a provider outage and must not falsely advance
provider-failure counters. Keep the existing revision-agnostic search
exception only when the request starts and remains unknown; no request-path
`/api/tags` probe is introduced.

Test with a controlled port that changes A→B during the embed and returns
different A/B vectors. Assert that neither search mode scores the A query
against B rows, that a stable retry uses B, and that repeated churn takes the
bounded failure path. Cover unknown→known, known→unknown, and provider failure
on retry, preserving the existing keyword and semantic-only contracts. A
same-digest refresh that only changes `verified_at` must neither retry nor
change the result. For exhausted revision churn, log one sanitized warning
and add `revision_churn` to the recorder's bounded search-fallback reasons;
assert the existing provider-failure health counters stay unchanged. Do not
imply that health gains a churn field in this patch. Add one only if a
separate operator need and response-contract decision justify it.
Check p95/p99 on the stable path proportionately: it must still perform one
provider call and two cheap in-memory snapshot reads, with no new probe.
**Stop** if the desired guarantee requires serializing all searches with
model refresh/backfill or a request-path probe; revisit the design and its
latency cost instead of silently expanding it.

The snapshot bounds what OC *knows*. A provider can swap weights before its
next `/api/tags` observation, and one provider endpoint need not switch at
the same instant as another. This plan cannot claim atomic knowledge of
provider weights. Record this limit in the implementation review.

**Implementation checkpoint (2026-09-23):** The first track entered `main`
through PR #34. It uses the bounded retry
and the known-to-unknown fail-closed refinement above. Hybrid churn returns
keyword results, logs a sanitized warning and records the bounded
`revision_churn` fallback without changing provider-failure health counters.
Semantic-only churn raises `MODEL_REVISION_CHANGED`, mapped to HTTP 502.
Ten focused regression tests, the full Windows suite (1,146 passed, one
Linux-only skip), Ruff and mypy passed locally. The complete recorder matrix
increased from 3,669 to 3,671 series because the bounded fallback label adds
two counter series. A synthetic stable-path check against `c7f36a7c` used 32
in-memory vectors and 600 alternating calls per version: p95 was 0.1405 ms
baseline versus 0.1409 ms current; p99 was 0.2432 versus 0.2274 ms. The
p99 difference is host noise, not a speed claim; this does not satisfy NAS
load gates. A stable call made one embed, two snapshot reads and no probe.
PR #34's Windows/Ubuntu test and quality checks plus CodeQL passed on
`2c3a25570b22a48a682f9b13ec7420679bdbe1e8`; PR #34 merged as
`7ffc277c0b997340ec6e6f50e9558aecf856ba65`. Production still runs the
older tagged image; no runtime cutover is claimed. Tracks
2, 4 and 5 have not been implemented.

### 2. Specify and correct timestamp storage

Before a data change, inventory the distinct timestamp shapes and counts in
`memory_items.created_at`, `memory_items.updated_at`, and
`projects.created_at` on a **read-only** copy or bounded production query.
Check offset-bearing, UTC, naive, malformed and out-of-range values without
recording memory content. Agree how to interpret any naive legacy row before
conversion; neither the machine's local timezone nor UTC is assumed silently.
If provenance cannot resolve a naive value, stop migration and report the
affected row IDs/counts for an operator decision. New naive inputs should be
rejected at the boundary with a useful error. Since current REST, MCP and
import paths accept naive values, that tighter rule also needs an explicit
STABILITY/version decision for the timestamp release; it is not covered by
the blank-content decision for v3.4.0.

Use one UTC serialization rule at the persistence boundary for every write,
including direct store callers and import/restore. Normalize `created_at`
and `updated_at` while preserving the represented instant and microseconds;
have `onboard_git` emit UTC as well. Convert existing rows in a transaction
with a Python ISO-8601 parser, not SQLite `datetime()`/`strftime()` (which
may lose subsecond precision). Prefer a migration-local Python normalization
function called from a versioned SQL migration: register it on the migration
connection, perform the updates inside the runner's existing savepoint, and
record the schema version only after success. This avoids a new general
migration framework or an unversioned startup rewrite. Do not reserve a
number yet: design 0015 tentatively calls its unratified prompt migration
`005`, so the later migration must take the next free number. Establish an
intact backup and a disposable restore rehearsal before touching live data.
The migration proposal must say whether the previous tagged image can read
the converted store and its new version marker. If not, rollback includes a
tested restoration path from the pre-migration backup, with no intervening
writes accepted during that restoration. An old image starting successfully
is insufficient: the current migrator can open a later schema version, and
the old write path can reintroduce offset-bearing timestamps.

Prove offset-equivalent instants sort together with a deterministic ID
tie-break; test listing and pagination, `context_recent`, FTS tie-breaks,
the Python search fallback, project and source listings, and export/import
round trips. Add an ID tie-break where project or source listings lack one.
Rehearse restoring an envelope written before this change under the chosen
naive-timestamp policy. Test migration rollback on
one malformed or naive row, idempotent rerun and preservation of IDs,
content, tags, project links, embedding identities and FTS integrity: the
existing FTS update trigger rewrites an FTS row even for timestamp-only
updates. Measure migration duration on a disposable copy. **Stop** on any
unresolved timestamp interpretation or failed restore comparison. The
timestamp work is a correctness fix, not an implicit release authorization.

**Read-only readiness checkpoint (2026-09-23):** The available local
development database has schema version 1, 833 memory rows and two projects.
All populated `created_at`/`updated_at` values in those tables are UTC-aware;
none are naive, malformed or nonzero-offset. No memory content was read. This
is not a production inventory or a migration rehearsal. Production-copy
inventory, the naive-row policy, the input-compatibility/version decision and
the rollback window remain gates before data-changing implementation.

### 3. Preserve Host allowlists when reconciling the NAS compose

Before track 3, the repo compose injected a nonempty `OC_API_ALLOWED_HOSTS` default
containing loopback and `oc:*`. That masks `HTTPConfig`'s documented fallback
to `OC_MCP_ALLOWED_HOSTS`: a stack with only `OC_MCP_ALLOWED_HOSTS=nas:*`
would begin rejecting LAN REST with 421 while loopback health stays 200.
Keep the API variable absent/empty by default so the fallback works. When
the optional metrics profile needs the `oc` alias, require an explicit API
allowlist combining the operator's external hosts and `oc:*`; document the
required value where the profile is enabled. Update the monitoring runbook
and Prometheus example, whose current instructions rely on `oc:*` being in
the compose default. A profile start without that explicit allowlist must
fail its scrape/access check rather than appear healthy from loopback alone.

Test the rendered compose and actual REST/MCP Host behavior for an MCP-only
LAN setting, an explicit API override, the collector alias, and a hostile
Host. Assert external `/health` and REST access as well as local health.
Review the network and log-path differences in V3_PLAN item 12 before any
stored-compose replacement. **Stop** if the rendered compose would narrow
existing client access or violate the fleet network rule. The v3.4.0
deployment, if separately approved, remains the documented env-only
`OC_TAG` plus `OC_LOG_FILE` update on the detached stack.

**Local implementation checkpoint (2026-09-23):** On the unmerged
`codex/nas-host-allowlist` branch, the repo compose injects an empty API
Host list by default. The runbook requires an explicit external-hosts-plus-
`oc:*` list for the opt-in collector and checks LAN REST, MCP and scrape
access. Tests render both compose settings and feed those values into the
app: LAN REST remains available, the collector alias is rejected by default
and allowed only by the explicit API list, and forged Hosts return 421.
The 24 focused tests and full Windows suite (1,150 passed, one Linux-only
skip), Ruff and mypy passed locally. An adversarial review caught a source-
line-only test and stale Git-stack wording; both were corrected before this
checkpoint. A follow-up PR review also requested mounted MCP checks using the
rendered values; the revised test drives allowed and rejected MCP Hosts.
Fresh CI on that revision is required. The detached live stack has not changed;
this is not a profile start, release or deployment.

### 4. Bound the prompt-library pilot and later ADR

Do not start Stage 0 by writing unapproved prompt bodies to the live memory
store merely under a dedicated project: unscoped `memory_search` and
`context_recent` can retrieve them. Recommend a separate disposable OC
store/instance with no routine agent connection for the two-week, zero-code
pilot. Connect only participating clients to that pilot store and record
prompt slug, version, provenance and *actual* reuse there. If reuse reaches
the Stage 0 threshold, freeze the same pilot corpus and a sanitized
intent→slug gold set for any later Option 0 versus Option B comparison. An
honest no-reuse result closes the proposal, as design 0015 specifies. If the
operator chooses a shared store, first demonstrate that every routine recall
consumer is explicitly scoped or excludes the pilot project; otherwise stop.
This changes the pilot's isolation requirement, not its two exit outcomes
or the requirement for a separately ratified Stage 1 ADR.

The future Stage 1 ADR must make human approval cover the served discovery
metadata (`title`, `description`, `tags`) as well as body and parameters.
The proposed Option B schema keeps that metadata on mutable
`prompt_templates`, so a draft edit could change how an approved version is
found without moving `approved_version`. Version that metadata or give it an
independent approval lifecycle, and test that an agent's draft update cannot
change an approved prompt's list/search description.

### 5. Make release decisions at the release boundary

Before selecting a v3.4.0 tag, resolve and record both open decisions:

- The blank-content fix rejects previously accepted values. The current
  [stability policy](../api/STABILITY.md) calls that MAJOR unless an existing
  exception applies. Decide whether to amend the policy narrowly for a fix
  that prevents destructive input, or choose a version consistent with the
  present policy. Keep the fix either way and state the behavioral change in
  the release notes.
- [Design 0010](0010-performance-measurement.md) still blocks releasing
  the metrics instrumentation carried by `main` with inconclusive B/A
  evidence, even while metrics are off. Record an explicit metrics-off
  exception, choose a release cut without that instrumentation, or run a
  newly authorized gate under unchanged budgets. Do not call local tests
  performance acceptance.

Before relying on any prior 4C/4D result for a final release SHA, perform
design 0010's change-impact review. The query-revision fix changes the search
path and the integrated recorder/exporter candidate is untimed, with affected
4D checks pending; old frozen evidence cannot accept the combined candidate.

After those decisions and the intended patch set are fixed, use a PR so
CI runs on the proposed changes. Put the version and CHANGELOG in the
commit that will be tagged; after merge, require test, quality, image smoke
and publication success for the **exact tag SHA** rather than treating the
PR head's green run as sufficient. Verify the published build revision and
release artifact. The workflow currently rebuilds after smoke testing, so
that check does not prove the pushed image has identical layers if a base
tag moves between builds. The risk is already deferred in V3_PLAN item 8;
record it as a release limitation unless the operator separately scopes a
push-of-tested-image or pinned-base change. After those checks, an env-only
move of the detached stack's `OC_TAG` and `OC_LOG_FILE` is eligible for its
separate operator release and deployment decision. Read back
`health.package_version` and
`health.build_revision`, REST and MCP access from a real LAN client, the
embedding status, and the Ollama restart gate in both startup orders.
If a pre-deploy gate fails, leave the existing tag pinned. If post-deploy
verification fails, restore the prior tag and env values through the same
file-stack mechanism, independently verify the old build and client access,
and report the failed gate. The tag and data-migration tracks each need their
own tested rollback story.

## Adversarial review of this plan

**Method:** challenged each proposed guarantee against the current source,
ADR 0005 §7, the SQL-only migration runner, compose interpolation, the
monitoring runbook, and the release workflow. No production mutation or
performance run was part of this review.

| Attack on the first draft | Disposition |
|---|---|
| A plain `before != after` snapshot check treats a routine same-digest re-probe as a model swap because `verified_at` changes. That creates needless second embeddings and latency spikes. | **Corrected:** compare only `known` and `value`; add a same-digest test. |
| Taking the pre-embed snapshot alone still cannot prove which weights the provider used if a re-pull lands mid-request. | **Corrected:** check again, retry once on observed identity change, fail closed on repeated change. Explicitly limit the guarantee to observed revisions. |
| A known-to-unknown transition could retry into a stable unknown snapshot and accidentally use revision-agnostic matching, which may include vectors from a different space. | **Corrected during local implementation:** fail closed whenever an operation opened known and ends unknown, including after the retry. |
| A new revision-churn error would be caught by hybrid's broad exception handler and falsely increase provider-failure counters. | **Corrected:** require a distinct fallback/classification and test it. |
| A new fallback reason would collapse into the metrics recorder's `_other` bucket, and the first draft never defined a health signal for churn. | **Corrected:** add bounded `revision_churn`, test that existing health failure counters stay unchanged, and make any new health field a separate decision. |
| Normalizing legacy times with SQLite `datetime()` loses fractions, while normalizing naive rows with `astimezone()` silently uses the migration host's timezone. | **Corrected:** require Python parsing, an explicit naive policy, atomic rollback, and instant-preservation tests. |
| A schema-version marker alone is not a rollback plan if an older image cannot read the converted database. | **Corrected:** require compatibility proof or a tested, write-frozen restore from the pre-migration backup. |
| A timestamp migration numbered `005` would collide with design 0015's proposed `005_prompt_library.sql` if that later Stage 1 is ratified. | **Corrected:** assign the next available migration number when implementation lands, and renumber the unratified proposal if needed. |
| Rejecting new naive timestamps changes input that REST, MCP and import currently accept; the first draft treated it as a purely internal normalization. | **Corrected:** require a separate STABILITY/version disposition for the timestamp release. |
| Removing the compose's `oc:*` default fixes LAN access but silently breaks the optional Prometheus scrape. | **Corrected:** make its explicit allowlist and scrape check part of the profile's runbook and acceptance. |
| A source-line test and hand-written app env values could both pass while rendered compose masks the fallback. | **Corrected during implementation:** render compose in a bounded test and pass its actual env values to the app; confirm LAN REST and collector behavior. |
| Prior 4C/4D observations might be reused for a final SHA even though the search path and recorder/exporter have changed. | **Corrected during implementation review:** require design 0010's impact review and any affected gate rerun before relying on those observations. |
| A green PR head can differ from the merged/tagged commit, and reverting `OC_TAG` after a failed deployment is not the same as leaving the prior tag pinned. | **Corrected:** require CI on the exact tag SHA, published build-revision readback, and post-deploy rollback/readback. |
| CI smoke-tests one local build and then rebuilds for push; the exact SHA check alone does not prove identical image layers. | **Corrected:** state the residual moved-base risk and keep the already deferred pin/push choice separate from this plan. |
| Treating five findings as one release would couple an urgent query correction to a data migration, a compose decision and a two-week pilot. | **Corrected:** separate the tracks and name only the query fix as a prerequisite for the planned correctness release. |
| The Stage 0 pilot could show no reuse, which design 0015 treats as a valid exit rather than a failed attempt to reach ten prompts. | **Corrected:** preserve the no-reuse closure and make the gold set conditional on a positive result. |
| UTC normalization tests limited to SQL ordering could miss the Python fallback's sort of mixed aware and naive datetimes, or break an older exported envelope. | **Corrected:** test both search paths and a pre-change export restore under the selected naive policy. |

**Residual decisions, not findings claimed closed:** the stability-policy
exception and design 0010 disposition need operator decisions; naive legacy
timestamps need provenance if present; the prompt pilot needs an isolation
choice; the stored NAS compose needs a network/reconciliation decision. None
is silently resolved by this plan.
