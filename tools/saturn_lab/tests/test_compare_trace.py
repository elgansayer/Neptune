from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compare_trace import compare, read


def fixture():
    return {"schema": "neptune.behaviour-trace.v1",
            "contract": {"scenario": "synthetic/movement-fuse", "ruleset": "synthetic-v1",
                         "observation_schema": "synthetic-pixels-v1", "input_sha256": "a" * 64,
                         "timebase": {"numerator": 60, "denominator": 1}},
            "source": {"kind": "synthetic", "build_sha256": "b" * 64,
                       "input_lock_sha256": "c" * 64, "capture_sha256": "d" * 64, "adapter_sha256": "e" * 64},
            "samples": [{"frame": i, "observations": {"player": {"x_fixed": i * 256}, "bomb": {"alive": i < 2}, "events": ["explode"] if i == 2 else []}} for i in range(4)]}


class TraceComparison(unittest.TestCase):
    def test_equal_trace_and_different_builds(self):
        reference = fixture()
        candidate = deepcopy(reference)
        candidate["source"]["build_sha256"] = "f" * 64
        result = compare(reference, candidate)
        self.assertTrue(result["match"])
        self.assertEqual(result["source_kinds"], ["synthetic", "synthetic"])
        self.assertIn("not certified", result["scope"])
        self.assertNotEqual(result["reference_sha256"], result["candidate_sha256"])

    def test_movement_mutation_reports_first_exact_frame(self):
        original, changed = fixture(), fixture()
        changed["samples"][1]["observations"]["player"]["x_fixed"] += 1
        result = compare(original, changed)
        self.assertFalse(result["match"])
        self.assertEqual((result["first_frame"], result["field"]), (1, "/player/x_fixed"))

    def test_one_frame_fuse_delay_fails(self):
        original, changed = fixture(), fixture()
        changed["samples"][2]["observations"]["bomb"]["alive"] = True
        changed["samples"][2]["observations"]["events"] = []
        result = compare(original, changed)
        self.assertFalse(result["match"])
        self.assertEqual(result["first_frame"], 2)

    def test_event_order_and_bool_integer_are_not_normalised(self):
        for a, b in ((["pickup", "death"], ["death", "pickup"]), (True, 1)):
            original, changed = fixture(), fixture()
            original["samples"][0]["observations"]["value"] = a
            changed["samples"][0]["observations"]["value"] = b
            self.assertFalse(compare(original, changed)["match"])

    def test_missing_and_extra_frames_fail(self):
        original, changed = fixture(), fixture()
        changed["samples"].pop()
        self.assertFalse(compare(original, changed)["match"])
        self.assertFalse(compare(changed, original)["match"])

    def test_mixed_release_input_timebase_or_schema_rejected(self):
        for key, value in (("ruleset", "another-region"), ("scenario", "another-room"), ("input_sha256", "f" * 64), ("observation_schema", "other-units"), ("timebase", {"numerator": 50, "denominator": 1})):
            original, changed = fixture(), fixture()
            changed["contract"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare(original, changed)

    def test_empty_duplicate_out_of_order_and_float_samples_fail(self):
        for change in (lambda t: t.update(samples=[]), lambda t: t["samples"][1].update(frame=0), lambda t: t["samples"][0].update(frame=1), lambda t: t["samples"][0].update(observations={}), lambda t: t["samples"][0]["observations"].update(position=0.1)):
            bad = fixture()
            change(bad)
            with self.assertRaises(ValueError):
                compare(fixture(), bad)

    def test_missing_provenance_rejected(self):
        for key in fixture()["source"]:
            bad = fixture()
            del bad["source"][key]
            with self.assertRaises(ValueError):
                compare(fixture(), bad)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"schema": "one", "schema": "two"}')
            with self.assertRaises(ValueError):
                read(path)

    def test_cli_pass_regression_and_error_exit_codes(self):
        cli = Path(__file__).resolve().parents[1] / "compare_trace.py"
        with tempfile.TemporaryDirectory() as directory:
            reference, candidate = [Path(directory) / name for name in ("a.json", "b.json")]
            reference.write_text(json.dumps(fixture()))
            cases = [(fixture(), 0), (fixture(), 1), ({}, 2)]
            cases[1][0]["samples"][0]["observations"]["player"]["x_fixed"] = 9
            for content, code in cases:
                candidate.write_text(json.dumps(content))
                process = subprocess.run([sys.executable, str(cli), str(reference), str(candidate)], capture_output=True, text=True)
                self.assertEqual(process.returncode, code, process.stdout + process.stderr)
                self.assertEqual(json.loads(process.stdout)["match"], code == 0)


if __name__ == "__main__":
    unittest.main()
