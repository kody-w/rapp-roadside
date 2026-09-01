#!/usr/bin/env python3
"""Build a deterministic, local-only RAPP Roadside review bundle."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "export"
STAGING = EXPORT / ".build" / "rapp-roadside"
PACKAGE = EXPORT / "rapp-roadside"
ZIP_PATH = EXPORT / "rapp-roadside.zip"
LEGACY_PACKAGE = EXPORT / "rar-installer-troubleshooter"
LEGACY_ZIP = EXPORT / "rar-installer-troubleshooter.zip"
IDENTITY = (
    "rappid:@kody-w/rar-installer-troubleshooter:"
    "296872e9cd739d0549707b5c22abfd3654c3667652ea55dedaa5621b9e5f733b"
)
EXCLUDE_PARTS = {"__pycache__", ".git", ".work", ".build", "export"}
TOKEN_PATTERN = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    + b"-----BEGIN "
    + b"PRIVATE KEY-----)"
)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _included_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT)
        if any(
            part in EXCLUDE_PARTS or part.startswith(".work")
            for part in relative.parts
        ):
            continue
        if relative.as_posix().endswith(".pyc"):
            continue
        yield relative


def _copy_package():
    if STAGING.parent.exists():
        shutil.rmtree(STAGING.parent)
    STAGING.mkdir(parents=True)
    records = []
    for relative in _included_files():
        source = ROOT / relative
        data = source.read_bytes()
        if TOKEN_PATTERN.search(data):
            raise RuntimeError(f"credential-like content refused: {relative}")
        target = STAGING / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if relative.as_posix().startswith("scripts/"):
            target.chmod(0o755)
        records.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(data),
                "bytes": len(data),
            }
        )
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    os.replace(STAGING, PACKAGE)
    shutil.rmtree(EXPORT / ".build")
    return records


def _write_zip():
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if not path.is_file():
                continue
            relative = Path("rapp-roadside") / path.relative_to(PACKAGE)
            info = zipfile.ZipInfo(relative.as_posix(), (1980, 1, 1, 0, 0, 0))
            mode = 0o755 if path.relative_to(PACKAGE).parts[0] == "scripts" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            archive.writestr(info, path.read_bytes())


def main():
    EXPORT.mkdir(parents=True, exist_ok=True)
    if LEGACY_PACKAGE.exists():
        shutil.rmtree(LEGACY_PACKAGE)
    if LEGACY_ZIP.exists():
        LEGACY_ZIP.unlink()
    records = _copy_package()
    audit = subprocess.run(
        [
            sys.executable,
            str(PACKAGE / "scripts" / "public_audit.py"),
            "--path",
            str(PACKAGE),
        ],
        cwd=PACKAGE,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    if audit.returncode != 0:
        raise RuntimeError("public package audit failed: " + audit.stdout)
    _write_zip()
    zip_bytes = ZIP_PATH.read_bytes()
    manifest = {
        "schema": "rar-local-export/1.0",
        "candidate": "rapp-roadside",
        "display_name": "RAPP Roadside",
        "maintainer_system": "RAPP Pit Crew",
        "machine_issue_artifact": "Roadside Frame",
        "closed_loop": "rapp/closed-loop.json",
        "repository": "https://github.com/kody-w/rapp-roadside",
        "license": "MIT",
        "copyright": "2026 kody-w",
        "telemetry": False,
        "network_default": False,
        "participation": "voluntary",
        "identity": IDENTITY,
        "protocol_identity_retained": True,
        "zip": ZIP_PATH.name,
        "zip_sha256": _sha256(zip_bytes),
        "files": records,
        "publication": "not-performed-parent-review-only",
    }
    (EXPORT / "export-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "zip": ZIP_PATH.name,
                "zip_sha256": manifest["zip_sha256"],
                "files": len(records),
                "bytes": len(zip_bytes),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
