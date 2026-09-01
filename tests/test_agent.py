from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_test_installer_troubleshooter",
    ROOT / "rar_installer_troubleshooter_agent.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def load_fixture(name, file_name="before.json"):
    return json.loads(
        (ROOT / "fixtures" / name / file_name).read_text(encoding="utf-8")
    )


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.agent = MODULE.RappRoadsideAgent()

    def perform(self, payload):
        return json.loads(self.agent.perform(**payload))

    def test_capability_is_local_and_copy_only(self):
        result = self.perform({"operation": "capability"})
        self.assertEqual("ok", result["status"])
        self.assertFalse(result["safety"]["credentials_collected"])
        self.assertFalse(result["safety"]["source_writes"])
        self.assertEqual("/chat", result["wire"]["path"])
        self.assertEqual("RAPP Roadside", result["display_name"])
        self.assertEqual("RAPP Pit Crew", result["maintainer_system"])
        self.assertEqual("Roadside Frame", result["machine_issue_artifact"])

    def test_synthetic_report_is_byte_deterministic(self):
        before = load_fixture("synthetic-slow-setup")
        first = self.agent.perform(operation="diagnose", observations=before)
        second = self.agent.perform(operation="diagnose", observations=before)
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual("slow-first-boot-progressing", report["finding"]["code"])
        self.assertEqual(
            "bounded-wait-and-local-retest", report["next_action"]["id"]
        )
        self.assertEqual(150, report["next_action"]["timeout_seconds"])
        self.assertEqual([], report["next_action"]["alternatives"])
        self.assertIn("--allow-loopback", report["next_action"]["command_argv"])
        self.assertEqual("RAPP Roadside", report["support_system"])
        self.assertEqual(
            "RAPP Pit Crew", report["maintainer_handoff"]["system"]
        )

    def test_synthetic_matches_expected_report_when_generated(self):
        expected_path = (
            ROOT / "fixtures" / "synthetic-slow-setup" / "expected-report.json"
        )
        if not expected_path.is_file():
            self.skipTest("expected report is generated after bootstrap forge")
        actual = self.perform(
            {
                "operation": "diagnose",
                "observations": load_fixture("synthetic-slow-setup"),
            }
        )
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        self.assertEqual(expected, actual)

    def test_synthetic_exact_retest_passes(self):
        before = load_fixture("synthetic-slow-setup")
        after = load_fixture("synthetic-slow-setup", "after.json")
        report = self.perform({"operation": "diagnose", "observations": before})
        retest = self.perform(
            {
                "operation": "retest",
                "diagnosis": report,
                "observations": after,
            }
        )
        self.assertEqual("PASS", retest["status"])
        self.assertGreaterEqual(len(retest["assertions"]), 20)
        self.assertTrue(all(item["passed"] for item in retest["assertions"]))

    def test_retest_fails_without_post_chat_envelope(self):
        before = load_fixture("synthetic-slow-setup")
        after = load_fixture("synthetic-slow-setup", "after.json")
        after["chat"]["response_keys"].remove("session_id")
        report = self.perform({"operation": "diagnose", "observations": before})
        retest = self.perform(
            {
                "operation": "retest",
                "diagnosis": report,
                "observations": after,
            }
        )
        self.assertEqual("FAIL", retest["status"])

    def test_linux_launcher_mode_action(self):
        report = self.perform(
            {
                "operation": "diagnose",
                "observations": load_fixture("linux-launcher-mode"),
            }
        )
        self.assertEqual("launcher-not-executable", report["finding"]["code"])
        self.assertEqual(
            "restore-launcher-executable-copy", report["next_action"]["id"]
        )

    def test_macos_installer_mirror_action(self):
        report = self.perform(
            {
                "operation": "diagnose",
                "observations": load_fixture("macos-installer-drift"),
            }
        )
        self.assertEqual("installer-mirror-drift", report["finding"]["code"])
        self.assertEqual(
            "synchronize-installer-mirrors-copy",
            report["next_action"]["id"],
        )

    def test_windows_post_chat_action(self):
        report = self.perform(
            {
                "operation": "diagnose",
                "observations": load_fixture("windows-post-chat"),
            }
        )
        self.assertEqual(
            "post-chat-contract-not-proven", report["finding"]["code"]
        )
        self.assertEqual(
            ["py", "-3"], report["next_action"]["command_argv"][:2]
        )

    def test_proven_setup_archives_only_local_evidence(self):
        report = self.perform(
            {
                "operation": "diagnose",
                "observations": load_fixture("synthetic-slow-setup", "after.json"),
            }
        )
        self.assertEqual("local-setup-proven", report["finding"]["code"])
        self.assertEqual("archive-local-evidence", report["next_action"]["id"])
        self.assertFalse(report["privacy"]["external_network_used"])


