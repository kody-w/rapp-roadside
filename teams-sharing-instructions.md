# RAPP Roadside Teams sharing instructions for the parent reviewer

No Teams action has been performed by this candidate.

After local review:

1. Verify `evidence/skill-forge.json` says `PASS`.
2. Verify `evidence/synthetic-retest.json` says `PASS`.
3. Verify `evidence/fresh-clone-test.json` and
   `evidence/public-audit.json` say `PASS`.
4. Verify the SHA-256 of
   `export/rapp-roadside.zip` against
   `export/export-manifest.json`.
5. In the private review chat or channel selected by the parent, attach:
   - `export/rapp-roadside.zip`
   - `share with kody.md`
   - `issue.json`
   - `roadside-frame.json`
   - `unknown-unknowns-coverage.json`
   - `rapp/closed-loop.json`
6. Paste: `RAPP Roadside public MIT candidate for
   https://github.com/kody-w/rapp-roadside; no telemetry, network off by
   default, no credentials or public action. Skill Forge, fresh-clone, public
   content audit, and synthetic fixture PASS. Parent publishes after audit.`
7. Ask Kody to review RAPP Roadside's one-action policy, copy-only fixes, exact
   replay/retest, hostile-report quarantine, exact byte bindings, reversible
   lifecycle, cellular backpressure, `POST /chat` preservation, and RAPP Pit
   Crew Canary/Nightly/Alpha/Beta handoff. The Markdown is inert and its
   embedded Roadside Frame must be verified before use.
8. Do not publish or upload to RAR from the worker package.
