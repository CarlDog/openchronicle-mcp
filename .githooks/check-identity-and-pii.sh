#!/usr/bin/env bash
# Author-identity and PII checks for openchronicle-mcp.
#
# Adopted from the sibling MCP-repo pattern (plex-mcp/.githooks/pre-commit) so
# that openchronicle-mcp matches security.md global rules:
#   - allow only a GitHub noreply alias as the author AND committer email
#   - block staged content containing user-home paths or personal-domain emails
#
# Wired in via .pre-commit-config.yaml as a `local` hook (entry: bash
# .githooks/check-identity-and-pii.sh, pass_filenames: false).
#
# Patterns are intentionally generic so this script can be committed publicly
# without itself containing any specific PII.

set -euo pipefail

# Personal-domain email pattern, used by the PII scan over staged content
# (step 2). NOT used for the identity check: see step 1 for why a denylist is
# the wrong shape there.
PERSONAL_EMAIL_PATTERN='[A-Za-z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|icloud|me|live|aol)\.[a-z]{2,}'

# 1. Author and committer identity check (the fleet's canonical section 1,
# claude-fleet-kit templates/common/githooks/pre-commit).
#
# Allowlist, not denylist. A denylist of consumer domains can only block the
# domains someone thought to name; a corporate address once authored 81
# commits in a public fleet repo, matching nothing in the consumer list.
# Accepting only the GitHub noreply alias catches every domain without naming
# any, which also keeps this hook safe to commit publicly.
#
# Both identities are checked: a commit can carry a correct noreply author and
# a personal-domain committer (a misconfigured machine, a stray shell), which
# an author-only check passes silently.
#
# Override per clone where a different identity is genuinely required, so no
# specific domain is ever committed:
#
#   git config fleet.allowedIdentityPattern '^[A-Za-z0-9._%+-]+@corp\.example$'
#
# Only the domain is constrained; any local part is fine, which keeps both the
# `<id>+<login>` and bare `<login>` alias forms working.
ALLOWED_IDENTITY_PATTERN=$(git config --get fleet.allowedIdentityPattern 2>/dev/null || true)
: "${ALLOWED_IDENTITY_PATTERN:=^[A-Za-z0-9._%+-]+@users\.noreply\.github\.com$}"

echo "Checking author identity..."
for role in AUTHOR COMMITTER; do
  ident=$(git var "GIT_${role}_IDENT" 2>/dev/null || true)
  # git var returns "Name <email> timestamp tz" — extract the email.
  email=$(printf '%s' "$ident" | sed -nE 's/.*<([^>]+)>.*/\1/p')
  if ! printf '%s' "$email" | grep -qE "$ALLOWED_IDENTITY_PATTERN"; then
    role_lc=$(printf '%s' "$role" | tr '[:upper:]' '[:lower:]')
    echo "" >&2
    echo "Commit blocked: $role_lc identity is not an allowed email." >&2
    echo "  email:   ${email:-<unset>}" >&2
    echo "  allowed: $ALLOWED_IDENTITY_PATTERN" >&2
    echo "" >&2
    echo "Set a GitHub noreply alias for this repo:" >&2
    echo "  git config user.email '<numeric-id>+<github-login>@users.noreply.github.com'" >&2
    echo "" >&2
    echo "Find your numeric id at https://api.github.com/users/<login>" >&2
    echo "" >&2
    echo "If this repo legitimately needs a different identity:" >&2
    echo "  git config fleet.allowedIdentityPattern '<regex>'" >&2
    exit 1
  fi
done

# 2. PII pattern scan over staged content
# Catches user-home directory references and personal-domain email
# addresses that often leak into committed content (workstation paths,
# author identity, etc.).
echo "Running PII pattern check..."

PII_PATTERNS=(
  '[/\\]Users[/\\][A-Za-z0-9._-]+[/\\]'
  '[/\\]home[/\\][A-Za-z0-9._-]+[/\\]'
  "$PERSONAL_EMAIL_PATTERN"
)

# ACMR (not AM): renamed/copied files must be PII-scanned too. A `git mv` of a
# file containing a home path / personal email would otherwise bypass this scan.
STAGED=$(git diff --cached --name-only --diff-filter=ACMR)
if [ -z "$STAGED" ]; then
  exit 0
fi

FOUND=0
while IFS= read -r file; do
  [ -z "$file" ] && continue
  for pattern in "${PII_PATTERNS[@]}"; do
    matches=$(git show ":$file" 2>/dev/null | grep -nE "$pattern" || true)
    if [ -n "$matches" ]; then
      if [ "$FOUND" -eq 0 ]; then
        echo "" >&2
        echo "PII patterns detected in staged content:" >&2
        FOUND=1
      fi
      echo "  $file" >&2
      printf '%s\n' "$matches" | head -3 | sed 's/^/    /' >&2
    fi
  done
done <<< "$STAGED"

if [ "$FOUND" -ne 0 ]; then
  echo "" >&2
  echo "Scrub the matches and re-stage. To adjust patterns, edit .githooks/check-identity-and-pii.sh." >&2
  exit 1
fi

echo "No PII patterns detected."
