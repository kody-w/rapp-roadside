# Privacy

RAPP Roadside is local-first and collects no credentials.

## Data behavior

- No telemetry, analytics, tracking, crash upload, or remote logging.
- No external network access by default.
- The optional probe permits only explicit plain-HTTP loopback access to
  `localhost`, `127.0.0.1`, or `::1`.
- Reporting-AI text and logs are treated as hostile data. Roadside accepts
  hashes, sizes, and separated observed/inferred claim identifiers rather than
  retaining raw bodies.
- Attachments are limited to allowlisted local `.json`, `.log`, `.md`, and
  `.txt` files up to 2 MB each. Public reports contain name, media type, byte
  count, and SHA-256 only.
- Credentials, tokens, passwords, private keys, cookies, authorization
  headers, private paths, and non-loopback URLs are refused.
- Repair operations write only to a new sibling copy after explicit
  source-bound human approval. They never activate that copy.

## Retention and sharing

Raw local retention defaults to zero. Quarantine records are hash-only and
TTL-bound. RAPP Roadside does not upload, publish, or post to collaboration
services. Users control any later sharing.

Closed-loop queueing and dedupe use a domain-separated issue signature built
from release/version bytes, failure phase/code, environment classes, and input
hashes. Person or account identity, raw logs, attachment bodies, and private
paths are excluded. Improvement-queue output is inert and local; no automatic network
submission occurs.

The local Brainstem may have its own network and privacy behavior. RAPP
Roadside does not provide credentials to it and invokes loopback checks only
when the user explicitly enables them.
