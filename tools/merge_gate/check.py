#!/usr/bin/env python3
"""Exercise required-selection and real Git checkout rejection boundaries."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from run import assert_pass, checkout_identity, commands, git, godot_binary_name, plan
from unittest.mock import patch


class GateContracts(unittest.TestCase):
    def test_updated_lock_selects_engine_without_changing_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / "tools/godot/toolchain.json"
            lock.parent.mkdir(parents=True)
            for version in ("4.7.2", "4.8"):
                name = f"Godot_v{version}-stable_linux.x86_64"
                lock.write_text(json.dumps({"binary_name": name}))
                with patch("run.ROOT", root):
                    checks = commands("gameplay", root / "evidence", root / "cache")
                for _, command, _ in checks:
                    if "--godot" in command:
                        self.assertEqual(command[command.index("--godot") + 1], str(root / "cache" / name))

    def test_engine_lock_rejects_paths_prereleases_and_other_platforms(self):
        for name in (None, 7, "../Godot_v4.7.2-stable_linux.x86_64", "/tmp/godot",
                     "Godot_v4.7.2-rc1_linux.x86_64", "Godot_v4.7.2-stable_windows.exe"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                godot_binary_name({"binary_name": name})

    def test_empty_or_unsafe_selection_fails(self):
        for paths in ([], [""], ["../game.gd"], ["/game.gd"], ["docs/../game.gd"]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                plan(paths)

    def test_metadata_has_real_nonempty_tests(self):
        result = plan(["docs/restart/README.md", "tools/merge_gate/run.py"])
        self.assertEqual(result["mode"], "metadata")
        self.assertIn("input-tooling", result["required"])
        self.assertIn("gate-contracts", result["required"])

    def test_factory_is_tooling_but_its_checks_are_always_required(self):
        self.assertEqual(plan(["tools/factory/store.py"])["mode"], "metadata")
        for paths in (["README.md"], ["game_instance.gd"]):
            self.assertIn("factory-contracts", plan(paths)["required"])
        report, identity = self.passing()
        del report["checks"]["factory-contracts"]
        with self.assertRaises(ValueError):
            assert_pass(report, identity)

    def test_film_contracts_are_required_for_every_selection(self):
        for paths in (["README.md"], ["tools/saturn_film/film.py"], ["game_instance.gd"]):
            self.assertIn("film-contracts", plan(paths)["required"])
        checks = dict((name, command) for name, command, _ in
                      commands("metadata", Path("/tmp/evidence"), Path("/tmp/binary")))
        self.assertEqual(checks["film-contracts"][-1], "tools/saturn_film/check.py")
        report, identity = self.passing()
        del report["checks"]["film-contracts"]
        with self.assertRaises(ValueError):
            assert_pass(report, identity)

    def test_gameplay_and_unknown_paths_require_runtime_and_full_bots(self):
        paths = ["shared/constants.gd", "game_config.gd", "new-gameplay/file.json",
                 "project.godot", "maps/new.pck", "characters/new.png", "assets/new.wav",
                 "tests/survival/test_new.gd", "ai/new.gd", "shared/rpc_interface.gd",
                 "tools/godot/runtime_probe.gd", "tools/godot/check_runtime.py",
                 "addons/limboai/liblimboai.so", "export_presets.cfg", "unknown"]
        for path in paths:
            with self.subTest(path=path):
                required = plan(["README.md", path])["required"]
                self.assertIn("native-runtime", required)
                self.assertIn("native-bots", required)

    def test_runner_only_still_executes_native_contracts(self):
        result = plan(["tests/bot_test_runner.gd", "tools/godot/run_bot_tests.py"])
        self.assertEqual(result["mode"], "runner")
        self.assertIn("native-project", result["required"])

    def test_every_plan_has_matching_executable_commands(self):
        for paths in (["README.md"], ["run_bot_tests.sh"], ["game_instance.gd"]):
            selection = plan(paths)
            actual = commands(selection["mode"], Path("/tmp/evidence"), Path("/tmp/binary"))
            self.assertEqual([name for name, _, _ in actual], selection["required"])
            for _, command, timeout in actual:
                self.assertTrue(command)
                self.assertGreater(timeout, 0)

    def passing(self):
        selection = plan(["README.md"])
        identity = {"head": "a" * 40, "base": "b" * 40, "merge": "c" * 40}
        checks = {name: {"status": "success", "exit": 0, "command": ["python3", "actual.py"]}
                  for name in selection["required"]}
        return {"identity": identity, "plan": selection, "checks": checks}, identity

    def test_success_is_accepted(self):
        report, identity = self.passing()
        assert_pass(report, identity)

    def test_engine_and_supervisor_logs_are_distinct_and_bounded(self):
        evidence = Path("/tmp/evidence")
        native = next(command for name, command, _ in commands("gameplay", evidence, Path("/tmp/binary")) if name == "native-bots")
        engine_log = Path(native[native.index("--log") + 1])
        self.assertNotEqual(engine_log, evidence / "native-bots.log")
        self.assertEqual(engine_log.parent, evidence)
        self.assertEqual(native[native.index("--max-log-mib") + 1], "16")

    def test_failure_missing_skipped_neutral_and_empty_do_not_pass(self):
        for status in ("failure", "skipped", "neutral", "cancelled", "timed_out", "running", None):
            report, identity = self.passing()
            report["checks"]["input-tooling"]["status"] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                assert_pass(report, identity)
        for missing in ("input-tooling", "catalogue-tests", "gate-contracts"):
            report, identity = self.passing()
            del report["checks"][missing]
            with self.assertRaises(ValueError):
                assert_pass(report, identity)
        report, identity = self.passing()
        report["checks"] = {}
        with self.assertRaises(ValueError):
            assert_pass(report, identity)

    def test_wrong_exit_or_no_command_is_not_success(self):
        for field, value in (("exit", 1), ("exit", None), ("command", [])):
            report, identity = self.passing()
            report["checks"]["input-tooling"][field] = value
            with self.assertRaises(ValueError):
                assert_pass(report, identity)

    def test_report_for_stale_head_or_base_is_rejected(self):
        for key in ("head", "base", "merge"):
            report, identity = self.passing()
            changed = deepcopy(identity)
            changed[key] = "d" * 40
            with self.assertRaises(ValueError):
                assert_pass(report, changed)

    def test_missing_checks_cannot_be_hidden_by_changed_plan(self):
        report, identity = self.passing()
        report["plan"]["paths"].append("game_instance.gd")
        with self.assertRaises(ValueError):
            assert_pass(report, identity)


class ActualGitCheckout(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="neptune-gate-git-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.call("init", "-q", "-b", "main")
        self.call("config", "user.name", "Gate Fixture")
        self.call("config", "user.email", "gate@example.invalid")
        self.commit("base.txt")
        self.base = git("rev-parse", "HEAD", root=self.root)
        self.call("switch", "-q", "-c", "candidate")
        self.commit("README.md")
        self.head = git("rev-parse", "HEAD", root=self.root)
        self.call("switch", "-q", "main")

    def call(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.STDOUT)

    def commit(self, name):
        (self.root / name).write_text(name)
        self.call("add", name)
        self.call("commit", "-qm", name)

    def event(self):
        return {"number": 123, "pull_request": {"base": {"sha": self.base}, "head": {"sha": self.head}}}

    def merge(self):
        self.call("merge", "--no-ff", "candidate", "-qm", "test merge")

    def test_actual_merge_and_head_recorded(self):
        self.merge()
        identity, paths = checkout_identity(self.event(), "pull_request", self.root)
        self.assertEqual(paths, ["README.md"])
        self.assertEqual(identity["head"], self.head)
        self.assertEqual(identity["base"], self.base)
        self.assertNotEqual(identity["merge"], self.head)

    def test_stale_event_head_or_base_rejected(self):
        self.merge()
        for member in ("base", "head"):
            event = self.event()
            event["pull_request"][member]["sha"] = "a" * 40
            with self.subTest(member=member), self.assertRaises(ValueError):
                checkout_identity(event, "pull_request", self.root)

    def test_real_head_behind_base_rejected_even_with_valid_merge(self):
        self.commit("new-base.txt")
        self.base = git("rev-parse", "HEAD", root=self.root)
        self.merge()
        with self.assertRaisesRegex(ValueError, "behind current base"):
            checkout_identity(self.event(), "pull_request", self.root)

    def test_branch_checkout_cannot_replace_merge_checkout(self):
        self.call("switch", "-q", "candidate")
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            checkout_identity(self.event(), "pull_request", self.root)

    def test_unsupported_event_or_invalid_sha_rejected(self):
        with self.assertRaises(ValueError):
            checkout_identity({}, "workflow_dispatch", self.root)
        event = self.event()
        event["pull_request"]["head"]["sha"] = "missing"
        with self.assertRaises(ValueError):
            checkout_identity(event, "pull_request", self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
