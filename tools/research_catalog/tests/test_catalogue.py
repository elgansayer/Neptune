"""Reject false-success metadata and broken relationships; not gameplay tests."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "cli.py"
spec = importlib.util.spec_from_file_location("research_catalogue", CLI)
catalogue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalogue)


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.data = deepcopy(catalogue.load(catalogue.DEFAULT))

    def test_empty_catalogue_fails(self):
        self.data["features"] = []
        with self.assertRaisesRegex(ValueError, "No features"):
            catalogue.validate(self.data)

    def test_duplicate_feature_fails(self):
        self.data["features"].append(deepcopy(self.data["features"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate feature"):
            catalogue.validate(self.data)

    def test_unknown_source_fails(self):
        self.data["features"][0]["source_ids"] = ["invented-source"]
        with self.assertRaisesRegex(ValueError, "unknown source"):
            catalogue.validate(self.data)

    def test_unknown_dependency_and_cycle_fail(self):
        feature = self.data["features"][0]
        for dependency in ("missing-feature", feature["id"]):
            with self.subTest(dependency=dependency):
                feature["depends_on"] = [dependency]
                with self.assertRaises(ValueError):
                    catalogue.validate(self.data)

    def test_observation_needs_pinned_evidence(self):
        self.data["features"][0]["reference_status"] = "observed"
        with self.assertRaisesRegex(ValueError, "pinned observation"):
            catalogue.validate(self.data)

    def test_verified_cannot_be_asserted_from_documentation(self):
        feature = self.data["features"][0]
        feature["implementation_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "passing evidence"):
            catalogue.validate(self.data)
        feature["verification"] = {"tested_commit": "a" * 40, "artifact_sha256": "b" * 64,
                                   "command": "synthetic example; not an actual test", "result": "pass"}
        with self.assertRaisesRegex(ValueError, "observed reference"):
            catalogue.validate(self.data)

    def test_failed_verification_cannot_promote(self):
        feature = self.data["features"][0]
        feature.update(reference="neptune", reference_status="not_applicable", implementation_status="verified",
                       verification={"tested_commit": "a" * 40, "artifact_sha256": "b" * 64,
                                     "command": "synthetic example", "result": "fail"})
        with self.assertRaisesRegex(ValueError, "passing evidence"):
            catalogue.validate(self.data)

    def test_duplicate_json_key_rejected_by_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalogue.json"
            path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
            result = subprocess.run([sys.executable, str(CLI), "validate", "--catalogue", str(path)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Duplicate JSON key", result.stderr)

    def test_report_keeps_claims_distinct_and_does_not_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalogue.json"
            sentinel = Path(temp) / "must-not-exist"
            feature = self.data["features"][0]
            feature["verification"] = {"tested_commit": "a" * 40, "artifact_sha256": "b" * 64,
                                       "command": f"touch {sentinel}", "result": "pass"}
            path.write_text(json.dumps(self.data), encoding="utf-8")
            result = subprocess.run([sys.executable, str(CLI), "report", "--catalogue", str(path)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("0 observed references; 0 verified implementations", result.stdout)
            self.assertFalse(sentinel.exists())


if __name__ == "__main__":
    unittest.main()
