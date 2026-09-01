#!/usr/bin/env python3
"""Checksum-pinned, reversible local RAR install/remove lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path


MARKER = ".rar-managed.json"
EXTRA_PACKAGE_FILES = {
    "manifest.json",
    "rapp/manifest.json",
    "rapp/package.lock.json",
    "toasted/manifest.json",
}
HASH64 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path):
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"{path.name} must contain one object")
    return result


def _safe_target(root, relative):
    relative_path = Path(relative)
    target = (root / relative_path).resolve()
    if (
        relative_path.is_absolute()
        or ".." in relative_path.parts
        or (root != target and root not in target.parents)
    ):
        raise ValueError(f"unsafe package path: {relative}")
    return target


def _catalog_digest(catalog_path):
    catalog = _load_json(catalog_path)
    if set(catalog) != {
        "package_lock_sha256",
        "schema",
        "skill_name",
    }:
        raise ValueError("trusted catalog entry has the wrong exact shape")
    if catalog.get("schema") != "rapp-roadside-catalog-entry/1.0":
        raise ValueError("unsupported trusted catalog entry")
    if catalog.get("skill_name") != "rapp-roadside":
        raise ValueError("trusted catalog entry names a different skill")
    digest = catalog.get("package_lock_sha256")
    if not isinstance(digest, str) or not HASH64.fullmatch(digest):
        raise ValueError("trusted catalog package lock digest is invalid")
    return digest


def _verify_package(root, expected_package_lock_sha256=None):
    root = root.resolve()
    lock_path = root / "rapp" / "package.lock.json"
    lock_bytes = lock_path.read_bytes()
    lock_digest = hashlib.sha256(lock_bytes).hexdigest()
    if (
        expected_package_lock_sha256 is not None
        and lock_digest != expected_package_lock_sha256
    ):
        raise ValueError("package lock does not match the trusted catalog digest")
    lock = json.loads(lock_bytes.decode("utf-8"))
    if not isinstance(lock, dict):
        raise ValueError("package lock must contain one object")
    if lock.get("schema") != "toasted-package-lock/1.0":
        raise ValueError("unsupported package lock")
    if lock.get("skill_name") != "rapp-roadside":
        raise ValueError("package is not RAPP Roadside")
    records = lock.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("package lock has no files")
    for record in records:
        target = _safe_target(root, record.get("path"))
        if not target.is_file() or target.is_symlink():
            raise ValueError(f"locked package file missing: {record.get('path')}")
        if _sha256(target) != record.get("sha256"):
            raise ValueError(f"locked package file drift: {record.get('path')}")
    return lock, {
        "integrity": "internally-consistent",
        "origin_status": (
            "catalog-pinned"
            if expected_package_lock_sha256 is not None
            else "unauthenticated"
        ),
        "trusted_authenticity": expected_package_lock_sha256 is not None,
        "package_lock_sha256": lock_digest,
    }


def _copy_locked_package(source, staging, lock):
    staging.mkdir(parents=True)
    relative_paths = {record["path"] for record in lock["files"]}
    relative_paths.update(EXTRA_PACKAGE_FILES)
    for relative in sorted(relative_paths):
        source_path = _safe_target(source, relative)
        if not source_path.is_file() or source_path.is_symlink():
            raise ValueError(f"required package file missing: {relative}")
        target = _safe_target(staging, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)


def _marker(target):
    path = target / MARKER
    return _load_json(path) if path.is_file() else None


def _write_marker(target, payload):
    (target / MARKER).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def install(source, skills_dir, state_dir, catalog_path):
    source = source.resolve()
    skills_dir = skills_dir.resolve()
    state_dir = state_dir.resolve()
    expected_digest = _catalog_digest(catalog_path)
    lock, trust = _verify_package(source, expected_digest)
    target = skills_dir / "rapp-roadside"
    skills_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    staging = state_dir / "staging" / (
        "rapp-roadside-" + lock["skill_sha256"][:16]
    )
    if staging.exists():
        shutil.rmtree(staging)
    _copy_locked_package(source, staging, lock)

    backup_relative = None
    existing = _marker(target) if target.is_dir() else None
    if target.exists() and existing is None:
        shutil.rmtree(staging)
        raise ValueError("unmanaged target exists and will not be overwritten")
    if (
        existing
        and existing.get("skill_sha256") == lock["skill_sha256"]
        and existing.get("package_lock_sha256")
        == trust["package_lock_sha256"]
    ):
        _verify_package(target, expected_digest)
        shutil.rmtree(staging)
        return {
            "status": "PASS",
            "result": "unchanged",
            **trust,
        }
    if target.exists():
        old_hash = str(existing.get("skill_sha256") or "unknown")
        backup = state_dir / "backups" / f"rapp-roadside-{old_hash[:16]}"
        if backup.exists():
            shutil.rmtree(staging)
            raise ValueError("preserved prior-version backup already exists")
        backup.parent.mkdir(parents=True, exist_ok=True)
        os.replace(target, backup)
        backup_relative = backup.relative_to(state_dir).as_posix()
    marker = {
        "schema": "rar-managed-skill/1.0",
        "skill_name": "rapp-roadside",
        "display_name": "RAPP Roadside",
        "skill_sha256": lock["skill_sha256"],
        "source_sha256": lock["source_sha256"],
        "package_lock_sha256": trust["package_lock_sha256"],
        "prior_backup": backup_relative,
        "reversible": True,
        "global_lock": False,
        **trust,
    }
    _write_marker(staging, marker)
    try:
        os.replace(staging, target)
    except OSError:
        if backup_relative and not target.exists():
            os.replace(state_dir / backup_relative, target)
        raise
    return {
        "status": "PASS",
        "result": "installed",
        "prior_version_preserved": backup_relative is not None,
        "global_lock": False,
        **trust,
    }


def remove(skills_dir, state_dir):
    skills_dir = skills_dir.resolve()
    state_dir = state_dir.resolve()
    target = skills_dir / "rapp-roadside"
    marker = _marker(target) if target.is_dir() else None
    if marker is None:
        raise ValueError("RAPP Roadside is not a managed local install")
    removed = (
        state_dir
        / "removed"
        / f"rapp-roadside-{str(marker.get('skill_sha256'))[:16]}"
    )
    if removed.exists():
        raise ValueError("preserved removed package already exists")
    removed.parent.mkdir(parents=True, exist_ok=True)
    os.replace(target, removed)
    prior_relative = marker.get("prior_backup")
    restored = False
    if prior_relative:
        prior = _safe_target(state_dir, prior_relative)
        if not prior.is_dir():
            os.replace(removed, target)
            raise ValueError("prior-version backup is missing")
        os.replace(prior, target)
        restored = True
    return {
        "status": "PASS",
        "result": "removed",
        "removed_version_preserved": True,
        "prior_version_restored": restored,
        "global_lock": False,
    }


def verify(skills_dir, catalog_path):
    target = skills_dir.resolve() / "rapp-roadside"
    marker = _marker(target) if target.is_dir() else None
    if marker is None:
        raise ValueError("RAPP Roadside is not a managed local install")
    expected_digest = _catalog_digest(catalog_path)
    lock, trust = _verify_package(target, expected_digest)
    if marker.get("skill_sha256") != lock.get("skill_sha256"):
        raise ValueError("managed marker and package lock disagree")
    if marker.get("package_lock_sha256") != trust["package_lock_sha256"]:
        raise ValueError("managed marker and trusted package lock digest disagree")
    return {
        "status": "PASS",
        "result": "verified",
        "skill_sha256": lock["skill_sha256"],
        "global_lock": False,
        **trust,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["install", "remove", "verify"])
    parser.add_argument("--source")
    parser.add_argument("--skills-dir", required=True)
    parser.add_argument("--state-dir")
    parser.add_argument(
        "--catalog",
        default=os.environ.get("RAPP_ROADSIDE_TRUSTED_CATALOG"),
        help="externally trusted local catalog entry containing the package lock digest",
    )
    args = parser.parse_args(argv)
    skills_dir = Path(args.skills_dir).expanduser()
    state_dir = Path(
        args.state_dir or (skills_dir.parent / ".rapp-roadside-state")
    ).expanduser()
    try:
        if args.operation == "install":
            if not args.source:
                raise ValueError("--source is required for install")
            if not args.catalog:
                raise ValueError("--catalog is required for trusted install")
            result = install(
                Path(args.source).expanduser(),
                skills_dir,
                state_dir,
                Path(args.catalog).expanduser(),
            )
        elif args.operation == "remove":
            result = remove(skills_dir, state_dir)
        else:
            if not args.catalog:
                raise ValueError("--catalog is required for trusted verification")
            result = verify(skills_dir, Path(args.catalog).expanduser())
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": type(error).__name__,
                    "message": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
