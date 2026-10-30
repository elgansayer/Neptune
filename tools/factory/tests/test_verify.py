"""Synthetic command receipts test preflight contracts, not Godot health."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import verify


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "game.gd").write_text("synthetic fixture")
        self.cache = self.root / "cache"
        self.cache.mkdir()
        binary = self.cache / "Godot_v4.5-stable_linux.x86_64"
        binary.write_bytes(b"synthetic binary, not an emulator/engine")
        binary.chmod(0o755)
        (self.root / "addon.so").write_bytes(b"synthetic addon")
        (self.root / "tools/godot").mkdir(parents=True)
        self.lock = {"binary_name": binary.name, "binary_sha256": verify.sha(binary),
                     "addons": {"addon.so": verify.sha(self.root / "addon.so")}}
        (self.root / "tools/godot/toolchain.json").write_text(json.dumps(self.lock))
        self.calls = []

    def runner(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    def run_checks(self, paths, runner=None):
        with patch.object(verify.gate, "git", return_value="a" * 40):
            return verify.verify(paths, self.root / "evidence", self.cache,
                                 root=self.root, runner=runner or self.runner)

    def test_selection_is_exactly_the_shared_ci_plan(self):
        for paths, count in [(["docs/readme.md"], 5), (["tools/godot/install.py"], 8),
                             (["game.gd"], 10), (["unknown/new.file"], 10)]:
            self.assertEqual(verify.selection(paths), verify.gate.plan(paths))
            self.assertEqual(len(verify.selection(paths)["required"]), count)

    def test_empty_unsafe_and_unbounded_selection_fails(self):
        for paths in ([], [""], ["../game"], ["/etc/file"], ["a/../file"], ["./file"],
                      ["C:/file"], ["a\\b"], ["a\nfile"], ["."], ["x"] * 1001):
            with self.subTest(paths=str(paths)[:60]), self.assertRaises(ValueError):
                verify.selection(paths)

    def test_metadata_does_not_require_offline_engine(self):
        report = self.run_checks(["docs/deleted.md"])
        self.assertEqual(report["conclusion"], "success")
        self.assertEqual(len(report["checks"]), 5)
        self.assertNotIn("offline_toolchain", report)
        self.assertEqual(report["schema"], verify.SCHEMA)

    def test_native_plan_requires_complete_success_and_records_cache(self):
        report = self.run_checks(["game.gd"])
        self.assertEqual(len(self.calls), 10)
        self.assertEqual(report["offline_toolchain"]["addon_count"], 1)
        self.assertEqual(report["conclusion"], "success")
        self.assertNotIn("event", report["identity"])  # Never impersonate required CI.

    def test_missing_tampered_nonexecutable_or_wrong_engine_fails_before_commands(self):
        binary = self.cache / self.lock["binary_name"]
        for alteration in ("missing", "tamper", "permissions", "addon"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as directory:
                # Direct cache validation avoids creating/reusing evidence receipts.
                original = binary.read_bytes()
                if alteration == "missing": binary.rename(binary.with_suffix(".saved"))
                elif alteration == "tamper": binary.write_bytes(b"changed")
                elif alteration == "permissions": binary.chmod(0o644)
                else: (self.root / "addon.so").write_bytes(b"changed")
                try:
                    with self.assertRaises((ValueError, OSError)):
                        verify.offline_toolchain(self.root, self.cache)
                finally:
                    if alteration == "missing": binary.with_suffix(".saved").rename(binary)
                    binary.write_bytes(original)
                    binary.chmod(0o755)
                    (self.root / "addon.so").write_bytes(b"synthetic addon")
        self.assertEqual(self.calls, [])

    def test_failure_and_timeout_never_publish_success(self):
        for timeout in (False, True):
            def fail(command, **kwargs):
                if timeout: raise subprocess.TimeoutExpired(command, kwargs["timeout"])
                return subprocess.CompletedProcess(command, 1)
            evidence = self.root / ("timeout" if timeout else "failed")
            with patch.object(verify.gate, "git", return_value="a" * 40), self.assertRaises(ValueError):
                verify.verify(["docs/file.md"], evidence, self.cache, root=self.root, runner=fail)
            report = json.loads((evidence / "report.json").read_text())
            self.assertEqual(report["conclusion"], "failure")
            self.assertEqual(len(report["checks"]), 1)

    def test_empty_command_set_and_selected_source_mutation_fail(self):
        with patch.object(verify.gate, "commands", return_value=[]), self.assertRaises(ValueError):
            self.run_checks(["docs/file.md"])
        def change(command, **kwargs):
            (self.root / "game.gd").write_text("changed during verification")
            return subprocess.CompletedProcess(command, 0)
        with patch.object(verify.gate, "git", return_value="a" * 40), self.assertRaisesRegex(ValueError, "changed during"):
            verify.verify(["game.gd"], self.root / "mutated", self.cache, root=self.root, runner=change)

    def test_reused_evidence_and_selected_symlinks_fail(self):
        evidence = self.root / "old"
        evidence.mkdir()
        (evidence / "report.json").write_text('{"old":"must remain"}')
        with self.assertRaises(ValueError): verify.verify(["docs/file.md"], evidence, self.cache)
        self.assertEqual((evidence / "report.json").read_text(), '{"old":"must remain"}')
        (self.root / "alias").symlink_to(self.root / "game.gd")
        with self.assertRaisesRegex(ValueError, "symlink"):
            verify.selected_contents(self.root, ["alias"])

    def test_real_cli_missing_offline_cache_exits_nonzero(self):
        command = [sys.executable, str(Path(verify.__file__)), "--changed-path", "game_instance.gd",
                   "--toolchain", str(self.root / "missing"), "--evidence", str(self.root / "cli")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("offline Godot", result.stderr)
        self.assertEqual(json.loads((self.root / "cli/report.json").read_text())["conclusion"], "failure")


if __name__ == "__main__": unittest.main()
