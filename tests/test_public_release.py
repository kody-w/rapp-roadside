from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseTests(unittest.TestCase):
    def test_mit_license_and_copyright(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", text)
        self.assertIn("Copyright (c) 2026 kody-w", text)

    def test_public_manifest_has_no_telemetry_or_default_network(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            "https://github.com/kody-w/rapp-roadside",
            manifest["repository"],
        )
        self.assertEqual("MIT", manifest["license"])
        self.assertEqual("2026 kody-w", manifest["copyright"])
        self.assertFalse(manifest["telemetry"])
        self.assertFalse(manifest["network_default"])
        self.assertEqual("voluntary", manifest["participation"])

    def test_cross_agent_instructions_cover_all_hosts(self):
        text = (ROOT / "docs" / "CROSS-AGENT.md").read_text(encoding="utf-8")
        for host in (
            "GitHub Copilot CLI",
            "Claude Code",
            "Microsoft Scout",
            "Microsoft Copilot Cowork",
            "OpenClaw",
            "Generic skill-aware or CLI agent",
        ):
            with self.subTest(host=host):
                self.assertIn(host, text)

    def test_public_content_audit_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/public_audit.py", "--path", "."],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("PASS", json.loads(result.stdout)["status"])

    def test_fresh_clone_smoke_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/test_fresh_clone.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertFalse(payload["network_used"])
        self.assertFalse(payload["telemetry"])

    def test_public_audit_contains_no_embedded_restricted_name_dictionary(self):
        source = (ROOT / "scripts" / "public_audit.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("BUSINESS_TERMS", source)
        self.assertNotIn("business-term:", source)


if __name__ == "__main__":
    unittest.main()
