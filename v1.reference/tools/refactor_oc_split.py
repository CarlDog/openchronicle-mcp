#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import sys
from pathlib import Path


ALLOWED_SHIMS = {
    "domain/services/narrative/__init__.py",
    "domain/services/scenes/__init__.py",
    "domain/services/timeline/__init__.py",
    "domain/services/characters/__init__.py",
    "domain/services/story_loader.py",
}

DEFAULT_STORY_TERMS = ["story", "scene", "character", "timeline", "lore", "narrative"]


def rel(base: Path, p: Path) -> str:
    return str(p.relative_to(base)).replace("\\", "/")


def grep(base: Path, pattern: str, roots):
    pat = re.compile(pattern, re.M)
    hits = []
    for root in roots:
        d = base / root
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if pat.search(t):
                hits.append(rel(base, f))
    return sorted(set(hits))


def discover_moves(SRC: Path, story_terms):
    infra_root = SRC / "infrastructure"
    if not infra_root.exists():
        return []
    pat = re.compile(r"\b(" + "|".join(map(re.escape, story_terms)) + r")\b", re.I | re.M)
    moves = []
    for f in infra_root.rglob("*.py"):
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if pat.search(t):
            sub = f.relative_to(infra_root)  # e.g., content/analysis/x.py
            dst = SRC / "plugins" / "storytelling" / "infrastructure" / sub
            moves.append({"from": rel(SRC, f), "to": rel(SRC, dst)})
    return moves


def build_import_map(moves):
    mapping = {}
    for m in moves:
        src_mod = m["from"].replace("/", ".")
        dst_mod = m["to"].replace("/", ".")
        if src_mod.endswith(".py"):
            src_mod = src_mod[:-3]
        if dst_mod.endswith(".py"):
            dst_mod = dst_mod[:-3]
        if ".infrastructure." in src_mod:

            def after_openchronicle(mod: str) -> str:
                ix = mod.find("openchronicle.")
                return mod[ix + len("openchronicle.") :] if ix != -1 else mod

            old_tail = after_openchronicle(src_mod)
            new_tail = after_openchronicle(dst_mod)
            old = f"openchronicle.{old_tail}"
            new = f"openchronicle.{new_tail}"
            mapping[old] = new
    return mapping


def rewrite_imports(SRC: Path, import_map: dict, dry: bool):
    patterns = []
    for old, new in import_map.items():
        patterns.append((re.compile(rf"^(\s*from\s+){re.escape(old)}(\s+import\s+)", re.M), rf"\1{new}\2"))
        patterns.append((re.compile(rf"^(\s*import\s+){re.escape(old)}(\s*as\s+\w+|\s*$)", re.M), rf"\1{new}\2"))
        subprefix = re.escape(old) + r"\."
        patterns.append((re.compile(rf"^(\s*from\s+){subprefix}", re.M), rf"\1{new}."))
    changed = []
    for f in SRC.rglob("*.py"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        new_text = text
        for rx, repl in patterns:
            new_text = rx.sub(repl, new_text)
        if new_text != text:
            changed.append(rel(SRC, f))
            if not dry:
                f.write_text(new_text, encoding="utf-8")
    return changed


def acceptance_checks(SRC: Path):
    bad_core_plugin = grep(
        SRC, r"^(from|import)\s+openchronicle\.plugins", ["domain", "application", "infrastructure", "interfaces"]
    )
    bad_core_plugin = [h for h in bad_core_plugin if h not in ALLOWED_SHIMS]
    core_story = grep(SRC, r"\b(story|scene|character|timeline|lore|narrative)\b", ["infrastructure"])
    plugin_infra = grep(SRC, r"^(from|import)\s+openchronicle\.infrastructure", ["plugins/storytelling"])
    ok = (not bad_core_plugin) and (not core_story) and (not plugin_infra)
    details = {
        "core_imports_plugin_outside_shims": bad_core_plugin,
        "core_infrastructure_has_story_terms": core_story,
        "plugin_imports_core_infrastructure": plugin_infra,
    }
    return ok, details


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Split storytelling infra into plugin and rewrite imports.")
    ap.add_argument("--repo-root", default=".", help="Repository root (contains src/openchronicle)")
    ap.add_argument("--move-map", default="tools/move_map.json", help="Explicit move map JSON (list of {from,to})")
    ap.add_argument("--dry-run", action="store_true", help="Preview operations without changing files")
    ap.add_argument("--no-rewrite-imports", action="store_true", help="Skip auto import rewriting")
    ap.add_argument("--autodiscover", action="store_true", help="Discover infra files mentioning story terms")
    ap.add_argument(
        "--story-terms", default="story,scene,character,timeline,lore,narrative", help="Comma-separated terms"
    )
    args = ap.parse_args()

    ROOT = Path(args.repo_root).resolve()
    SRC = ROOT / "src" / "openchronicle"
    if not SRC.exists():
        print(f"[ERROR] {SRC} not found")
        sys.exit(2)

    # Load explicit move map
    move_map_path = ROOT / args.move_map
    try:
        explicit = json.loads(move_map_path.read_text(encoding="utf-8"))
    except Exception:
        explicit = []

    # Autodiscover
    terms = [t.strip() for t in args.story_terms.split(",") if t.strip()]
    discovered = discover_moves(SRC, terms) if args.autodiscover else []
    by_from = {m["from"]: m for m in (explicit + discovered)}
    moves = list(by_from.values())

    if not moves:
        print("[INFO] No files to move. Nothing to do.")
        sys.exit(0)

    print(f"[PLAN] {len(moves)} move(s)")
    for m in moves:
        print(f"  - {m['from']}  →  {m['to']}")

    if args.dry_run:
        imap = build_import_map(moves)
        if imap:
            print("\n[REWRITES] (import paths old → new)")
            for old, new in imap.items():
                print(f"  - {old}  →  {new}")
        else:
            print("\n[REWRITES] (none)")
        sys.exit(0)

    # Perform moves
    for m in moves:
        src = SRC / m["from"]
        dst = SRC / m["to"]
        if not src.exists():
            print(f"[MISS] {m['from']} (source missing)")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"[MOVE] {m['from']}  →  {m['to']}")

    # Rewrite imports
    if not args.no_rewrite_imports:
        imap = build_import_map(moves)
        changed = rewrite_imports(SRC, imap, dry=False)
        print(f"[REWRITE] Updated imports in {len(changed)} file(s)")

    # Acceptance checks
    ok, details = acceptance_checks(SRC)
    print("\n[CHECKS]")
    print(
        " - core imports plugin (outside shims):",
        "NONE" if not details["core_imports_plugin_outside_shims"] else details["core_imports_plugin_outside_shims"],
    )
    print(
        " - core infra has story nouns:",
        "NONE"
        if not details["core_infrastructure_has_story_terms"]
        else f"{len(details['core_infrastructure_has_story_terms'])} files",
    )
    print(
        " - plugin importing core infrastructure:",
        "NONE" if not details["plugin_imports_core_infrastructure"] else details["plugin_imports_core_infrastructure"],
    )

    if not ok:
        print("\n[FAIL] Acceptance checks failed. Review above.")
        sys.exit(1)

    print("\n[OK] Core is now clean; plugin owns storytelling infra.")


if __name__ == "__main__":
    main()
