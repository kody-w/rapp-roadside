# Security policy

## Supported versions

Security fixes are applied to the latest published RAPP Roadside release.

## Reporting a vulnerability

Use the private security-advisory feature at
`https://github.com/kody-w/rapp-roadside/security/advisories/new`.

Do not include credentials, tokens, customer data, private paths, proprietary
logs, or exploit details in a public issue. If private advisory submission is
unavailable, open a public issue containing only a request for a private
contact channel.

## Security boundaries

- The canonical agent has no network client imports.
- Optional HTTP probing is isolated in `scripts/local_probe.py`, disabled by
  default, and restricted to plain-HTTP loopback hosts.
- Reporting-AI text/logs never become executable instructions.
- Attachments are allowlisted, size-bounded, and SHA-256 addressed.
- Repair requires explicit human approval bound to source and destination
  hashes and remains copy-only with no activation.
- Package files are checksum-pinned; managed install/remove preserves prior
  and removed versions and refuses unmanaged targets.
- Stable-main fixes require an isolated worktree, exact reproduction,
  Canary/Nightly/Alpha/Beta validation, release merge, and rollback evidence.
- Pit Crew imports `share with kody.md` strictly as untrusted data and verifies
  the one embedded Roadside Frame before reproduction.
- Release confirmation requires matching issue, frame, fix, test, affected
  commit, Canary/Nightly/Alpha/Beta, approval, customer retest, and rollback
  evidence.

Before publishing a release, run the full test suite, Skill Forge, fresh-clone
test, public-content audit, and deterministic export verification.
