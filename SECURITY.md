# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OpenChronicle, **do not open a
public issue.** Please report it privately using
[GitHub's security advisory feature](https://github.com/CarlDog/openchronicle-mcp/security/advisories/new).

I'll acknowledge your report within 72 hours and work with you to understand
the scope and develop a fix.

## Supported Versions

OpenChronicle v3 is pre-release software. Security fixes are applied to
the active development branch (`v3/develop` until the v3 cutover, then
`main` after).

| Version | Supported |
| --------- | ----------- |
| v3 (active development) | Yes |
| v2 (frozen on `archive/openchronicle.v2`) | No |
| v1 (frozen on `archive/openchronicle.v1`) | No |

## Scope

The following are in scope for security reports:

- Authentication or authorization bypasses (`OC_API_KEY` middleware,
  per-request validation)
- Data leakage (memory content, embedding API keys, log redaction)
- SQL injection or other injection vulnerabilities
- Path traversal in `oc memory import`, `onboard_git`, or any other
  filesystem-touching surface
- Dependency vulnerabilities with a known exploit path

The following are **out of scope**:

- Denial of service against the local CLI (single-user tool)
- Vulnerabilities in upstream embedding providers (OpenAI, Ollama)
- Social engineering attacks

See also: [`docs/configuration/security_posture.md`](docs/configuration/security_posture.md)
for the complete threat model + secrets handling + container hardening
posture.
