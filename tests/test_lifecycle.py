from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_test_rapp_roadside_lifecycle",
    ROOT / "scripts" / "rar_lifecycle.py",
)
LIFECYCLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIFECYCLE)


class ReversibleLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.work = ROOT / "tests" / ".work-lifecycle"
        if self.work.exists():
            shutil.rmtree(self.work)
        self.skills = self.work / "skills"
        self.state = self.work / "state"
        self.work.mkdir()
        self.catalog = self.work / "catalog-entry.json"
        self.catalog.write_text(
            json.dumps(
                {
                    "schema": "rapp-roadside-catalog-entry/1.0",
                    "skill_name": "rapp-roadside",
                    "package_lock_sha256": hashlib.sha256(
                        (ROOT / "rapp" / "package.lock.json").read_bytes()
                    ).hexdigest(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.work.exists():
            shutil.rmtree(self.work)

    def test_fresh_install_verify_remove_preserves_removed_bytes(self):
        installed = LIFECYCLE.install(
            ROOT, self.skills, self.state, self.catalog
        )
        self.assertEqual("PASS", installed["status"])
        self.assertTrue(installed["trusted_authenticity"])
        self.assertFalse(installed["global_lock"])
        verified = LIFECYCLE.verify(self.skills, self.catalog)
        self.assertEqual("PASS", verified["status"])
        self.assertTrue(verified["trusted_authenticity"])
        removed = LIFECYCLE.remove(self.skills, self.state)
        self.assertEqual("PASS", removed["status"])
        self.assertTrue(removed["removed_version_preserved"])
        self.assertFalse((self.skills / "rapp-roadside").exists())
        self.assertTrue(any((self.state / "removed").iterdir()))

    def test_prior_managed_version_is_restored_on_remove(self):
        target = self.skills / "rapp-roadside"
        target.mkdir(parents=True)
        (target / "old.txt").write_text("prior version\n", encoding="utf-8")
        (target / ".rar-managed.json").write_text(
            json.dumps(
                {
                    "schema": "rar-managed-skill/1.0",
                    "skill_name": "rapp-roadside",
                    "skill_sha256": "1" * 64,
                }
            ),
            encoding="utf-8",
        )
        installed = LIFECYCLE.install(
            ROOT, self.skills, self.state, self.catalog
        )
        self.assertTrue(installed["prior_version_preserved"])
        removed = LIFECYCLE.remove(self.skills, self.state)
        self.assertTrue(removed["prior_version_restored"])
        self.assertEqual(
            "prior version\n",
            (self.skills / "rapp-roadside" / "old.txt").read_text(
                encoding="utf-8"
            ),
        )

    def test_unmanaged_target_is_never_overwritten(self):
        target = self.skills / "rapp-roadside"
        target.mkdir(parents=True)
        (target / "user-file.txt").write_text("keep\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            LIFECYCLE.install(ROOT, self.skills, self.state, self.catalog)
        self.assertEqual(
            "keep\n", (target / "user-file.txt").read_text(encoding="utf-8")
        )

    def test_tampered_managed_install_fails_verification(self):
        LIFECYCLE.install(ROOT, self.skills, self.state, self.catalog)
        target = self.skills / "rapp-roadside"
        (target / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "drift"):
            LIFECYCLE.verify(self.skills, self.catalog)
        with self.assertRaisesRegex(ValueError, "drift"):
            LIFECYCLE.install(ROOT, self.skills, self.state, self.catalog)

    def test_unpinned_package_check_reports_unauthenticated_origin(self):
        _, trust = LIFECYCLE._verify_package(ROOT)
        self.assertEqual("internally-consistent", trust["integrity"])
        self.assertEqual("unauthenticated", trust["origin_status"])
        self.assertFalse(trust["trusted_authenticity"])

    def test_wrong_catalog_digest_blocks_install(self):
        payload = json.loads(self.catalog.read_text(encoding="utf-8"))
        payload["package_lock_sha256"] = "0" * 64
        self.catalog.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "trusted catalog"):
            LIFECYCLE.install(ROOT, self.skills, self.state, self.catalog)

    def test_lifecycle_manifest_has_no_network_or_global_lock(self):
        manifest = json.loads(
            (ROOT / "rapp" / "lifecycle.json").read_text(encoding="utf-8")
        )
        self.assertFalse(manifest["network"])
        self.assertFalse(manifest["global_lock"])
        self.assertTrue(manifest["install"]["prior_version_preserved"])
        self.assertTrue(manifest["remove"]["removed_version_preserved"])


if __name__ == "__main__":
    unittest.main()
