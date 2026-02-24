# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OpenChronicle, **do not open a
public issue.** Please report it privately using
[GitHub's security advisory feature](https://github.com/OpenChronicle/core/security/advisories/new).

I'll acknowledge your report within 72 hours and work with you to understand
the scope and develop a fix.

## Supported Versions

OpenChronicle v2 is pre-release software. Security fixes are applied to the
`main` branch only.

| Version | Supported |
| --------- | ----------- |
| main (v2 dev) | Yes |
| v1 (archived) | No |

## Scope

The following are in scope for security reports:

- Authentication or authorization bypasses
- Data leakage (conversation content, memory, API keys)
- SQL injection or other injection vulnerabilities
- Dependency vulnerabilities with a known exploit path

The following are **out of scope**:

- Denial of service against the local CLI (single-user tool)
- Vulnerabilities in upstream LLM providers
- Social engineering attacks
