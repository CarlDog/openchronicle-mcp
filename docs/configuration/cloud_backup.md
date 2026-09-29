# Offsite cloud backup

The nightly `cloud_backup` maintenance job encrypts the newest published
snapshots with [age](https://age-encryption.org) and copies them to a cloud
remote with [rclone](https://rclone.org). The design and its reviews are in
[design 0001](../design/0001-cloud-backup.md); this page is the operator
runbook. On the NAS the remote is a Dropbox App folder (`ocdrop`), and the
two age recipients are the ones escrowed in cloud-backup Phase 0.

## What it does, nightly

1. It selects the 3 newest published snapshots in `OC_BACKUP_DIR/auto`
   (on the NAS, `/exports/backups/auto`), plus the newest one from each of the
   3 most recent UTC days. "Published" means the `.db` has its `.json`
   manifest. Quarantined `*.failed-*` files, `manual/` and the frozen pre-v3.5.0
   `/data/backups/auto` are never pushed.
2. It re-checks each selected snapshot against its manifest, and refuses to
   push one that no longer matches.
3. It encrypts each `.db` and its `.json` to **both** recipients into a
   private (0700) `cloud-push-*` directory under the backup root.
4. It runs `rclone copy --ignore-existing` to the remote. That is append-only:
   the job never deletes and never overwrites, and only new names upload.
5. It logs each pushed snapshot's SHA-256 at INFO.

The job **fails** rather than report a hollow success when:

- the configuration is invalid;
- it is running as root;
- `rclone.conf` is missing;
- no published snapshot exists;
- the newest snapshot is more than 26 hours old;
- a snapshot is stamped in the future;
- verification, age or rclone fails.

The whole run is bounded at 900 s.

## Health

`GET /api/v1/health` and the MCP `health` tool carry `cloud_backup_status`:

| `status` | Meaning | Action |
|---|---|---|
| `disabled` | `OC_CLOUD_REMOTE` is empty | none |
| `ok` | a push succeeded within the last 48 hours | none |
| `stale` | enabled, and no success within 48 hours (or ever) | read `/api/v1/maintenance/status` → `cloud_backup.last_error` |
| `misconfigured` | the remote or recipients are invalid (takes precedence) | fix the stack env values |

48 hours is two failed nights. The day-based window means a snapshot is only
lost offsite after about three consecutive failures, so `stale` fires before
anything is lost. `cloud_backup_status` never touches `maintenance_degraded`
(a corrupt database) or `backup_last_run_failed` (the local backup).

The rclone exit code in `last_error` decodes as:

- `0`: success;
- `5`: temporary, and the next night retries;
- `6`: non-retryable minor;
- `7`: fatal, meaning the account is suspended or the token revoked, which
  never self-heals;
- `1` to `4`: configuration or wiring errors.

## Enabling it (first time, or on a new NAS)

Order matters. A new job runs on its first tick after boot, and if that run
fails the next attempt is 24 hours later.

1. **Build a minimal `rclone.conf` holding only the `[ocdrop]` section** from
   the desktop's rclone config, not the whole file, which may hold other
   remotes' credentials. Keep the re-install copy in the password manager.
2. **Install it into the named `/config` volume as uid 1000, with no copy
   left on the NAS host.** From the desktop, pipe it over SSH:

   ```bash
   ssh <nas> "sudo docker exec -i --user 1000:1000 openchronicle-mcp sh -c 'umask 077; cat > /config/rclone.conf'" < ocdrop-rclone.conf
   ```

   Or paste it in the Portainer console with **User** set to `oc`. A restart
   also runs the entrypoint's `chown` and `chmod 600` on it.
3. **Deploy the release that carries the job, in one step:** the compose file
   (its three `OC_CLOUD_*` and `RCLONE_CONFIG` lines), then `OC_TAG` together with
   `OC_CLOUD_REMOTE=ocdrop:openchronicle/nas` and
   `OC_CLOUD_AGE_RECIPIENTS=<primary>,<recipient>`.
4. **Verify:**
   - `health.build_revision` is the expected commit;
   - after the boot-time run, `cloud_backup_status.status` is `ok`;
   - `/api/v1/maintenance/status` shows `cloud_backup` with `last_outcome: ok`;
   - the log line `cloud_backup: age recipients ...` matches the escrowed
     public keys. A valid but wrong key encrypts without complaint and cannot
     be decrypted.

## Manual runs: always as uid 1000

The image has no `USER`, so the Portainer console and `docker exec` default
to root. A root run would refresh the Dropbox token and rewrite `rclone.conf`
as root, locking the nightly job out. The job therefore refuses to run as root.
Use:

```bash
sudo docker exec --user 1000:1000 openchronicle-mcp oc maintenance run-once cloud_backup
```

(or the Portainer console with **User** `oc`). A manual run bypasses the
maintenance loop, so it neither advances `cloud_backup_status` nor clears
`stale`: the next scheduled run does. With `OC_CLOUD_REMOTE` unset it prints
`SKIPPED: cloud_backup did nothing (OC_CLOUD_REMOTE is unset)`.

A log line `cloud_backup: rclone reported errors: ...` after a successful
push usually means rclone could not save a refreshed token to `rclone.conf`.
The upload landed. Check that `/config` and the file are owned by `oc`; a
restart re-runs the entrypoint's `chown`.

## Restoring from the cloud (the NAS is gone)

1. On any machine with rclone and age, copy down the newest
   `openchronicle-<stamp>-<hex>.db.age` and its `.json.age` from
   `ocdrop:openchronicle/nas`.
2. Decrypt both with the **escrowed** primary identity (or the printed
   recovery identity): `age -d -i <identity> -o <name>.db <name>.db.age`, and
   the same for the manifest.
3. Check `sha256(<name>.db)` equals the manifest's `sha256`, then run the
   integrity and row checks in [local_backup_restore.md](local_backup_restore.md).
4. **Authenticity caveat.** age recipient mode gives confidentiality, not
   authenticity. Anyone holding the public keys and write access to the
   Dropbox folder could plant a well-formed artifact whose manifest matches it.
   Before trusting the newest artifact, compare its SHA-256 with an
   off-cloud record where one exists: the `cloud_backup: offsite ... sha256=`
   log lines, or an earlier verified copy. If they disagree, prefer an older
   artifact that matches.

## The token and what it can do

- The only secret on the NAS is the Dropbox refresh token in
  `/config/rclone.conf`. It is not encrypted; treat it as a password.
- Its App-folder scope confines it to `Apps/<app>/`, but inside that folder
  it can **delete and overwrite** as well as write. "Never deletes" describes
  the job, not the credential. A compromised NAS or desktop could wipe the
  offsite copy. Dropbox keeps deleted files for 30 days, which is the backstop.
- The desktop and the NAS share one token. Revoking the app in Dropbox's App
  Console stops both, so re-issue it (`rclone config reconnect ocdrop:`) and
  reinstall.

## Maintenance

- **Bump rclone** (`COPY --from=rclone/rclone:<tag>` in the Dockerfile) at the
  phase-end audit. Dependabot does not track `COPY --from` images, and a stale
  rclone falls behind provider OAuth changes.
- Remote growth is about 10 MB a night, append-only. Prune by hand only if the
  Dropbox quota ever runs short (design 0001 §8).
