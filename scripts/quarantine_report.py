#!/usr/bin/env python3
"""Write one bounded, hash-only local Roadside quarantine record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = json.loads(
        Path(args.report).expanduser().resolve().read_text(encoding="utf-8")
    )
    if report.get("schema") != "rar-installer-troubleshooter/report-1":
        raise SystemExit("unsupported retained report protocol ID")
    controls = report.get("report_controls") or {}
    replay = report.get("replay_manifest") or {}
    bindings = report.get("byte_bindings") or {}
    scaling = report.get("scaling") or {}
    record = {
        "schema": "rapp-roadside/quarantine-1",
        "support_system": "RAPP Roadside",
        "maintainer_system": "RAPP Pit Crew",
        "report_id": report.get("report_id"),
        "dedupe_key": controls.get("dedupe_key"),
        "quarantine_reasons": controls.get("quarantine_reasons") or [
            "cell-backpressure"
        ],
        "source_cell_id": controls.get("source_cell_id"),
        "ttl_seconds": controls.get("ttl_seconds"),
        "attachment_hashes": [
            {
                "name": item.get("name"),
                "media_type": item.get("media_type"),
                "sha256": item.get("sha256"),
                "bytes": item.get("bytes"),
            }
            for item in (
                report.get("evidence_partition", {})
                .get("observed", {})
                .get("attachments", [])
            )
        ],
        "replay_hashes": {
            "input_sha256": replay.get("input_sha256"),
            "before_state_sha256": replay.get("before_state_sha256"),
            "output_sha256": replay.get("output_sha256"),
        },
        "byte_bindings": bindings.get("values"),
        "shard_key_sha256": scaling.get("shard_key_sha256"),
        "raw_reporting_ai_text_or_logs_retained": False,
        "private_paths_retained": False,
        "global_raw_data_store": False,
        "global_lock": False,
        "publication": "none",
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": "PASS", "output": "<quarantine-record>"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
