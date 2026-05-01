#!/usr/bin/env bash
# Author-identity and PII checks for openchronicle-mcp.
#
# Adopted from the sibling MCP-repo pattern (plex-mcp/.githooks/pre-commit) so
# that openchronicle-mcp matches security.md global rules:
#   - block commits authored under a personal-domain email
#   - block staged content containing user-home paths or personal-domain emails
#
# Wired in via .pre-commit-config.yaml as a `local` hook (entry: bash
# .githooks/check-identity-and-pii.sh, pass_filenames: false).
#
# Patterns are intentionally generic so this script can be committed publicly
# without itself containing any specific PII.

set -euo pipefail

# Personal-domain email pattern used in two places:
#  - the author-identity check below (step 1)
#  - the PII pattern scan over staged content (step 2)
PERSONAL_EMAIL_PATTERN='[A-Za-z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|icloud|me|live|aol)\.[a-z]{2,}'

# 1. Author identity check
# git's staged-content scan can't see commit metadata, so the author
# email can leak into commit history even when file contents are clean.
# Block personal-domain emails in the configured author identity.
echo "Checking author identity..."
AUTHOR_IDENT=$(git var GIT_AUTHOR_IDENT 2>/dev/null || true)
# git var returns "Name <email> timestamp tz" — extract the email.
AUTHOR_EMAIL=$(printf '%s' "$AUTHOR_IDENT" | sed -nE 's/.*<([^>]+)>.*/\1/p')
if printf '%s' "$AUTHOR_EMAIL" | grep -qE "$PERSONAL_EMAIL_PATTERN"; then
  echo "" >&2
  echo "Commit blocked: author identity uses a personal-domain email." >&2
  echo "  email: $AUTHOR_EMAIL" >&2
  echo "" >&2
  echo "Set a GitHub noreply alias for this repo:" >&2
  echo "  git config user.email '<numeric-id>+<github-login>@users.noreply.github.com'" >&2
  echo "" >&2
  echo "Find your numeric id at https://api.github.com/users/<login>" >&2
  exit 1
fi

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

STAGED=$(git diff --cached --name-only --diff-filter=AM)
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
