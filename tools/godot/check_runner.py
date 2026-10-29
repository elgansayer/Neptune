#!/usr/bin/env python3
"""Exercise runner failure boundaries using real Godot, not gameplay assertions."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GODOT = "godot"
PASS = "extends Node\nfunc execute() -> bool:\n\treturn true\n"


class RunnerChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="neptune-runner-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / "tests").mkdir()
        (self.project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Runner verification"\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        for name in ("bot_test_runner.gd", "bot_test_runner.tscn"):
            shutil.copyfile(ROOT / "tests" / name, self.project / "tests" / name)

    def fixture(self, name, content):
        path = self.project / "tests" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def run_case(self, expected, *selection, timeout=5, reason=None):
        command = [sys.executable, str(ROOT / "tools/godot/run_bot_tests.py"),
                   "--godot", GODOT, "--project", str(self.project),
                   "--timeout", str(timeout), *selection]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout + 10)
        self.assertEqual(result.returncode, expected, result.stdout)
        if reason:
            self.assertIn(reason, result.stdout)
        return result.stdout

    def test_recursive_both_names_and_sorted_order(self):
        self.fixture("z_test.gd", PASS)
        self.fixture("nested/deeper/test_a.gd", PASS)
        output = self.run_case(0, reason="2 tests in 2 files")
        self.assertLess(output.index("Running test file: res://tests/nested"),
                        output.index("Running test file: res://tests/z_test"))

    def test_specific_filename_stem_and_full_path(self):
        self.fixture("nested/test_a.gd", PASS)
        self.fixture("test_fail.gd", PASS.replace("true", "false"))
        for name in ("test_a", "test_a.gd", "res://tests/nested/test_a.gd"):
            with self.subTest(name=name):
                self.run_case(0, "--run-specific", name, reason="1 tests in 1 files")

    def test_category_only_selects_matching_directory(self):
        self.fixture("survival/nested/test_a.gd", PASS)
        self.fixture("survival_other/test_fail.gd", PASS.replace("true", "false"))
        self.run_case(0, "--run-category", "survival", reason="1 tests in 1 files")

    def test_nested_false_fails(self):
        self.fixture("nested/test_fail.gd", PASS.replace("true", "false"))
        self.run_case(1, reason="execute() returned false")

    def test_empty_discovery_fails(self):
        self.run_case(1, reason="No test files selected")

    def test_missing_selection_fails(self):
        self.fixture("test_a.gd", PASS)
        self.run_case(1, "--run-specific", "missing", reason="0 matches")

    def test_ambiguous_selection_fails(self):
        self.fixture("a/test_a.gd", PASS)
        self.fixture("b/test_a.gd", PASS)
        self.run_case(1, "--run-specific", "test_a", reason="2 matches")

    def test_missing_category_fails(self):
        self.fixture("test_a.gd", PASS)
        self.run_case(1, "--run-category", "missing", reason="No test files selected")

    def test_parse_error_fails(self):
        self.fixture("nested/test_bad.gd", "extends Node\nfunc execute( !!\n")
        self.run_case(1, reason="Parse Error")

    def test_runtime_error_cannot_hide_behind_success(self):
        self.fixture("test_error.gd", 'extends Node\nfunc execute() -> bool:\n\tpush_error("injected error")\n\treturn true\n')
        self.run_case(1, reason="Engine exit or logged engine/script error")

    def test_null_result_fails(self):
        self.fixture("test_null.gd", "extends Node\nfunc execute():\n\treturn null\n")
        self.run_case(1, reason="execute() requires a bool")

    def test_invalid_contract_fails(self):
        self.fixture("test_missing.gd", "extends Node\n")
        self.run_case(1, reason="Missing run_tests()/execute() contract")

    def test_non_node_fails(self):
        self.fixture("test_resource.gd", "extends RefCounted\n")
        self.run_case(1, reason="Test script must extend Node")

    def test_empty_suite_fails(self):
        self.fixture("test_empty.gd", 'extends Node\nvar passed = 0\nvar failed = 0\nvar results = {}\nfunc run_tests():\n\tpass\n')
        self.run_case(1, reason="Suite must report at least one result")

    def test_inconsistent_suite_fails(self):
        self.fixture("test_counts.gd", 'extends Node\nvar passed = 1\nvar failed = 0\nvar results = {"case": "FAIL: injected"}\nfunc run_tests():\n\tpass\n')
        self.run_case(1, reason="Suite counters disagree")

    def test_explicit_suite_results_pass(self):
        self.fixture("test_suite.gd", 'extends Node\nvar passed = 1\nvar failed = 0\nvar results = {"case": "PASS"}\nfunc run_tests():\n\tpass\n')
        self.run_case(0, reason="1 tests in 1 files")

    def test_legacy_setup_execute_teardown(self):
        self.fixture("test_legacy.gd", 'extends Node\nvar test_result = ""\nvar ready_to_run = false\nfunc setup():\n\tready_to_run = true\nfunc execute():\n\tif ready_to_run:\n\t\ttest_result = "PASS: setup ran"\nfunc teardown():\n\tprint("TEARDOWN_RAN")\n')
        self.run_case(0, reason="TEARDOWN_RAN")

    def test_inconclusive_legacy_fails(self):
        self.fixture("test_warn.gd", 'extends Node\nvar test_result = "WARN: no bomb"\nfunc execute():\n\tpass\n')
        self.run_case(1, reason="inconclusive")

    def test_timeout_fails(self):
        self.fixture("test_hang.gd", 'extends Node\nfunc execute():\n\tawait get_tree().create_timer(20).timeout\n\treturn true\n')
        self.run_case(1, timeout=0.5, reason="FAIL: timeout")

    def test_terminated_supervisor_reaps_godot(self):
        self.fixture("test_hang.gd", 'extends Node\nfunc execute():\n\tvar file = FileAccess.open("res://godot.pid", FileAccess.WRITE)\n\tfile.store_string(str(OS.get_process_id()))\n\tfile.close()\n\tawait get_tree().create_timer(30).timeout\n\treturn true\n')
        command = [sys.executable, str(ROOT / "tools/godot/run_bot_tests.py"),
                   "--godot", GODOT, "--project", str(self.project), "--timeout", "40"]
        with (self.project / "supervisor.log").open("w") as output:
            process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
            try:
                pid_file = self.project / "godot.pid"
                deadline = time.monotonic() + 5
                while not pid_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pid_file.exists(), "Godot did not reach the hanging fixture")
                pid = int(pid_file.read_text())
                process.send_signal(signal.SIGTERM)
                self.assertNotEqual(process.wait(timeout=5), 0)
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)

    def test_early_zero_exit_without_summary_fails(self):
        self.fixture("test_quit.gd", 'extends Node\nfunc execute():\n\tget_tree().quit(0)\n\tawait get_tree().process_frame\n')
        self.run_case(1, reason="Expected exactly one complete test summary")

    def test_shell_entrypoint_works_from_other_directory(self):
        self.fixture("test_a.gd", PASS)
        result = subprocess.run(
            ["bash", str(ROOT / "run_bot_tests.sh"), "--godot", GODOT,
             "--project", str(self.project)], cwd="/tmp", text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=os.environ.get("GODOT_BIN", "godot"))
    args = parser.parse_args()
    GODOT = args.godot
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RunnerChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
