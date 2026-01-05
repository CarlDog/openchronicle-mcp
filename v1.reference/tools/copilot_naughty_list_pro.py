#!/usr/bin/env python3
import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Dict
from typing import List


def load_rules(p: Path) -> List[Dict]:
    return json.loads(p.read_text(encoding="utf-8"))


def load_protected_words(p: Path) -> List[str]:
    if p.exists():
        return [w.strip().upper() for w in p.read_text(encoding="utf-8").splitlines() if w.strip()]
    # fallback
    return [
        "CHARACTER",
        "STORY",
        "SCENE",
        "PLUGIN",
        "PLUGINS",
        "INFRASTRUCTURE",
        "BOOTSTRAP",
        "OPENCHRONICLE",
        "FACADE",
    ]


def is_literal_concat(snippet: str) -> bool:
    # Detect simple 'a' + 'b' + "c" forms
    return bool(re.search(r"(?:'[^']*'|\"[^\"]*\")\s*\+\s*(?:'[^']*'|\"[^\"]*\")", snippet))


def evaluate_literal_concat(snippet: str) -> str:
    # Very conservative: only join adjacent pure string literals separated by +; ignore escapes
    parts = re.findall(r"(?:'([^']*)'|\"([^\"]*)\")", snippet)
    if not parts:
        return ""
    # parts is list of tuples; take the non-empty group
    vals = [a or b for a, b in parts]
    return "".join(vals)


def detect_protected_assembly(line: str, protected: List[str]) -> str:
    # Check several patterns that result in assembled strings that might match protected words.
    # 1) Simple literal concatenation
    if is_literal_concat(line):
        assembled = evaluate_literal_concat(line).upper()
        for w in protected:
            if assembled == w or (len(assembled) > 2 and w in assembled):
                return f"assembled='{assembled}'"
    # 2) join of literal parts: ''.join(['CH','ARACTER'])
    m = re.search(r"join\s*\(\s*\[\s*((?:'[^']*'|\"[^\"]*\")(?:\s*,\s*(?:'[^']*'|\"[^\"]*\"))*)\s*\]\s*\)", line)
    if m:
        parts = re.findall(r"(?:'([^']*)'|\"([^\"]*)\")", m.group(1))
        vals = [a or b for a, b in parts]
        assembled = "".join(vals).upper()
        for w in protected:
            if assembled == w or (len(assembled) > 2 and w in assembled):
                return f"assembled='{assembled}'"
    # 3) f-string adjacent literal braces like f{'CH'}{'ARACTER'}
    if re.search(r"f(['\"])\\{\s*'[^']*'\s*\\}\\{\s*'[^']*'\s*\\}\\1", line):
        inner = re.findall(r"\\{\s*'([^']*)'\s*\\}", line)
        assembled = "".join(inner).upper()
        for w in protected:
            if assembled == w or (len(assembled) > 2 and w in assembled):
                return f"assembled='{assembled}'"
    # 4) chr/bytes/hex patterns (flag only; not assembling for safety)
    if re.search(r"''.join\(\s*map\(\s*chr", line) or "base64.b64decode" in line or "bytes.fromhex" in line:
        return "obfuscated-construction"
    return ""


def scan_file(path: Path, rules: List[Dict], protected: List[str]):
    text = path.read_text(encoding="utf-8", errors="ignore")
    findings = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        # Rule-based regex scanning
        for rule in rules:
            try:
                pat = re.compile(rule["pattern"], re.M)
            except re.error as e:
                # Skip malformed rule but report it once
                print(f"[RULE-SKIP] {rule.get('id','?')} invalid regex: {e}")
            continue
            if pat.search(line):
                extra = ""
                if rule["id"] == "NC01":
                    extra = detect_protected_assembly(line, protected)
                    if not extra:
                        # if it's just any concat but not protected, skip to reduce noise
                        continue
                findings.append(
                    {
                        "rule": rule["id"],
                        "severity": rule.get("severity", "warning"),
                        "name": rule["name"],
                        "path": str(path),
                        "line": i,
                        "snippet": line.strip(),
                        "extra": extra,
                    }
                )
    return findings


def apply_autofix(path: Path, protected: List[str]) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    original = text

    # Autofix only very safe cases: "CHARACTER" -> "CHARACTER"
    def concat_repl(m):
        parts = re.findall(r"(?:'([^']*)'|\"([^\"]*)\")", m.group(0))
        vals = [a or b for a, b in parts]
        glued = "".join(vals)
        if glued.upper() in protected:
            return f'"{glued}"'
        return m.group(0)

    text = re.sub(
        r"(?:'[^']*'|\"[^\"]*\")\s*\+\s*(?:'[^']*'|\"[^\"]*\")(?:\s*\+\s*(?:'[^']*'|\"[^\"]*\"))*", concat_repl, text
    )

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Copilot Naughty List PRO — global guardrail dodge detector")
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument("--paths", nargs="*", default=["."], help="Paths to scan recursively")
    ap.add_argument(
        "--exclude",
        nargs="*",
        default=[
            ".git",
            ".venv",
            "venv",
            ".tox",
            ".mypy_cache",
            "__pycache__",
            "dist",
            "build",
            ".pytest_cache",
            ".idea",
            ".vscode",
        ],
        help="Directories to skip",
    )
    ap.add_argument("--rules", default="tools/naughty_rules.json", help="Rules JSON")
    ap.add_argument("--protected-words", default="tools/protected_words.txt", help="Protected words list")
    ap.add_argument("--autofix", action="store_true", help="Apply safe autofixes (literal concat)")
    ap.add_argument("--fail-on-findings", action="store_true", help="Exit nonzero if any findings")
    ap.add_argument("--output", choices=["text", "json"], default="text", help="Report format")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    rules = load_rules(root / args.rules)
    protected = load_protected_words(root / args.protected_words)

    all_findings = []
    fixed_files = []

    excludes = set(args.exclude)
    for rel in args.paths:
        base = root / rel
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            rel_parts = p.relative_to(root).parts
            if any(part in excludes for part in rel_parts):
                continue
            if args.autofix:
                if apply_autofix(p, protected):
                    fixed_files.append(str(p.relative_to(root)))
            f = scan_file(p, rules, protected)
            all_findings.extend(f)

    if args.output == "json":
        out = {"fixed_files": fixed_files, "findings": all_findings}
        print(json.dumps(out, indent=2))
    else:
        if fixed_files:
            print("🛠 Autofixed files:")
            for f in fixed_files:
                print(f"  - {f}")
            print()
        if not all_findings:
            print("✅ No naughty patterns found.")
        else:
            print("🚨 Naughty patterns detected:\n")
            by_file = {}
            for f in all_findings:
                by_file.setdefault(f["path"], []).append(f)
            for fname, items in by_file.items():
                rel = Path(fname).resolve().relative_to(root)
                print(f"{rel}")
                for it in items:
                    sev = it.get("severity", "warning").upper()
                    extra = f" [{it['extra']}]" if it.get("extra") else ""
                    print(f"  {sev} {it['rule']}:{it['line']}  {it['name']}{extra}")
                    print(f"    ⇒ {it['snippet']}")
                print()

    if all_findings and args.fail_on_findings:
        sys.exit(2)


if __name__ == "__main__":
    main()
