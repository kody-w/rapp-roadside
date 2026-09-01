#!/usr/bin/env python3
"""Exercise a clean local copy without network access."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / ".fresh-clone-check"
EXCLUDED_PARTS = {
    ".fresh-clone-check",
    ".git",
    "__pycache__",
    "export",
}


def _run(argv, cwd):
    result = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("fresh-clone command returned non-object JSON")
    return payload


def _copy_public_tree():
    files = [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not any(
            part in EXCLUDED_PARTS or part.startswith(".work")
            for part in path.relative_to(ROOT).parts
        )
    ]
    DESTINATION.mkdir()
    for source in files:
        relative = source.relative_to(ROOT)
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main():
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    checks = []
    try:
        _copy_public_tree()
        preflight = _run(
            [sys.executable, "scripts/run_agent.py", "--preflight"],
            DESTINATION,
        )
        checks.append(preflight.get("status") == "PASS")
        public_audit = _run(
            [
                sys.executable,
                "scripts/public_audit.py",
                "--path",
                ".",
            ],
            DESTINATION,
        )
        checks.append(public_audit.get("status") == "PASS")
        embedded_frame = _run(
            [
                sys.executable,
                "scripts/extract_roadside_frame.py",
                "share with kody.md",
            ],
            DESTINATION,
        )
        checks.append(
            embedded_frame.get("kind") == "rar.review.rev-13"
            and embedded_frame.get("payload", {}).get("candidate")
            == "rapp-roadside"
        )
        before = json.loads(
            (
                DESTINATION
                / "fixtures"
                / "synthetic-slow-setup"
                / "before.json"
            ).read_text(encoding="utf-8")
        )
        after = json.loads(
            (
                DESTINATION
                / "fixtures"
                / "synthetic-slow-setup"
                / "after.json"
            ).read_text(encoding="utf-8")
        )
        diagnosis = _run(
            [
                sys.executable,
                "scripts/run_agent.py",
                "--json",
                json.dumps(
                    {"operation": "diagnose", "observations": before},
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ],
            DESTINATION,
        )
        checks.append(
            diagnosis.get("next_action", {}).get("id")
            == "bounded-wait-and-local-retest"
        )
        retest = _run(
            [
                sys.executable,
                "scripts/run_agent.py",
                "--json",
                json.dumps(
                    {
                        "operation": "retest",
                        "diagnosis": diagnosis,
                        "observations": after,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ],
            DESTINATION,
        )
        checks.append(retest.get("status") == "PASS")
        runtime = DESTINATION / ".runtime"
        for operation, arguments in (
            (
                "install",
                [
                    "install",
                    "--source",
                    ".",
                    "--skills-dir",
                    ".runtime/skills",
                    "--state-dir",
                    ".runtime/state",
                ],
            ),
            (
                "verify",
                [
                    "verify",
                    "--skills-dir",
                    ".runtime/skills",
                    "--state-dir",
                    ".runtime/state",
                ],
            ),
            (
                "remove",
                [
                    "remove",
                    "--skills-dir",
                    ".runtime/skills",
                    "--state-dir",
                    ".runtime/state",
                ],
            ),
        ):
            result = _run(
                [sys.executable, "scripts/rar_lifecycle.py", *arguments],
                DESTINATION,
            )
            checks.append(
                result.get("status") == "PASS" and result.get("global_lock") is False
            )
        status = "PASS" if all(checks) else "FAIL"
        print(
            json.dumps(
                {
                    "status": status,
                    "checks": len(checks),
                    "network_used": False,
                    "telemetry": False,
                    "private_paths_exported": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if status == "PASS" else 1
    finally:
        if DESTINATION.exists():
            shutil.rmtree(DESTINATION)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
