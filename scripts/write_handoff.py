#!/usr/bin/env python3
"""Render a concise RAPP Roadside to RAPP Pit Crew handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = json.loads(
        Path(args.report).expanduser().resolve().read_text(encoding="utf-8")
    )
    action = report["next_action"]
    command = " ".join(json.dumps(part) for part in action["command_argv"])
    content = f"""# Share with Kody

## RAPP Roadside finding

- Case: `{report["case_id"]}`
- Code: `{report["finding"]["code"]}`
- Summary: {report["finding"]["summary"]}
- Deterministic report: `{report["report_id"]}`

## One bounded next action

**{action["title"]}** — timeout `{action["timeout_seconds"]}s`

```text
{command}
```

Expected: {action["expected"]}

## RAPP Pit Crew guardrails

- Local-only; no credentials, external network, upload, Teams post, or public action.
- Preserve the Grail and the sole capability wire: `POST /chat` with `user_input`.
- Target stable `kody-w/rapp-roadside@main`.
- RAPP Pit Crew owns intake, reproduction, fix, exact retest, and release.
- Any Pit Crew fix must use an isolated feature/fix worktree, pass tests there,
  and enter main through the release merge. Never push directly to main.
- Parent RAR review owns publication.
"""
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "output": "<handoff-file>"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
