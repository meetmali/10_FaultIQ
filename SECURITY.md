# Security Policy

## Supported versions

FaultIQ is pre-release. Only the latest commit on `main` receives security fixes.

## Reporting a vulnerability

**Please don't open a public issue.** Report vulnerabilities privately through
**GitHub's private vulnerability reporting**: go to the repository's **Security** tab and choose
**Report a vulnerability**.

Please include:

- What the vulnerability is and the impact you expect it to have.
- Steps to reproduce it, using synthetic data only.
- The affected component (`api/`, `pipeline/` or `frontend/`) and version or commit.

You can expect an acknowledgement within 7 days. We'll keep you informed until a fix is released,
and credit you if you'd like.

## Scope notes

- FaultIQ is **read-only decision support**. It never sends commands to building equipment.
  Any path that could cause it to do so is treated as critical.
- Self-hosters are responsible for securing their own deployment (network exposure, TLS, credentials
  and backups). Deployment hardening guidance arrives with the Phase 9 runbook.
