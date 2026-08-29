# Long-Term Scale & Resilience Path

**Status:** PROPOSED — staged options with named triggers; no stage is
scheduled by this document · **Date:** 2026-08-29 · **Requested by the
operator:** "OC is the backbone of our fleet… how do we handle multiple
development tasks, Mnemosyne integration, Wobblebot integration, and
others all interacting at the same time as our needs grow? What about
cloud backup and possible live sync? Think DEFENSIVELY — now is the
time to consider our long term options."

## The anchor principle: the state tier scales before the app tier

OC's application layer is nearly stateless — a request touches the DI
container, the store, and (optionally) the embedding provider. Running
N replicas of it behind a balancer is a compose-file exercise *the day
the state tier allows it*. SQLite does not allow it: one file, one
host, one writer, no remote access. So every scale/HA question reduces
to a database question, and **the hexagonal ports (`MemoryStorePort`,
`StoragePort`) are the asset this document exists to protect** — they
are what makes the eventual state-tier swap a bounded adapter project
instead of a rewrite. Defensive rule #1: nothing new may bypass the
ports.

A load balancer in front of a single SQLite-backed instance adds a hop
and no capacity; that specific shape stays rejected. Everything else
is staged below.

## What actually limits us today (measured/read, not guessed)

1. **Process-level serialization.** `SqliteStore` is ONE connection
   behind ONE `threading.RLock` — every read and write from every
   client serializes, stricter than WAL requires (WAL supports
   concurrent readers alongside one writer). This is the first real
   ceiling and the cheapest to lift.
2. **Long-transaction writers.** `onboard_git` and `memory import`
   hold write transactions for whole batches; under concurrent fleet
   load they stall everyone behind the lock.
3. **Embedding serialization.** NAS Ollama runs `NUM_PARALLEL=1` by
   fleet policy; concurrent semantic searches queue ~400 ms each at
   the provider.
4. **One host.** The NAS is the failure domain for OC, its backups
   (until 0001 ships), and its embedding provider.
5. **Unknown headroom.** Nobody has measured OC under concurrent
   multi-client load. Defensive rule #2: measure before re-architecting.

## The staged path

Each stage has a trigger. A stage is entered when its trigger fires,
not before — and the triggers are observable, not vibes.

### Stage 0 — durability + instrumentation (fund now; small)

- **Cloud backup Phase 0** (design 0001) — already P2 on the active
  plan. A backup that has never been restore-drilled is a hope, not a
  backup; the drill is part of Phase 0.
- **Concurrency load probe**: a benchmark-harness sibling that runs N
  simulated clients (mixed search/save/list) against a store and
  reports latency percentiles vs N. This turns every later trigger
  from a feeling into a number. One-day build, reusable forever.
- **Per-request timing visibility** if the probe shows contention:
  surface store-lock wait time in health/diagnostics so saturation is
  observable in production, not just in the probe.

### Stage 1 — single-node concurrency headroom (trigger: probe or

production shows store-lock contention at realistic fleet N)

All within SQLite, all behind the ports, all invisible to clients:

- Read/write split in `SqliteStore`: a small pool of read-only
  connections (WAL supports it) so reads stop queuing behind writes
  and behind each other; the RLock shrinks to the write path.
- `busy_timeout` + bounded write-transaction sizes for the batch
  writers (chunked git onboarding/import commits).
- If semantic-search volume grows: request-coalescing or a second
  Ollama `NUM_PARALLEL` slot — measured against the cache-fragmentation
  caveat in the fleet NAS rules.

Expected to carry the fleet for a long time: this workload is small
writes + read-heavy retrieval, which is SQLite's home turf.

### Stage 2 — state tier swap (trigger: corpus ~10× current with

semantic latency degradation — the sqlite-vec ceiling item — OR
sustained multi-writer contention Stage 1 can't absorb OR Stage 3's
trigger fires)

- **Postgres adapter** implementing `MemoryStorePort`/`StoragePort`
  (+ pgvector for the similarity scan, retiring the load-the-whole-
  table numpy path and the sqlite-vec question in one move).
- Runs as one more container on the NAS initially — same host, new
  engine. Schema migration = `oc memory export` → import; the
  envelope format is already strict and versioned.
- SQLite remains the default for single-user installs; Postgres is a
  deployment choice, not a replacement. The ports make dual support
  cheap to keep honest (the same contract tests run against both).

### Stage 3 — replicated app tier / real HA (trigger: an availability

requirement beyond one host — a second site, an uptime need during NAS
maintenance windows — ratified by the operator as worth its ops cost)

Only coherent AFTER Stage 2: with state in Postgres, N stateless OC
replicas behind a reverse proxy is configuration, and the DB gets a
replica/failover story from the Postgres ecosystem instead of from us.
Not designed further here on purpose — designing failover for a
trigger that hasn't fired is the over-engineering this fleet's rules
forbid. The commitment now is only: *nothing lands that would make
this stage harder* (rule #1, plus: no server-side session state
outside the DB, no filesystem coupling beyond the store).

### Live sync / offline write-behind (independent track, gated on its

own ADR)

The V3_PLAN research note (2026-07-30) stands, sharpened by this
document's lens: **single-primary with client-side write-behind
queues** — option (a), replaying buffered `memory_save`s through the
real MCP tools on reconnect — is the shape that stays compatible with
every stage above (the primary just moves tiers). Multi-master /
shadow-instance sync (option b) is where distributed-systems
complexity actually lives (id collision, conflict rules, merge
ordering) and is NOT required by any named fleet need; it stays
research-only. Prerequisite already on record from the NemoClaw
review: stable operation identity + postcondition checking, so a
replayed write is idempotent. That ADR happens when the write-behind
queue is scheduled, not before.

## What this document deliberately rejects

- **Load balancing the current single-SQLite instance** — a hop with
  no capacity gain (the question that started this review).
- **HA before Stage 2** — two containers sharing a SQLite volume is a
  corruption mechanism, not availability.
- **Multi-master sync** — no fleet need names it; single-primary
  covers every scenario raised.

## Defensive rules adopted now (cost ≈ 0)

1. All persistence through the ports; no new bypass.
2. Measure before re-architecting (the Stage 0 probe is the
   instrument).
3. No server-side state outside the DB (keeps Stage 3 trivial).
4. Backups are not done until a restore has been drilled.