class CopyRepairTests(unittest.TestCase):
    def setUp(self):
        self.agent = MODULE.RappRoadsideAgent()
        self.work = ROOT / "tests" / ".work"
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir()

    def tearDown(self):
        if self.work.exists():
            shutil.rmtree(self.work)

    def perform(self, payload):
        return json.loads(self.agent.perform(**payload))

    def approval(self, action_id, source, destination):
        return {
            "human_approved": True,
            "action_id": action_id,
            "source_fingerprint": MODULE._tree_fingerprint(source.resolve()),
            "copy_target_sha256": MODULE._copy_target_hash(destination.resolve()),
            "reversible": True,
            "activation": "copy-only-no-activation",
        }

    def source_tree(self):
        source = self.work / "source"
        (source / "installer").mkdir(parents=True)
        (source / "docs").mkdir()
        (source / "safe.py").write_text("print('safe')\n", encoding="utf-8")
        (source / ".env").write_text("VALUE=not-copied\n", encoding="utf-8")
        (source / "private-key.pem").write_text("not-copied\n", encoding="utf-8")
        (source / "start.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (source / "installer" / "brainstem").write_text(
            "#!/bin/sh\nexit 0\n", encoding="utf-8"
        )
        for filename in ("install.sh", "install.ps1", "install.cmd"):
            (source / filename).write_text(f"root-{filename}\n", encoding="utf-8")
            (source / "docs" / filename).write_text(
                f"drift-{filename}\n", encoding="utf-8"
            )
        return source

    def test_executable_fix_changes_copy_not_source(self):
        source = self.source_tree()
        source_mode = source.joinpath("start.sh").stat().st_mode
        source.joinpath("start.sh").chmod(source_mode & ~stat.S_IXUSR)
        destination = self.work / "copy"
        action_id = "restore-launcher-executable-copy"
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": action_id,
                "source_dir": str(source),
                "copy_dir": str(destination),
                "approval": self.approval(action_id, source, destination),
            }
        )
        self.assertEqual("PASS", result["status"])
        self.assertFalse(source.joinpath("start.sh").stat().st_mode & stat.S_IXUSR)
        self.assertTrue(destination.joinpath("start.sh").stat().st_mode & stat.S_IXUSR)
        self.assertFalse(destination.joinpath(".env").exists())
        self.assertFalse(destination.joinpath("private-key.pem").exists())
        self.assertTrue(result["source_modified"] is False)
        self.assertNotIn("source_dir", result)
        self.assertNotIn("copy_dir", result)
        self.assertTrue(result["human_approved"])
        self.assertTrue(result["rollback"]["required"])

    def test_mirror_fix_is_byte_exact_in_copy(self):
        source = self.source_tree()
        destination = self.work / "copy"
        action_id = "synchronize-installer-mirrors-copy"
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": action_id,
                "source_dir": str(source),
                "copy_dir": str(destination),
                "approval": self.approval(action_id, source, destination),
            }
        )
        self.assertEqual("PASS", result["status"])
        for filename in ("install.sh", "install.ps1", "install.cmd"):
            self.assertEqual(
                destination.joinpath(filename).read_bytes(),
                destination.joinpath("docs", filename).read_bytes(),
            )
            self.assertNotEqual(
                source.joinpath(filename).read_bytes(),
                source.joinpath("docs", filename).read_bytes(),
            )

    def test_windows_launcher_normalization_is_crlf_in_copy(self):
        source = self.source_tree()
        destination = self.work / "copy"
        action_id = "normalize-windows-launchers-copy"
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": action_id,
                "source_dir": str(source),
                "copy_dir": str(destination),
                "approval": self.approval(action_id, source, destination),
            }
        )
        self.assertEqual("PASS", result["status"])
        self.assertIn(b"\r\n", destination.joinpath("install.cmd").read_bytes())
        self.assertNotIn(b"\r\n", source.joinpath("install.cmd").read_bytes())

    def test_unlisted_fix_is_refused(self):
        source = self.source_tree()
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": "rewrite-grail",
                "source_dir": str(source),
                "copy_dir": str(self.work / "copy"),
            }
        )
        self.assertEqual("error", result["status"])
        self.assertFalse((self.work / "copy").exists())

    def test_copy_inside_source_is_refused(self):
        source = self.source_tree()
        destination = source / "copy"
        action_id = "restore-launcher-executable-copy"
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": action_id,
                "source_dir": str(source),
                "copy_dir": str(destination),
                "approval": self.approval(action_id, source, destination),
            }
        )
        self.assertEqual("error", result["status"])
        self.assertFalse((source / "copy").exists())

    def test_symlink_is_excluded(self):
        source = self.source_tree()
        symlink = source / "linked.py"
        try:
            symlink.symlink_to(source / "safe.py")
        except OSError:
            self.skipTest("symlinks unavailable")
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": "restore-launcher-files-copy",
                "source_dir": str(source),
                "copy_dir": str(self.work / "copy"),
                "approval": self.approval(
                    "restore-launcher-files-copy",
                    source,
                    self.work / "copy",
                ),
            }
        )
        self.assertEqual("PASS", result["status"])
        self.assertFalse((self.work / "copy" / "linked.py").exists())
        self.assertIn("linked.py", result["excluded_paths"])

    def test_copy_repair_requires_bound_human_approval(self):
        source = self.source_tree()
        destination = self.work / "copy"
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": "restore-launcher-executable-copy",
                "source_dir": str(source),
                "copy_dir": str(destination),
            }
        )
        self.assertEqual("error", result["status"])
        self.assertIn("human approval", result["message"])
        self.assertFalse(destination.exists())

    def test_prepare_repair_emits_unapproved_exact_binding(self):
        source = self.source_tree()
        destination = self.work / "copy"
        result = self.perform(
            {
                "operation": "prepare_repair",
                "action_id": "restore-launcher-executable-copy",
                "source_dir": str(source),
                "copy_dir": str(destination),
            }
        )
        self.assertEqual("approval-required", result["status"])
        self.assertFalse(result["approval"]["human_approved"])
        self.assertEqual(
            MODULE._tree_fingerprint(source.resolve()),
            result["approval"]["source_fingerprint"],
        )
        self.assertEqual(
            MODULE._copy_target_hash(destination.resolve()),
            result["approval"]["copy_target_sha256"],
        )
        self.assertFalse(result["source_path_exported"])
        self.assertFalse(result["copy_path_exported"])

    def test_wrong_source_approval_is_refused(self):
        source = self.source_tree()
        destination = self.work / "copy"
        approval = self.approval(
            "restore-launcher-executable-copy", source, destination
        )
        approval["source_fingerprint"] = "0" * 64
        result = self.perform(
            {
                "operation": "fix_copy",
                "action_id": "restore-launcher-executable-copy",
                "source_dir": str(source),
                "copy_dir": str(destination),
                "approval": approval,
            }
        )
        self.assertEqual("error", result["status"])
        self.assertFalse(destination.exists())


