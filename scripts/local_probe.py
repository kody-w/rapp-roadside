#!/usr/bin/env python3
"""Create a sanitized local RAPP Roadside observation.

Network is disabled by default. With --allow-loopback, only localhost health
and the canonical POST /chat route may be probed. Response bodies are reduced
to statuses and key names; credentials and agent output are never retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _file_hash(path):
    return _sha256(path.read_bytes()) if path.is_file() else "unknown"


def _source_tree_hash(root):
    records = []
    for relative in (
        "VERSION",
        "brainstem.py",
        "rapp_brainstem/VERSION",
        "rapp_brainstem/brainstem.py",
        "install.sh",
        "install.ps1",
        "install.cmd",
    ):
        path = root / relative
        if path.is_file():
            records.append({"path": relative, "sha256": _file_hash(path)})
    return _sha256(_canonical(records)) if records else "unknown"


def _platform_name():
    return {
        "Darwin": "macos",
        "Windows": "windows",
    }.get(platform.system(), "linux")


def _loopback_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("base URL must be plain HTTP loopback")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain credentials, query, or fragment")
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
    ).rstrip("/")


def _request(method, url, body=None, timeout=3):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_001)
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read(1_000_001)
        status = error.code
    except (urllib.error.URLError, TimeoutError):
        return None, {}
    if len(raw) > 1_000_000:
        return status, {}
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    return status, payload if isinstance(payload, dict) else {}


def _installer_mirrors_match(root):
    for filename in ("install.sh", "install.ps1", "install.cmd"):
        source = root / filename
        mirror = root / "docs" / filename
        if source.exists() != mirror.exists():
            return False
        if source.is_file() and source.read_bytes() != mirror.read_bytes():
            return False
    return True


def _launcher_state(root, platform_name):
    candidates = (
        [root / "installer" / "brainstem.cmd"]
        if platform_name == "windows"
        else [root / "installer" / "brainstem", root / "start.sh"]
    )
    present = [path for path in candidates if path.is_file()]
    executable = True
    if platform_name != "windows" and present:
        executable = all(
            bool(path.stat().st_mode & stat.S_IXUSR) for path in present
        )
    return {"present": bool(present), "executable": executable}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument(
        "--base-url", default=os.environ.get("RAPP_BRAINSTEM_URL", "http://127.0.0.1:7071")
    )
    parser.add_argument("--check-chat", action="store_true")
    parser.add_argument("--allow-loopback", action="store_true")
    args = parser.parse_args(argv)
    if args.wait_seconds < 0 or args.wait_seconds > 180:
        raise SystemExit("wait-seconds must be between 0 and 180")
    workspace = Path(args.workspace).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not workspace.is_dir():
        raise SystemExit("workspace must be an existing directory")
    started = time.monotonic()
    if args.wait_seconds:
        time.sleep(args.wait_seconds)
    platform_name = _platform_name()
    source_present = (workspace / "brainstem.py").is_file() or (
        workspace / "rapp_brainstem" / "brainstem.py"
    ).is_file()
    python_version = ".".join(str(item) for item in sys.version_info[:3])
    health_status = "not-probed"
    health_http_status = None
    chat = {
        "method": "POST",
        "path": "/chat",
        "request_field": "user_input",
        "http_status": None,
        "response_keys": [],
    }
    if args.allow_loopback:
        base_url = _loopback_url(args.base_url)
        health_http_status, health_payload = _request(
            "GET", base_url + "/health"
        )
        health_status = str(health_payload.get("status") or "unreachable")
        if args.check_chat and health_http_status == 200:
            chat_status, chat_payload = _request(
                "POST",
                base_url + "/chat",
                {
                    "user_input": (
                        "Installer stability retest. Reply only "
                        "RAPP_LOCAL_RETEST_OK."
                    )
                },
                timeout=30,
            )
            chat["http_status"] = chat_status
            chat["response_keys"] = sorted(chat_payload)
    installer_hashes = {
        filename: _file_hash(workspace / filename)
        for filename in ("install.sh", "install.ps1", "install.cmd")
        if (workspace / filename).is_file()
    }
    dependency_path = next(
        (
            workspace / name
            for name in (
                "requirements.lock",
                "requirements-dev.txt",
                "requirements.txt",
            )
            if (workspace / name).is_file()
        ),
        None,
    )
    catalog_path = next(
        (
            workspace / name
            for name in ("registry.json", "catalog.json")
            if (workspace / name).is_file()
        ),
        None,
    )
    ring_path = next(
        (
            workspace / name
            for name in ("ring-manifest.json", "manifest.json", "VERSION")
            if (workspace / name).is_file()
        ),
        None,
    )
    installer_frame_path = next(
        (
            workspace / name
            for name in (
                "installer-release-frame.json",
                "rapp/installer-release-frame.json",
            )
            if (workspace / name).is_file()
        ),
        None,
    )
    installer_frame_version = "unknown"
    if installer_frame_path is not None:
        try:
            installer_frame_payload = json.loads(
                installer_frame_path.read_text(encoding="utf-8")
            )
            installer_frame_version = str(
                installer_frame_payload.get("schema") or "unknown"
            )
        except (OSError, json.JSONDecodeError):
            installer_frame_version = "unknown"
    input_record = {
        "workspace": "<rapp-root>",
        "wait_seconds": args.wait_seconds,
        "check_chat": args.check_chat,
        "allow_loopback": args.allow_loopback,
    }
    before_record = {
        "source_present": source_present,
        "launcher": _launcher_state(workspace, platform_name),
        "installer_hashes": installer_hashes,
    }
    output_record = {
        "health_status": health_status,
        "health_http_status": health_http_status,
        "chat_http_status": chat["http_status"],
        "chat_response_keys": chat["response_keys"],
    }
    now_epoch = int(time.time())
    source_tree_sha256 = _source_tree_hash(workspace)
    report_id = _sha256(
        _canonical(
            {
                "input": input_record,
                "before": before_record,
                "output": output_record,
            }
        )
    )
    observation = {
        "case_id": "local-rapp-setup",
        "failure_code": "unclassified",
        "platform": platform_name,
        "setup_elapsed_seconds": args.wait_seconds,
        "setup_stage": (
            "starting-server"
            if health_http_status != 200
            else "ready"
        ),
        "signature_phase": (
            "starting-server"
            if health_http_status != 200
            else "ready"
        ),
        "source": {"present": source_present},
        "launcher": _launcher_state(workspace, platform_name),
        "python": {"version": python_version},
        "health": {
            "status": health_status,
            "http_status": health_http_status,
        },
        "chat": chat,
        "installers": {
            "docs_mirrors_match": _installer_mirrors_match(workspace)
        },
        "repository": {"direct_main_change_requested": False},
        "safety": {
            "external_network_observed": False,
            "grail_modified": False,
        },
        "environment": {
            "architecture": platform.machine().lower() or "unknown",
            "certificate_state": "unknown",
            "clock_state": "monotonic-and-wall-clock-observed",
            "filesystem": "unknown",
            "locale": "unknown",
            "managed_policy": "unknown",
            "os_build": platform.release().lower() or "unknown",
            "proxy_state": "unknown",
            "security_product_state": "unknown",
            "shell": "unknown",
        },
        "bindings": {
            "ring": "unknown",
            "installer_release_frame_version": installer_frame_version,
            "installer_release_frame_sha256": (
                _file_hash(installer_frame_path)
                if installer_frame_path is not None
                else "unknown"
            ),
            "ring_manifest_sha256": (
                _file_hash(ring_path) if ring_path is not None else "unknown"
            ),
            "source_commit": "unknown",
            "source_tree_sha256": source_tree_sha256,
            "dependency_lock_sha256": (
                _file_hash(dependency_path)
                if dependency_path is not None
                else "unknown"
            ),
            "catalog_sha256": (
                _file_hash(catalog_path)
                if catalog_path is not None
                else "unknown"
            ),
            "installer_sha256s": installer_hashes,
        },
        "reporting_ai": {
            "text_present": False,
            "text_sha256": None,
            "text_bytes": 0,
            "log_count": 0,
            "log_sha256s": [],
            "instruction_markers_detected": False,
            "observed_claim_ids": [
                "local-probe.health",
                "local-probe.launcher",
            ],
            "inferred_claim_ids": [],
        },
        "attachments": [],
        "replay": {
            "argv": [
                "python3",
                "scripts/local_probe.py",
                "--workspace",
                "<rapp-root>",
                "--wait-seconds",
                str(args.wait_seconds),
                "--output",
                "<observation-json>",
            ]
            + (["--check-chat"] if args.check_chat else [])
            + (["--allow-loopback"] if args.allow_loopback else []),
            "logical_cwd": "<rapp-root>",
            "input_sha256": _sha256(_canonical(input_record)),
            "before_state_sha256": _sha256(_canonical(before_record)),
            "phase": "local-roadside-probe",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "output_sha256": _sha256(_canonical(output_record)),
            "output_bytes": len(_canonical(output_record)),
        },
        "transport": {
            "report_id": report_id,
            "created_epoch": now_epoch,
            "received_epoch": now_epoch,
            "ttl_seconds": 86400,
            "source_cell_id": f"roadside-{platform_name}-local",
            "source_verified": True,
            "frame_verified": True,
            "trust_weight_bps": 10000,
            "dedupe_count": 0,
            "rate_window_seconds": 3600,
            "rate_count": 1,
            "rate_limit": 3,
            "correlation_id": None,
            "correlation_disclosed": True,
        },
        "cell": {
            "cell_id": f"roadside-{platform_name}-local",
            "shard_key_sha256": _sha256(
                _canonical(
                    {
                        "platform": platform_name,
                        "source_tree_sha256": source_tree_sha256,
                    }
                )
            ),
            "queue_depth": 0,
            "backpressure_threshold": 8,
            "max_queue_depth": 32,
            "local_raw_retention_seconds": 0,
            "global_raw_data_store": False,
            "global_lock": False,
            "global_exchange": (
                "verified-signatures-frames-aggregate-evidence-only"
            ),
            "hot_cache_hits": 0,
            "negative_cache_hits": 0,
            "fairness_lane": "normal",
            "marginal_information_gain_bps": 10000,
        },
    }
    signature_fields = {
        "installer_release_frame_version": observation["bindings"][
            "installer_release_frame_version"
        ],
        "installer_release_frame_sha256": observation["bindings"][
            "installer_release_frame_sha256"
        ],
        "ring": observation["bindings"]["ring"],
        "ring_manifest_sha256": observation["bindings"][
            "ring_manifest_sha256"
        ],
        "source_commit": observation["bindings"]["source_commit"],
        "installer_sha256s": observation["bindings"]["installer_sha256s"],
        "phase": observation["signature_phase"],
        "fixed_code": observation["failure_code"],
        "environment_classes": {
            "platform": observation["platform"],
            "os_build": observation["environment"]["os_build"],
            "managed_policy": observation["environment"]["managed_policy"],
            "filesystem": observation["environment"]["filesystem"],
            "shell": observation["environment"]["shell"],
        },
        "input_hashes": [
            observation["replay"]["input_sha256"],
            observation["replay"]["before_state_sha256"],
        ],
    }
    observation["cell"]["shard_key_sha256"] = _sha256(
        b"rapp-roadside:issue-signature/v1\n"
        + _canonical(signature_fields)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(observation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"status": "PASS", "output": "<observation-json>"},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
