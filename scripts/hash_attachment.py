#!/usr/bin/env python3
"""Create allowlisted, hash-only Roadside attachment metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MEDIA_BY_SUFFIX = {
    ".json": "application/json",
    ".log": "text/x-log",
    ".md": "text/markdown",
    ".txt": "text/plain",
}
MAX_BYTES = 2_000_000


def attachment_record(path):
    path = path.expanduser().resolve()
    media_type = MEDIA_BY_SUFFIX.get(path.suffix.lower())
    if media_type is None:
        raise ValueError("attachment extension is not allowlisted")
    if not path.is_file() or path.is_symlink():
        raise ValueError("attachment must be one regular local file")
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise ValueError("attachment exceeds the 2 MB per-file limit")
    data = path.read_bytes()
    return {
        "name": path.name,
        "media_type": media_type,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(attachment_record(Path(args.path)), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": type(error).__name__,
                    "message": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
