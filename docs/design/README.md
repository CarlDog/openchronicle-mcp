# Design Documents and Reviews

Numbered documents in this directory capture proposed architecture and
comparative repository research. A proposal or recommendation is not
current product behavior until `docs/CODEBASE_ASSESSMENT.md` records it
as shipped.

| Document | Type | Status |
|---|---|---|
| [0001 — Cloud backup](0001-cloud-backup.md) | Design | Phase 0 passed 2026-09-28 (DATA-02); Phase 1, the nightly encrypted offsite push, deployed in v3.6.0 on 2026-09-29 (OPS-08, closing after three green nights and a breakage check); Phase 2 trigger-gated (GATE-15) |
| [0002 — OpenClaw memory review](0002-openclaw-memory-review.md) | Comparative review | Batches A + B shipped 2026-08-28/29 (revs 120-124, 129); ranking-policy items stay trigger-gated |
| [0003 — Ollama repository review](0003-ollama-repository-review.md) | Comparative review | all verified findings shipped (revs 125-126, 134-136 via ADR 0005); benchmark/trigger-gated items remain |
| [0004 — NemoClaw repository review](0004-nemoclaw-repository-review.md) | Comparative review | Ranks 1-5, 7, 8, 10 and 11 shipped or closed (rank 3 for the offline restore path, with DATA-04); rank 6 waits on write-behind, rank 9 is QUAL-06 |
| [0005 — Composite embedding identity](0005-embedding-identity.md) | ADR | **Accepted 2026-08-29** (rev 2, post-adversarial-review); fully implemented — Phases B/C/D shipped (revs 134-136); §7 amendment (unknown revision is not "no revision") shipped in v3.4.0 |
| [0006 — Embedding provider review](0006-embedding-provider-review.md) | Review | Complete 2026-08-29. The local `ollama/nomic-embed-text` cleared the gate and became production in v3.2.0 (`content_egress: local`); the quarterly provider sweep continues (ROADMAP CAL-01) |
| [0007 — Long-term scale and resilience](0007-long-term-scale-and-resilience.md) | Design | Accepted 2026-08-29; staged trigger-gated path (durability, read pool, Postgres+pgvector, live sync) |
| [0008 — Pins as ranking prior](0008-pins-as-ranking-prior.md) | ADR | **Accepted 2026-08-29** (rev 4); implemented on `v4/develop` (winning cell `PIN_RANK_LIFT = 0`, ships with v4.0.0) |
| [0009 — Permanent embed-failure classification](0009-permanent-embed-failure-classification.md) | ADR | **Accepted 2026-08-29** (rev 3); implemented on `main` (tombstones, `unembeddable` bucket, `CONTENT_TOO_LONG`, ships with v3.3.0) |
| [0010 — Application performance measurement](0010-performance-measurement.md), [attribution and integration](0010-4c-attribution.md) | Design and implementation evidence | Recorder/exporter optimizations locally verified and included in the 2026-09-09 source checkpoint; corrected integration untimed. Final 4C overhead remains inconclusive, REST list-tail gate failed, MCP samples insufficient, affected live 4D checks pending; metrics off by default. Release: shipped in v3.4.0 under an explicit operator exception (2026-09-24); enabling stays blocked (ROADMAP MEAS-01) |
| [0011 — Memory ecosystem review](0011-memory-ecosystem-review.md) | Comparative review | Research recorded 2026-09-08; Basic Memory, Graphiti, Hindsight, Mem0, Cognee, LangMem, MCP reference and evaluation sources; recommendations unscheduled, existing decisions and acceptance gates unchanged |
| [0012 — FreeToken repository review](0012-freetoken-repository-review.md) | Comparative review | Recorded 2026-09-09 UTC; no compatible embedding endpoint at the reviewed snapshot; query-cache measurement candidate remains unratified and unscheduled; no provider or performance-acceptance change |
| 0013 — (reserved) | — | Number used only by the unmerged Gemini branch's remediation plan; not on `main`. See 0014 |
| [0014 — Gemini remediation branch review](0014-gemini-audit-branch-review.md) | Adversarial review | Recorded 2026-09-22/23; the branch was rejected as a unit and survives only as tag `archive/gemini-audit-18092026`. Its one real `main` defect (§1.1 Ollama revision probe) was fixed in v3.4.0, deployed 2026-09-28; the interim control is retired (OPS-02). Salvage: the persistent Ollama client (ROADMAP QUAL-08) |
| [0015 — Prompt library](0015-prompt-library.md) | Research and proposal | Recorded 2026-09-22; operator-scoped to any MCP client; Option B recommended after a zero-code Stage 0; unratified and unscheduled |
| [0016 — Review findings plan](0016-review-findings-plan.md) | Plan and adversarial review | Tracks 1 and 3 shipped in v3.4.0 and were deployed 2026-09-28. Track 2 (timestamps) is ROADMAP TS-01 to TS-04 (draft PR #38); track 4 (the prompt pilot) is LLM-03/LLM-04 |
| [0017 — Exposed local backups and guarded restore preparation](0017-exposed-backup-and-restore.md) | Plan and adversarial review | Shipped in v3.5.0 and deployed 2026-09-28 with the `/exports` mount (OPS-04, OPS-05; the step-5 check passed). The MCP backup tools ship off by default; the operator decided on 2026-09-30 to enable them at the v3.7.0 deploy (OPS-07). Open: the pre-migration gate (TS-03) |
| [0018 — Self-improving prompts](0018-self-improving-prompts.md) | Idea capture | Recorded 2026-09-24: the operator's intent behind 0015, prompts that improve from tracked outcomes. Concepts, research warnings and the open architectural fork. Not a design; nothing scheduled |
| [0019 — Cloud LLM cost north star](0019-cloud-llm-cost-north-star.md) | Idea capture | Recorded 2026-09-24: the operator's aspiration that OC lower the cost of cloud LLM use; candidate levers from measurement to a request-path gateway, and the gap in 0012's FreeToken scope. Nothing scheduled |
| [0020 — Persistent storage review](0020-persistent-storage-review.md) | Review | DATA-01, 2026-09-28: decisions 1-4 adopted, steps A and B deployed (B with OPS-03), decision 6 answered. Open: decision 5 for the share root, and removing the dead host directories after a week of green nights |
| [0021 — #memory (usememory.com) review](0021-usememory-review.md) | Comparative review and operator aspiration | Recorded 2026-09-28 from four public pages: a hosted, keyword-only memory service with native apps, scoped OAuth, sync upserts, attachments and client-side encryption. The operator's aim is parity and better; gaps are ROADMAP PAR-01 to PAR-07, all unratified and unscheduled |

The numbering is chronological, not a priority ranking. The order of open
work lives in `docs/ROADMAP.md`; release history lives in `CHANGELOG.md`.
