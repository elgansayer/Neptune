"""Actual named comparator execution with real Git and explicitly synthetic artifacts."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest

import feature_contracts as features
import test_task_verification as tasks
import verify


class FeatureContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tasks.TaskVerificationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.directory = self.fixture.private / "artifacts"
        self.artifacts = self.directory / features.NAME
        self.artifacts.mkdir(parents=True)
        self.reference = {
            "schema": "neptune.behaviour-trace.v1",
            "contract": {"scenario": "synthetic/factory-contract", "ruleset": "fixture-v1",
                         "observation_schema": "fixture-fixed-point-v1", "input_sha256": "a" * 64,
                         "timebase": {"numerator": 60, "denominator": 1}},
            "source": {"kind": "reference", "build_sha256": "b" * 64,
                       "input_lock_sha256": "c" * 64, "capture_sha256": "d" * 64,
                       "adapter_sha256": "e" * 64},
            "samples": [{"frame": 0, "observations": {"x_fixed": 100, "events": ["place", "explode"]}},
                        {"frame": 1, "observations": {"x_fixed": 110, "events": []}}]}
        self.candidate = copy.deepcopy(self.reference)
        self.candidate["source"].update(kind="implementation", build_sha256="f" * 64)
        self.publish()

    def publish(self):
        for role, value in (("reference", self.reference), ("candidate", self.candidate)):
            (self.artifacts / (role + ".json")).write_text(json.dumps(value))
        self.snapshot = self.fixture.snapshot()
        self.snapshot["task"]["acceptance"].append(features.SELECTOR)
        identities = {"contract": features.identity(self.reference["contract"]),
                      "reference-source": features.identity(self.reference["source"]),
                      "candidate-source": features.identity(self.candidate["source"])}
        for role in ("reference", "candidate"):
            identities[role + "-file"] = hashlib.sha256((self.artifacts / (role + ".json")).read_bytes()).hexdigest()
        self.snapshot["task"]["evidence"] += [features.PREFIX + key + ":" + value for key, value in identities.items()]
        self.fixture.save_snapshot(self.snapshot)

    def run_contract(self, name="verification", **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return verify.verify(self.fixture.paths, self.fixture.private / name, self.fixture.cache,
                                 root=self.fixture.root, runner=kwargs.pop("runner", self.fixture.runner),
                                 intake=kwargs.pop("intake", self.fixture.intake), now=lambda: 1000,
                                 feature_artifacts=kwargs.pop("artifacts", self.directory), **kwargs)

    def rejected(self, name="verification", **kwargs):
        with self.assertRaises((ValueError, OSError, RecursionError)):
            self.run_contract(name, **kwargs)
        report = json.loads((self.fixture.private / name / "report.json").read_text())
        self.assertEqual(report["conclusion"], "failure")
        return report

    def test_actual_comparator_and_task_binding_are_additive_to_path_checks(self):
        result = self.run_contract()
        self.assertEqual(result["schema"], verify.SCHEMA)
        self.assertEqual(len(self.fixture.calls), 5)
        self.assertEqual(list(result["checks"]), list(verify.gate.CORE))
        self.assertEqual(result["task_binding"], self.fixture.bind())
        check = result["feature_checks"][features.NAME]
        self.assertEqual(check["status"], "success")
        self.assertIs(check["comparison"]["match"], True)
        self.assertEqual(check["comparer_sha256"], verify.sha(features.COMPARER))
        self.assertIn("authenticity", check["scope"])

    def test_position_order_and_early_termination_mutations_fail_actual_comparison(self):
        original = copy.deepcopy(self.candidate)
        for kind in ("position", "event-order", "truncated"):
            self.candidate = copy.deepcopy(original)
            if kind == "position":
                self.candidate["samples"][0]["observations"]["x_fixed"] += 1
            elif kind == "event-order":
                self.candidate["samples"][0]["observations"]["events"].reverse()
            else:
                self.candidate["samples"].pop()
            self.publish()  # Rebind hashes, so the actual comparator must detect divergence.
            with self.subTest(kind=kind):
                report = self.rejected(kind)
                check = report["feature_checks"][features.NAME]
                self.assertEqual(check["status"], "failure")
                self.assertIs(check["comparison"]["match"], False)
                self.assertIn("first_frame", check["comparison"])

    def test_missing_required_artifacts_fail_before_path_checks(self):
        self.rejected(artifacts=None)
        self.assertEqual(self.fixture.calls, [])

    def test_artifacts_require_named_trusted_intake(self):
        self.rejected(intake=None)
        self.fixture.save_snapshot()
        self.rejected("no-selector")
        self.assertEqual(self.fixture.calls, [])

    def test_missing_identity_and_unknown_checks_fail_closed(self):
        self.snapshot["task"]["evidence"].pop()
        self.fixture.save_snapshot(self.snapshot)
        self.rejected("incomplete")
        self.publish()
        self.snapshot["task"]["acceptance"].append("check:unrecognised-v1")
        self.fixture.save_snapshot(self.snapshot)
        self.rejected("unknown")
        self.assertEqual(self.fixture.calls, [])

    def test_duplicate_unknown_or_malformed_identity_is_not_ignored(self):
        for name, extra in (("duplicate", self.snapshot["task"]["evidence"][-1]),
                            ("unknown", "trace-v1:other:" + "a" * 64),
                            ("malformed", "trace-v1:contract:invalid")):
            task = copy.deepcopy(self.snapshot["task"])
            task["evidence"].append(extra)
            with self.subTest(name=name), self.assertRaises(ValueError):
                features.requirements(task)

    def test_changed_file_source_and_contract_identities_are_rejected(self):
        original = copy.deepcopy(self.candidate)
        for name in ("file", "source", "contract", "role"):
            self.candidate = copy.deepcopy(original)
            self.publish()
            if name == "file":
                self.candidate["samples"][0]["observations"]["x_fixed"] += 1
            elif name == "source":
                self.candidate["source"]["build_sha256"] = "0" * 64
            elif name == "contract":
                self.candidate["contract"]["timebase"]["numerator"] = 61
            else:
                self.candidate["source"]["kind"] = "reference"
            path = self.artifacts / "candidate.json"
            path.write_text(json.dumps(self.candidate))
            if name != "file":
                # Keep the file expectation current, leaving the independent semantic identity stale.
                prefix = "trace-v1:candidate-file:"
                values = self.snapshot["task"]["evidence"]
                self.snapshot["task"]["evidence"] = [prefix + verify.sha(path) if x.startswith(prefix) else x for x in values]
                self.fixture.save_snapshot(self.snapshot)
            with self.subTest(name=name):
                self.rejected(name)

    def test_missing_symlink_and_oversize_artifacts_are_rejected(self):
        path = self.artifacts / "candidate.json"
        path.unlink()
        self.rejected("missing")
        path.symlink_to(self.artifacts / "reference.json")
        self.rejected("symlink")
        path.unlink()
        with path.open("wb") as output:
            output.truncate(features.trace.MAX_BYTES + 1)
        self.rejected("oversize")

    def test_duplicate_json_keys_and_skipped_receipt_are_not_trace_artifacts(self):
        path = self.artifacts / "candidate.json"
        for name, raw in (("duplicate", '{"schema":1,"schema":2}'),
                          ("skipped", '{"status":"skipped","match":true}'),
                          ("empty", ''), ("truncated", '{"schema":')):
            path.write_text(raw)
            with self.subTest(name=name):
                self.rejected(name)

    def test_replacement_during_path_checks_cannot_pass_cached_observations(self):
        def runner(command, **kwargs):
            result = self.fixture.runner(command, **kwargs)
            if len(self.fixture.calls) == 5:
                (self.artifacts / "candidate.json").write_text('{"status":"success"}')
            return result
        self.rejected(runner=runner)

    def test_artifact_mount_cannot_be_candidate_source_or_output(self):
        self.rejected("inside-source", artifacts=self.fixture.root)
        output = self.fixture.private / "inside-output"
        self.rejected("inside-output", artifacts=output)

    def test_intake_revision_change_after_execution_fails(self):
        def runner(command, **kwargs):
            result = self.fixture.runner(command, **kwargs)
            if len(self.fixture.calls) == 5:
                self.snapshot["task"]["revision"] = "0" * 64
                self.fixture.save_snapshot(self.snapshot)
            return result
        self.rejected(runner=runner)


if __name__ == "__main__":
    unittest.main()
