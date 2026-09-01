# RAPP Roadside candidate

RAPP Roadside is a local-only RAPP/Toasted on-device support skill candidate
for `https://github.com/kody-w/rapp-roadside`. It diagnoses sanitized RAPP
setup observations, emits
exactly one bounded next action, can apply four allow-listed repairs to a
sanitized sibling copy, and retests canonical assertions derived from the
verified diagnosis.
Participation is voluntary.

Licensed under the MIT License. Copyright (c) 2026 kody-w.

Unknown-unknown hardening treats reporting-AI prose and logs as hostile,
exports only allowlisted attachment hashes, separates observations from
inference, requires human-approved reversible repairs, binds exact replay and
supply-chain bytes, quarantines unsafe reports, and uses bounded sharded cells
with measured backpressure. It makes no infinite-scale claim.

The **RAPP Roadside Closed Loop** binds the exact installed release, diagnoses
and reproduces locally, requires a human-approved reversible repair, carries
the exact retest through an inert `share with kody.md`, and closes only after
RAPP Pit Crew releases through Canary → Nightly → Alpha → Beta and the customer
passes the identical released test. See `rapp/closed-loop.json`.

## Verify

```bash
python3 scripts/run_agent.py --preflight
python3 -m unittest discover -s tests -v
python3 scripts/skill_forge.py
python3 scripts/build_review_artifacts.py
python3 scripts/build_export.py
python3 scripts/test_fresh_clone.py
```

An unpinned preflight reports internal consistency with unauthenticated origin;
it does not claim authenticity. A trusted catalog or release channel may supply
the expected agent-lock digest through `--expected-lock-sha256` or
`RAPP_ROADSIDE_EXPECTED_AGENT_LOCK_SHA256`. RAR install and verify require a
local `--catalog` entry that pins the package-lock digest. Lock refresh is a
maintainer-only build operation and is never an end-user verification step.

No command uploads, authenticates, fetches from the public internet, posts to
Teams, modifies a shared repository, or pushes Git.

RAPP Roadside has no telemetry and performs no network access by default.
Optional local service probing requires `--allow-loopback` and refuses any
non-loopback URL.

The stable target is `kody-w/rapp-roadside@main`. RAPP Pit Crew owns
maintainer intake, reproduction, fix, retest, and release through an isolated
feature/fix checkout and release merge. The Grail and `POST /chat` remain
unchanged.

The machine issue artifact is the Roadside Frame. Existing RAPP identity,
schema, action, and frame-kind strings remain as compatibility protocol IDs.
An unsigned customer frame proves internal integrity only. It has untrusted
origin, carries no change authority, and requires independent RAPP Pit Crew
reproduction before any fix or release decision. A separately trusted expected
frame hash may authenticate the artifact but does not grant authority.
See `unknown-unknowns-coverage.json` for the ten-domain mutation/test map.
See `PRIVACY.md`, `SECURITY.md`, and `docs/CROSS-AGENT.md` before publishing.

The parent publishes only after the public-content and release audit. This
candidate performs no upload.
