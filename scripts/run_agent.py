#!/usr/bin/env python3
"""Checksum-gated runner for the canonical troubleshooting agent."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "rapp" / "agent.lock.json"
AGENT_PATH = ROOT / "rar_installer_troubleshooter_agent.py"
HASH64 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_digest(value):
    digest = str(
        value
        or os.environ.get("RAPP_ROADSIDE_EXPECTED_AGENT_LOCK_SHA256")
        or ""
    ).strip().lower()
    if digest and not HASH64.fullmatch(digest):
        raise ValueError("expected agent lock digest must be 64 lowercase hex characters")
    return digest or None


def _load_lock(expected_lock_sha256=None):
    lock_bytes = LOCK_PATH.read_bytes()
    lock_digest = hashlib.sha256(lock_bytes).hexdigest()
    expected = _expected_digest(expected_lock_sha256)
    if expected is not None and lock_digest != expected:
        raise RuntimeError(
            f"agent lock digest mismatch: {lock_digest} != {expected}"
        )
    lock = json.loads(lock_bytes.decode("utf-8"))
    if lock.get("schema") != "rapp-agent-lock/1.0":
        raise RuntimeError("agent lock has the wrong schema")
    if lock.get("agent") != AGENT_PATH.name:
        raise RuntimeError("agent lock points to a different file")
    actual = _sha256(AGENT_PATH)
    if actual != lock.get("sha256"):
        raise RuntimeError(
            f"canonical agent checksum mismatch: {actual} != {lock.get('sha256')}"
        )
    return lock, {
        "trusted": expected is not None,
        "origin_status": (
            "externally-pinned" if expected is not None else "unauthenticated"
        ),
        "lock_sha256": lock_digest,
    }


def _load_agent(expected_lock_sha256=None):
    _load_lock(expected_lock_sha256)
    spec = importlib.util.spec_from_file_location(
        "_rar_installer_troubleshooter_locked",
        AGENT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the canonical agent")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module.RappRoadsideAgent()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--tool", action="store_true")
    parser.add_argument("--json")
    parser.add_argument("--expected-lock-sha256")
    args = parser.parse_args(argv)
    try:
        lock, trust = _load_lock(args.expected_lock_sha256)
        if args.preflight:
            print(
                json.dumps(
                    {
                        "status": "PASS" if trust["trusted"] else "CONSISTENT",
                        "agent": AGENT_PATH.name,
                        "sha256": lock["sha256"],
                        "lock_sha256": trust["lock_sha256"],
                        "integrity": "internally-consistent",
                        "origin_status": trust["origin_status"],
                        "trusted_authenticity": trust["trusted"],
                        "python": sys.version.split()[0],
                        "network": "none",
                        "credentials": "not accepted",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        agent = _load_agent(args.expected_lock_sha256)
        if args.tool:
            print(json.dumps(agent.to_tool(), indent=2, sort_keys=True))
            return 0
        raw = args.json if args.json is not None else sys.stdin.read()
        arguments = json.loads(raw.strip() or "{}")
        if not isinstance(arguments, dict):
            raise TypeError("arguments must be one JSON object")
        print(agent.perform(**arguments))
        return 0
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
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
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
