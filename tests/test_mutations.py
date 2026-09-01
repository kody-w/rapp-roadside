from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_test_installer_mutations",
    ROOT / "rar_installer_troubleshooter_agent.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PROBE_SPEC = importlib.util.spec_from_file_location(
    "_test_local_probe",
    ROOT / "scripts" / "local_probe.py",
)
PROBE = importlib.util.module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(PROBE)


def synthetic():
    return json.loads(
        (
            ROOT / "fixtures" / "synthetic-slow-setup" / "before.json"
        ).read_text(encoding="utf-8")
    )


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.agent = MODULE.RappRoadsideAgent()

    def perform(self, observations):
        return json.loads(
            self.agent.perform(operation="diagnose", observations=observations)
        )

    def test_sensitive_field_names_are_refused(self):
        for key in (
            "api_key",
            "authorization",
            "credential",
            "oauth_token",
            "password",
            "private_key",
            "secret",
            "session_cookie",
        ):
            with self.subTest(key=key):
                mutated = synthetic()
                mutated[key] = "redacted"
                result = self.perform(mutated)
                self.assertEqual("error", result["status"])
                self.assertFalse(result["credentials_collected"])

    def test_credential_like_values_are_refused(self):
        values = [
            "ghp_" + ("1" * 30),
            "github_" + "pat_" + ("1" * 24),
            "Bearer abcdefghijklmnopqrstuvwxyz",
            "-----BEGIN " + "PRIVATE KEY-----",
        ]
        for value in values:
            with self.subTest(value=value[:12]):
                mutated = synthetic()
                mutated["probe_url"] = value
                result = self.perform(mutated)
                self.assertEqual("error", result["status"])

    def test_non_loopback_urls_are_refused(self):
        mutated = synthetic()
        mutated["probe_url"] = "https://example.invalid/setup"
        result = self.perform(mutated)
        self.assertEqual("error", result["status"])

    def test_loopback_url_text_is_allowed(self):
        mutated = synthetic()
        mutated["probe_url"] = "http://127.0.0.1:7071/chat"
        result = self.perform(mutated)
        self.assertEqual("slow-first-boot-progressing", result["finding"]["code"])

    def test_external_network_observation_is_blocked_first(self):
        mutated = synthetic()
        mutated["safety"]["external_network_observed"] = True
        result = self.perform(mutated)
        self.assertEqual("external-network-observed", result["finding"]["code"])
        self.assertEqual(
            "recollect-local-only-observation", result["next_action"]["id"]
        )

    def test_grail_mutation_is_blocked(self):
        mutated = synthetic()
        mutated["safety"]["grail_modified"] = True
        result = self.perform(mutated)
        self.assertEqual("grail-change-refused", result["finding"]["code"])
        self.assertIn("handoff", result["next_action"]["id"])

    def test_direct_main_mutation_is_blocked(self):
        mutated = synthetic()
        mutated["repository"]["direct_main_change_requested"] = True
        result = self.perform(mutated)
        self.assertEqual("direct-main-change-refused", result["finding"]["code"])
        self.assertEqual("RAPP Pit Crew", result["maintainer_handoff"]["system"])
        self.assertIn("direct push to main", result["maintainer_handoff"]["forbidden"])

    def test_python_mutations_route_to_python_check(self):
        for version in ("2.7.18", "3.9.19", "3.10.14", "bad"):
            with self.subTest(version=version):
                mutated = synthetic()
                mutated["python"]["version"] = version
                result = self.perform(mutated)
                self.assertEqual("python-3-11-required", result["finding"]["code"])

    def test_stage_mutation_past_bound_escalates_once(self):
        mutated = synthetic()
        mutated["setup_elapsed_seconds"] = 181
        result = self.perform(mutated)
        self.assertEqual(
            "brainstem-not-ready-after-bound", result["finding"]["code"]
        )
        self.assertEqual([], result["next_action"]["alternatives"])

    def test_chat_request_field_mutation_is_detected(self):
        mutated = json.loads(
            (
                ROOT / "fixtures" / "synthetic-slow-setup" / "after.json"
            ).read_text(encoding="utf-8")
        )
        mutated["chat"]["request_field"] = "messages"
        result = self.perform(mutated)
        self.assertEqual(
            "post-chat-contract-not-proven", result["finding"]["code"]
        )

    def test_missing_response_key_mutations_are_detected(self):
        after = json.loads(
            (
                ROOT / "fixtures" / "synthetic-slow-setup" / "after.json"
            ).read_text(encoding="utf-8")
        )
        for key in ("response", "agent_logs", "session_id"):
            with self.subTest(key=key):
                mutated = deepcopy(after)
                mutated["chat"]["response_keys"].remove(key)
                result = self.perform(mutated)
                self.assertEqual(
                    "post-chat-contract-not-proven", result["finding"]["code"]
                )

    def test_platform_aliases_are_stable(self):
        expected = {"darwin": "macos", "win32": "windows", "linux": "linux"}
        for alias, normalized in expected.items():
            with self.subTest(alias=alias):
                mutated = synthetic()
                mutated["platform"] = alias
                result = self.perform(mutated)
                self.assertEqual(normalized, result["platform"])

    def test_invalid_platform_is_refused(self):
        mutated = synthetic()
        mutated["platform"] = "plan9"
        result = self.perform(mutated)
        self.assertEqual("error", result["status"])

    def test_local_probe_rejects_non_loopback_hosts(self):
        for url in (
            "https://127.0.0.1:7071",
            "http://example.invalid",
            "http://user:pass@localhost:7071",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    PROBE._loopback_url(url)

    def test_local_probe_accepts_plain_http_loopback(self):
        self.assertEqual(
            "http://127.0.0.1:7071",
            PROBE._loopback_url("http://127.0.0.1:7071"),
        )


if __name__ == "__main__":
    unittest.main()
