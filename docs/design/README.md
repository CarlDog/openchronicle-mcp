# Design Documents and Reviews

Numbered documents in this directory capture proposed architecture and
comparative repository research. A proposal or recommendation is not
current product behavior until `docs/CODEBASE_ASSESSMENT.md` records it
as shipped.

| Document | Type | Status |
|---|---|---|
| [0001 — Cloud backup](0001-cloud-backup.md) | Design | Proposed; Dropbox and age decisions recorded, Phase 0 (operator runbook) not yet run |
| [0002 — OpenClaw memory review](0002-openclaw-memory-review.md) | Comparative review | Batches A + B shipped 2026-08-28/29 (revs 120-124, 129); ranking-policy items stay trigger-gated |
| [0003 — Ollama repository review](0003-ollama-repository-review.md) | Comparative review | Health/backfill/backup findings shipped (revs 125-126); adapter contract + reindex gated on ADR 0005 |
| [0004 — NemoClaw repository review](0004-nemoclaw-repository-review.md) | Comparative review | Findings ranked 1-5, 8, 10 shipped (revs 116-119, 126); remainder trigger-gated |
| [0005 — Composite embedding identity](0005-embedding-identity.md) | ADR | **Proposed** — awaiting operator acceptance; unblocks 0003 Phases C/D |

The numbering is chronological, not a priority ranking. Current backlog
status lives in `docs/V3_PLAN.md`; release history lives in
`CHANGELOG.md`.
