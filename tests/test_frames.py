from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_test_roadside_frame",
    ROOT / "scripts" / "extract_roadside_frame.py",
)
FRAME_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FRAME_MODULE)


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class RoadsideFrameTests(unittest.TestCase):
    def setUp(self):
        self.frame = json.loads(
            (ROOT / "roadside-frame.json").read_text(encoding="utf-8")
        )
        self.markdown = (ROOT / "share with kody.md").read_text(encoding="utf-8")

    def test_unsigned_frame_reports_untrusted_origin_and_no_authority(self):
        result = FRAME_MODULE.extract(self.markdown)
        self.assertEqual("PASS", result["status"])
        self.assertEqual("verified", result["integrity_status"])
        self.assertEqual("untrusted-unsigned", result["origin_status"])
        self.assertEqual("not-established", result["authenticity_status"])
        self.assertEqual("none", result["authority_status"])
        self.assertTrue(result["independent_reproduction_required"])
        self.assertFalse(result["fix_or_release_authorized"])
        self.assertEqual(self.frame, result["frame"])

    def test_external_frame_pin_authenticates_artifact_but_grants_no_authority(self):
        result = FRAME_MODULE.extract(
            self.markdown,
            self.frame["frame_hash"],
        )
        self.assertEqual("externally-pinned", result["origin_status"])
        self.assertEqual("externally-pinned", result["authenticity_status"])
        self.assertEqual("none", result["authority_status"])
        self.assertTrue(result["independent_reproduction_required"])
        self.assertFalse(result["fix_or_release_authorized"])

    def test_recomputed_automatic_push_mutation_is_refused_by_schema(self):
        mutated = deepcopy(self.frame)
        mutated["payload"]["invariants"]["automatic_push"] = True
        mutated["payload_hash"] = hashlib.sha256(
            b"rapp/1:particle\n" + canonical(mutated["payload"])
        ).hexdigest()
        wave_input = {
            key: value
            for key, value in mutated.items()
            if key not in {"frame_hash", "sig"}
        }
        mutated["frame_hash"] = hashlib.sha256(
            b"rapp/1:wave\n" + canonical(wave_input)
        ).hexdigest()
        markdown = (
            FRAME_MODULE.BEGIN
            + "\n```json\n"
            + json.dumps(mutated, indent=2, sort_keys=True)
            + "\n```\n"
            + FRAME_MODULE.END
        )
        with self.assertRaisesRegex(ValueError, "invariant schema"):
            FRAME_MODULE.extract(markdown)

    def test_write_handoff_round_trips_one_validated_frame(self):
        work = ROOT / "tests" / ".work-handoff"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir()
        output = work / "share.md"
        try:
            written = subprocess.run(
                [
                    sys.executable,
                    "scripts/write_handoff.py",
                    "--report",
                    "evidence/synthetic-report.json",
                    "--retest",
                    "evidence/synthetic-retest.json",
                    "--skill-forge",
                    "evidence/skill-forge.json",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env={"PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(0, written.returncode, written.stdout + written.stderr)
            text = output.read_text(encoding="utf-8")
            self.assertEqual(1, text.count(FRAME_MODULE.BEGIN))
            self.assertEqual(1, text.count(FRAME_MODULE.END))
            extracted = subprocess.run(
                [
                    sys.executable,
                    "scripts/extract_roadside_frame.py",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                env={"PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(
                0, extracted.returncode, extracted.stdout + extracted.stderr
            )
            payload = json.loads(extracted.stdout)
            self.assertEqual("PASS", payload["status"])
            self.assertEqual(
                self.frame["payload"]["fixture"]["report_id"],
                payload["frame"]["payload"]["fixture"]["report_id"],
            )
        finally:
            if work.exists():
                shutil.rmtree(work)


if __name__ == "__main__":
    unittest.main()
