#!/usr/bin/env python3
"""Local Skill Forge acceptance gate for RAPP Roadside."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "SKILL.md",
    "LICENSE",
    "PRIVACY.md",
    "SECURITY.md",
    "rar_installer_troubleshooter_agent.py",
    "scripts/run_agent.py",
    "scripts/hash_attachment.py",
    "scripts/extract_roadside_frame.py",
    "scripts/local_probe.py",
    "scripts/quarantine_report.py",
    "scripts/public_audit.py",
    "scripts/rar_lifecycle.py",
    "scripts/test_fresh_clone.py",
    "rapp/agent.lock.json",
    "rapp/package.lock.json",
    "rapp/capability.json",
    "rapp/closed-loop.json",
    "rapp/lifecycle.json",
    "manifest.json",
    "rapp/manifest.json",
    "toasted/manifest.json",
    "canonical.html",
    "docs/CROSS-AGENT.md",
    "schemas/agent-input.schema.json",
    "schemas/observation.schema.json",
    "schemas/report.schema.json",
    "schemas/issue.schema.json",
    "schemas/roadside-frame.schema.json",
    "schemas/rev-13-frame.schema.json",
    "fixtures/synthetic-slow-setup/before.json",
    "fixtures/synthetic-slow-setup/after.json",
    "companion/PLAYBOOK.md",
    "teams-sharing-instructions.md",
    "unknown-unknowns-coverage.json",
]


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_agent(arguments):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_agent.py"),
            "--json",
            json.dumps(arguments, separators=(",", ":"), sort_keys=True),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout or result.stderr)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("runner returned non-object JSON")
    return payload


def _check(condition, name, failures, passes):
    (passes if condition else failures).append(name)


def _frame_hashes_valid(frame):
    canonical = lambda value: json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    particle = hashlib.sha256(
        b"rapp/1:particle\n" + canonical(frame["payload"])
    ).hexdigest()
    wave_input = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    wave = hashlib.sha256(
        b"rapp/1:wave\n" + canonical(wave_input)
    ).hexdigest()
    return frame["payload_hash"] == particle and frame["frame_hash"] == wave


def main(argv=None):
    final = "--final" in (argv or sys.argv[1:])
    failures = []
    passes = []
    for relative in REQUIRED:
        _check((ROOT / relative).is_file(), f"required:{relative}", failures, passes)

    try:
        lock = json.loads(
            (ROOT / "rapp" / "agent.lock.json").read_text(encoding="utf-8")
        )
        _check(
            lock.get("sha256")
            == _sha256(ROOT / "rar_installer_troubleshooter_agent.py"),
            "agent-lock",
            failures,
            passes,
        )
    except (OSError, json.JSONDecodeError):
        failures.append("agent-lock")

    for relative in (
        "manifest.json",
        "rapp/manifest.json",
        "toasted/manifest.json",
    ):
        try:
            payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            _check("PENDING" not in json.dumps(payload), f"resolved:{relative}", failures, passes)
        except (OSError, json.JSONDecodeError):
            failures.append(f"json:{relative}")

    try:
        candidate_manifest = json.loads(
            (ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        _check(
            candidate_manifest.get("skill_name") == "rapp-roadside"
            and candidate_manifest.get("display_name") == "RAPP Roadside"
            and candidate_manifest.get("maintainer_system") == "RAPP Pit Crew"
            and candidate_manifest.get("machine_issue_artifact")
            == "Roadside Frame"
            and candidate_manifest.get("protocol_identity_retained") is True,
            "canonical-naming-metadata",
            failures,
            passes,
        )
        _check(
            candidate_manifest.get("repository")
            == "https://github.com/kody-w/rapp-roadside"
            and candidate_manifest.get("license") == "MIT"
            and candidate_manifest.get("copyright") == "2026 kody-w"
            and candidate_manifest.get("telemetry") is False
            and candidate_manifest.get("network_default") is False,
            "public-release-metadata",
            failures,
            passes,
        )
    except (OSError, json.JSONDecodeError):
        failures.append("canonical-naming-metadata")

    try:
        coverage = json.loads(
            (ROOT / "unknown-unknowns-coverage.json").read_text(
                encoding="utf-8"
            )
        )
        domain_ids = [item.get("id") for item in coverage.get("domains", [])]
        _check(
            domain_ids
            == [
                "01-untrusted-reporting-ai",
                "02-secret-privacy-rights-leakage",
                "03-destructive-or-wrong-repair",
                "04-environmental-unknowns",
                "05-version-ring-and-supply-chain-drift",
                "06-nonreproducible-user-evidence",
                "07-support-frame-spam-replay-and-poisoning",
                "08-fix-regression-and-main-release-risk",
                "09-distribution-and-skill-lifecycle",
                "10-scale-cost-and-coordination",
            ],
            "unknown-unknown-domain-map",
            failures,
            passes,
        )
        scaling = coverage.get("scaling", {})
        _check(
            scaling.get("unbounded_or_infinite_claim") is False
            and scaling.get("global_lock") is False
            and scaling.get("global_raw_data_store") is False
            and "horizontal-cellular" in str(scaling.get("claim")),
            "bounded-cellular-scaling-claim",
            failures,
            passes,
        )
    except (OSError, json.JSONDecodeError):
        failures.append("unknown-unknown-domain-map")

    for path in sorted((ROOT / "schemas").glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            passes.append(f"schema-json:{path.name}")
        except json.JSONDecodeError:
            failures.append(f"schema-json:{path.name}")

    try:
        tree = ast.parse(
            (ROOT / "rar_installer_troubleshooter_agent.py").read_text(
                encoding="utf-8"
            )
        )
        imported = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import) and node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        _check(
            not imported.intersection(
                {"http", "requests", "socket", "subprocess", "urllib"}
            ),
            "canonical-agent-no-network",
            failures,
            passes,
        )
    except (OSError, SyntaxError):
        failures.append("canonical-agent-parse")

    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for needle in (
        "one bounded next action",
        "Never ask for, accept, print, copy",
        "POST /chat",
        "isolated feature/fix worktree",
        "Never push directly to main",
        "Parent RAR review owns publication",
        "RAPP Roadside",
        "RAPP Pit Crew",
        "toaster:generated:begin",
    ):
        _check(needle in skill_text, f"skill-contract:{needle}", failures, passes)

    before = json.loads(
        (ROOT / "fixtures" / "synthetic-slow-setup" / "before.json").read_text(
            encoding="utf-8"
        )
    )
    after = json.loads(
        (ROOT / "fixtures" / "synthetic-slow-setup" / "after.json").read_text(
            encoding="utf-8"
        )
    )
    first = _run_agent({"operation": "diagnose", "observations": before})
    second = _run_agent({"operation": "diagnose", "observations": before})
    _check(first == second, "synthetic-fixture-deterministic", failures, passes)
    _check(
        first.get("finding", {}).get("code") == "slow-first-boot-progressing",
        "synthetic-fixture-finding",
        failures,
        passes,
    )
    _check(
        first.get("next_action", {}).get("id")
        == "bounded-wait-and-local-retest",
        "synthetic-fixture-one-action",
        failures,
        passes,
    )
    _check(
        first.get("next_action", {}).get("timeout_seconds") == 150
        and first.get("next_action", {}).get("alternatives") == [],
        "bounded-action",
        failures,
        passes,
    )
    retest = _run_agent(
        {"operation": "retest", "diagnosis": first, "observations": after}
    )
    _check(
        retest.get("status") == "PASS",
        "synthetic-fixture-exact-retest",
        failures,
        passes,
    )
    _check(
        first.get("invariants", {}).get("wire", {}).get("path") == "/chat"
        and first.get("invariants", {}).get("grail_modified") is False,
        "grail-wire-preserved",
        failures,
        passes,
    )
    _check(
        first.get("support_system") == "RAPP Roadside"
        and first.get("machine_issue_artifact") == "Roadside Frame"
        and first.get("maintainer_handoff", {}).get("system")
        == "RAPP Pit Crew",
        "canonical-naming-report",
        failures,
        passes,
    )
    _check(
        first.get("evidence_partition", {}).get(
            "embedded_instructions_executed"
        )
        is False
        and first.get("evidence_partition", {}).get(
            "raw_reporting_ai_text_or_logs_retained"
        )
        is False
        and first.get("byte_bindings", {}).get("exact") is True
        and first.get("replay_manifest", {}).get("reported") is True
        and first.get("report_controls", {}).get("quarantined") is False,
        "unknown-unknown-synthetic-boundary",
        failures,
        passes,
    )
    _check(
        first.get("scaling", {}).get("claim")
        == "horizontal-cellular-scaling"
        and first.get("scaling", {}).get("unbounded_or_infinite_claim")
        is False
        and first.get("scaling", {}).get("global_lock") is False
        and first.get("scaling", {}).get("global_raw_data_store") is False,
        "bounded-cellular-report",
        failures,
        passes,
    )
    try:
        lifecycle = json.loads(
            (ROOT / "rapp" / "lifecycle.json").read_text(encoding="utf-8")
        )
        _check(
            lifecycle.get("global_lock") is False
            and lifecycle.get("network") is False
            and lifecycle.get("install", {}).get("prior_version_preserved")
            is True
            and lifecycle.get("remove", {}).get("removed_version_preserved")
            is True,
            "reversible-rar-lifecycle",
            failures,
            passes,
        )
    except (OSError, json.JSONDecodeError):
        failures.append("reversible-rar-lifecycle")
    try:
        closed_loop = json.loads(
            (ROOT / "rapp" / "closed-loop.json").read_text(encoding="utf-8")
        )
        _check(
            closed_loop.get("name") == "RAPP Roadside Closed Loop"
            and closed_loop.get("pit_crew_state_machine", {}).get(
                "follow_up_limit"
            )
            == 1
            and closed_loop.get("pit_crew_state_machine", {}).get("soak_order")
            == ["Canary", "Nightly", "Alpha", "Beta"]
            and closed_loop.get("customer_state_machine", {}).get("export", {}).get(
                "automatic_send"
            )
            is False,
            "closed-loop-contract",
            failures,
            passes,
        )
    except (OSError, json.JSONDecodeError):
        failures.append("closed-loop-contract")

    test_result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    evidence = ROOT / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "test-results.txt").write_text(
        test_result.stdout + test_result.stderr,
        encoding="utf-8",
        newline="\n",
    )
    _check(test_result.returncode == 0, "unittest-suite", failures, passes)

    fresh_clone = subprocess.run(
        [sys.executable, "scripts/test_fresh_clone.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    (evidence / "fresh-clone-test.json").write_text(
        fresh_clone.stdout,
        encoding="utf-8",
        newline="\n",
    )
    try:
        fresh_clone_payload = json.loads(fresh_clone.stdout)
    except json.JSONDecodeError:
        fresh_clone_payload = {}
    _check(
        fresh_clone.returncode == 0
        and fresh_clone_payload.get("status") == "PASS",
        "fresh-clone",
        failures,
        passes,
    )

    public_audit = subprocess.run(
        [sys.executable, "scripts/public_audit.py", "--path", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    (evidence / "public-audit.json").write_text(
        public_audit.stdout,
        encoding="utf-8",
        newline="\n",
    )
    try:
        public_audit_payload = json.loads(public_audit.stdout)
    except json.JSONDecodeError:
        public_audit_payload = {}
    _check(
        public_audit.returncode == 0
        and public_audit_payload.get("status") == "PASS",
        "public-content-audit",
        failures,
        passes,
    )

    if final:
        for relative in (
            "share with kody.md",
            "issue.json",
            "roadside-frame.json",
            "rev-13-frame.json",
            "evidence/synthetic-report.json",
            "evidence/synthetic-retest.json",
            "evidence/unknown-unknowns-matrix.json",
            "evidence/closed-loop-matrix.json",
            "evidence/fresh-clone-test.json",
            "evidence/public-audit.json",
        ):
            _check(
                (ROOT / relative).is_file(),
                f"final-artifact:{relative}",
                failures,
                passes,
            )
        if (ROOT / "roadside-frame.json").is_file():
            frame = json.loads(
                (ROOT / "roadside-frame.json").read_text(encoding="utf-8")
            )
            _check(
                set(frame)
                == {
                    "spec",
                    "kind",
                    "stream_id",
                    "seq",
                    "utc",
                    "payload",
                    "payload_hash",
                    "frame_hash",
                    "prev",
                    "prev_wave",
                    "sig",
                }
                and len(frame.get("payload", {})) == 13
                and frame.get("payload", {}).get("candidate") == "rapp-roadside",
                "roadside-frame-exact-rev-13-shape",
                failures,
                passes,
            )
            _check(
                _frame_hashes_valid(frame),
                "roadside-frame-rev-13-hashes",
                failures,
                passes,
            )
            _check(
                (ROOT / "roadside-frame.json").read_bytes()
                == (ROOT / "rev-13-frame.json").read_bytes(),
                "roadside-frame-protocol-alias",
                failures,
                passes,
            )
            extracted = subprocess.run(
                [
                    sys.executable,
                    "scripts/extract_roadside_frame.py",
                    "share with kody.md",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                env={"PYTHONDONTWRITEBYTECODE": "1"},
            )
            try:
                extracted_frame = json.loads(extracted.stdout)
            except json.JSONDecodeError:
                extracted_frame = {}
            _check(
                extracted.returncode == 0 and extracted_frame == frame,
                "inert-share-embedded-frame",
                failures,
                passes,
            )
            _check(
                frame.get("payload", {})
                .get("fixture", {})
                .get("issue_signature", {})
                .get("sha256")
                == first.get("issue_signature", {}).get("sha256")
                and first.get("report_controls", {}).get("dedupe_key")
                == first.get("issue_signature", {}).get("sha256"),
                "issue-signature-queue-dedupe",
                failures,
                passes,
            )
        matrix_path = ROOT / "evidence" / "unknown-unknowns-matrix.json"
        if matrix_path.is_file():
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            matrix_domains = {
                item.get("domain") for item in matrix.get("cases", [])
            }
            _check(
                matrix.get("status") == "PASS"
                and matrix_domains
                == {
                    "01-untrusted-reporting-ai",
                    "02-secret-privacy-rights-leakage",
                    "03-destructive-or-wrong-repair",
                    "04-environmental-unknowns",
                    "05-version-ring-and-supply-chain-drift",
                    "06-nonreproducible-user-evidence",
                    "07-support-frame-spam-replay-and-poisoning",
                    "08-fix-regression-and-main-release-risk",
                    "09-distribution-and-skill-lifecycle",
                    "10-scale-cost-and-coordination",
                },
                "unknown-unknown-evidence-matrix",
                failures,
                passes,
            )
        closed_loop_matrix_path = (
            ROOT / "evidence" / "closed-loop-matrix.json"
        )
        if closed_loop_matrix_path.is_file():
            closed_loop_matrix = json.loads(
                closed_loop_matrix_path.read_text(encoding="utf-8")
            )
            _check(
                closed_loop_matrix.get("status") == "PASS"
                and all(
                    closed_loop_matrix.get(field) is False
                    for field in (
                        "automatic_teams_send",
                        "automatic_push",
                        "automatic_main_edit",
                        "automatic_production_deploy",
                        "destructive_customer_repair",
                        "automatic_data_bakery_network_send",
                    )
                ),
                "closed-loop-mutation-matrix",
                failures,
                passes,
            )

    test_output = test_result.stdout + test_result.stderr
    count_match = re.search(r"Ran (\d+) tests?", test_output)
    tests_run = int(count_match.group(1)) if count_match else None
    result = {
        "schema": "skill-forge-result/1.0",
        "status": "PASS" if not failures else "FAIL",
        "candidate": "rapp-roadside",
        "display_name": "RAPP Roadside",
        "repository": "https://github.com/kody-w/rapp-roadside",
        "license": "MIT",
        "copyright": "2026 kody-w",
        "maintainer_system": "RAPP Pit Crew",
        "machine_issue_artifact": "Roadside Frame",
        "closed_loop": "RAPP Roadside Closed Loop",
        "protocol_ids_retained": True,
        "checks_passed": sorted(passes),
        "checks_failed": sorted(failures),
        "network_used": False,
        "network_default": False,
        "telemetry": False,
        "participation": "voluntary",
        "credentials_collected": False,
        "public_action": False,
        "tests_run": tests_run,
        "fixture": {
            "case_id": "synthetic-slow-setup",
            "report_id": first.get("report_id"),
            "retest_id": retest.get("retest_id"),
            "status": retest.get("status"),
        },
    }
    (evidence / "skill-forge.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