class PackageTests(unittest.TestCase):
    def test_legacy_agent_class_alias_is_preserved(self):
        self.assertIs(
            MODULE.RarInstallerTroubleshooterAgent,
            MODULE.RappRoadsideAgent,
        )

    def test_canonical_names_and_protocol_ids_coexist(self):
        manifest = json.loads(
            (ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual("rapp-roadside", manifest["skill_name"])
        self.assertEqual("RAPP Roadside", manifest["display_name"])
        self.assertEqual("RAPP Pit Crew", manifest["maintainer_system"])
        self.assertEqual("Roadside Frame", manifest["machine_issue_artifact"])
        self.assertTrue(manifest["protocol_identity_retained"])
        self.assertIn(
            "/rar-installer-troubleshooter:",
            manifest["identity"],
        )

    def test_runner_preflight_verifies_lock(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_agent.py"), "--preflight"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("PASS", json.loads(result.stdout)["status"])

    def test_package_lock_records_are_current(self):
        lock = json.loads(
            (ROOT / "rapp" / "package.lock.json").read_text(encoding="utf-8")
        )
        for record in lock["files"]:
            path = ROOT / record["path"]
            self.assertEqual(
                record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
            )

    def test_all_json_artifacts_parse(self):
        for path in ROOT.rglob("*.json"):
            if "export" in path.parts or ".work" in path.parts:
                continue
            with self.subTest(path=path):
                json.loads(path.read_text(encoding="utf-8"))

    def test_canonical_html_is_self_contained(self):
        html = (ROOT / "canonical.html").read_text(encoding="utf-8")
        self.assertIn("Copilot CLI", html)
        self.assertIn("Claude Code", html)
        self.assertIn("Scout", html)
        self.assertIn("Cowork", html)
        self.assertIn("RAPP Roadside", html)
        self.assertIn("RAPP Pit Crew", html)
        self.assertIn("Roadside Frame", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("<link rel=", html)


if __name__ == "__main__":
    unittest.main()
