# Cloud Backup for OpenChronicle — Design

**Status:** Proposed — provider decided, nothing built · **Date:** 2026-08-23
**Resolves:** `docs/V3_PLAN.md` open question 12 · **Leaves open:** sync-as-store (stays in the Out of Scope table)

> **Corrected baseline.** The brief said ~3.7 MB / 277 memories. Live health on 2026-08-23T17:29Z: **8,650,752 bytes (8.25 MiB), 730 memories, 728 embedded**, `package_version 3.0.0rc8`, `schema_version 1`. Growth ≈ 5 MiB/quarter. Nothing below changes at this scale — but size the work off 8.25 MiB.
>
> **This is the second revision.** It is materially smaller than the first: the `cloud/` package, the persistent staging directory, four of six env vars, `classify_exit`, `redact`, and Phase 2 are all gone. Where a critique was wrong or a tradeoff was deliberate, there is an explicit *considered and rejected* note rather than silence.
>
> **Revision 3 (2026-08-23, same day): the provider is no longer a recommendation.** §4 is rewritten around the operator's actual accounts — Dropbox is chosen, OneDrive is rejected despite being preferred, and the App Folder fallback changed from "a dedicated new account" to "Full Dropbox on the same account" once it emerged that the account carries 23.13 GB of non-reproducible grandfathered quota. §13 question 1 is answered, question 6 is moot, and a `remote_free_bytes` health field was proposed and rejected in §6.2. No other section is affected: age recipient mode, no port, no MCP tool, and the §9 sync analysis are all provider-independent.

---

## 1. Decision summary

Nightly, the maintenance loop encrypts the three newest local SQLite backup artifacts to an **age** public key into a throwaway temp directory and `rclone copy --ignore-existing` them to a cloud remote. No snapshot engine, no port, no new module, no new MCP tool, no new CLI subcommand.

| Question | Decision | Loser and why |
|---|---|---|
| Transport | `rclone` — one integration covers OneDrive, Dropbox, Google Drive, and the no-OAuth tier (B2/S3/WebDAV/SFTP) | Per-provider SDKs: N integrations for one 8 MiB nightly upload |
| Backup engine | **None.** Plain files + `rclone copy` | restic / kopia — §10.1 |
| Encryption | **age, recipient mode** (`age -r <pubkey>`) | rclone `crypt` — §10.2 |
| Where the code lives | **`core/infrastructure/maintenance/jobs.py`**, directly under `db_backup`. No new package, no port | A `cloud/push.py` module — and a port is then a question nobody can even ask |
| Scheduling | New `cloud_backup` entry in `HANDLERS`, own 24h job | Chaining off `db_backup` (a cloud failure would mark the local backup failed — a lie); a sidecar or host cron |
| Job default | `enabled: True`, no-ops when `OC_CLOUD_REMOTE` is empty | `enabled: False` — job enable/disable is core.json-only, so `False` makes the feature unreachable from Portainer |
| What gets pushed | **The 3 newest `auto/*.db`**, encrypted into a temp dir, `--ignore-existing` | Newest-only (loses an artifact permanently on a *single* failed night); a persistent staging mirror (§10.3) |
| Remote deletion | **The daemon never deletes and never overwrites.** Unbounded growth accepted (~3 GB/yr) | Any daemon-side prune — the machinery most capable of destroying what it manages |
| Status surface | 3 fields on `/api/v1/health`, derived from `maintenance_state.json` | Touching `maintenance_degraded` (it means "the DB may be corrupt" and must stay sharp); duplicating the per-job counters already at `/api/v1/maintenance/status` |
| Provider | **Dropbox — decided 2026-08-23** (§4). App Folder scope if it verifies; Full Dropbox on the *same* account if not | Google Drive (mandatory own client_id, seven-day fuse if left in Testing), OneDrive (cannot be narrowed below full-drive) |

**Headline property: zero new secret-bearing environment variables.** age recipient mode means the container holds only a *public* key. Both new vars are safe in Portainer stack env, in `docker inspect`, and in logs — and `OC_CLOUD_REMOTE` is constrained by regex to `name:path` form specifically so an rclone *connection string* (`:s3,access_key_id=…,secret_access_key=…:bucket`) cannot be pasted there and turn a plain var into a credential. The only at-rest secret is `rclone.conf` (the OAuth refresh token) on the existing `/config` mount at 0600. A NAS compromise gets the ability to *write* new backups and nothing else — it cannot read a single historical one. Neither restic nor kopia nor rclone crypt can offer that: in all three, the credential required to write is the credential that decrypts everything.

**The two things that will actually bite:**

