#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Apply storytelling plugin scaffold (safe in-memory adapters)")
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = ap.parse_args()

    ROOT = Path(args.repo_root).resolve()
    src = Path(__file__).resolve().parent / "templates" / "storytelling_plugin"
    dst = ROOT / "src" / "openchronicle" / "plugins" / "storytelling"
    print(f"[PLAN] copy {src} -> {dst}")
    if args.dry_run:
        return
    if dst.exists():
        print("[INFO] destination exists; copying files without removing existing")
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            # Don't clobber existing files; write only missing
            continue
        out.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[WRITE] {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
