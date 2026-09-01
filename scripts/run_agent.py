#!/usr/bin/env python3
"""Checksum-gated runner for the canonical troubleshooting agent."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "rapp" / "agent.lock.json"
AGENT_PATH = ROOT / "rar_installer_troubleshooter_agent.py"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_lock():
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if lock.get("schema") != "rapp-agent-lock/1.0":
        raise RuntimeError("agent lock has the wrong schema")
    if lock.get("agent") != AGENT_PATH.name:
        raise RuntimeError("agent lock points to a different file")
    actual = _sha256(AGENT_PATH)
    if actual != lock.get("sha256"):
        raise RuntimeError(
            f"canonical agent checksum mismatch: {actual} != {lock.get('sha256')}"
        )
    return lock


def _load_agent():
    _load_lock()
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
    args = parser.parse_args(argv)
    try:
        lock = _load_lock()
        if args.preflight:
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "agent": AGENT_PATH.name,
                        "sha256": lock["sha256"],
                        "python": sys.version.split()[0],
                        "network": "none",
                        "credentials": "not accepted",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        agent = _load_agent()
        if args.tool:
            print(json.dumps(agent.to_tool(), indent=2, sort_keys=True))
            return 0
        raw = args.json if args.json is not None else sys.stdin.read()
        arguments = json.loads(raw.strip() or "{}")
        if not isinstance(arguments, dict):
            raise TypeError("arguments must be one JSON object")
        print(agent.perform(**arguments))
        return 0
    except (OSError, RuntimeError, TypeError, json.JSONDecodeError) as error:
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
