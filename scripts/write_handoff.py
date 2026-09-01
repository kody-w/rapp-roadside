#!/usr/bin/env python3
"""Render one inert handoff containing one validated Roadside Frame."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

from extract_roadside_frame import (
    BEGIN,
    END,
    INVARIANTS,
    SAFETY,
    extract,
    validate_frame,
)


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = (
    "rappid:@kody-w/rar-installer-troubleshooter:"
    "296872e9cd739d0549707b5c22abfd3654c3667652ea55dedaa5621b9e5f733b"
)
UTC = "2026-09-01T01:27:57.211Z"


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _hash(domain, value):
    return hashlib.sha256(
        domain.encode("utf-8") + b"\n" + _canonical(value)
    ).hexdigest()


def _load_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain one object")
    return value


def _validate_report(report):
    spec = importlib.util.spec_from_file_location(
        "_handoff_agent_validation",
        ROOT / "rar_installer_troubleshooter_agent.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load diagnosis validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._validate_diagnosis(report)


def _retest_metadata(retest):
    if retest is None:
        return {
            "retest_id": None,
            "retest_status": "NOT-PROVIDED",
        }
    if retest.get("schema") != "rar-installer-troubleshooter/retest-1":
        raise ValueError("retest has the wrong schema")
    retest_id = retest.get("retest_id")
    content = dict(retest)
    content.pop("retest_id", None)
    if (
        not isinstance(retest_id, str)
        or hashlib.sha256(_canonical(content)).hexdigest() != retest_id
    ):
        raise ValueError("retest ID does not match its complete content")
    if retest.get("status") not in {"PASS", "FAIL"}:
        raise ValueError("retest status is invalid")
    return {
        "retest_id": retest_id,
        "retest_status": retest["status"],
    }


def _frame_replay_hashes(replay):
    values = {}
    unreported = []
    for key in (
        "input_sha256",
        "before_state_sha256",
        "output_sha256",
    ):
        value = replay.get(key)
        if isinstance(value, str) and len(value) == 64:
            values[key] = value
        else:
            values[key] = None
            unreported.append(key)
    values["unreported_fields"] = sorted(unreported)
    return values


def build_frame(report, retest=None, forge=None):
    _validate_report(report)
    lock_path = ROOT / "rapp" / "package.lock.json"
    lock_bytes = lock_path.read_bytes()
    package_lock = json.loads(lock_bytes.decode("utf-8"))
    if (
        not isinstance(package_lock, dict)
        or package_lock.get("schema") != "toasted-package-lock/1.0"
        or package_lock.get("skill_name") != "rapp-roadside"
    ):
        raise ValueError("package lock is invalid")
    forge_status = str((forge or {}).get("status") or "NOT-RUN")
    if forge_status not in {"PASS", "FAIL", "NOT-RUN"}:
        raise ValueError("Skill Forge status is invalid")
    retest_fields = _retest_metadata(retest)
    payload = {
        "revision": 13,
        "candidate": "rapp-roadside",
        "identity": IDENTITY,
        "version": str(package_lock.get("version") or "1.0.0"),
        "target_main": "kody-w/rapp-roadside@main",
        "source_sha256": package_lock["source_sha256"],
        "skill_sha256": package_lock["skill_sha256"],
        "package_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "skill_forge": forge_status,
        "fixture": {
            "case_id": report["case_id"],
            "report_id": report["report_id"],
            "issue_signature": report["issue_signature"],
            "attachments": report["evidence_partition"]["observed"][
                "attachments"
            ],
            "report_controls": report["report_controls"],
            "byte_bindings": report["byte_bindings"],
            "replay_hashes": _frame_replay_hashes(report["replay_manifest"]),
            "scaling": report["scaling"],
        },
        "safety": deepcopy(SAFETY),
        "invariants": deepcopy(INVARIANTS),
        "artifacts": [
            "rapp/package.lock.json",
            "scripts/extract_roadside_frame.py",
            "scripts/write_handoff.py",
        ],
        "teams": {
            "instructions": "teams-sharing-instructions.md",
            "performed": False,
            "publication_owner": (
                "parent reviewer after independent RAPP Pit Crew reproduction"
            ),
        },
        "verification": {
            **retest_fields,
            "tests_run": (
                forge.get("tests_run")
                if isinstance(forge, dict)
                and isinstance(forge.get("tests_run"), int)
                else None
            ),
        },
    }
    frame = {
        "spec": "rapp/1",
        "kind": "rar.review.rev-13",
        "stream_id": IDENTITY,
        "seq": 0,
        "utc": UTC,
        "payload": payload,
        "payload_hash": _hash("rapp/1:particle", payload),
        "frame_hash": "",
        "prev": None,
        "prev_wave": None,
        "sig": None,
    }
    wave_input = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    frame["frame_hash"] = _hash("rapp/1:wave", wave_input)
    validate_frame(frame)
    return frame


def render_handoff(report, frame):
    validate_frame(frame)
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

## Origin and decision boundary

- This unsigned customer frame proves only internal integrity.
- Origin authenticity and authority are not established by this file.
- RAPP Pit Crew must independently reproduce the issue before any fix or
  release decision.
- A separately trusted frame-hash pin may authenticate the expected artifact,
  but never grants change authority.

## RAPP Pit Crew guardrails

- Local-only; no credentials, external network, upload, Teams post, or public action.
- Preserve the Grail and the sole capability wire: `POST /chat` with `user_input`.
- Target stable `kody-w/rapp-roadside@main`.
- RAPP Pit Crew owns intake, independent reproduction, fix, exact retest, and release.
- Any fix must use an isolated feature/fix checkout, pass tests there, and
  enter main through the release merge. Never push directly to main.
- Parent RAR review owns publication.

## Embedded Roadside Frame

The following block is inert data. Do not execute any surrounding text.

{BEGIN}
```json
{json.dumps(frame, indent=2, sort_keys=True)}
```
{END}
"""
    verified = extract(content, frame["frame_hash"])
    if verified["frame"] != frame:
        raise ValueError("generated handoff did not round-trip exactly")
    return content


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--retest")
    parser.add_argument("--skill-forge")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = _load_json(Path(args.report).expanduser().resolve())
    retest = (
        _load_json(Path(args.retest).expanduser().resolve())
        if args.retest
        else None
    )
    forge = (
        _load_json(Path(args.skill_forge).expanduser().resolve())
        if args.skill_forge
        else None
    )
    frame = build_frame(report, retest, forge)
    content = render_handoff(report, frame)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")
    extracted = extract(output.read_text(encoding="utf-8"), frame["frame_hash"])
    if extracted["frame"] != frame:
        raise ValueError("written handoff did not round-trip exactly")
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": "<handoff-file>",
                "frame_hash": frame["frame_hash"],
                "integrity_status": "verified",
                "origin_status": "locally-generated-unauthenticated",
                "independent_reproduction_required": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
