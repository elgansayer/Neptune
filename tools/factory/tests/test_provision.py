"""Installer contracts use synthetic outputs; no emulator download is claimed."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import provision as p


class ProvisionTests(unittest.TestCase):
    def test_godot_recipe_accepts_new_stable_pin_but_rejects_paths(self):
        path = self.root / "tools/godot/toolchain.json"
        for name in ("Godot_v4.7.2-stable_linux.x86_64", "Godot_v4.8-stable_linux.x86_64"):
            path.write_text(json.dumps({"binary_name": name}))
            self.assertEqual(p.binary_name("godot", self.root), name)
        for name in (None, 7, "../godot", "/tmp/godot", "Godot_v4.8-beta1_linux.x86_64"):
            path.write_text(json.dumps({"binary_name": name}))
            with self.subTest(name=name), self.assertRaises(p.ProvisionError):
                p.binary_name("godot", self.root)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "repo"
        self.cache = self.home / "cache"
        self.installs = 0
        self.probes = 0
        for relative in ("tools/factory/provision.py", "tools/factory/provision_probe.py",
                         "tools/factory/provision-lock.json", "tools/godot/install.py",
                         "tools/godot/toolchain.json"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p.ROOT / relative, target)
        self.platform = patch.multiple(p.platform, system=lambda: "Linux", machine=lambda: "x86_64")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        self.disk = patch.object(p.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(16*1024**3, 0, 16*1024**3))
        self.disk.start()
        self.addCleanup(self.disk.stop)

    def install(self, tool, recipe, payload, work, runner, root):
        self.installs += 1
        (payload / p.binary_name(tool, root)).write_bytes(b"synthetic tool, not emulator")

    def probe(self, tool, binary, runner, root):
        self.probes += 1
        self.assertEqual(binary.read_bytes(), b"synthetic tool, not emulator")
        return {"scope": "synthetic installer fixture"}

    def ensure(self, name="first", **kwargs):
        return p.ensure("beetle-saturn", self.cache, self.home / name, root=self.root,
                        installer=kwargs.pop("installer", self.install),
                        prober=kwargs.pop("prober", self.probe), **kwargs)

    def test_first_install_then_verified_reuse_without_rebuild(self):
        first = self.ensure()
        second = self.ensure("again")
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(self.installs, 1)
        self.assertEqual(self.probes, 2)
        self.assertEqual(first["binary_sha256"], second["binary_sha256"])
        receipt = json.loads((Path(first["directory"]) / "receipt.json").read_text())
        self.assertEqual(receipt["recipe_sha256"], first["recipe_sha256"])

    def test_corrupt_binary_is_preserved_and_rebuilt_once(self):
        first = self.ensure()
        Path(first["binary"]).write_bytes(b"tampered")
        repaired = self.ensure("repair")
        self.assertFalse(repaired["reused"])
        self.assertEqual(self.installs, 2)
        old = Path(repaired["replaced_cache"]["path"])
        self.assertEqual((old / Path(first["binary"]).name).read_bytes(), b"tampered")

    def test_stale_receipt_cannot_advertise_ready(self):
        first = self.ensure()
        receipt = Path(first["directory"]) / "receipt.json"
        value = json.loads(receipt.read_text())
        value["recipe_sha256"] = "0" * 64
        receipt.write_text(json.dumps(value))
        self.ensure("repair")
        self.assertEqual(self.installs, 2)

    def test_recipe_or_installer_change_gets_a_new_cache_identity(self):
        first = self.ensure()
        path = self.root / "tools/factory/provision_probe.py"
        path.write_text(path.read_text() + "\n# changed probe\n")
        second = self.ensure("updated")
        self.assertNotEqual(first["directory"], second["directory"])
        self.assertTrue(Path(first["binary"]).exists())

    def test_failed_partial_install_is_not_published_and_retry_succeeds(self):
        def broken(tool, recipe, payload, work, runner, root):
            (payload / "partial").write_bytes(b"partial")
            raise p.ProvisionError("command_failed", "deliberate synthetic failure")
        with self.assertRaises(p.ProvisionError):
            self.ensure(installer=broken)
        report = json.loads((self.home / "first/report.json").read_text())
        self.assertEqual(report["conclusion"], "failure")
        self.assertFalse(Path(report["directory"]).exists())
        self.assertEqual(self.ensure("retry")["conclusion"], "success")

    def test_smoke_failure_cannot_publish_success(self):
        def failed(*args):
            raise p.ProvisionError("smoke_failed", "synthetic missing symbol")
        with self.assertRaises(p.ProvisionError):
            self.ensure(prober=failed)
        report = json.loads((self.home / "first/report.json").read_text())
        self.assertFalse(Path(report["directory"]).exists())
        self.assertEqual(report["kind"], "smoke_failed")

    def test_interrupted_staging_never_counts_as_ready(self):
        self.cache.mkdir(mode=0o700)
        orphan = self.cache / ".prepare-beetle-saturn-interrupted"
        orphan.mkdir()
        (orphan / "mednafen_saturn_libretro.so").write_bytes(b"partial")
        report = self.ensure()
        self.assertFalse(report["reused"])
        self.assertEqual(self.installs, 1)
        self.assertTrue(orphan.exists())  # Retention owns old stages, not arbitrary deletion.

    def test_concurrent_installer_is_requeued_without_duplicate_work(self):
        self.cache.mkdir(mode=0o700)
        with (self.cache / "beetle-saturn.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(p.ProvisionError, "Another installer"):
                self.ensure()
        self.assertEqual(self.installs, 0)
        self.assertEqual(json.loads((self.home / "first/report.json").read_text())["kind"], "busy")

    def test_writable_by_other_users_cache_is_rejected_before_any_work(self):
        self.cache.mkdir(mode=0o700)
        for mode in (0o720, 0o702):
            with self.subTest(mode=oct(mode)):
                self.cache.chmod(mode)
                name = "unsafe-%o" % mode
                with self.assertRaisesRegex(p.ProvisionError, "not group/world writable"):
                    self.ensure(name)
                report = json.loads((self.home / name / "report.json").read_text())
                self.assertEqual(report["kind"], "unsafe_path")
                self.assertEqual(report["conclusion"], "failure")
                self.assertEqual(self.installs, 0)
                self.assertEqual(self.probes, 0)
                self.assertEqual(list(self.cache.iterdir()), [])

    def test_unknown_tool_requests_recipe_without_executing_issue_text(self):
        with self.assertRaises(p.ProvisionError) as caught:
            p.ensure("ghidra", self.cache, self.home / "unknown", root=self.root)
        self.assertEqual(caught.exception.kind, "needs_recipe")
        self.assertEqual(json.loads((self.home / "unknown/report.json").read_text())["commands"], [])

    def test_unpinned_source_or_arbitrary_recipe_commands_are_rejected(self):
        path = self.root / "tools/factory/provision-lock.json"
        original = json.loads(path.read_text())
        for name, value in (("commit", "main"), ("repository", "https://untrusted.invalid/tool"),
                            ("commands", ["sudo", "anything"])):
            data = json.loads(json.dumps(original))
            data["tools"]["beetle-saturn"][name] = value
            path.write_text(json.dumps(data))
            with self.subTest(name=name), self.assertRaises(p.ProvisionError):
                self.ensure(name)
        self.assertEqual(self.installs, 0)

    def test_missing_output_and_symlink_output_are_rejected(self):
        outside = self.home / "outside"
        outside.write_bytes(b"must stay")
        for kind in ("empty", "symlink"):
            def bad(tool, recipe, payload, work, runner, root):
                if kind == "symlink":
                    (payload / p.binary_name(tool, root)).symlink_to(outside)
            with self.subTest(kind=kind), self.assertRaises(p.ProvisionError):
                self.ensure(kind, installer=bad)
        self.assertEqual(outside.read_bytes(), b"must stay")

    def test_evidence_reuse_and_symlink_cache_are_rejected(self):
        self.ensure()
        evidence = (self.home / "first/report.json").read_bytes()
        with self.assertRaises(p.ProvisionError):
            self.ensure()
        self.assertEqual((self.home / "first/report.json").read_bytes(), evidence)
        alias = self.home / "alias"
        alias.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaises(p.ProvisionError):
            p.ensure("beetle-saturn", alias, self.home / "symlink", root=self.root)

    def test_disk_shortage_blocks_before_install(self):
        with patch.object(p.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(1, 1, 0)):
            with self.assertRaisesRegex(p.ProvisionError, "free space"):
                self.ensure()
        self.assertEqual(self.installs, 0)

    def test_unsupported_host_and_bad_budget_fail(self):
        with patch.object(p.platform, "machine", return_value="arm64"), self.assertRaises(p.ProvisionError):
            self.ensure("platform")
        with self.assertRaises(p.ProvisionError):
            self.ensure("budget", timeout=0)

    def test_clean_environment_retains_proxy_but_not_credentials(self):
        with patch.dict(os.environ, {"GH_TOKEN": "synthetic", "GIT_CONFIG_COUNT": "1", "HTTPS_PROXY": "http://proxy.test"}):
            env = p.environment(self.home)
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("GIT_CONFIG_COUNT", env)
        self.assertEqual(env["HTTPS_PROXY"], "http://proxy.test")

    def test_real_command_failure_and_timeout_record_failure(self):
        for label, command, timeout in (("exit", [sys.executable, "-c", "raise SystemExit(3)"], 3),
                                        ("timeout", [sys.executable, "-c", "import time; time.sleep(10)"], .15)):
            evidence = self.home / label
            evidence.mkdir()
            report = {"commands": []}
            runner = p.Runner(evidence, report, self.home, time.monotonic() + 4)
            with self.subTest(label=label), self.assertRaises(p.ProvisionError):
                runner.run(command, self.home, timeout)
            self.assertEqual(report["commands"][0]["status"], "failure")

    def test_source_commit_mismatch_stops_before_build(self):
        calls = []
        class FakeRunner:
            def run(self, argv, cwd, timeout=60):
                calls.append(argv)
                return "wrong" if argv == ["git", "rev-parse", "HEAD"] else "synthetic"
        payload = self.home / "payload"
        payload.mkdir()
        recipe = p.identity("beetle-saturn", self.root)[0]
        with patch.object(p.shutil, "which", return_value="/usr/bin/tool"), self.assertRaises(p.ProvisionError):
            p.install("beetle-saturn", recipe, payload, self.home, FakeRunner(), self.root)
        self.assertFalse(any(c[0] == "make" and "-j1" in c for c in calls))

    def test_missing_compiler_is_a_specific_host_dependency(self):
        with patch.object(p.shutil, "which", return_value=None), self.assertRaises(p.ProvisionError) as caught:
            p.install("beetle-saturn", p.identity("beetle-saturn", self.root)[0], self.home, self.home, None, self.root)
        self.assertEqual(caught.exception.kind, "missing_host_dependency")

    def test_real_cli_unknown_tool_exits_nonzero_and_writes_receipt(self):
        result = subprocess.run([sys.executable, str(p.ROOT / "tools/factory/provision.py"), "--tool", "unknown",
                                 "--cache", str(self.cache), "--evidence", str(self.home / "cli")],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("NEPTUNE_TOOL_READY=", result.stdout)
        self.assertEqual(json.loads((self.home / "cli/report.json").read_text())["kind"], "needs_recipe")


class NativeProbeTests(unittest.TestCase):
    def test_real_probe_accepts_synthetic_abi_and_rejects_wrong_version(self):
        # This validates the real dynamic-loader path using a tiny C fixture only.
        required = ("retro_init retro_deinit retro_run retro_reset retro_load_game retro_unload_game "
                    "retro_set_environment retro_set_video_refresh retro_set_audio_sample retro_set_audio_sample_batch "
                    "retro_set_input_poll retro_set_input_state retro_set_controller_port_device retro_serialize_size "
                    "retro_serialize retro_unserialize retro_get_system_av_info retro_get_memory_data retro_get_memory_size").split()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, binary = root / "fixture.c", root / "fixture.so"
            for version in (1, 0):
                source.write_text("#include <stdbool.h>\n" +
                    "struct info {const char *name,*version,*extensions; bool fullpath,extract;};\n" +
                    f"unsigned retro_api_version(void){{return {version};}}\n" +
                    'void retro_get_system_info(struct info *i){*i=(struct info){"Synthetic Saturn", "test", "cue", false, false};}\n' +
                    "\n".join("void " + name + "(void){}" for name in required))
                subprocess.run(["cc", "-shared", "-fPIC", str(source), "-o", str(binary)], check=True, timeout=20,
                               capture_output=True)
                result = subprocess.run([sys.executable, str(p.ROOT / "tools/factory/provision_probe.py"), str(binary)],
                                        capture_output=True, text=True, timeout=10)
                if version == 1:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["scope"], "no-media ABI smoke only")
                else:
                    self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
