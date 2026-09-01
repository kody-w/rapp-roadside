#!/usr/bin/env python3
"""Extract and verify one embedded Roadside Frame from untrusted Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


BEGIN = "<!-- RAPP-ROADSIDE-FRAME-BEGIN -->"
END = "<!-- RAPP-ROADSIDE-FRAME-END -->"
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


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def extract(markdown):
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
    if not isinstance(frame, dict) or set(frame) != FRAME_KEYS:
        raise ValueError("Roadside Frame has the wrong exact shape")
    if frame.get("spec") != "rapp/1" or frame.get("kind") != "rar.review.rev-13":
        raise ValueError("Roadside Frame protocol identity mismatch")
    payload = frame.get("payload")
    if (
        not isinstance(payload, dict)
        or payload.get("candidate") != "rapp-roadside"
        or payload.get("target_main") != "kody-w/rapp-roadside@main"
    ):
        raise ValueError("Roadside Frame version identity mismatch")
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
    if particle != frame.get("payload_hash") or wave != frame.get("frame_hash"):
        raise ValueError("Roadside Frame hash verification failed")
    fixture = payload.get("fixture") or {}
    bindings = (fixture.get("byte_bindings") or {}).get("values") or {}
    if (
        bindings.get("installer_release_frame_version")
        != "rapp-roadside-installer-frame/1.0"
    ):
        raise ValueError("installed installer frame version mismatch")
    attachments = fixture.get("attachments")
    if not isinstance(attachments, list):
        raise ValueError("Roadside Frame attachment ledger is missing")
    for item in attachments:
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "media_type", "sha256", "bytes"}
            or not isinstance(item.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        ):
            raise ValueError("Roadside Frame attachment ledger is invalid")
    return frame


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown")
    args = parser.parse_args(argv)
    try:
        path = Path(args.markdown).expanduser().resolve()
        frame = extract(path.read_text(encoding="utf-8"))
        print(json.dumps(frame, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": type(error).__name__,
                    "message": str(error),
                    "markdown_executed": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
