#!/usr/bin/env python3
"""Extract and validate one inert Roadside Frame from untrusted Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


BEGIN = "<!-- RAPP-ROADSIDE-FRAME-BEGIN -->"
END = "<!-- RAPP-ROADSIDE-FRAME-END -->"
HASH64 = re.compile(r"^[0-9a-f]{64}$")
STREAM_ID = re.compile(
    r"^rappid:@kody-w/rar-installer-troubleshooter:[0-9a-f]{64}$"
)
UTC_TEXT = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$"
)
FRAME_KEYS = {
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
PAYLOAD_KEYS = {
    "artifacts",
    "candidate",
    "fixture",
    "identity",
    "invariants",
    "package_lock_sha256",
    "revision",
    "safety",
    "skill_forge",
    "skill_sha256",
    "source_sha256",
    "target_main",
    "teams",
    "verification",
    "version",
}
FIXTURE_KEYS = {
    "attachments",
    "byte_bindings",
    "case_id",
    "issue_signature",
    "replay_hashes",
    "report_controls",
    "report_id",
    "scaling",
}
SAFETY = {
    "attachments": "allowlisted-hash-only",
    "credentials": "not-collected",
    "customer_frame_origin": "untrusted-unless-externally-pinned",
    "network": "not-used",
    "network_default": "off",
    "participation": "voluntary",
    "public_action": "not-performed",
    "repair": "human-approved-reversible-copy-only",
    "report_controls": "dedupe-rate-ttl-correlation-quarantine",
    "reporting_ai": "hostile-data-never-instructions",
    "support_system": "RAPP Roadside",
    "telemetry": "none",
}
INVARIANTS = {
    "automatic_main_edit": False,
    "automatic_maintainer_feedback_network_send": False,
    "automatic_production_deploy": False,
    "automatic_push": False,
    "automatic_teams_send": False,
    "bounded_follow_up_limit": 1,
    "copyright": "2026 kody-w",
    "destructive_customer_repair": False,
    "direct_push_main": False,
    "embedded_roadside_frame": True,
    "exact_byte_bindings": True,
    "exact_replay": True,
    "frame_only_fix_or_release": False,
    "global_lock": False,
    "global_raw_data_store": False,
    "grail": "unchanged",
    "independent_reproduction_required": True,
    "infinity_claim": False,
    "issue_signature_domain": "rapp-roadside:issue-signature/v1",
    "issue_signature_excludes_identity_and_raw_logs": True,
    "license": "MIT",
    "maintainer_system": "RAPP Pit Crew",
    "pit_crew_soak_order": ["Canary", "Nightly", "Alpha", "Beta"],
    "public_repository": "https://github.com/kody-w/rapp-roadside",
    "rar_lifecycle": "reversible-install-remove",
    "release_gate": "isolated-checkout-Canary-Nightly-Alpha-Beta",
    "scaling": "bounded-horizontal-cellular-measured-backpressure",
    "unsigned_customer_frame_authenticity": False,
    "unsigned_customer_frame_authority": False,
    "verified_resolution_requires_customer_pass": True,
    "wire": "POST /chat",
}


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _require_object(value, keys, location):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{location} has the wrong exact shape")


def _require_hash(value, location):
    if not isinstance(value, str) or not HASH64.fullmatch(value):
        raise ValueError(f"{location} must be a SHA-256 value")


def _validate_fixture(fixture):
    _require_object(fixture, FIXTURE_KEYS, "Roadside Frame fixture")
    if not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*",
        str(fixture.get("case_id") or ""),
    ):
        raise ValueError("Roadside Frame fixture case ID is invalid")
    _require_hash(fixture.get("report_id"), "Roadside Frame fixture report ID")
    signature = fixture.get("issue_signature")
    _require_object(
        signature,
        {
            "dedupe_key",
            "domain",
            "fields",
            "identity_included",
            "queue_key",
            "raw_logs_included",
            "sha256",
        },
        "Roadside Frame issue signature",
    )
    if (
        signature["domain"] != "rapp-roadside:issue-signature/v1"
        or signature["identity_included"] is not False
        or signature["raw_logs_included"] is not False
        or signature["queue_key"] is not True
        or signature["dedupe_key"] is not True
    ):
        raise ValueError("Roadside Frame issue signature controls are invalid")
    fields = signature["fields"]
    _require_object(
        fields,
        {
            "environment_classes",
            "fixed_code",
            "input_hashes",
            "installer_release_frame_sha256",
            "installer_release_frame_version",
            "installer_sha256s",
            "phase",
            "ring",
            "ring_manifest_sha256",
            "source_commit",
        },
        "Roadside Frame issue signature fields",
    )
    _require_object(
        fields["environment_classes"],
        {"filesystem", "managed_policy", "os_build", "platform", "shell"},
        "Roadside Frame environment classes",
    )
    if (
        not isinstance(fields["input_hashes"], list)
        or len(fields["input_hashes"]) != 2
    ):
        raise ValueError("Roadside Frame issue signature input hashes are invalid")
    for value in fields["input_hashes"]:
        _require_hash(value, "Roadside Frame issue signature input hash")
    _require_hash(
        signature.get("sha256"),
        "Roadside Frame issue signature",
    )
    expected_signature = hashlib.sha256(
        b"rapp-roadside:issue-signature/v1\n"
        + _canonical(signature["fields"])
    ).hexdigest()
    if signature["sha256"] != expected_signature:
        raise ValueError("Roadside Frame issue signature does not match its fields")

    attachments = fixture.get("attachments")
    if not isinstance(attachments, list) or len(attachments) > 8:
        raise ValueError("Roadside Frame attachment ledger is invalid")
    for item in attachments:
        _require_object(
            item,
            {"bytes", "media_type", "name", "sha256"},
            "Roadside Frame attachment",
        )
        if (
            not isinstance(item["name"], str)
            or "/" in item["name"]
            or "\\" in item["name"]
            or item["name"].startswith(".")
            or item["media_type"]
            not in {
                "application/json",
                "text/markdown",
                "text/plain",
                "text/x-log",
            }
            or not isinstance(item["bytes"], int)
            or not 0 <= item["bytes"] <= 2_000_000
        ):
            raise ValueError("Roadside Frame attachment ledger is invalid")
        _require_hash(item["sha256"], "Roadside Frame attachment hash")

    byte_bindings = fixture.get("byte_bindings")
    _require_object(
        byte_bindings,
        {"exact", "reported", "unknown_fields", "values"},
        "Roadside Frame byte bindings",
    )
    _require_object(
        byte_bindings["values"],
        {
            "catalog_sha256",
            "dependency_lock_sha256",
            "installer_release_frame_sha256",
            "installer_release_frame_version",
            "installer_sha256s",
            "ring",
            "ring_manifest_sha256",
            "source_commit",
            "source_tree_sha256",
            "unreported_fields",
        },
        "Roadside Frame binding values",
    )
    if (
        not isinstance(byte_bindings["unknown_fields"], list)
        or not isinstance(byte_bindings["values"]["unreported_fields"], list)
        or not isinstance(byte_bindings["values"]["installer_sha256s"], dict)
        or byte_bindings["exact"]
        is not (not byte_bindings["unknown_fields"])
    ):
        raise ValueError("Roadside Frame byte binding status is invalid")
    expected_unreported = {
        key
        for key, value in byte_bindings["values"].items()
        if key != "unreported_fields" and (value is None or value == {})
    }
    if set(byte_bindings["values"]["unreported_fields"]) != expected_unreported:
        raise ValueError("Roadside Frame unreported bindings are inconsistent")
    for key in (
        "catalog_sha256",
        "dependency_lock_sha256",
        "installer_release_frame_sha256",
        "ring_manifest_sha256",
        "source_tree_sha256",
    ):
        value = byte_bindings["values"][key]
        if value is not None:
            _require_hash(value, f"Roadside Frame binding {key}")
    source_commit = byte_bindings["values"]["source_commit"]
    if source_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("Roadside Frame source commit binding is invalid")
    for value in byte_bindings["values"]["installer_sha256s"].values():
        _require_hash(value, "Roadside Frame installer binding")

    replay_hashes = fixture.get("replay_hashes")
    _require_object(
        replay_hashes,
        {
            "before_state_sha256",
            "input_sha256",
            "output_sha256",
            "unreported_fields",
        },
        "Roadside Frame replay hashes",
    )
    if not isinstance(replay_hashes["unreported_fields"], list):
        raise ValueError("Roadside Frame replay unreported fields are invalid")
    expected_replay_unreported = set()
    for key in ("before_state_sha256", "input_sha256", "output_sha256"):
        value = replay_hashes[key]
        if value is None:
            expected_replay_unreported.add(key)
        else:
            _require_hash(value, f"Roadside Frame replay hash {key}")
    if set(replay_hashes["unreported_fields"]) != expected_replay_unreported:
        raise ValueError("Roadside Frame replay unreported fields are inconsistent")

    controls = fixture.get("report_controls")
    _require_object(
        controls,
        {
            "age_seconds",
            "correlation",
            "dedupe_count",
            "dedupe_key",
            "frame_verified",
            "quarantine_reasons",
            "quarantined",
            "rate",
            "raw_report_data_globalized",
            "source_cell_id",
            "source_verified",
            "transport_reported",
            "trust_weight_bps",
            "ttl_seconds",
        },
        "Roadside Frame report controls",
    )
    if controls["raw_report_data_globalized"] is not False:
        raise ValueError("Roadside Frame may not globalize raw report data")
    _require_object(
        controls["rate"],
        {"count", "limit", "window_seconds"},
        "Roadside Frame report rate controls",
    )
    _require_object(
        controls["correlation"],
        {"disclosed", "id_present"},
        "Roadside Frame report correlation controls",
    )
    if (
        not isinstance(controls["quarantined"], bool)
        or not isinstance(controls["quarantine_reasons"], list)
        or not isinstance(controls["transport_reported"], bool)
    ):
        raise ValueError("Roadside Frame report control types are invalid")

    scaling = fixture.get("scaling")
    _require_object(
        scaling,
        {
            "cache_measurements",
            "cell_id",
            "cell_reported",
            "claim",
            "fairness_lane",
            "global_exchange",
            "global_lock",
            "global_raw_data_store",
            "local_raw_retention_seconds",
            "marginal_information_gain_bps",
            "measured_backpressure",
            "shard_key_sha256",
            "unbounded_or_infinite_claim",
        },
        "Roadside Frame scaling evidence",
    )
    if (
        scaling["global_lock"] is not False
        or scaling["global_raw_data_store"] is not False
        or scaling["unbounded_or_infinite_claim"] is not False
    ):
        raise ValueError("Roadside Frame scaling invariants are invalid")
    _require_hash(
        scaling["shard_key_sha256"],
        "Roadside Frame scaling shard",
    )
    _require_object(
        scaling["cache_measurements"],
        {"hot_cache_hits", "negative_cache_hits"},
        "Roadside Frame cache measurements",
    )
    _require_object(
        scaling["measured_backpressure"],
        {
            "active",
            "max_queue_depth",
            "queue_depth",
            "threshold",
            "utilization_basis_points",
        },
        "Roadside Frame backpressure measurements",
    )


def validate_frame(frame, expected_frame_hash=None):
    _require_object(frame, FRAME_KEYS, "Roadside Frame")
    if (
        frame["spec"] != "rapp/1"
        or frame["kind"] != "rar.review.rev-13"
        or not isinstance(frame["stream_id"], str)
        or not STREAM_ID.fullmatch(frame["stream_id"])
        or frame["seq"] != 0
        or not isinstance(frame["utc"], str)
        or not UTC_TEXT.fullmatch(frame["utc"])
        or frame["prev"] is not None
        or frame["prev_wave"] is not None
        or frame["sig"] is not None
    ):
        raise ValueError("Roadside Frame protocol identity is invalid")
    payload = frame["payload"]
    _require_object(payload, PAYLOAD_KEYS, "Roadside Frame payload")
    if (
        payload["revision"] != 13
        or payload["candidate"] != "rapp-roadside"
        or payload["identity"] != frame["stream_id"]
        or not re.fullmatch(r"\d+\.\d+\.\d+", str(payload["version"]))
        or payload["target_main"] != "kody-w/rapp-roadside@main"
        or payload["skill_forge"] not in {"PASS", "FAIL", "NOT-RUN"}
    ):
        raise ValueError("Roadside Frame payload identity is invalid")
    for key in ("source_sha256", "skill_sha256", "package_lock_sha256"):
        _require_hash(payload[key], f"Roadside Frame payload {key}")
    _validate_fixture(payload["fixture"])
    _require_object(payload["safety"], SAFETY, "Roadside Frame safety")
    if payload["safety"] != SAFETY:
        raise ValueError("Roadside Frame safety schema is invalid")
    _require_object(payload["invariants"], INVARIANTS, "Roadside Frame invariants")
    if payload["invariants"] != INVARIANTS:
        raise ValueError("Roadside Frame invariant schema is invalid")
    artifacts = payload["artifacts"]
    if (
        not isinstance(artifacts, list)
        or not artifacts
        or len(artifacts) != len(set(artifacts))
        or any(
            not isinstance(item, str)
            or not item
            or Path(item).is_absolute()
            or ".." in Path(item).parts
            for item in artifacts
        )
    ):
        raise ValueError("Roadside Frame artifact ledger is invalid")
    _require_object(
        payload["teams"],
        {"instructions", "performed", "publication_owner"},
        "Roadside Frame sharing metadata",
    )
    if (
        payload["teams"]["instructions"] != "teams-sharing-instructions.md"
        or payload["teams"]["performed"] is not False
        or not isinstance(payload["teams"]["publication_owner"], str)
    ):
        raise ValueError("Roadside Frame sharing metadata is invalid")
    verification = payload["verification"]
    _require_object(
        verification,
        {"retest_id", "retest_status", "tests_run"},
        "Roadside Frame verification",
    )
    if (
        verification["retest_status"] not in {"PASS", "FAIL", "NOT-PROVIDED"}
        or (
            verification["retest_id"] is not None
            and (
                not isinstance(verification["retest_id"], str)
                or not HASH64.fullmatch(verification["retest_id"])
            )
        )
        or (
            verification["tests_run"] is not None
            and (
                not isinstance(verification["tests_run"], int)
                or verification["tests_run"] < 0
            )
        )
    ):
        raise ValueError("Roadside Frame verification metadata is invalid")
    if (
        verification["retest_status"] == "NOT-PROVIDED"
        and verification["retest_id"] is not None
    ) or (
        verification["retest_status"] in {"PASS", "FAIL"}
        and verification["retest_id"] is None
    ):
        raise ValueError("Roadside Frame retest status and ID disagree")

    particle = hashlib.sha256(
        b"rapp/1:particle\n" + _canonical(payload)
    ).hexdigest()
    wave_input = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    wave = hashlib.sha256(
        b"rapp/1:wave\n" + _canonical(wave_input)
    ).hexdigest()
    if particle != frame["payload_hash"] or wave != frame["frame_hash"]:
        raise ValueError("Roadside Frame hash verification failed")
    expected = str(expected_frame_hash or "").strip().lower()
    if expected:
        _require_hash(expected, "expected Roadside Frame hash")
        if expected != frame["frame_hash"]:
            raise ValueError("Roadside Frame does not match the external pin")
    return frame


def extract(markdown, expected_frame_hash=None):
    if len(markdown.encode("utf-8")) > 1_000_000:
        raise ValueError("Markdown exceeds the 1 MiB import limit")
    if markdown.count(BEGIN) != 1 or markdown.count(END) != 1:
        raise ValueError("Markdown must contain exactly one Roadside Frame")
    start = markdown.index(BEGIN) + len(BEGIN)
    stop = markdown.index(END, start)
    block = markdown[start:stop].strip()
    if not block.startswith("```json\n") or not block.endswith("\n```"):
        raise ValueError("Roadside Frame must use the exact JSON fence")
    frame = json.loads(block[len("```json\n") : -len("\n```")])
    expected = str(expected_frame_hash or "").strip().lower() or None
    validate_frame(frame, expected)
    externally_pinned = expected is not None
    return {
        "status": "PASS",
        "integrity_status": "verified",
        "origin_status": (
            "externally-pinned" if externally_pinned else "untrusted-unsigned"
        ),
        "authenticity_status": (
            "externally-pinned" if externally_pinned else "not-established"
        ),
        "authority_status": "none",
        "independent_reproduction_required": True,
        "fix_or_release_authorized": False,
        "frame": frame,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown")
    parser.add_argument(
        "--expected-frame-hash",
        default=os.environ.get("RAPP_ROADSIDE_EXPECTED_FRAME_HASH"),
        help="externally trusted frame hash from a separate channel",
    )
    args = parser.parse_args(argv)
    try:
        path = Path(args.markdown).expanduser().resolve()
        result = extract(
            path.read_text(encoding="utf-8"),
            args.expected_frame_hash,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": type(error).__name__,
                    "message": str(error),
                    "markdown_executed": False,
                    "fix_or_release_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
