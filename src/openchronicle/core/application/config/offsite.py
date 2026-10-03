"""Cloud backup configuration, validated in one place (design 0001 §5, A5).

The maintenance job and the health payload read the same two variables and
must agree on whether the feature is off, working or misconfigured, so both
call :func:`read_cloud_backup_config`. It never raises: the job turns a
problem into a failed run, and health turns it into ``misconfigured``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

# A security control, not tidiness: `name:path` only. It rejects an rclone
# connection string (":s3,access_key_id=...,secret_access_key=...:bucket"),
# which would put a live credential in a plain Portainer variable, as well as
# a leading "-", spaces, quotes and shell metacharacters. Do not loosen it.
_REMOTE_RE = re.compile(r"^[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]*$")


@dataclass(frozen=True)
class CloudBackupConfig:
    """What `OC_CLOUD_REMOTE` and `OC_CLOUD_AGE_RECIPIENTS` say."""

    enabled: bool
    remote: str
    recipients: tuple[str, ...]
    problem: str | None


def read_cloud_backup_config() -> CloudBackupConfig:
    """Read and validate the cloud backup settings; never raises.

    An empty `OC_CLOUD_REMOTE` disables the feature. A malformed remote, or a
    remote with no recipients, is a problem, never a silent disable: the
    operator must be able to tell "left off" from "broken".
    """
    remote = os.getenv("OC_CLOUD_REMOTE", "").strip()
    recipients = tuple(part.strip() for part in os.getenv("OC_CLOUD_AGE_RECIPIENTS", "").split(",") if part.strip())
    if not remote:
        return CloudBackupConfig(enabled=False, remote="", recipients=recipients, problem=None)
    if remote.startswith("-") or not _REMOTE_RE.fullmatch(remote):
        return CloudBackupConfig(
            enabled=True,
            remote="",
            recipients=recipients,
            problem="OC_CLOUD_REMOTE must be an rclone remote in name:path form, e.g. ocdrop:openchronicle/nas",
        )
    if not recipients:
        return CloudBackupConfig(
            enabled=True,
            remote=remote,
            recipients=(),
            problem="OC_CLOUD_AGE_RECIPIENTS is empty while OC_CLOUD_REMOTE is set; refusing to push unencrypted",
        )
    return CloudBackupConfig(enabled=True, remote=remote, recipients=recipients, problem=None)
