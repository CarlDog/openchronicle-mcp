"""DPAPI-encrypted env vault for the provider sweep (Windows only).

Keeps provider API keys OUT of chat transcripts, shell history, and
application logs: the operator fills the gitignored ``.env`` by hand,
``encrypt`` turns it into ``.env.dpapi`` (Windows DPAPI, CurrentUser
scope — ciphertext is bound to this machine + this Windows account and
undecryptable anywhere else) and shreds the plaintext. Consumers call
``load_vault()`` which decrypts straight into ``os.environ`` and never
prints a value.

Commands:
    python scripts/env_vault.py encrypt   # .env -> .env.dpapi, shred .env
    python scripts/env_vault.py status    # key NAMES present (never values)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAIN_PATH = ROOT / ".env"
VAULT_PATH = ROOT / ".env.dpapi"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _DataBlob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _crypt(data: bytes, *, protect: bool) -> bytes:
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    inp, out = _blob(data), _DataBlob()
    # CRYPTPROTECT_UI_FORBIDDEN (0x1): never pop a UI; fail instead.
    if not fn(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out)):
        op = "protect" if protect else "unprotect"
        raise OSError(f"DPAPI {op} failed — wrong machine/user, or corrupt vault")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _parse_env(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip("'\"")
        if name and value:
            entries[name] = value
    return entries


def encrypt() -> None:
    if not PLAIN_PATH.exists():
        raise SystemExit(f"{PLAIN_PATH} not found — nothing to encrypt")
    text = PLAIN_PATH.read_text(encoding="utf-8")
    new_entries = _parse_env(text)
    if not new_entries:
        raise SystemExit("no non-empty entries in .env — fill in values first")
    # MERGE with the existing vault: adding one key must not drop the
    # rest. New values win over stored ones for the same name.
    entries: dict[str, str] = {}
    if VAULT_PATH.exists():
        entries = _parse_env(_crypt(VAULT_PATH.read_bytes(), protect=False).decode("utf-8"))
    entries.update(new_entries)
    serialized = "\n".join(f"{k}={v}" for k, v in entries.items()).encode("utf-8")
    VAULT_PATH.write_bytes(_crypt(serialized, protect=True))
    # Shred the plaintext: overwrite with zeros before unlinking so the
    # values don't linger in the file's old blocks any more than the
    # filesystem forces.
    size = PLAIN_PATH.stat().st_size
    with PLAIN_PATH.open("r+b") as fh:
        fh.write(b"\0" * size)
        fh.flush()
        os.fsync(fh.fileno())
    PLAIN_PATH.unlink()
    print(f"vault written: {VAULT_PATH.name} ({len(entries)} keys) — plaintext .env shredded")
    print("keys:", ", ".join(entries))


def load_vault(*, required: bool = False) -> list[str]:
    """Decrypt the vault into os.environ. Returns the key NAMES loaded.

    Existing environment values win — the vault fills gaps, it doesn't
    override an explicitly-set shell variable.
    """
    if not VAULT_PATH.exists():
        if required:
            raise SystemExit(f"{VAULT_PATH} not found — run: python scripts/env_vault.py encrypt")
        return []
    entries = _parse_env(_crypt(VAULT_PATH.read_bytes(), protect=False).decode("utf-8"))
    loaded = []
    for name, value in entries.items():
        if not os.environ.get(name):
            os.environ[name] = value
            loaded.append(name)
    return loaded


def status() -> None:
    if not VAULT_PATH.exists():
        print("no vault (.env.dpapi missing)")
        return
    entries = _parse_env(_crypt(VAULT_PATH.read_bytes(), protect=False).decode("utf-8"))
    print(f"vault OK ({len(entries)} keys): " + ", ".join(entries))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "encrypt":
        encrypt()
    elif cmd == "status":
        status()
    else:
        raise SystemExit(__doc__)
