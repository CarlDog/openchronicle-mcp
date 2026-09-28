# 0020 — Persistent storage review (DATA-01)

**Status:** Review, 2026-09-28. **Recommendations adopted by the operator the
same day; step A done.** The inventory was read-only. The operator then
adopted decisions 1-4 as recommended and had step A applied (see
[Step A result](#step-a-result-2026-09-28)). Step B still runs as its own
reviewed step with OPS-03, and decisions 5 and 6 wait on the operator-run
checks. Roadmap item: [DATA-01](../ROADMAP.md).

## Why this review

On 2026-09-24 the operator feared that each release had wiped the
database. That premise was checked and is false: the production database has
persisted since the 2026-05-06 cutover, and it survived the 2026-09-25
recreate. The review still matters, because the layout that kept the data safe
does so by convention, not by construction, and several parts of it are
leftovers or quietly broken.

## Method and limits

Evidence gathered read-only on 2026-09-28:

- stack 151's stored compose and environment (`portainer_get_stack`);
- the running container, its logs and every OpenChronicle volume
  (`portainer_list_containers`, `portainer_container_logs`,
  `portainer_list_volumes`);
- the host share `/volume1/docker/openchronicle`, through the filesystem MCP
  (the `/docker` root);
- `mcp__openchronicle__health`;
- the image's entrypoint, the Dockerfile, and the v3.3.0 and `main` sources.

The filesystem MCP cannot see `/volume1/@docker/volumes`, and it reports POSIX
modes, not Synology ACLs. Claims that depend on those are marked **unverified**
and have an operator-run check in [Confirm before cutover](#confirm-before-cutover).

## What production looks like today

Stack 151 (`openchronicle-mcp`, detached from Git, stored compose file
version 142), container `openchronicle-mcp-oc-1`, image `v3.3.0` build
`7349f94`, up since 2026-09-25, `network_mode: bridge`.

| Container path | Backing store | Contents | Status |
| --- | --- | --- | --- |
| `/data` | Named volume `openchronicle-mcp_oc-data`, created 2026-04-29 | `openchronicle.db` (9.9 MB, 1,091 memories on 2026-09-28), WAL sidecars, maintenance state, `backups/auto/` | Live and healthy |
| `/config` | Bind mount `/volume1/docker/openchronicle/config`, mode 0777 | `.bootstrapped` and nine `models/*.json` files, all dated 2026-05-02 | **Nothing v3 reads** (S2) |
| `/output` | Named volume `openchronicle-mcp_oc-output`, created 2026-04-29 | Believed empty (**unverified**) | **No writer** (S3) |
| `/app/output/logs/...` | The container's writable layer | Nothing: the file was never created | **Log mirror broken** (S3) |

The host share also holds `assets/`, `output/` and `plugins/`, all empty and
dated 2026-05-02.

## Findings

### S1 — The data volume's identity rests on the stack name (high)

Compose names the volume `<project>_oc-data`, and the project is the stack
name. Deploy the same compose under any other project name (a renamed stack, a
new stack created to replace a broken one, a `docker compose up` from a
directory with a different name) and Compose silently creates a new, empty
`<other>_oc-data`. OpenChronicle then starts cleanly on an empty database. That
is exactly what "the release wiped my data" would look like, and it is also the
shape of the 2026-05-06 cutover incident, when live v3 restarted against an
empty volume.

Nothing in the stack prevents this today. It has not happened since May only
because the stack has never been renamed or recreated under another name.

### S2 — `/config` is a dead, world-writable bind mount (medium)

- There is no `core.json`. The only files are `.bootstrapped` and nine v2
  model definitions (Anthropic, Gemini, Groq, Ollama, OpenAI, xAI), seeded by
  the **v2** image on 2026-05-02, before the v3 cutover.
- v3 reads only `core.json` (`config_loader.py`). It never reads `models/`.
  Production runs on environment configuration alone.
- The v2 `.bootstrapped` marker stops the v3 entrypoint from seeding its own
  `core.json.example`.
- The directory is mode 0777 on an SMB-visible share, and the entrypoint runs
  `chown -R oc:oc` over it on every start (its ctime, 2026-09-25T04:57Z,
  matches the last container start). A `core.json` dropped there by any
  principal that can write the share would be loaded on the next start, and it
  would configure anything the stack's environment leaves unset (maintenance
  jobs, rate limits, search settings).

### S3 — The log mirror has never worked, and `oc-output` has no writer (medium)

- The stored compose defaults `OC_LOG_FILE` to `/app/output/logs/...`. That
  path is in the container's writable layer, not on a volume, and it is
  root-owned, so the unprivileged `oc` process cannot create the file. Nothing
  sets a different value in the stack environment. This repeats the 2026-09-23
  finding: the file mirror, which exists so a redeploy does not erase the
  previous release's logs, has never produced a file in production.
- In v3, `OC_OUTPUT_DIR` is only created (`init_runtime`) and reported
  (`oc system`). The one intended writer is the log mirror above. So the
  `oc-output` volume is almost certainly empty.
- `main` already fixes the default (`/output/logs/openchronicle.log`, rev 210).
  Production can get the fix without a release: `/output` is chowned to `oc`
  by the v3.3.0 entrypoint too, so setting `OC_LOG_FILE` in the stack
  environment works on the running image.

### S4 — Automatic backups share the database's failure domain (medium)

`db_backup` writes to `/data/backups/auto/`, on the same `oc-data` volume as
the live database. Retention keeps the 7 newest files plus the newest file from
each of the last 7 days, so at most 14 files (about 140 MB at today's size).
Backups run nightly at about 23:39 UTC. The weekly vacuum takes its own
backup first, so on 2026-09-27 two backups were written 23 seconds apart; that
is the documented shape, not a fault.

Deleting or pruning the volume, or losing it to the S1 failure mode, loses
the database and every automatic backup at once. The backups are also
invisible from the desktop. Design 0017's `/exports/backups` bind (merged to
`main`, unreleased) moves them onto a host path. That is a different failure
domain from a Docker volume, but it is still the same NAS.

### S5 — The share has no deliberate access control (medium; partly unverified)

`/volume1/docker/openchronicle` and `config/` are mode 0777. Earlier
inspection recorded that the `docker` share grants `Everyone` read at the
Synology ACL layer; this review cannot re-read that layer (**unverified**). The
directory will soon hold database snapshots (`exports/backups`), and every
snapshot is a full copy of the memory store. It needs an owner and a mode
chosen on purpose before it holds them.

### S6 — The `main` compose cannot be deployed as it stands (high, for the cutover)

The `main` compose binds `/volume1/docker/openchronicle/exports` with
`create_host_path: false`, and that directory does not exist (the share has
only `assets`, `config`, `output` and `plugins`; the bootstrap copy directory
from 2026-09-24 was cleaned up). Deploying it today fails at container
creation. That is the intended behavior, a loud failure instead of a silently
created root-owned directory, but the cutover must create the directory first.

The same compose also replaces `network_mode: bridge` with a dedicated
`oc-observability` network, against the fleet's address-pool rule. That
belongs to OPS-03, not this review; it is listed because the cutover applies a
compose file and must not carry it along unreviewed.

### S7 — Twenty orphaned test volumes; the assessment's claim about stack 216 is stale (low)

All twenty are dangling (no container references them), and none of their
stacks still exists:

| Compose project | Created | Volumes |
| --- | --- | --- |
| `openchronicle-metrics-test` | 2026-09-04 | config, data, output, prometheus |
| `openchronicle-phase4d-obs-20260905` | 2026-09-05 | config, data, output, prometheus |
| `openchronicle-phase4d-obs-20260905b` | 2026-09-05 | config, data, output, prometheus |
| `openchronicle-phase4d-obs-20260905c` | 2026-09-05 | config, data, output, prometheus |
| `openchronicle-phase4d-obs-20260905c2` | 2026-09-05 | config, data, output, prometheus |

The Phase 4D report names stack 216 as project
`openchronicle-phase4d-obs-20260905c2`. So the "preserved Prometheus history"
is the volume `openchronicle-phase4d-obs-20260905c2_oc-phase4d-prometheus`.
The assessment and the Current Sprint still say stack 216 "is stopped with its
history volume preserved"; the stack is gone and only the volume remains. The
sanitized report and summary are retained outside the repository, in the main
checkout's git-ignored `data/performance/phase4-20260904/phase4d-20260905/`.

### S8 — Everything is on one NAS (high; already tracked)

The live database, its automatic backups and (after 0017) its exposed
snapshots all sit on `volume1` of one NAS. The only other copy is the
2026-09-24 off-NAS file on the desktop, which ages every day. This is DATA-02
and OPS-08 (encrypted cloud backup); this review does not duplicate them, but
the target layout below is shaped so they can plug in.

### Not a finding

- **"`db_integrity_check` skipped: previous run still in progress" on
  2026-09-27.** The check ran: the vacuum and the integrity check fell due on
  the same tick, the integrity check logged `running`, and the next tick saw
  its own job lock held and logged the warning. `db_backup` took the global
  lock 22 seconds later, no failure was logged, and health reports
  `maintenance_degraded: false`. The warning's wording is misleading, because
  an in-flight run reads as a stale one. That is a log-wording nit, noted for
  QUAL, not a storage problem.
- **The database has not been lost since 2026-05-06.** Confirmed again: the
  volume dates from 2026-04-29, and the memory count only grows.

## Target layout (proposal)

| Container path | Target backing store | Change |
| --- | --- | --- |
| `/data` | The **existing** volume `openchronicle-mcp_oc-data`, declared `external: true` with that explicit `name:` | No data moves. Compose can no longer create an empty substitute: if the volume is missing, the deploy fails (S1) |
| `/exports` | Host bind `/volume1/docker/openchronicle/exports`, `create_host_path: false`, with `exports/backups` owned by uid 1000 (`oc`), mode 0750 | Catalog and automatic backups move off the data volume (S4); the directory exists before the compose is applied (S6) |
| `/config` | A named volume, `openchronicle-mcp_oc-config`, with an explicit `name:`, **not** SMB-visible | Stop binding the dead host directory (S2). The v3 entrypoint seeds only `core.json.example`, which the loader ignores, so behavior is unchanged. A future `core.json` is edited through the Portainer console |
| `/output` | The existing `openchronicle-mcp_oc-output`, with an explicit `name:` | `OC_LOG_FILE=/output/logs/openchronicle.log` makes it the log mirror's home (S3) |
| Host share | `assets/`, `output/`, `plugins/` and `config/` removed after the cutover is verified; the share root tightened from 0777 | S2, S5 |

Also, from the operator's standing instruction:
`container_name: openchronicle-mcp`.

The local `docker-compose.yml` keeps implicit volumes. `external: true` suits
the NAS stack, where the volume already exists; it would make a fresh local
`docker compose up` fail.

### What the layout does not solve

It does not answer "one NAS". Off-NAS copies stay DATA-02 and OPS-08, which
read from `/exports`. A DSM-level backup job (Hyper Backup or Snapshot
Replication) covering `/volume1/docker/openchronicle` and
`/volume1/@docker/volumes/openchronicle-mcp_*` would narrow the gap in the
meantime. Whether one exists is an open question for the operator.

## Cutover plan (proposal)

It runs in two steps, because one of them can happen now and the other
needs OPS-03.

### Step A — environment only, available now on v3.3.0

1. `portainer_set_stack_env`: set `OC_LOG_FILE=/output/logs/openchronicle.log`.
   Redeploy.
2. Verify: `health.build_revision` is unchanged (`7349f94`), `total_memories`
   has not dropped, and `/output/logs/openchronicle.log` exists and grows.

Rollback: remove the variable and redeploy. No data is touched.

#### Step A result, 2026-09-28

Applied at 15:58Z with `portainer_set_stack_env` (no image pull). The
container was recreated at 15:58:56Z. Checked afterwards:

- the container environment has `OC_LOG_FILE=/output/logs/openchronicle.log`;
- `build_revision` is still `7349f94`, and `total_memories` is 1,091 before
  and after;
- the mounts are unchanged (`oc-data`, `oc-output`, the `config` bind);
- the stored compose is still file version 142, and the stack's access
  control is unchanged;
- the startup log has no `not usable` warning and no logging-error
  traceback, so the file handler attached and has been writing.

The operator then confirmed the file over SSH: `logs/openchronicle.log`
exists, is owned `1000:1000`, and was 11,914 bytes and growing at 16:31Z.

### Step B — with OPS-03's compose reconciliation

The repository side landed on 2026-09-28: `docker-compose.nas.yml` now
carries the target layout, and `tests/test_nas_compose_shape.py` pins it.
The steps below are the deploy.

Revised 2026-09-28 after the OPS-03 pre-deploy review. Portainer has no
"restore version" call, and `portainer_update_stack_file` cannot change the
stack env, so the change is two ordered redeploys. A local rehearsal showed
both intermediate states are valid.

1. Save stack 151's current `StackFileContent` (file version 142) verbatim to
   a local file. Rollback re-sends that text; nothing else restores it.
2. Take and verify a fresh off-NAS copy of the database, following the
   runbook's bootstrap procedure. The 2026-09-24 copy is too old to be the
   rollback point.
3. On the NAS, over SSH, create the bind source, then confirm it:
   `sudo install -d -o 1000 -g 1000 -m 0750 /volume1/docker/openchronicle/exports /volume1/docker/openchronicle/exports/backups`
   and `ls -ldn /volume1/docker/openchronicle/exports/backups`.
4. Apply the repository compose with `portainer_update_stack_file`, with
   `HOST_CONFIG_DIR` still set. Only the container name, the `/exports` bind,
   three variables v3.3.0 does not read, and the dropped Watchtower label
   change; `/config` is untouched. Compose replaces the old container by its
   labels, and if the bind source were missing, the old container would keep
   running. Verify with `portainer_get_container`: name `openchronicle-mcp`,
   `/data` from `openchronicle-mcp_oc-data`, `/exports` present, healthy.
5. Remove `HOST_CONFIG_DIR` with `portainer_set_stack_env`. `/config` becomes
   the new `openchronicle-mcp_oc-config` volume, seeded with
   `core.json.example` only, which v3.3.0 does not load.
6. Verify:
   - `health.build_revision` is still `7349f94`;
   - `total_memories` is at least the pre-change count;
   - `db_path` is `/data/openchronicle.db`;
   - the log file at `/output/logs/openchronicle.log` keeps growing;
   - the mounts are the three named volumes plus the `/exports` bind.
   Nightly backups still land in `/data/backups/auto`: v3.3.0 does not read
   `OC_BACKUP_DIR`. They move to `/exports/backups` with the release that
   carries 0017 (OPS-04).
7. After a week of green nights: remove the dead host directories
   (`assets`, `output`, `plugins`, `config`). The orphaned volumes were
   already pruned on 2026-09-28.

#### Step B result, 2026-09-28

Done, operator-approved at each step:

- **Saved first:** the version 142 file, checked against git: it is
  `682c68f0~1`'s compose plus the two Watchtower label lines.
- **Fresh off-NAS copy:** `pre-change-20260928T181210Z.db`, SHA-256
  `d0ec3407…b66f3` on the share and on the workstation. `integrity_check`
  `ok`, schema 4, 1,094 memories (equal to live), 39 projects. The plaintext
  copy on the share was deleted afterwards.
- **`exports` and `exports/backups`:** owner `1000:100`, mode 0750, Linux
  mode (no Synology ACL).
- **`portainer_update_stack_file` (18:18Z):** file version 143, byte-identical
  to `main` at `5a207070`. One container, `openchronicle-mcp`, replaced
  `openchronicle-mcp-oc-1` with no orphan. `/data` stayed
  `openchronicle-mcp_oc-data`, `/exports` was bound, and the startup log was
  clean. Healthy, build `7349f94`, 1,094 memories.
- **`HOST_CONFIG_DIR` removed (18:23Z):** `/config` is now
  `openchronicle-mcp_oc-config`, seeded on first run. The same build and
  count, and a clean startup.
- **Stack access control** (administrators only) is unchanged.
- **Still to do** (step 7): after a week of green nights, remove
  `/volume1/docker/openchronicle/{assets,output,plugins,config}`.

Rollback runs the same steps in reverse: set `HOST_CONFIG_DIR` back, then
re-send the saved version 142 text with `portainer_update_stack_file`. The
image and the data volume never change, so writes made after the deploy
survive. The new `openchronicle-mcp_oc-config` volume is left behind,
harmless. Design 0017's `stage`/`activate`/`rollback` helper restores
database files, not volumes; it applies only if the database itself has to
be replaced.

## Confirm before cutover

Operator-run on the NAS, all read-only:

```bash
sudo synoacltool -get /volume1/docker
sudo synoacltool -get /volume1/docker/openchronicle
sudo du -sh /volume1/@docker/volumes/openchronicle-mcp_oc-data/_data /volume1/@docker/volumes/openchronicle-mcp_oc-output/_data
sudo ls -la /volume1/@docker/volumes/openchronicle-mcp_oc-data/_data/backups/auto/
sudo find /volume1/@docker/volumes/openchronicle-mcp_oc-output/_data | head -20
sudo find /volume1/docker /volume1/@docker/volumes -xdev \( -iname '*pre-migration*' -o -iname '*premigration*' -o -iname '*v2*backup*' \) 2>/dev/null | head
```

The last line looks for the v2 pre-migration backup that DATA-05 wants to
delete; this review did not find where it lives. If it finds nothing, the
backup may be on the laptop instead (the cutover triage recorded a laptop
pre-cutover copy).

## Operator decisions

Decisions 1-4 were adopted as recommended on 2026-09-28 ("go with your
recommendations, do step A now").

1. **`/config`:** a named volume. **Adopted.** (The alternative was to keep
   the host bind and clean out its v2 contents.)
2. **Volume pinning:** `external: true` with an explicit name. **Adopted.**
   (An explicit `name:` alone would still let Compose create an empty volume
   if it went missing.)
3. **Step A now:** **Adopted and done**; see the step A result above.
4. **Orphaned volumes:** prune all 20. **Adopted and done** on 2026-09-28,
   ahead of step B at the operator's request. Each was deleted by exact name
   with a tool that refuses any volume still attached. Afterwards only
   `openchronicle-mcp_oc-data` and `openchronicle-mcp_oc-output` remain, and
   production health was unchanged. The Phase 4D Prometheus history is gone;
   its sanitized report and summary remain outside the repository.
5. **Share access:** owner, group and mode for `/volume1/docker/openchronicle`
   and `exports/`, after the ACL check.
6. **DSM-level backup:** does one cover these paths today, and should one?
   **Answered 2026-09-28: none does.** No Hyper Backup or Snapshot
   Replication task covers the `docker` share or `/volume1/@docker`.
   Recommendation: do not file-copy the live volume, which is not a shared
   folder and cannot be snapshotted. After step B, optionally snapshot the
   `docker` share to protect `exports/backups` against deletion. Loss of the
   NAS itself is answered only by off-NAS copies: DATA-02 (Phase 0 done the
   same day) and OPS-08.
