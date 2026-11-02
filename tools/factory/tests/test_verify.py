"""Synthetic command receipts test preflight contracts, not Godot health."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

import verify


class VerificationTests(unittest.TestCase):
    # Representative selections retain every baseline and applicable native check.
    CORE_COUNT = len(verify.gate.CORE)
    RUNNER_COUNT = CORE_COUNT + len(verify.gate.NATIVE)
    GAMEPLAY_COUNT = RUNNER_COUNT + len(verify.gate.RUNTIME)
    SELECTIONS = [(["README.md"], "metadata", CORE_COUNT),
                  (["docs/readme.md", "tools/factory/verify.py"], "metadata", CORE_COUNT),
                  (["tools/godot/install.py"], "runner", RUNNER_COUNT),
                  (["README.md", "tools/godot/toolchain.json"], "runner", RUNNER_COUNT),
                  (["game.gd"], "gameplay", GAMEPLAY_COUNT),
                  (["unknown/new.file"], "gameplay", GAMEPLAY_COUNT),
                  (["tools/godot/install.py", "game.gd", "README.md"], "gameplay", GAMEPLAY_COUNT)]

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
        self.lock = {"godot_version": "synthetic.4.5", "binary_name": binary.name, "binary_sha256": verify.sha(binary),
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
        for paths, count in [(["docs/readme.md"], self.CORE_COUNT),
                             (["tools/godot/install.py"], self.RUNNER_COUNT),
                             (["game.gd"], self.GAMEPLAY_COUNT),
                             (["unknown/new.file"], self.GAMEPLAY_COUNT)]:
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
        self.assertEqual(len(report["checks"]), self.CORE_COUNT)
        self.assertNotIn("offline_toolchain", report)
        self.assertEqual(report["schema"], verify.SCHEMA)

    def test_native_plan_requires_complete_success_and_records_cache(self):
        report = self.run_checks(["game.gd"])
        self.assertEqual(len(self.calls), self.GAMEPLAY_COUNT)
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

    def write_lock(self, lock):
        (self.root / "tools/godot/toolchain.json").write_text(lock if isinstance(lock, str) else json.dumps(lock))

    def cli(self, *arguments, cwd):
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, str(Path(verify.__file__)), *arguments], capture_output=True,
                              text=True, timeout=10, cwd=cwd, env=environment)

    def empty_directory(self):
        directory = self.root / "empty-cwd"
        directory.mkdir()
        return directory

    def test_plan_names_exactly_the_checks_and_cache_use_of_a_real_run(self):
        for index, (paths, mode, count) in enumerate(self.SELECTIONS):
            with self.subTest(paths=paths):
                planned = verify.requirements(paths, root=self.root)
                self.assertEqual(planned["plan"], verify.gate.plan(paths))
                self.assertEqual((planned["plan"]["mode"], len(planned["plan"]["required"])), (mode, count))
                with patch.object(verify.gate, "git", return_value="a" * 40):
                    ran = verify.verify(paths, self.root / ("run-%d" % index), self.cache,
                                        root=self.root, runner=self.runner)
                self.assertEqual(ran["plan"], planned["plan"])
                self.assertEqual(list(ran["checks"]), planned["plan"]["required"])
                self.assertEqual("offline_toolchain" in ran, planned["native"]["required"])
                if planned["native"]["required"]:
                    self.assertEqual(planned["native"]["toolchain"]["lock_sha256"], ran["offline_toolchain"]["lock_sha256"])

    def test_baseline_prerequisites_are_separate_from_native_requirements(self):
        core, native_checks = list(verify.gate.CORE), list(verify.gate.NATIVE)
        for paths, mode, _ in self.SELECTIONS:
            with self.subTest(paths=paths):
                result = verify.requirements(paths, root=self.root)
                self.assertEqual(set(result), {"schema", "scope", "plan", "baseline", "native"})
                self.assertEqual(result["baseline"], {"checks": core, "python": ">=3.11", "executables": ["cc", "git", "openssl"]})
                native = result["native"]
                self.assertEqual(set(native), {"required", "checks", "executables", "toolchain"})
                self.assertEqual(result["baseline"]["checks"] + native["checks"], result["plan"]["required"])
                self.assertEqual(native["required"], mode != "metadata")
                self.assertEqual(native["checks"], {"metadata": [], "runner": native_checks,
                                                    "gameplay": native_checks + list(verify.gate.RUNTIME)}[mode])
                self.assertEqual(native["executables"], ["Xvfb"] if mode == "gameplay" else [])
                self.assertEqual(native["toolchain"] is not None, native["required"])
        self.assertEqual(verify.requirements(["README.md"], root=self.root)["native"],
                         {"required": False, "checks": [], "executables": [], "toolchain": None})

    def test_display_requirement_tracks_the_shared_graphical_runtime_command(self):
        commands = verify.gate.commands("gameplay", Path("evidence"), Path("toolchain"))
        self.assertEqual([name for name, command, _ in commands if "--graphical" in command], ["native-runtime"])

    def test_native_requirement_is_the_pinned_lock_with_cache_engine_and_addons_absent(self):
        self.write_lock({**self.lock, "archive_url": "https://download.invalid/godot.zip", "archive_sha256": "9" * 64})
        observed = verify.offline_toolchain(self.root, self.cache)  # Valid while everything is still present.
        shutil.rmtree(self.cache)
        (self.root / "addon.so").unlink()
        before = sorted(self.root.rglob("*"))
        result = verify.requirements(["game.gd"], root=self.root)
        self.assertEqual(result["native"]["toolchain"], {
            "tool": "godot", "lock": "tools/godot/toolchain.json",
            "lock_sha256": hashlib.sha256((self.root / "tools/godot/toolchain.json").read_bytes()).hexdigest(),
            "godot_version": "synthetic.4.5", "binary_name": "Godot_v4.5-stable_linux.x86_64",
            "binary_sha256": self.lock["binary_sha256"], "addons": self.lock["addons"]})
        self.assertEqual(result["native"]["toolchain"]["lock_sha256"], observed["lock_sha256"])
        self.assertEqual(len(result["native"]["toolchain"]["addons"]), observed["addon_count"])
        self.assertNotIn("download.invalid", json.dumps(result))  # Identities only: no download location.
        self.assertEqual(sorted(self.root.rglob("*")), before)
        with self.assertRaisesRegex(ValueError, "offline Godot"):  # Real verification still demands them.
            self.run_checks(["game.gd"])
        self.assertEqual(self.calls, [])

    def test_metadata_plan_does_not_read_the_lock(self):
        (self.root / "tools/godot/toolchain.json").unlink()
        self.assertFalse(verify.requirements(["README.md"], root=self.root)["native"]["required"])

    def test_native_plan_fails_closed_on_missing_or_invalid_lock(self):
        without = lambda key: {name: value for name, value in self.lock.items() if name != key}
        invalid = {"wrong engine": {**self.lock, "binary_name": "Godot_v4.5-stable_windows.exe"},
                   "no version": without("godot_version"), "blank version": {**self.lock, "godot_version": ""},
                   "short binary hash": {**self.lock, "binary_sha256": "abc"},
                   "uppercase binary hash": {**self.lock, "binary_sha256": "A" * 64},
                   "no addons": without("addons"), "empty addons": {**self.lock, "addons": {}},
                   "listed addons": {**self.lock, "addons": ["addon.so"]},
                   "unsafe addon path": {**self.lock, "addons": {"../addon.so": "a" * 64}},
                   "absolute addon path": {**self.lock, "addons": {"/addon.so": "a" * 64}},
                   "bad addon hash": {**self.lock, "addons": {"addon.so": "not-a-hash"}},
                   "numeric addon hash": {**self.lock, "addons": {"addon.so": 7}},
                   "malformed json": "{", "array": "[]", "null": "null"}
        self.write_lock(self.lock)
        self.assertTrue(verify.requirements(["game.gd"], root=self.root)["native"]["required"])  # Control.
        for name, lock in invalid.items():
            self.write_lock(lock)
            for paths in (["tools/godot/install.py"], ["game.gd"]):
                with self.subTest(lock=name, paths=paths), self.assertRaises(ValueError):
                    verify.requirements(paths, root=self.root)
        (self.root / "tools/godot/toolchain.json").unlink()
        with self.assertRaises(OSError):
            verify.requirements(["game.gd"], root=self.root)

    def test_plan_starts_no_process_download_or_verification_and_creates_nothing(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("planning must not run, install, download, write or verify anything")
        before, output = sorted(self.root.rglob("*")), io.StringIO()
        with contextlib.ExitStack() as stack:
            for owner, name in [(subprocess, "run"), (subprocess, "Popen"), (subprocess, "check_output"),
                                (os, "system"), (urllib.request, "urlopen"), (verify, "verify"),
                                (verify, "offline_toolchain"), (Path, "mkdir"), (Path, "write_text"),
                                (Path, "write_bytes")]:
                stack.enter_context(patch.object(owner, name, forbidden))
            for paths, _, _ in self.SELECTIONS:
                verify.requirements(paths, root=self.root)
            with contextlib.redirect_stdout(output):
                self.assertEqual(verify.main(["--plan", "--changed-path", "game.gd"]), 0)
        self.assertEqual(sorted(self.root.rglob("*")), before)
        self.assertEqual(len(output.getvalue().splitlines()), 1)

    def test_cli_plan_emits_one_structured_result_without_toolchain_or_evidence_arguments(self):
        work = self.empty_directory()
        result = self.cli("--plan", "--changed-path", "README.md", cwd=work)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(len(result.stdout.splitlines()), 1)
        prefix, separator, payload = result.stdout.rstrip("\n").partition("=")
        self.assertEqual((prefix, separator), ("NEPTUNE_FACTORY_REQUIREMENTS", "="))
        report = json.loads(payload)
        self.assertEqual(report["schema"], "neptune.factory-requirements.v1")
        self.assertTrue(report["scope"].startswith("requirements only"))
        self.assertEqual(report, verify.requirements(["README.md"]))
        self.assertEqual(report["plan"], verify.gate.plan(["README.md"]))
        # A plan is not a receipt: nothing here can be mistaken for a verification result.
        self.assertTrue(all(key not in report for key in ("conclusion", "identity", "checks", "offline_toolchain")))
        self.assertNotIn("NEPTUNE_FACTORY_VERIFICATION", result.stdout)
        self.assertEqual(list(work.iterdir()), [])

    def test_cli_plan_stays_one_parseable_line_for_unusual_valid_paths(self):
        paths = ["docs/naïve.md", "docs/line separator.md", 'docs/quote"d.md', "docs/naïve.md"]
        result = self.cli("--plan", *[argument for path in paths for argument in ("--changed-path", path)],
                          cwd=self.empty_directory())
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(len(result.stdout.splitlines()), 1)
        report = json.loads(result.stdout.partition("=")[2])
        self.assertEqual(report["plan"]["paths"], sorted(set(paths)))  # Duplicates collapse, as in CI.
        self.assertEqual(report["plan"], verify.gate.plan(paths))

    def test_cli_plan_for_gameplay_reports_the_repository_lock_without_an_engine_argument(self):
        work = self.empty_directory()
        result = self.cli("--plan", "--changed-path", "game_instance.gd", "--changed-path", "README.md", cwd=work)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        report = json.loads(result.stdout.partition("=")[2])
        lock_path = verify.ROOT / "tools/godot/toolchain.json"
        lock = json.loads(lock_path.read_text())
        self.assertEqual(report["plan"]["paths"], ["README.md", "game_instance.gd"])
        self.assertEqual((report["plan"]["mode"], len(report["plan"]["required"])),
                         ("gameplay", self.GAMEPLAY_COUNT))
        toolchain = report["native"]["toolchain"]
        self.assertEqual(toolchain["lock_sha256"], verify.sha(lock_path))
        for key in ("godot_version", "binary_name", "binary_sha256", "addons"):
            self.assertEqual(toolchain[key], lock[key])
        self.assertNotIn(lock["archive_url"], result.stdout)
        self.assertEqual(list(work.iterdir()), [])

    def test_cli_plan_rejects_empty_unsafe_or_unbounded_selection_without_output(self):
        work = self.empty_directory()
        for paths in ([""], ["../outside"], ["/etc/passwd"], ["a/../b"], ["./file"], ["."], ["C:/file"],
                      ["a\\b"], ["a\nfile"], ["README.md", "../outside"], ["x"] * 1001):
            with self.subTest(paths=str(paths)[:60]):
                arguments = [argument for path in paths for argument in ("--changed-path", path)]
                result = self.cli("--plan", *arguments, cwd=work)
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertTrue(result.stderr.startswith("FAIL: "), result.stderr)
        self.assertEqual(list(work.iterdir()), [])

    def test_cli_usage_errors_keep_verification_inputs_required_and_reject_them_for_plan(self):
        evidence, toolchain = self.root / "new-evidence", str(self.cache)
        for arguments, message in [
                (["--plan"], "required: --changed-path"),
                (["--plan", "--changed-path", "README.md", "--toolchain", toolchain], "remove --toolchain"),
                (["--plan", "--changed-path", "README.md", "--evidence", str(evidence)], "remove --evidence"),
                (["--plan", "--changed-path", "README.md", "--toolchain", toolchain, "--evidence", str(evidence)],
                 "remove --toolchain, --evidence"),
                (["--changed-path", "README.md"], "required: --toolchain, --evidence"),
                (["--changed-path", "README.md", "--toolchain", toolchain], "required: --evidence"),
                (["--changed-path", "README.md", "--evidence", str(evidence)], "required: --toolchain")]:
            with self.subTest(arguments=arguments):
                result = self.cli(*arguments, cwd=self.root)
                self.assertEqual((result.returncode, result.stdout), (2, ""))
                self.assertIn(message, result.stderr)
        self.assertFalse(evidence.exists())


if __name__ == "__main__": unittest.main()