1. **Key loss is the dominant risk.** An encrypted backup whose identity file is gone is a deleted backup. The age identity is generated on the desktop, escrowed off-NAS, and **never installed on the NAS at all** — not in `/config`, not anywhere. (`/config` defaults to a Docker named volume, `docker-compose.nas.yml:116`, which is a good reason to bind-mount it for `rclone.conf`'s sake — but the identity is not the thing at risk there, because the identity is never on the NAS.) Phase 0 does not complete until a decrypt round-trip has been proven from the escrowed copy.
2. **OAuth dies silently, months after it looks fine.** rclone rewrites refreshed tokens back into `rclone.conf` using write-temp-then-rename, so the *directory* must be writable by uid 1000 — a read-only or root-owned `/config` works for hours and then fails forever. And Google's shared client_id is being retired during 2026; a Drive app left in "Testing" has grants that expire after **one week**.

---

## 2. Goals and non-goals

**Goals.** An offsite copy that survives total loss of the NAS. Cross-device restore from a machine that has never seen the NAS. Encryption at rest with a key the provider and the NAS both lack. Zero interactive credential handling on the serving path. One operator-visible fact: **how long since a verified artifact landed.** Keep sync-as-store reachable at bounded cost without building any of it.

**Non-goals.** Not sync — one-way push, and the SQLite file is never the synced object. Not dedup or snapshot management (that is what restic exists for, and it is worth ~nothing at 8.25 MiB). Not remote retention. Not restore-over-the-live-DB (§9.3 records the trap so whoever builds it starts from the right place). Not a notification system — OC makes staleness cheaply queryable; the operator's existing scheduled-agent tooling does the noticing. Not an MCP tool (§10.5). Not encryption of the local DB.

---

## 3. Architecture

### 3.1 Files touched — no new package

```text
core/infrastructure/maintenance/jobs.py       + cloud_backup handler + HANDLERS entry  (157 → ~220 lines)
core/application/services/maintenance_loop.py + _DEFAULT_JOBS entry; JobState.last_success_at + persistence
core/application/use_cases/diagnose_runtime.py+ cloud_backup_status block (reads the state file)
config/core.json.example                      + cloud_backup entry            ← see §5, this is a real landmine
Dockerfile                                    + rclone (COPY --from) and age (apt), both with build-time version gates
docker-compose.nas.yml                        + 3 env lines
tools/docker/entrypoint.sh                    + guarded chmod 600 on rclone.conf
.gitignore / .dockerignore                    + rclone.conf, *.age, backup-identity*
tests/test_maintenance_loop.py                + ~8 tests
```

**Considered and rejected: a `core/infrastructure/cloud/push.py` module and the "why no port" argument that came with it.** The first draft spent four sentences and three citations defending the absence of a port. Putting the handler in `jobs.py` — where `db_backup` already calls `container.storage.backup_to()` with no port, no use case, no abstraction — means the question cannot be asked. The right defense of "no port" is a file path, not a paragraph. `jobs.py` lands around 220 lines, well under the 300–400 soft cap. Corollary: `tests/test_hexagonal_boundaries.py` is **unchanged**; if you find yourself editing it for this feature, the code landed in the wrong layer.

### 3.2 The pipeline

Once per 24h, the whole handler body inside a single `asyncio.timeout(900)`:

1. `remote = os.getenv("OC_CLOUD_REMOTE", "").strip()`. Empty → debug log, return. (Status `disabled`.)
2. `remote` fails `^[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]*$` → **raise** (status `misconfigured`). Recipients empty → **raise**. Never push plaintext, never silently self-disable.
3. `artifacts = sorted(auto_dir.glob("*.db"))[-3:]`. Empty → info log, return (a `db_backup` has not run yet; not a failure).
4. `with tempfile.TemporaryDirectory(dir=backups_dir) as tmp:` — encrypt each artifact to `tmp/<name>.db.age` via `age -r <pub> [-r <pub>…] -o <dest> <src>`.
5. `rclone copy <tmp> <remote>/ --ignore-existing …` (§3.3).
6. Non-zero exit → raise with the code and a 2 KB-truncated stderr tail. Zero → advance `last_success_at`.

The temp dir is created **under the data volume**, not `/tmp`, so 24 MiB of ciphertext never lands in the container's writable layer, and the context manager cleans it on the exception path too. It cannot collide with local retention: `_retention_prune` globs `backups/auto/*.db` non-recursively (`jobs.py:55`) and can neither see nor unlink `backups/tmp*/*.age`.

**Why three artifacts, and why `--ignore-existing`.** `_invoke`'s `finally` advances `last_run_at` even when the handler raises (`maintenance_loop.py`), so a single failed night is not retried — the next attempt is 24 hours later, by which time `db_backup` has produced a newer artifact. Under a newest-only push, **one transient network failure permanently loses one night from the offsite history**, and that artifact ages out of `auto/` within 7 days. A 3-deep rolling window means three *consecutive* failures are needed to lose anything — and the 48h staleness alarm (§6.3) fires after two, so the alarm precedes the loss by a full night. That is the derivation of N=3.

`--ignore-existing` — *"Skip all files that exist on destination"* ([rclone flags](https://rclone.org/flags/)) — makes the two already-uploaded artifacts a no-op listing skip rather than a re-upload. This matters because age ciphertext is non-deterministic (fresh file key and nonce per encryption), so re-encrypting yesterday's artifact yields different bytes under the same name; without the flag rclone would overwrite a known-good remote object every night for no gain and with a small partial-write exposure. With it the remote is genuinely **append-only**: the daemon never deletes and never overwrites. Steady-state upload is ~8 MiB/night (one new object); the wasted work is two redundant local encryptions of 8 MiB each, roughly a second, which is cheaper than an extra `rclone lsf` round-trip to avoid them.

**Considered and rejected: the persistent `backups/cloud/` staging mirror with its own 30-day retention.** It existed to close multi-day-outage history gaps, and it brought `_prune_staging`, `OC_CLOUD_STAGING_DAYS`, a three-directory retention table, a correctness rule the first draft itself admitted "no naturally-written test catches," and a `STAGING_DAYS=0` path that would delete every staged ciphertext *before* the upload and still report success. The scenario it protected against pays almost nothing: during the outage the staging ciphertext sits on the same NAS that might die, and afterwards the newest artifact gets through regardless. When a design's correctness depends on a rule no natural test catches, delete the machinery. The residual exposure — an outage longer than 3 nights leaves a hole in the offsite history, though never in the *current* offsite copy — is accepted, alarmed at 48h, and named here rather than engineered away.

### 3.3 The exact rclone invocation

```bash
rclone copy <tmpdir> <remote>/ --ignore-existing --transfers 1 --contimeout 30s --stats 0 --ask-password=false --log-level INFO --
```

`RCLONE_CONFIG=/config/rclone.conf` travels in the subprocess **environment**, never on argv — argv is world-readable via `/proc`, and this mirrors `git_onboard._build_clone_env`, which deliberately keeps the GitHub PAT off the command line. rclone's default config lookup finds nothing in this container anyway (the `oc` user is created `--no-create-home`), so this is mandatory, not stylistic; without it the failure is "remote not found," which points nowhere near the cause.

**Transfer integrity is not lost by dropping `--checksum`.** rclone verifies every transfer by default: *"Normally rclone will check that the checksums of transferred files match, and give an error 'corrupted on transfer' if they don't"* ([rclone docs](https://rclone.org/docs/)); `--ignore-checksum` is the flag that would disable it, and we do not pass it. `--checksum` only changes the *equality/skip* comparison, which `--ignore-existing` now owns. This retires the first draft's load-bearing-and-backwards `--checksum` claim entirely.

Flags deliberately absent:

- **`sync` — never.** It deletes at the destination and would mirror local 7-day retention up to the cloud, turning DR into a second copy of the same week. This word must not appear in the implementation.
- **`--max-duration` — dropped.** The first draft nested `13m` inside a `900s` outer bound with nothing enforcing the relationship: a drift trap for one 8 MiB upload a day. One timeout, the outer one, which is also the global-mutex release guarantee.
- **`--retries 3` — dropped, it is the default** (verified). Keeping it reads as a considered tuning decision when it is a restatement. `--contimeout 30s` *is* a real tightening (default `1m0s`) — keep it.
- **`--transfers 1`** reduces 429 pressure on what is effectively a single-file workload. Retry-After is honored inside rclone's pacer where OC cannot see it; OC's obligation to *bound* it is discharged by the outer 900s timeout.
- **`--` end-of-options guard**, because *"anything after a `--` option will not be interpreted as an option"* (verified). With the `OC_CLOUD_REMOTE` regex in place this is belt-and-braces, not the primary defense.
- **`rclone rcd` / `serve`** — a supervised daemon and a second HTTP auth surface, for one file a day.

**Use `asyncio.create_subprocess_exec`, not `asyncio.to_thread` + `subprocess.run`.** Cancelling a `to_thread` task does not stop the worker thread, and interpreter shutdown joins it — a hung upload would stall container shutdown past Docker's grace period into SIGKILL. Native async subprocess costs the same LOC. On `TimeoutError` **or** `CancelledError`, `proc.kill()` then `await proc.wait()` in a shared `finally`. *Considered:* the scope critique called the two kill-path tests gold-plating. Half-accepted — write the kill in one shared `finally` and test it once; the cancel path is the same code.

`_invoke` holds the process-wide `_global_lock` for the whole handler and the loop has **no per-job timeout of any kind**, so the 900s bound is simultaneously the mutex's only release guarantee and the worst-case container-stop delay. That is why it wraps the *entire handler* — encryption included — and not just the rclone call.

### 3.4 Getting the binaries into the image

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends git gosu age \
 && rm -rf /var/lib/apt/lists/*

# rclone is MIT (c) 2012 Nick Craig-Wood. The official image is Alpine/musl built
# CGO_ENABLED=0; the upstream release binary measures fully static, so it should run
# unmodified on Debian trixie. The version gate below makes that a BUILD failure, not
# a runtime one.
COPY --from=rclone/rclone:1.75.0 /usr/local/bin/rclone /usr/local/bin/rclone
RUN rclone version && age --version
```

**Do not `apt-get install rclone`.** Debian trixie ships 1.60.1 (2022); upstream is 1.75.0 (2026-07-31, verified). A 2022 rclone predates the Google client_id retirement and years of provider OAuth changes. That is a correctness issue, not version hygiene. **Do `apt-get install age`** — age has no OAuth policy surface and a stable file format, so trixie's 1.2.x vs upstream has no correctness consequence. One word beats a second pinned download; `age --version` gates the assumption.

**Considered and rejected: pinning rclone by image digest.** The base image is `FROM python:3.14-slim`, a floating tag, and every apt package floats. Digest-pinning one link of an otherwise-open chain is inconsistent hardening that buys a resolve-at-implementation-time blocker and a confidence-register row. Dependabot does not update `COPY --from` images either way ([dependabot-core#12988](https://github.com/dependabot/dependabot-core/pull/12988) is open), so **add "bump the rclone tag" to the phase-end audit checklist** regardless — a stale rclone is a live risk given how fast provider OAuth policy moves.

**Cost, named up front:** rclone ~81 MiB uncompressed, age ~7 MiB — roughly **+88 MiB, 50–60% image growth**, to move 8 MiB once a day. There is no cheaper way to get multi-provider coverage from one integration. Accept it deliberately rather than discovering it at the first CI build.

---

## 4. Provider strategy and bootstrap

**Decided 2026-08-23: Dropbox.** The operator holds OneDrive (preferred), Google
Drive, and a Dropbox account they had been planning to retire. That last one wins
anyway, and the deciding argument is not the ranking below — it is that Dropbox is
the only one of the three whose scope rclone can actually narrow.

Ranked by *unattended reliability*, the only ranking that matters for a backup:

| Provider | Own OAuth app? | Narrow scope via rclone? | Inactivity deadline | Verdict |
|---|---|---|---|---|
| **Dropbox** | No (shared App ID works) | **Yes** — App Folder access type | None documented | **Chosen** |
| Google Drive | **Yes, mandatory** — shared id retires during 2026 | Yes — `--drive-scope drive.file` | 6 months (**7 days** if left in "Testing") | Runner-up, highest-maintenance |
| OneDrive personal | No | **No** — see below | ~90 days | Rejected despite being preferred |
| *B2 / S3 / WebDAV / SFTP* | **No OAuth at all** | Yes (bucket + prefix + capability) | None | Strictly better, but the operator has none |

**Dropbox.** No app review for a single-user app (production approval only past 50 linked users), refresh tokens with no documented expiry, `Retry-After` always present on 429, and App Folder is the narrowest blast radius rclone can actually use. Create the app with **App folder** access and enable exactly `account_info.read`, `files.metadata.write`, `files.content.write`, `files.content.read`, `sharing.write`.

**Two facts about this specific account that change the plan.**

*It is not reproducible.* It is a Basic (free) plan carrying **23.13 GB** — far above
the 2 GB baseline, from referral and promo space accumulated since Dropbox's earliest
days. That quota is bound to the account: delete it and a fresh Basic account gives
you 2 GB and none of whatever else is grandfathered in. So the runbook line is not
"remember to keep this account" but **this account is irreplaceable** — a fact worth
stating in a sentence that survives forgetting why. Reassuringly, the *app*
registration is fully reversible: a token can be revoked from the App Console without
touching the account or its quota, so Phase 0 experimentation costs nothing.

*The retirement plan is now load-bearing.* The operator described this account as
deprecated. Adopting it as the backup target is a decision to keep it alive, and that
decision must be recorded where someone tidying up their subscriptions will meet it.

**Storage headroom, measured rather than assumed.** 29.17% of 23.13 GB is in use, so
about **16.4 GB is free** — roughly five years at today's 9 MB nightly artifact, or
about two if the database keeps growing at the ≈5 MiB/quarter estimate. This is why
§8's operator-run prune stays deferred: "years away" is a measurement here, not a
hope. Dropbox Basic also retains deleted and overwritten files for **30 days**, a free
backstop against a bad push that complements — rather than duplicates — the
never-delete rule.

**The fallback changed, and the first draft had it wrong.** If App Folder does not
verify (§12), the fallback is **Full Dropbox scope on this same account**, *not* a
dedicated new account. A new account means 2 GB and no grandfathered space, which
trades a narrow token for a target that cannot hold the backups — a strictly worse
deal. Under Full Dropbox the exposure is this account's contents specifically, which
the operator has already written off, and age encryption still means a stolen token
reads nothing of OC's.

**Why not OneDrive, despite being the preferred provider.** rclone's OneDrive backend
roots at `/drives/{driveID}` and never addresses `/special/approot`; its
`access_scopes` enum contains no AppFolder value (`backend/onedrive/onedrive.go`).
Using it means granting `Files.ReadWrite.All Sites.Read.All` over the entire drive to
hold a 9 MiB file — and **encryption does not offset this**, because age protects the
*contents of the backups* while scope protects *everything else in the account*. The
two are orthogonal. That grant turns "someone reached the NAS" into "someone has
read/write across my whole personal drive," which is a materially larger prize than
the OC corpus they would already have from the NAS itself. A dedicated Microsoft
account would neutralize it; the operator has an account that already satisfies the
requirement without one.

**OneDrive cannot be narrowed.** rclone's OneDrive backend roots at `/drives/{driveID}` and never addresses `/special/approot`; its `access_scopes` enum contains no AppFolder value (`backend/onedrive/onedrive.go`). Using OneDrive means granting `Files.ReadWrite.All Sites.Read.All` over the entire drive to hold an 8 MiB file. Narrowing it would mean hand-writing a Graph client — a second implementation of what rclone already does.

**Google Drive's trap has a one-week fuse.** Per rclone's own docs the shared client_id "is being retired and will stop working during 2026," and an app left in "Testing" has grants that "expire after a week." `drive.file` and `drive.appdata` are classified non-sensitive, so "Publish app" is self-serve — no review, no fee, no 100-user cap; the cost is a nameless consent screen once. Files created under one client_id are invisible under a different one, so **register your own client_id before uploading anything**. Prefer `drive.file` over `drive.appfolder`: appfolder is invisible in the Drive web UI, defeating browser-based emergency restore.

### 4.1 Bootstrap runbook (one operator session, ~30 min, desktop only)

**Step 0 — settle the App Folder question first (~10 min).** It is the one
UNVERIFIED claim on this path (§12), and it decides the app's access type, which
every later step inherits. In the Dropbox App Console create an app with **App
folder** access and the five scopes above, then:

```bash
rclone config                               # new remote, type dropbox, name it e.g. ocdrop
rclone lsd ocdrop:                          # ← the actual test
rclone copy ./probe.txt ocdrop:probe/ -v    # and a real write
```

If either errors with `Path root is not supported for sandbox app`, delete the app,
recreate it with **Full Dropbox** access on this same account, and carry on — see §4
for why the fallback is *not* a dedicated new account. Record which access type you
ended up with; it is the difference between a token that can read one folder and one
that can read the account.

```bash
# 1. Generate the age keypair. The only irreplaceable secret in the design.
age-keygen -o backup-identity.txt          # prints: # public key: age1...

# 2. ESCROW IT NOW, BEFORE ANYTHING ELSE. Password manager + printed offline copy.
#    The NAS never receives this file. Ever.

# 3. Configure the remote. Include the instance segment in the path (see §9.2):
rclone config                               # name it e.g. ocdrop
rclone config file                          # prints the path you copy in step 5

# 4. Prove the round-trip BEFORE any code exists — this IS the restore drill (§8).
age -r age1... -o probe.db.age /path/to/some/openchronicle-<ts>.db
rclone copy . ocdrop:openchronicle/nas/ --ignore-existing --include probe.db.age -v
rclone copyto ocdrop:openchronicle/nas/probe.db.age ./back.db.age
age -d -i backup-identity.txt -o back.db back.db.age
sqlite3 back.db "PRAGMA integrity_check; SELECT COUNT(*) FROM memory_items;"

# 5. Install rclone.conf on the NAS (host side of the /config mount), then:
#    chown 1000:1000 rclone.conf && chmod 600 rclone.conf
```

Both bootstrap routes are supported: configure on the desktop and copy the file (simplest — no rclone on the NAS, no TTY into a container), or `rclone config` → answer `N` → `rclone authorize "dropbox"` on the desktop → paste the token. rclone's docs advise matching versions across the two machines for the authorize route.

*Retained for the runner-up only:* were Google Drive ever adopted, insert before step 3 — create a Cloud project, create an OAuth client (Desktop app), add scope `.../auth/drive.file`, and **press "Publish app."** Skipping the publish step produces a backup that silently dies exactly seven days later. Register the client_id *before* uploading anything: files created under one client_id are invisible under another.

---

## 5. Config and compose surface

| Variable | Meaning | Default |
|---|---|---|
| `OC_CLOUD_REMOTE` | rclone destination including the instance segment, e.g. `ocdrop:openchronicle/nas`. **Empty disables the whole feature.** Must match `^[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]*$`. | *(unset)* |
| `OC_CLOUD_AGE_RECIPIENTS` | comma-separated age **public** keys. Empty while remote is set = hard error. | *(unset)* |
| `RCLONE_CONFIG` | container-internal wiring — the mount path, not configuration | `/config/rclone.conf` (hardcoded) |

```yaml
# docker-compose.nas.yml, environment:
  OC_CLOUD_REMOTE: ${OC_CLOUD_REMOTE:-}
  OC_CLOUD_AGE_RECIPIENTS: ${OC_CLOUD_AGE_RECIPIENTS:-}
  RCLONE_CONFIG: /config/rclone.conf
```

**The regex is a security control, not tidiness.** It deliberately rejects rclone *connection strings* (`:s3,access_key_id=…,secret_access_key=…:bucket`), which would put a live credential into a plainly-visible Portainer var that `oc config show` does not mask. It also rejects leading `-`, spaces, quotes, and shell metacharacters. Do not "fix" it to be more permissive. A malformed value **raises daily** and reports `misconfigured` — it never self-disables, because `disabled` is what the operator sees when they deliberately left the var empty and the two must not be confusable.

**Considered and rejected: `OC_CLOUD_TIMEOUT`, `OC_CLOUD_STALE_HOURS`, `OC_CLOUD_INSTANCE`, `OC_CLOUD_STAGING_DAYS`.** The first two become module constants (`_CLOUD_TIMEOUT_SECONDS = 900.0`, `_STALE_HOURS = 48`); the third is folded into the path the operator types into `OC_CLOUD_REMOTE`; the fourth dies with the staging dir. This is in tension with the fleet rule that every operator-tunable compose value gets `${VAR:-default}` — the resolution is that the rule exists so a *feature* is not unreachable from Portainer, and here the feature's on/off switch and its key both are. A subprocess timeout and an alerting threshold are implementation tuning that a single user will never retune; promoting either constant to a var later is a 3-line change. Cutting them also deletes `CloudSettings`, `load_cloud_settings`, `container.cloud_settings`, and the whole "fail soft on every field" paragraph — constants cannot be unparseable. Read both vars with `os.getenv(...).strip()`, matching the existing `is_disabled()` precedent, so empty-string means unset.

Do **not** regex-validate the recipient keys. `age` itself rejects malformed recipients and supports plugin forms (`age1yubikey1…`) a naive pattern would break — defer to upstream validation. Do log the configured recipients at INFO on the first run of each process: they are public keys, safe in logs, and eyeballing them against escrow is the cheapest defense against the *valid-but-wrong-key* failure (§6.4).

**`config/core.json.example` is a third registration site and it is a live landmine.** `load_jobs` treats a present `maintenance.jobs` list as a **total replacement**, not a merge, and warns only on *unknown* names, never missing ones. The shipped example enumerates all five current jobs and its own first line says "Copy to core.json and edit" — and the entrypoint copies it into `/config` on first run. An operator who tunes one interval silently loses cloud backup forever, with no log line, while `OC_CLOUD_REMOTE` is set. Add `cloud_backup` to the example **in the same commit**, and extend `test_handlers_registry_complete` (which today asserts `_DEFAULT_JOBS` == `HANDLERS`) to cover the example file too. Three registration sites, one test. The deeper defect — that `load_jobs` replaces rather than merges, so the example will silently drop *every future* job — is §11.

**Entrypoint, and the crash-loop it would otherwise cause.** `tools/docker/entrypoint.sh` is `set -eu`. A bare `chmod 600 /config/rclone.conf` on a `/config` without that file exits non-zero, aborts the entrypoint before `exec gosu oc oc serve`, and `restart: unless-stopped` loops it forever — on *every* deployment that has not installed the file, which today is all of them. The chmod is still needed (the entrypoint chowns but never chmods, and rclone *mirrors an existing file's permissions* onto the temp file it renames into place, so a conf that arrives 0644 stays 0644 forever). Write it guarded, immediately after the existing `chown -R`:

```sh
[ -f "$OC_CONFIG_DIR/rclone.conf" ] && chmod 600 "$OC_CONFIG_DIR/rclone.conf" || true
```

Add a test that boots the image with an empty `/config` and asserts a healthy container.

**Recommend setting `HOST_CONFIG_DIR` to a real NAS path when this feature is enabled** — `/config` otherwise defaults to a named volume with no host path, and `rclone.conf` should be readable and re-installable without `docker exec`.

---

## 6. Failure and status semantics

### 6.1 The one thing that matters

**How long since a verified artifact landed.** `JobState` today records `last_run_at` and `last_outcome`, has **no `last_success_at`**, and persists only `last_run_at` — every counter is per-process. Combined with this project's rule that every push to main bounces the container, a persistently failing push presents a clean surface after each redeploy. That is the mechanism by which a backup silently stops working for three weeks.

**Add `last_success_at: datetime | None` to `JobState`, persist it alongside `last_run_at`, advance it only on genuine success.** ~5 lines, generic across all jobs, and it closes two unmet bullets of V3_PLAN open question 16 (last successful `db_backup` / `db_vacuum`). Per the project's own "separate commits per finding category," **land this as its own commit before the feature** — it touches all five jobs and a V3_PLAN question and does not belong inside a cloud-backup diff.

### 6.2 Health block — three fields, read from the state file

```json
"cloud_backup_status": {
  "status": "disabled | ok | stale | misconfigured",
  "last_success_at": "2026-08-23T04:15:02Z",
  "hours_since_last_success": 13.2
}
```

Built in `build_health_payload(container)` by reading `container.paths.db_path.parent / "maintenance_state.json"` — the same path `app.py` hands the loop, and container-reachable. **This is the resolution to a real wiring problem:** `CoreContainer` holds no reference to the loop (it lives on `app.state.maintenance`), so a block populated from in-process `JobState` would have been unbuildable at the only assembly point both REST and MCP share. Restricting the block to what the state file can carry makes it buildable *and* makes it durable across the redeploys that would otherwise reset it.

**Considered and rejected: `last_failure_at`, `last_failure_kind`, `last_error`, `runs_failed`, `instance`, `remote_name`, `recipients`.** Four of those are a second copy of `/api/v1/maintenance/status`, which already serves `MaintenanceLoop.status()` for every job. `remote_name` would leak part of a value the design otherwise treats carefully — nothing to redact if nothing is surfaced. `recipients: 2` told an operator nothing checkable; the startup log line of the actual public keys does.

**Also considered and rejected (2026-08-23): a `remote_free_bytes` field fed by
`rclone about`.** It was proposed as early warning before the remote fills, and the
reasoning does not survive contact with the rest of this section: a full remote makes
pushes *fail*, which stops `last_success_at` advancing, which raises `stale` within 48
hours — the alarm that already exists catches it. The field would buy warning weeks
earlier at the cost of a per-job payload in a state file whose schema is shared by all
five jobs, plus an extra nightly subprocess that can itself fail, on the one job whose
entire purpose is not failing. Against five years of measured headroom (§8) and a
quota the provider's own client displays on demand, that is not a trade worth making.
Revisit only if the prune in §8 is ever actually triggered.

Three defined inputs, all of which must yield a status and never an exception: **state file absent** (first boot) → `stale` if enabled, `disabled` if not; **key absent** (old state file, pre-`last_success_at`) → same; **malformed JSON** → `stale`, logged. `last_success_at is None` while the feature is enabled is **stale, not ok** — otherwise the sole alarm never fires for the case that matters most, a deployment that never worked once.

The Docker healthcheck is unaffected and cannot be broken by this: it probes the top-level `@app.get("/health")` at `app.py:170`, which returns a static `{"status": "ok"}` and does not call `build_health_payload`. The rich payload lives at `/api/v1/health`. Wrap the state-file read in try/except anyway.

**Never touch `maintenance_degraded`.** It is set only by `db_integrity_check` and means "the DB may be corrupt." Overloading it with "the cloud is unreachable" dilutes a sharp signal an agent reads.

### 6.3 Staleness threshold: 48 hours, derived

`_retention_prune` keeps 7 newest ∪ newest-per-day-for-7-days, so a local artifact survives ~7 days, and the 3-deep push window tolerates two consecutive failed nights with no loss at all. 48 hours therefore alarms **one full night before** the first artifact can be permanently missed, with about five days of margin before local retention starts dropping unpushed artifacts. That is why the number is 48 and not a round guess.

### 6.4 Failure handling

Non-zero exit → raise, with the exit code and a 2 KB-truncated stderr tail attached so `last_error` in `/api/v1/maintenance/status` carries something actionable. `_invoke` already logs every raise at ERROR via `_logger.exception`.

**Considered and rejected: a `classify_exit()` function and a `redact()` function.** The classifier's only outputs were a log level (already ERROR for every raise) and a `last_failure_kind` field that no longer exists. Keep the table below as an **operator decoder ring in the docs**, not as code:

| Exit | Meaning |
|---|---|
| 0 | success (including "nothing new to upload" — the normal steady state) |
| 5 | temporary / retryable; next tick retries |
| 6 | non-retryable minor (e.g. Dropbox 461) |
| 7 | **fatal** — account suspended or credentials revoked. Will not self-heal. |
| 1/2/3/4 | uncategorised / syntax / dir-not-found / file-not-found — config or wiring error |

`redact()` was justified by an uncited claim that rclone echoes tokens in some auth errors, and structurally the credential never enters this process at all — it lives in `rclone.conf`, is read by rclone, and OC never touches it. The one real exposure the critique identified was `OC_CLOUD_REMOTE` accepting a credential-bearing connection string, and the §5 regex closes that at the source, which is the better place. Keep the 2 KB truncation.

A **valid-but-wrong** age recipient fails open: age succeeds, rclone succeeds, health goes green, and every artifact is undecryptable. Escrow discipline does not touch this — it is key *mismatch*, not key loss. Two cheap, offline, network-free defenses: the recipient log line (§5), and Phase 1's DONE criterion requiring a decrypt of one **daemon-produced** artifact, not just the hand-made Phase 0 probe.

Every rclone and age call uses captured pipes, never inherited stdio; every diagnostic goes to stderr via `logging`.

### 6.5 Fail-soft, always

If rclone is missing, `rclone.conf` is absent, the remote is malformed, or recipients are empty, the handler **raises** — the loop counts a failure and continues. Never validate cloud config in `CoreContainer.__init__`; never `exit(1)`. Under `restart: unless-stopped`, a boot-time validator turns one stale Portainer value into a total outage of the memory server for the sake of a nice-to-have offsite copy. A daily ERROR for a genuinely-broken enabled feature is correct behavior; do not add log-once suppression.

### 6.6 How a human finds out

`/api/v1/health` and the MCP `health` tool carry `cloud_backup_status.status`; any agent session that calls health sees it. The actual notification is an existing-fleet scheduled agent that alerts when `status` is neither `ok` nor `disabled` — **zero new code in OC**. One requirement on that agent, because the zero-code path only alarms when OC is healthy enough to answer: **it must alert on "unreachable for N hours" as well as on a bad status.** A crash-looping or dead NAS produces no backups *and* no alarm otherwise.

---

## 7. Security and key custody

**Threat model.** Protects against: a breach at the cloud provider; compromise of the cloud account (which on OneDrive is unavoidably full-account); a stolen `rclone.conf`. Does not protect against: NAS shell access (the live DB is plaintext); theft of the `/config` volume — weaker than it sounds, since that volume holds only the OAuth token and public keys, granting write-new-backups, not read-old-ones; a subpoena served on the operator. A subpoena to the provider gets ciphertext; a subpoena to you gets the key. Add this as a "Cloud backup" section in `docs/configuration/security_posture.md`.

**Why encrypt — corrected justification. Considered and rejected: the scope critique's claim that recommending Dropbox App Folder makes encryption redundant.** That argument conflates *token scope* with *read access*. App Folder narrows what rclone's OAuth token can reach; it does nothing about what Dropbox itself, or anyone who obtains the account password, can read — the corpus sits readable-by-password in a consumer account either way. The first draft's "provider-scope asymmetry" framing was a weak argument (it is really an argument about OneDrive, which we do not recommend) for a feature that is nonetheless correct. Replace the argument, keep the feature. The honest counter is availability, not necessity, and it is §12.2.

**Key custody.** The age identity is generated on the desktop, escrowed off-NAS (password manager plus a printed offline copy), and never installed on the NAS. The container holds only public recipients, in a plain env var. **Set two recipients** (`age1primary,age1recovery`): an artifact encrypted to both opens with either, so losing one is survivable — native escrow at the cost of one comma, and impossible to add retroactively for artifacts already written. Rotation affects **future** artifacts only, so never destroy a retired identity while artifacts encrypted to it still exist on the remote.

**Secret hygiene.** Add `rclone.conf`, `*.age`, `backup-identity*` to `.gitignore` and `.dockerignore` (`*.key` / `*.pem` / `*.env` are already covered; `*.conf` is not). Never put key material or an example `rclone.conf` in the repo's `config/` — `Dockerfile:65` bakes that directory into the published image and the entrypoint copies it into `/config`. `rclone obscure` is **not** encryption (AES-CTR with a static key shared across every rclone build, and OAuth tokens are not obscured at all) — treat `rclone.conf` as plaintext-equivalent and never describe it to the operator as encrypted. Do **not** enable rclone config encryption: the password would sit in Portainer env, readable by exactly the population that can already read the volume, and "there is no way to recover the configuration if you lose your password." Pass `--ask-password=false` as slip-defense against a headless hang.

`tests/test_no_secrets_committed.py` **would not** catch a stray committed `rclone.conf`, confirmed: `FORBIDDEN_PATTERNS` has no `*.conf` entry, and the check uses non-recursive `repo_root.glob(pattern)`, so it would not reach `config/rclone.conf` even with the pattern added; the `SECRET_PATTERNS` arm targets JSON shapes. Extending it needs both `"*.conf"` and `rglob` plus a fixture. `.gitignore` is the actual control — an obscured rclone password is not a shape gitleaks recognizes either.

---

## 8. Phased delivery

### Phase 0 — Bootstrap, and the first run of the restore drill (operator, zero code)

Provider is decided (§4). Settle the App Folder question (§4.1 step 0), create the app
with whichever access type verified, generate and **escrow** the age keypair, run
`rclone config`, and execute §4.1 end to end.

**Considered and accepted: Phase 0's exit gate and the old Phase 2 "restore drill" were the same five commands.** They are now one thing, run for the first time here and re-run quarterly via the phase-end audit checklist.

**DONE when** one manually-encrypted artifact has been uploaded, pulled back, `age -d`-ed from the **escrowed** identity, and passes `PRAGMA integrity_check` (exactly `ok`) *and* a row-count floor of ≥ 90% of live `memory_items` / `projects` — on a machine that is not the NAS. The row-count floor is the load-bearing half: an empty-but-well-formed schema passes `integrity_check` cleanly.

On the quarterly re-runs, **sample an artifact older than the newest one** — `rclone lsjson … | tail` picks the object most recently written and therefore least likely to have rotted. Nothing in this design ever re-reads an old remote object, so the drill is the only coverage old artifacts get; say so plainly rather than implying continuous verification.

### Phase 1 — The push job

Two commits. **First:** `JobState.last_success_at` for all five jobs plus persistence, on its own (§6.1). **Then:** Dockerfile, the `cloud_backup` handler in `jobs.py`, all three registrations (`HANDLERS`, `_DEFAULT_JOBS`, `core.json.example`), the health block, the guarded entrypoint chmod, compose lines, ignore files, and docs (ADR + `docs/configuration/cloud_backup.md` runbook + security_posture section + env_vars + MAINTENANCE job table + V3_PLAN Q12 resolved + CHANGELOG).

Tests (~8, 589 → ~597):

- argv assembly: correct verb, the flags, the `--` guard, and **no `sync` anywhere**.
- config path arrives via subprocess **env**, not argv.
- `asyncio.timeout` wraps the **whole handler** and equals `_CLOUD_TIMEOUT_SECONDS` — this is the global-mutex release guarantee and deserves a named test.
- timeout kills the child and `await`s `proc.wait()` (one test on the shared `finally`).
- `OC_CLOUD_REMOTE` validator: rejects a connection string, a leading `-`, and a bare path, **before any subprocess** (`mock.assert_not_called()`).
- remote set + recipients empty → raises, and **no plaintext file is written**.
- unconfigured → clean no-op (mirrors `test_embedding_backfill_no_op_when_service_missing`).
- exactly the 3 newest artifacts are encrypted, and the temp dir is removed on the exception path.
- `maintenance_state.json` shape change: an old state file with no `last_success_at` loads without raising. *Verify, don't assume* — a state-file exception at boot is the exact crash-loop that file exists to prevent.
- `test_handlers_registry_complete` extended to `core.json.example`.
- `tests/test_hexagonal_boundaries.py` **unchanged**.

**No CLI subcommand ships.** Manual trigger is `oc maintenance run-once cloud_backup`, which works the moment the handler is in `HANDLERS`. `oc cloud push` would be a second name for an existing operation; `oc cloud status` would restate the health payload.

**DONE when:** three consecutive nights green on the NAS with `status: ok` and a real `last_success_at`; **and** one artifact *produced by the daemon* has been pulled, decrypted from the escrowed identity, and passed the drill's checks (this is the key-mismatch gate, §6.4); **and** deliberate breakage verified — set a malformed remote, confirm the job raises daily, `status` reads `misconfigured` not `disabled`, `db_backup` still succeeds, and `maintenance_degraded` stays `false`.

### Phase 2 — Deferred, each gated on a named trigger

| Item | Trigger that reopens it |
|---|---|
| Co-push the `oc memory export` JSON envelope | A SQLite-version restore problem actually occurs, or sync-as-store becomes funded |
| `oc cloud list` / `oc cloud pull` | Reading health JSON / typing rclone flags becomes a real annoyance |
| Operator-run remote prune | Remote storage actually pinches. Measured 2026-08-23: ~16.4 GB free of 23.13 GB, against ~3.3 GB/yr — five years at today's size, ~two if growth continues. Visible any time in the Dropbox client; no code needed to watch it |
| Restore-over-the-live-DB | An actual disaster, or a second machine — §9.3 |
| Sync-as-store | §9 |

---

## 9. The sync-as-store door

### 9.1 What is already free (verified, no action)

The most expensive-to-retrofit sync primitive already exists: memory ids are **uuid4, generated server-side at construction, never caller-supplied** (`MemoryItem.id` defaults to `uuid.uuid4()`; the MCP `memory_save` path constructs without an id), and carried verbatim through export/import. Two devices writing concurrently produce disjoint id spaces automatically — no coordination, no allocation scheme, no collision handling, ever. `memory_items` carries `updated_at`; the envelope emits every field a per-item sync would need, versioned as `EXPORT_FORMAT_VERSION = 1`.

"Embeddings excluded, regenerable" survives an adversarial check: a mixed-provider merge (768-dim ollama vs 1536-dim openai) is already defended — `list_embeddings(model=…)` filters by model, `count_stale_embeddings(current_model)` counts mismatches, `save_embedding` records `dimensions` as measured fact, and the cascade is live (`PRAGMA foreign_keys = ON`). Foreign-model vectors are ignored, not mixed into cosine.

And the JSON envelope is a **pure function of any restored `.db`** — `export_memory` reads only `list_projects()` and `list_memory()`. Deferring the envelope push therefore loses **zero** information: a future sync effort can regenerate every envelope it wants from the artifact history. That is the actual answer to "does backup-only foreclose sync," and it is no.

### 9.2 The three cheap decisions

1. **Host-qualified remote path — `<remote>:<prefix>/<instance>/`.** Justified on non-sync grounds alone: local backup filenames carry no instance identifier, so two OC instances pointed at one prefix would interleave and overwrite each other's history. With `OC_CLOUD_INSTANCE` cut (§5) this is **zero code** — a convention the operator types into `OC_CLOUD_REMOTE` and the runbook documents.
2. **The authority-seed bootstrap rule, written down.** When sync is adopted at time T, every new device is seeded from the authority's state at T — **never from an old export or backup**. This is a *procedure*, not a mechanism, which is exactly why it must be recorded. **Narrowing on the first draft's claim:** authority-seed makes missing history harmless **at bootstrap only**, not in steady-state divergence after T. The first draft overstated it as making "all the missing history harmless."
3. **The deletion gap, named and not filled.** There are no tombstones — a deleted memory is simply absent, so a future sync cannot distinguish "deleted here" from "not yet seen here." Recording this costs a paragraph. Building a tombstone table now is speculative machinery for an unfunded feature, adjacent to the ratified "hard delete stays" decision (`V3_PLAN.md:1053`). *No implementation sketch is given here on purpose* — sketching the rejected feature is how it gets built.

An independent verification pass could not construct a scenario where following this design makes later sync work harder, and found no additional cheap-now/irreversible-later item to add. Three items, necessary and sufficient.

### 9.3 Deferred, with the trap pre-recorded

**Restore-over-the-live-DB.** The serving process holds the DB open in WAL mode, so replacing the file leaves stale `-wal`/`-shm` sidecars from the *old* database beside the *new* one. Whoever builds it must: decrypt to a temp path → `PRAGMA integrity_check` the **candidate** and abort on anything but `ok` → take a pre-restore snapshot via the existing `backup_to` and abort if *that* fails → replace and unlink the sidecars → **print "restart the container,"** because the running server is still on the old inode. Gate it on the human-readable artifact name echoed back, not a boolean flag.

**And permanently: the SQLite file is never the synced object,** under any future variant.

---

## 10. Rejected alternatives

### 10.1 restic (and kopia)

Rejected — and **not on quality.** restic's crypto is well-reviewed, its format is published, and rustic-rs is a second interoperable implementation, so "opaque format lock-in" is a weak argument and should not be used. It loses on five concrete grounds: (1) its central feature is worth nothing at 8.25 MiB with retention already solved locally; (2) it does not reduce the dependency count — it has no native OneDrive/Dropbox/Drive backend and reaches them *through rclone*, so it is two binaries, not one; (3) **its credential is strictly worse than age's** — the repository password grants write *and* decrypts all history, whereas age recipient mode gives the container a write-only capability, which is the single strongest technical argument in this document; (4) killed-mid-upload leaves a stale exclusive lock that blocks the *next* backup until a human runs `restic unlock`, with open upstream issues where unlock reports success while the lock persists — precisely the silent-failure shape this feature exists to prevent, in a container that gets recreated routinely; (5) pack-blob storage forecloses §9, since no individual memory is addressable inside a repo.

**kopia is rejected harder:** rclone support self-described *experimental* with three providers tested, experimental CLI-only Google Drive, and a genuine second scheduler (quick hourly, full every 24h, blob deletion delayed across "several hours and/or multiple maintenance cycles") running inside a container whose lifecycle is governed by OC's own loop and by Portainer redeploys.

**restic is the correct upgrade path** if the dataset grows an order of magnitude or the requirement genuinely becomes "many versioned snapshots where storage cost matters." Revisit then, and choose it over kopia.

### 10.2 rclone `crypt` remote

Rejected despite costing **zero** Python, which makes it the most tempting option. Its key cannot rotate ("it is not possible to change the password/key of already encrypted content") — a permanent property, not a scale-dependent one. Its key is symmetric, lives in a file the container must keep writable for token refresh, and decrypts all history. It encrypts filenames by default, fighting a datestamped scheme and making hand-restore from a browser impossible. And it stores no hashes, so verification requires `cryptcheck`. Keep it documented as the fallback if `age` cannot be added to the image; if crypt is ever used, do **not** also age-encrypt, and always set `password2`.

### 10.3 A persistent staging mirror, and newest-only push

Both rejected — §3.2. The mirror was unearned machinery whose correctness rule no natural test catches; newest-only loses an artifact permanently on a single failed night. The 3-deep window with `--ignore-existing` is cheaper than the first and safer than the second.

### 10.4 apt-installing rclone

Rejected — Debian trixie ships 1.60.1 (2022), predating the Google client_id retirement and years of provider OAuth changes. A correctness issue, not version hygiene.

### 10.5 An MCP tool for cloud push

Rejected. No agent use case — backup cadence is an operator concern on a schedule. The risk class differs in kind from every existing tool: this is egress of the entire corpus to a third party, and V3_PLAN itself calls OC's data "sometimes secrets-adjacent." A `confirm: true` flag is documented project-wide as advisory against an autonomous agent because it self-confirms; the gate that actually works is that no tool exists. A 19th tool an agent should never call is also pure selection noise against the deliberate Q13 description-quality pass. Accepted tradeoff: an LLM agent cannot see cloud-backup health. The operator can.

### 10.6 Also rejected, one line each

A **sidecar container or host cron** (in-process is ratified at `V3_PLAN.md:559` because the job needs in-process state; it also gets scheduling, locking, `/api/v1/maintenance/status` and `oc maintenance run-once` for free — though notably a once-a-day single-file copy exercises few of those, so do not over-argue it; the sidecar remains the honest escape hatch if +88 MiB is judged unacceptable, at the cost of a second config store). A **boot-time "can I still decrypt" check** — a network call to a cloud provider under `restart: unless-stopped` turns a provider outage into a crash-loop. An **automated weekly decrypt-verify job** — for a static file, with no evidence of rot, and the drill covers it. A **`docs/design/README.md` index table** for a single row — add it at three ADRs.

---

## 11. Adjacent findings — flagged, not folded in

Each is real, each is outside this feature's diff, each needs its own yes/no.

1. **`load_jobs` replaces rather than merges** (`maintenance_loop.py:307`). Adding `cloud_backup` to `core.json.example` fixes today; the shape means the shipped example will silently drop *every future* job. Fix is either merge onto `_DEFAULT_JOBS`, or drop the `jobs` array from the example entirely.
2. **Lock storm on any long-held job.** The loop ticks at 1s and `_invoke` acquires `job._lock` *before* awaiting `_global_lock`, so a queued job holds its own lock while waiting; every subsequent tick logs a warning and increments `runs_skipped_overlap` — corrupting the exact field `status()` exposes to diagnose it. A 900s hold means ~900 spurious warnings per concurrently-due job. **Pre-existing** (any slow `db_vacuum` does this), not introduced here, but this feature can hit the 900s bound. Fix is to log the skip once per blocked interval. Note: verified that a skipped tick does **not** lose the run — `last_run_at` is not advanced on skip, so `_is_due` stays true and the job fires as soon as the lock frees.
3. **The git-onboard watermark ships in every export envelope and resurrects on merge.** `save_watermark` writes a fresh-uuid row with `source="git-onboard-watermark"`; `export_memory.py:53` calls `list_memory(limit=None)` with no source filter; `import_memory.py:91` inserts any absent id; `onboard_git_prepare` then elects a winner via `created_at DESC` — i.e. **by wall-clock write time across devices**, on a control value. A resurrected unreachable SHA causes a full re-walk and duplicate cluster memories across all history; a resurrected *ahead* SHA silently skips commits. The existing `_WATERMARK_HASH_RE` guard only catches *malformed* content. **Fix: filter `source == "git-onboard-watermark"` out of `export_memory.py` — ~2 lines, zero read-path impact,** justified independently of sync (a watermark is one device's git working state, not portable content). Verified clean: `git_onboard.py:754-755` means a restored DB with cluster memories and no watermark returns `status="exists"` and refuses to re-walk, so the degradation is a loud "needs `--force`," not a silent duplicate.
4. **`oc memory import --mode merge` is a union by id, not a merge.** It only ever `add_memory`s — there is no update branch — so an edit made on another device (content, tags, pin) is silently discarded, and a stale envelope resurrects memories deleted since. Cross-device restore is an explicit Goal of this design, which *manufactures the trigger*. Cheapest fix: stamp `exported_at` into the envelope and have import emit an **unconditional warning** plus a CLI help line ("merge resurrects anything deleted since the export"). **Do not compare against `max(created_at)`** — `git_onboard.py:687,695` sets cluster `created_at` to the *commit author date*, and future-dated commits are a documented real phenomenon in this repo, so one rebased commit would make every legitimate envelope read as stale forever. Compare `exported_at` against the destination's newest `updated_at`. Skip `--allow-stale` and the format bump; for two lifetime invocations the warning is enough.
5. **`set_pinned` does not bump `updated_at`** (`sqlite_store.py:406-414`), unlike `update_memory` at `:423`. V3_PLAN's Out of Scope table ratifies "`updated_at` is enough" in place of edit history; that ratification is currently false for pin state. Related: `projects` has no `updated_at` column at all, so project metadata edits carry zero version; and `update_memory` uses inline `datetime.now(UTC)` rather than the mandated `utc_now()`.
6. **`security_posture.md:103-105` doc drift.** It states the `oc config show` mask covers "any env var whose name contains KEY/SECRET/TOKEN/PASSWORD," but `system.py:72` *also* requires an `OC_` prefix. Someone will name a secret `RESTIC_PASSWORD` and believe it is masked. This feature does not depend on the predicate — it introduces no secret-bearing vars — but the doc is wrong.

---

## 12. Confidence register

Carry these into implementation. Do not let them quietly become assertions.

| Claim | Status | How to settle it |
|---|---|---|
| rclone works against a **Dropbox App folder** app (reports of "Path root is not supported for sandbox app") | **UNVERIFIED — now the first step of Phase 0** (§4.1 step 0). It no longer gates the *provider*, only the *scope* | 10 min, before any other bootstrap step: create the app with App folder access, `rclone authorize "dropbox"`, then `rclone lsd remote:` and copy a file. Fallback is Full Dropbox **on the same account** — a wider token, but the alternative (a fresh 2 GB account) cannot hold the backups at all. |
| The official `rclone/rclone` image binary runs on `python:3.14-slim` | **UNVERIFIED, mitigated** — the upstream release binary measures fully static and the image is built `CGO_ENABLED=0`, but the image binary was not executed on Debian | `RUN rclone version` makes it a build failure, not a runtime one. Keep that line. |
| trixie's `age` package satisfies the `age -r … -o …` invocation | **UNVERIFIED, mitigated** | `RUN age --version` in the same gate; the encrypt path is exercised in Phase 0 by hand before any code exists. |
| Dropbox refresh tokens never expire | **LIKELY** — stated by Dropbox Community staff; the OAuth guide itself is silent on refresh-token expiry | Only matters after a >90-day OC outage. Re-bootstrap is documented; accept. |
| Microsoft's exact refresh-token inactivity window | **LIKELY (~90 days)** — documented baseline, but Conditional Access / CAE can revoke earlier | Only relevant if OneDrive is chosen. Recovery is `rclone config reconnect remote:`. |
| An aborted upload leaves a *detectable* partial remote object | **UNVERIFIED, backend-dependent** — Dropbox commits upload sessions atomically (likely leaves nothing, which is fine); other backends differ | `--ignore-existing` means the daemon never repairs an existing object, so a partial would persist until the drill finds it. Sample an old artifact in the quarterly drill (§8). |

**Verified during this revision** — do not relitigate: rclone verifies transfer checksums by default and errors "corrupted on transfer" ([docs](https://rclone.org/docs/)), so dropping `--checksum` costs no integrity checking; `--ignore-existing` = "Skip all files that exist on destination", `--retries` default 3, `--contimeout` default `1m0s` ([flags](https://rclone.org/flags/)); `--` ends option parsing; rclone latest is **1.75.0**, 2026-07-31 ([releases](https://github.com/rclone/rclone/releases)); Debian trixie ships 1.60.1; Google's shared client_id "is being retired and will stop working during 2026" and "Testing" grants "expire after a week"; `drive.file` is non-sensitive so "Publish app" needs no verification; the liveness `/health` at `app.py:170` is a static handler independent of `build_health_payload`; the entrypoint is `set -eu`; and the overlap-skip branch does not advance `last_run_at`, so a skipped tick is deferred, not lost.

**Retired as moot:** restic append-only mode, rclone-vs-restic-vs-kopia CPU/RSS, crypt-via-`RCLONE_CONFIG_*` env vars, whether a personal Microsoft account can register an Entra app, the rclone image *digest* (tag pin instead), and whether local and remote share a computable hash (`--checksum` is gone).

---

## 13. Open questions for the operator

Only decisions that genuinely need a human.

1. ~~**Which provider?**~~ **RESOLVED 2026-08-23: Dropbox** (§4). The operator's
   OneDrive preference lost to a scope limitation rclone cannot work around, and the
   Dropbox account slated for retirement is kept alive as the backup target instead.
   Scope is App Folder if §4.1 step 0 verifies, Full Dropbox on the same account if
   not. No B2/S3/Nextcloud is available, which would otherwise have beaten all three.

2. **Encrypt at all?** The design says yes, on confidentiality against the provider and against anyone who obtains the cloud account (§7). The honest counter is availability: encryption adds a **new single point of failure** to a path that previously had none — today a lost NAS means restoring a plaintext `.db`; afterwards it means restoring a plaintext `.db` **and** having the key. For a thing whose whole job is to work when everything else has failed, that concession deserves real weight. If your answer is "I will not reliably escrow a key," the correct decision is to ship unencrypted to a **narrowly-scoped** Dropbox App Folder or Google `drive.file` remote and drop `age` entirely — a smaller, simpler feature that also deletes ~7 MiB from the image, `OC_CLOUD_AGE_RECIPIENTS`, the recipients guard and its test, half of Phase 0, and question 3 below. Decide with eyes open; do not half-do it.

3. **One recipient or two?** Two (`age1primary,age1recovery`) costs one comma and is **impossible to add retroactively** for artifacts already written. Related: where does the identity actually live — password manager plus a printed offline copy is the usual answer, and it must not be on the NAS.

4. **Push the JSON export envelope alongside the `.db`?** The design says no in Phase 1 — the `.db` is already produced, already retained, already pruned, and is the fast restore path; the envelope is regenerable from any restored `.db` (§9.1), and adding it means a second file family with a second retention rule. Several reviewers leaned "push both, it's a few hundred KB." Cheap, reversible, genuinely yours.

5. **Fix the `oc memory import --mode merge` hazard (§11.4) and the watermark leak (§11.3) now, or park them?** Neither blocks Phase 1 — cloud backup is push-only and nothing here performs a merge. But **cross-device restore is an explicit Goal of this design**, and the first restore-and-merge is the trigger condition. So this is not "operator's call, adjacent scope" — it is "must be fixed before the first cross-device merge is attempted." The watermark filter is ~2 lines and independently correct.

6. ~~**Is egress metered on your plan?**~~ **Moot for the chosen target.** Dropbox
   consumer plans do not meter egress; the per-drill transfer is ~9 MiB regardless.
   The question survives only if the provider ever changes.

7. **How much of that account's existing 6.75 GB do you want to keep?** Not a design
   question — but you had planned to retire this account, and clearing what you no
   longer want pushes the prune trigger (§8) further out at zero engineering cost.
   Purely yours; the design works either way.

---

---

*Method: seven parallel research strands (rclone mechanics · restic/kopia vs
plain-copy · per-provider OAuth policy · this codebase's seam · sync-door
analysis · ops/failure semantics · encryption and key custody) → synthesis →
three adversarial critiques (ops red-team · an over-engineering critic armed
with this project's own no-over-engineering rule · a verifier attacking the
sync-door claim) → revision. Provider and tool claims were checked against
current vendor docs where possible; anything that could not be settled is in
the §12 confidence register rather than asserted. No code was written.*

*This establishes `docs/design/` as the ADR home — the directory existed but
was empty. Numbered, `NNNN-topic.md`. Add an index README at three entries.*
