#!/usr/bin/env python3
"""Maintainer-only refresh of local consistency records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "rar_installer_troubleshooter_agent.py"
IDENTITY = (
    "rappid:@kody-w/rar-installer-troubleshooter:"
    "296872e9cd739d0549707b5c22abfd3654c3667652ea55dedaa5621b9e5f733b"
)
LOCKED_PATHS = [
    ".github/workflows/test.yml",
    ".gitignore",
    "CONTRIBUTING.md",
    "SKILL.md",
    "README.md",
    "LICENSE",
    "PRIVACY.md",
    "SECURITY.md",
    "canonical.html",
    "companion/PLAYBOOK.md",
    "docs/CROSS-AGENT.md",
    "rar_installer_troubleshooter_agent.py",
    "rapp/capability.json",
    "rapp/closed-loop.json",
    "rapp/lifecycle.json",
    "scripts/build_export.py",
    "scripts/build_review_artifacts.py",
    "scripts/extract_roadside_frame.py",
    "scripts/hash_attachment.py",
    "scripts/local_probe.py",
    "scripts/quarantine_report.py",
    "scripts/public_audit.py",
    "scripts/rar_lifecycle.py",
    "scripts/refresh_integrity.py",
    "scripts/run_agent.py",
    "scripts/skill_forge.py",
    "scripts/test_fresh_clone.py",
    "scripts/write_handoff.py",
    "teams-sharing-instructions.md",
    "unknown-unknowns-coverage.json",
]


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _update_json(path, updates):
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
    _write_json(path, payload)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--maintainer",
        action="store_true",
        help="acknowledge that this rewrites local consistency records",
    )
    args = parser.parse_args(argv)
    if not args.maintainer:
        parser.error(
            "--maintainer is required; end users must verify against an "
            "externally trusted digest instead of rewriting locks"
        )
    source_bytes = AGENT.read_bytes()
    source_sha = _sha256(source_bytes)
    agent_lock = {
        "schema": "rapp-agent-lock/1.0",
        "agent": AGENT.name,
        "display_name": "RAPP Roadside",
        "maintainer_system": "RAPP Pit Crew",
        "identity": IDENTITY,
        "version": "1.0.0",
        "sha256": source_sha,
        "bytes": len(source_bytes),
        "algorithm": "sha256",
        "line_endings": "LF",
    }
    _write_json(ROOT / "rapp" / "agent.lock.json", agent_lock)
    _update_json(
        ROOT / "manifest.json",
        {"source_sha256": source_sha},
    )
    _update_json(
        ROOT / "rapp" / "manifest.json",
        {"source_sha256": source_sha},
    )
    _update_json(
        ROOT / "toasted" / "manifest.json",
        {"linked_agent_sha256": source_sha},
    )

    paths = list(LOCKED_PATHS)
    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "schemas").glob("*.json"))
    )
    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "tests").glob("test_*.py"))
    )
    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "fixtures").rglob("*"))
        if path.is_file() and path.name != "expected-report.json"
    )
    paths.append("rapp/agent.lock.json")
    records = []
    for relative in sorted(set(paths)):
        path = ROOT / relative
        data = path.read_bytes()
        records.append(
            {
                "path": relative,
                "sha256": _sha256(data),
                "bytes": len(data),
            }
        )
    skill_sha = _sha256(
        json.dumps(
            records,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    _update_json(ROOT / "manifest.json", {"skill_sha256": skill_sha})
    _update_json(ROOT / "rapp" / "manifest.json", {"skill_sha256": skill_sha})
    _update_json(
        ROOT / "toasted" / "manifest.json",
        {"skill_sha256": skill_sha},
    )
    for relative in (
        "manifest.json",
        "rapp/manifest.json",
        "toasted/manifest.json",
    ):
        path = ROOT / relative
        data = path.read_bytes()
        records.append(
            {
                "path": relative,
                "sha256": _sha256(data),
                "bytes": len(data),
            }
        )
    records.sort(key=lambda item: item["path"])
    package_lock = {
        "schema": "toasted-package-lock/1.0",
        "identity": IDENTITY,
        "skill_name": "rapp-roadside",
        "display_name": "RAPP Roadside",
        "maintainer_system": "RAPP Pit Crew",
        "protocol_identity_retained": True,
        "version": "1.0.0",
        "source_sha256": source_sha,
        "skill_sha256": skill_sha,
        "skill_hash_scope": "core-files-before-manifest-annotations",
        "files": records,
    }
    _write_json(ROOT / "rapp" / "package.lock.json", package_lock)
    print(
        json.dumps(
            {
                "status": "PASS",
                "source_sha256": source_sha,
                "skill_sha256": skill_sha,
                "files": len(records),
                "authenticity_claimed": False,
                "maintainer_only": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
