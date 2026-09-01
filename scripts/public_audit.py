#!/usr/bin/env python3
"""Audit a RAPP Roadside tree for public-release safety."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


PRIVATE_PATHS = [
    re.compile(r"/" + r"Users/[^\s\"']+"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\s\"']+"),
]
SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_" + r"pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN " + r"(?:[A-Z ]+ )?PRIVATE KEY-----"),
]
EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    ".fresh-clone-check",
    ".runtime",
    "export",
}


def _files(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(
            part in EXCLUDED_PARTS or part.startswith(".work")
            for part in relative.parts
        ):
            continue
        yield path, relative


def audit(root):
    failures = []
    required = {
        "LICENSE",
        "PRIVACY.md",
        "SECURITY.md",
        "SKILL.md",
        "README.md",
        "docs/CROSS-AGENT.md",
        "share with kody.md",
        "rapp/agent.lock.json",
        "rapp/closed-loop.json",
        "rapp/package.lock.json",
        "scripts/extract_roadside_frame.py",
    }
    present = {relative.as_posix() for _, relative in _files(root)}
    for relative in sorted(required - present):
        failures.append(f"missing:{relative}")
    for path, relative in _files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in PRIVATE_PATHS:
            if pattern.search(text):
                failures.append(f"private-path:{relative}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"secret-pattern:{relative}")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in license_text or "Copyright (c) 2026 kody-w" not in license_text:
        failures.append("license")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("repository") != "https://github.com/kody-w/rapp-roadside"
        or manifest.get("license") != "MIT"
        or manifest.get("copyright") != "2026 kody-w"
        or manifest.get("telemetry") is not False
        or manifest.get("network_default") is not False
    ):
        failures.append("public-manifest")
    agent_tree = ast.parse(
        (root / "rar_installer_troubleshooter_agent.py").read_text(
            encoding="utf-8"
        )
    )
    imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(agent_tree)
        if isinstance(node, ast.Import) and node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(agent_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    if imports.intersection({"http", "requests", "socket", "urllib"}):
        failures.append("canonical-agent-network-import")
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    for host in (
        "Copilot CLI",
        "Claude Code",
        "Microsoft Scout",
        "Microsoft Copilot Cowork",
        "OpenClaw",
        "Generic skill-aware",
    ):
        if host not in skill and host not in (
            root / "docs" / "CROSS-AGENT.md"
        ).read_text(encoding="utf-8"):
            failures.append(f"cross-agent:{host}")
    return sorted(set(failures))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=".")
    args = parser.parse_args(argv)
    root = Path(args.path).expanduser().resolve()
    failures = audit(root)
    print(
        json.dumps(
            {
                "status": "PASS" if not failures else "FAIL",
                "failures": failures,
                "telemetry": False,
                "network_used": False,
                "uploads": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
