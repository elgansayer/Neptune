"""Installer contracts use synthetic outputs; no emulator download is claimed."""
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tarfile
import time
import unittest
from unittest.mock import MagicMock, patch

import provision as p
import provision_xvfb as xvfb


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
        for relative in ("tools/factory/provision.py", "tools/factory/provision_probe.py", "tools/factory/provision_xvfb.py", "tools/factory/provision_ocr.py",
                         "tools/factory/provision-lock.json", "tools/godot/install.py",
                         "tools/godot/toolchain.json", "tools/factory/provision_call_trace.py",
                         "tools/factory/provision_call_trace.h", "tools/factory/provision_call_trace_abi.py",
                         "tools/factory/provision_context_trace.py", "tools/factory/provision_context_trace.h",
                         "tools/factory/provision_context_trace_abi.py", "tools/factory/provision_ghidra.py",
                         "tools/factory/provision_ghidra_smoke.java", "tools/factory/provision_init_trace.py",
                         "tools/factory/provision_init_trace.h", "tools/factory/provision_init_trace_abi.py",
                         "tools/factory/provision_command_trace.py", "tools/factory/provision_command_trace.h",
                         "tools/factory/provision_command_trace_abi.py"):
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

    def test_xvfb_uses_existing_publication_lock_and_reuse_contract(self):
        first = p.ensure("xvfb", self.cache, self.home / "first", root=self.root,
                         installer=self.install, prober=self.probe)
        again = p.ensure("xvfb", self.cache, self.home / "again", root=self.root,
                         installer=self.install, prober=self.probe)
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual((self.installs, self.probes), (1, 2))
        self.assertEqual(Path(first["binary"]).name, "Xvfb")

    def test_ocr_uses_existing_publication_lock_and_reuse_contract(self):
        first = p.ensure("tesseract", self.cache, self.home / "first", root=self.root,
                         installer=self.install, prober=self.probe)
        again = p.ensure("tesseract", self.cache, self.home / "again", root=self.root,
                         installer=self.install, prober=self.probe)
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual((self.installs, self.probes), (1, 2))
        self.assertEqual(Path(first["binary"]).name, "tesseract")

    def test_trace_core_has_separate_identity_and_uses_the_existing_reuse_protocol(self):
        regular = p.identity("beetle-saturn", self.root)
        instrumented = p.identity("beetle-saturn-call-trace", self.root)
        self.assertNotEqual(regular[2], instrumented[2])
        self.assertIn("tools/factory/provision_call_trace.h", instrumented[1]["installer_sources"])
        first = p.ensure("beetle-saturn-call-trace", self.cache, self.home / "first", root=self.root,
                         installer=self.install, prober=self.probe)
        again = p.ensure("beetle-saturn-call-trace", self.cache, self.home / "again", root=self.root,
                         installer=self.install, prober=self.probe)
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual((self.installs, self.probes), (1, 2))

    def test_context_core_is_separate_and_all_patch_dependencies_are_keyed(self):
        tool = "beetle-saturn-context-trace"
        recipe, inputs, key = p.identity(tool, self.root)
        self.assertEqual(recipe["kind"], "beetle-context-trace")
        self.assertNotEqual(key, p.identity("beetle-saturn-call-trace", self.root)[2])
        self.assertIn("tools/factory/provision_call_trace.py", inputs["installer_sources"])
        self.assertIn("tools/factory/provision_context_trace.h", inputs["installer_sources"])
        first = p.ensure(tool, self.cache, self.home / "first", root=self.root,
                         installer=self.install, prober=self.probe)
        again = p.ensure(tool, self.cache, self.home / "again", root=self.root,
                         installer=self.install, prober=self.probe)
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual((self.installs, self.probes), (1, 2))
        header = self.root / "tools/factory/provision_context_trace.h"
        header.write_bytes(header.read_bytes() + b"\n/* owned identity mutation */\n")
        self.assertNotEqual(key, p.identity(tool, self.root)[2])

    def test_ghidra_uses_existing_publication_and_reuse_contract(self):
        first = p.ensure("ghidra", self.cache, self.home / "first", root=self.root,
                         installer=self.install, prober=self.probe)
        again = p.ensure("ghidra", self.cache, self.home / "again", root=self.root,
                         installer=self.install, prober=self.probe)
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual((self.installs, self.probes), (1, 2))
        self.assertEqual(Path(first["binary"]).name, "ghidra-headless")

    def test_init_core_is_separate_and_reuses_without_adopting_other_observers(self):
        tool = "beetle-saturn-init-trace"
        recipe, inputs, key = p.identity(tool, self.root)
        old_context = p.identity("beetle-saturn-context-trace", self.root)[2]
        self.assertEqual(recipe["kind"], "beetle-init-trace")
        self.assertNotEqual(key, old_context)
        self.assertIn("tools/factory/provision_init_trace_abi.py", inputs["installer_sources"])
        self.assertNotIn("tools/factory/provision_context_trace.h", inputs["installer_sources"])
        first = p.ensure(tool, self.cache, self.home / "first", root=self.root,
                         installer=self.install, prober=self.probe)
        again = p.ensure(tool, self.cache, self.home / "again", root=self.root,
                         installer=self.install, prober=self.probe)
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual((self.installs, self.probes), (1, 2))
        header = self.root / "tools/factory/provision_init_trace.h"
        header.write_bytes(header.read_bytes()+b"\n/* owned identity mutation */\n")
        self.assertNotEqual(key, p.identity(tool, self.root)[2])
        self.assertEqual(old_context, p.identity("beetle-saturn-context-trace", self.root)[2])

    def test_command_core_is_separate_and_reuses_with_pinned_header_abi_and_patch(self):
        tool = "beetle-saturn-command-trace"
        recipe, inputs, key = p.identity(tool, self.root)
        self.assertEqual(recipe["kind"], "beetle-command-trace")
        self.assertIn("tools/factory/provision_command_trace.py", inputs["installer_sources"])
        self.assertIn("tools/factory/provision_command_trace.h", inputs["installer_sources"])
        self.assertIn("tools/factory/provision_command_trace_abi.py", inputs["installer_sources"])
        self.assertNotEqual(key, p.identity("beetle-saturn-init-trace", self.root)[2])
        first = p.ensure(tool, self.cache, self.home / "first", root=self.root,
                         installer=self.install, prober=self.probe)
        again = p.ensure(tool, self.cache, self.home / "again", root=self.root,
                         installer=self.install, prober=self.probe)
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual((self.installs, self.probes), (1, 2))
        header = self.root / "tools/factory/provision_command_trace.h"
        header.write_bytes(header.read_bytes() + b"\n/* owned identity mutation */\n")
        self.assertNotEqual(key, p.identity(tool, self.root)[2])
        self.assertEqual(recipe["commit"], p.identity(tool, self.root)[0]["commit"])

    def test_command_observer_smoke_requires_actual_lossless_abi_v2_fences(self):
        class Runner:
            def __init__(self, observer):
                self.outputs = [
                    {"scope": "no-media ABI smoke only", "api": 1},
                    observer,
                ]
            def run(self, command, cwd, timeout):
                return json.dumps(self.outputs.pop(0))

        observer = {"abi": 2, "record_bytes": 216, "capacity": 128,
                    "witness_words": 424,
                    "rejected_invalid_profile_witness_and_frame": True}
        result = p.smoke("beetle-saturn-command-trace", self.home / "matched-core.so",
                         Runner(observer), self.root)
        self.assertEqual(result["observer"], observer)

        stale = dict(observer, abi=1)
        with self.assertRaisesRegex(p.ProvisionError, "bounded command observer ABI/fence"):
            p.smoke("beetle-saturn-command-trace", self.home / "matched-core.so",
                    Runner(stale), self.root)

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
            p.ensure("unregistered-tool", self.cache, self.home / "unknown", root=self.root)
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


class XvfbRecipeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipe = p.identity("xvfb", p.ROOT)[0]

    def test_untrusted_sources_versions_and_commands_are_rejected(self):
        for key, value in (("archive_url", "https://untrusted.invalid/tool.deb"),
                           ("version", "latest"), ("archive_bytes", 0),
                           ("binary_sha256", "missing"), ("commands", ["sudo"])):
            with self.subTest(key=key), self.assertRaises(p.ProvisionError):
                xvfb.validate(dict(self.recipe, **{key: value}))

    def test_unsupported_distribution_and_missing_dependencies_are_explicit(self):
        release = self.root / "os-release"
        for body in ('ID=ubuntu\nVERSION_ID="24.04"\n', 'ID=debian\nVERSION_ID="12"\n'):
            release.write_text(body)
            with self.assertRaises(p.ProvisionError) as caught:
                xvfb.host_check(self.recipe, release)
            self.assertEqual(caught.exception.kind, "unsupported_platform")
        release.write_text('ID=debian\nVERSION_ID="13"\n')
        with patch.object(xvfb.shutil, "which", return_value=None), self.assertRaises(p.ProvisionError) as caught:
            xvfb.host_check(self.recipe, release)
        self.assertEqual(caught.exception.kind, "missing_host_dependency")

    def test_corrupt_or_truncated_package_is_rejected_before_extraction(self):
        payload = self.root / "payload"
        payload.mkdir()
        for archive in (b"truncated", bytes(self.recipe["archive_bytes"])):
            with self.subTest(size=len(archive)), patch.object(xvfb.subprocess, "run") as command:
                with self.assertRaises(p.ProvisionError) as caught:
                    xvfb.unpack(archive, self.recipe, payload)
                self.assertEqual(caught.exception.kind, "source_mismatch")
                command.assert_not_called()
                self.assertEqual(list(payload.iterdir()), [])

    def test_only_pinned_regular_binary_can_be_extracted(self):
        payload = self.root / "payload"
        payload.mkdir()
        archive = b"synthetic package"
        recipe = dict(self.recipe, archive_bytes=len(archive),
                      archive_sha256=hashlib.sha256(archive).hexdigest())
        for kind in ("symlink", "wrong-hash", "valid"):
            stream = io.BytesIO()
            content = b"synthetic binary"
            with tarfile.open(fileobj=stream, mode="w") as tar:
                member = tarfile.TarInfo("./usr/bin/Xvfb")
                member.size = len(content)
                if kind == "symlink":
                    member.type, member.linkname = tarfile.SYMTYPE, "/outside"
                tar.addfile(member, io.BytesIO(content) if member.isfile() else None)
            recipe["binary_sha256"] = hashlib.sha256(content).hexdigest() if kind == "valid" else "0" * 64
            result = subprocess.CompletedProcess([], 0, stdout=stream.getvalue())
            with self.subTest(kind=kind), patch.object(xvfb.subprocess, "run", return_value=result):
                if kind == "valid":
                    xvfb.unpack(archive, recipe, payload)
                    self.assertEqual((payload / "Xvfb").read_bytes(), content)
                    self.assertEqual((payload / "Xvfb").stat().st_mode & 0o777, 0o755)
                else:
                    with self.assertRaises(p.ProvisionError):
                        xvfb.unpack(archive, recipe, payload)
                    self.assertFalse((payload / "Xvfb").exists())

    def test_failed_start_and_timeout_reap_real_processes(self):
        processes = []
        original = subprocess.Popen
        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process
        with patch.object(xvfb.subprocess, "Popen", side_effect=start):
            with self.assertRaises(p.ProvisionError):
                xvfb.probe(Path("/bin/false"))
            with patch.object(xvfb.select, "select", return_value=([], [], [])):
                with self.assertRaises(p.ProvisionError):
                    xvfb.probe(Path("/bin/false"))
        self.assertEqual(len(processes), 2)
        self.assertTrue(all(process.poll() is not None for process in processes))

    def test_displayfd_readiness_line_can_arrive_in_separate_real_pipe_writes(self):
        binary = self.root / "owned-display-producer"
        binary.write_text("#!/usr/bin/python3\nimport os,sys,time\n"
                          "fd=int(sys.argv[sys.argv.index('-displayfd')+1])\n"
                          "os.write(fd,b'12')\ntime.sleep(0.1)\nos.write(fd,b'3\\n')\ntime.sleep(2)\n")
        binary.chmod(0o755)
        with patch.object(xvfb, "pixel_roundtrip", return_value={"owned": "protocol fixture"}) as pixel:
            self.assertEqual(xvfb.probe(binary), {"owned": "protocol fixture"})
        pixel.assert_called_once_with(":123")

    def test_truncated_displayfd_never_reaches_pixel_check_and_retains_bytes(self):
        binary = self.root / "owned-truncated-display"
        binary.write_text("#!/usr/bin/python3\nimport os,sys\n"
                          "os.write(int(sys.argv[sys.argv.index('-displayfd')+1]),b'12')\n")
        binary.chmod(0o755)
        with patch.object(xvfb, "pixel_roundtrip") as pixel, self.assertRaisesRegex(p.ProvisionError, "12"):
            xvfb.probe(binary)
        pixel.assert_not_called()

    def test_pixel_mutation_is_detected_and_connection_closed(self):
        library = MagicMock()
        library.XOpenDisplay.return_value = 1
        library.XDefaultScreen.return_value = 0
        library.XDisplayWidth.return_value = 640
        library.XDisplayHeight.return_value = 480
        library.XDefaultDepth.return_value = 24
        library.XGetImage.return_value = 1
        library.XGetPixel.return_value = 0x123457
        with patch.object(xvfb.C, "CDLL", return_value=library):
            with self.assertRaisesRegex(p.ProvisionError, "pixel roundtrip mismatch"):
                xvfb.pixel_roundtrip(":0")
        library.XDestroyImage.assert_called_once_with(1)
        library.XCloseDisplay.assert_called_once_with(1)


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
