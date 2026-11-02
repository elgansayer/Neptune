"""Owned public fixtures test preparation fences; real Ghidra runs in required CI."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

import provision as p
import provision_ghidra as g


class GhidraPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.recipe = json.loads((p.ROOT / "tools/factory/provision-lock.json").read_text())["tools"]["ghidra"]

    def test_recipe_rejects_wrong_release_host_hash_and_untrusted_commands(self):
        g.validate(self.recipe)
        for change in [dict(version="12.3"), dict(jdk_version="21.0.5"), dict(jdk_build=True),
                       dict(version="12.2-beta"), dict(commands=["issue text"]), dict(sources={})]:
            with self.subTest(change=change), self.assertRaises(p.ProvisionError):
                g.validate(dict(self.recipe, **change))
        for key, value in [("url", "https://example.invalid/tool"), ("bytes", True),
                           ("bytes", 769 * 1024**2), ("sha256", "bad")]:
            recipe = copy.deepcopy(self.recipe)
            recipe["sources"]["ghidra"][key] = value
            with self.subTest(key=key), self.assertRaises(p.ProvisionError):
                g.validate(recipe)

    def test_fetch_requires_exact_length_and_hash(self):
        data = b"public artifact fixture"
        source = dict(url="https://example.invalid/tool", bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        for index, content in enumerate((data, data[:-1], data + b"!", b"x" * len(data))):
            with patch.object(g.urllib.request, "urlopen", return_value=io.BytesIO(content)):
                if index == 0:
                    g.fetch(source, self.home / str(index))
                    self.assertEqual((self.home / str(index)).read_bytes(), data)
                else:
                    with self.assertRaises(p.ProvisionError):
                        g.fetch(source, self.home / str(index))

    def archive(self, members, zipped):
        path = self.home / "fixture.archive"
        if zipped:
            with zipfile.ZipFile(path, "w") as archive:
                for name, kind, content in members:
                    item = zipfile.ZipInfo(name)
                    item.external_attr = (0o120777 if kind == "link" else 0o106755) << 16
                    archive.writestr(item, content)
        else:
            with tarfile.open(path, "w:gz") as archive:
                for name, kind, content in members:
                    item = tarfile.TarInfo(name)
                    item.mode = 0o6755
                    if kind in ("link", "hard"):
                        item.type = tarfile.SYMTYPE if kind == "link" else tarfile.LNKTYPE
                        item.linkname = content
                        archive.addfile(item)
                    else:
                        item.size = len(content)
                        archive.addfile(item, io.BytesIO(content))
        return path

    def test_archives_reject_escape_duplicate_roots_links_and_non_directory_parents(self):
        cases = [[("../outside", "file", b"a")], [("/outside", "file", b"a")],
                 [("root/a", "file", b"a"), ("root/a", "file", b"b")],
                 [("root/a", "file", b"a"), ("other/b", "file", b"b")],
                 [("root/a", "file", b"a"), ("root/a/b", "file", b"b")],
                 [("root/a", "link", "../../outside")], [("root/a", "link", "missing")],
                 [("root/a", "link", "b"), ("root/b", "link", "a")]]
        for zipped in (True, False):
            for index, members in enumerate(cases):
                with self.subTest(zipped=zipped, index=index), self.assertRaises(p.ProvisionError):
                    g.unpack(self.archive(members, zipped), self.home / f"bad-{zipped}-{index}", zipped)
        self.assertFalse((self.home / "outside").exists())
        with self.assertRaises(p.ProvisionError):
            g.unpack(self.archive([("root/a", "hard", "root/b")], False), self.home / "hard", False)

    def test_files_extract_without_privileged_modes_and_internal_jdk_links_become_copies(self):
        for zipped in (True, False):
            output = self.home / str(zipped)
            g.unpack(self.archive([("root/bin/tool", "file", b"public")], zipped), output, zipped)
            self.assertEqual((output / "bin/tool").read_bytes(), b"public")
            self.assertEqual((output / "bin/tool").stat().st_mode & 0o7777, 0o755)
        output = self.home / "jdk"
        g.unpack(self.archive([("root/legal/base/NOTICE", "file", b"notice"),
                               ("root/legal/other/NOTICE", "link", "../base/NOTICE")], False), output, False)
        notice = output / "legal/other/NOTICE"
        self.assertFalse(notice.is_symlink())
        self.assertEqual(notice.read_bytes(), b"notice")

    def test_archive_expansion_and_index_limits_apply(self):
        archive = self.archive([("root/file", "file", b"abc")], True)
        with patch.object(g, "MAX_EXPANSION", 2), self.assertRaises(p.ProvisionError):
            g.unpack(archive, self.home / "large", True)
        with patch.object(g, "MAX_FILES", 0), self.assertRaises(p.ProvisionError):
            g.unpack(archive, self.home / "many", True)

    def payload(self):
        directory = self.home / "payload"
        directory.mkdir(exist_ok=True)
        for relative in ("ghidra-headless", "jdk/bin/java", "ghidra/library.jar"):
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic payload member")
        (directory / g.MANIFEST).write_text(json.dumps(g.files_identity(directory), sort_keys=True))
        return directory

    def runner(self, directory, *, result=None, version=None, missing=False):
        runner = MagicMock()
        runner.evidence = self.home / "evidence"
        runner.evidence.mkdir(exist_ok=True)
        def run(argv, cwd, timeout):
            if argv[-1] == "-version":
                return version if version is not None else 'openjdk version "25.0.5" 2026-10-20'
            if not missing:
                observation = {"version": "12.2", "language": g.LANGUAGE, "base": "06004000",
                               "instructions": ["mov", "rts", "nop"], "constant_return": 42}
                (runner.evidence / "ghidra-public-sh2.json").write_text(json.dumps(observation if result is None else result))
            return "headless output is not evidence without the observation"
        runner.run.side_effect = run
        return runner

    def test_public_smoke_binds_fixture_language_base_decompilation_and_payload(self):
        directory = self.payload()
        result = g.smoke(self.recipe, directory / "ghidra-headless", self.runner(directory), p.ROOT)
        self.assertEqual(result["constant_return"], 42)
        self.assertEqual(result["fixture_sha256"], hashlib.sha256(bytes.fromhex("e02a000b0009")).hexdigest())
        self.assertEqual(result["payload_sha256"], p.digest(directory / g.MANIFEST))
        for changed in ({}, {"constant_return": 41}, {"version": "12.1"}):
            with self.subTest(changed=changed), self.assertRaises(p.ProvisionError):
                g.smoke(self.recipe, directory / "ghidra-headless", self.runner(directory, result=changed), p.ROOT)

    def test_missing_empty_wrong_jdk_and_no_observation_never_pass(self):
        directory = self.payload()
        for version in ('openjdk version "21.0.5"', ""):
            with self.subTest(version=version), self.assertRaises(p.ProvisionError):
                g.smoke(self.recipe, directory / "ghidra-headless", self.runner(directory, version=version), p.ROOT)
        with self.assertRaises(p.ProvisionError):
            g.smoke(self.recipe, directory / "ghidra-headless", self.runner(directory, missing=True), p.ROOT)

    def test_changed_missing_added_and_symlinked_library_rejected_before_execution(self):
        for change in ("changed", "missing", "added", "symlink"):
            directory = self.payload()
            jar = directory / "ghidra/library.jar"
            if change == "changed":
                jar.write_bytes(b"changed")
            elif change == "missing":
                jar.unlink()
            elif change == "added":
                (directory / "extra.jar").write_bytes(b"extra")
            else:
                jar.unlink()
                jar.symlink_to("/etc/hosts")
            runner = self.runner(directory)
            with self.subTest(change=change), self.assertRaises(p.ProvisionError):
                g.smoke(self.recipe, directory / "ghidra-headless", runner, p.ROOT)
            runner.run.assert_not_called()
            shutil.rmtree(directory)

    def test_manifest_must_match_previous_publication_and_probe_may_not_mutate_payload(self):
        directory = self.payload()
        (directory / "receipt.json").write_text(json.dumps({"smoke": {"payload_sha256": "0" * 64}}))
        runner = self.runner(directory)
        with self.assertRaises(p.ProvisionError):
            g.smoke(self.recipe, directory / "ghidra-headless", runner, p.ROOT)
        runner.run.assert_not_called()
        (directory / "receipt.json").unlink()
        runner = self.runner(directory)
        original = runner.run.side_effect
        def mutate(*args):
            result = original(*args)
            (directory / "ghidra/library.jar").write_bytes(b"runtime mutation")
            return result
        runner.run.side_effect = mutate
        with self.assertRaises(p.ProvisionError):
            g.smoke(self.recipe, directory / "ghidra-headless", runner, p.ROOT)

    def test_launcher_selects_pinned_jdk_and_keeps_home_paths_as_single_arguments(self):
        directory = self.home / "path with spaces"
        java = directory / "jdk/bin/java"
        java.parent.mkdir(parents=True)
        java.write_text('#!/usr/bin/python3\nimport json,sys,os\nprint(json.dumps({"argv":sys.argv[1:],"java_options":os.environ.get("JAVA_TOOL_OPTIONS")}))\n')
        java.chmod(0o755)
        properties = directory / "ghidra/support/launch.properties"
        properties.parent.mkdir(parents=True)
        properties.write_text("VMARGS=-Djava.system.class.loader=ghidra.GhidraClassLoader\nVMARGS_LINUX=-Dtest.linux=true\nVMARGS_WINDOWS=-Dtest.windows=true\n")
        wrapper = directory / "ghidra-headless"
        wrapper.write_text(g.WRAPPER)
        wrapper.chmod(0o755)
        result = subprocess.run([str(wrapper), "project dir", "public"], check=True, capture_output=True, text=True,
                                timeout=10, env={"HOME": str(directory), "TMPDIR": str(directory),
                                                 "JAVA_TOOL_OPTIONS": "untrusted options", "PATH": os.defpath})
        observation = json.loads(result.stdout)
        self.assertIsNone(observation["java_options"])
        self.assertIn("-Djava.system.class.loader=ghidra.GhidraClassLoader", observation["argv"])
        self.assertIn("-Dtest.linux=true", observation["argv"])
        self.assertNotIn("-Dtest.windows=true", observation["argv"])
        self.assertIn("-Duser.home=" + str(directory), observation["argv"])
        self.assertEqual(observation["argv"][-2:], ["project dir", "public"])


if __name__ == "__main__":
    unittest.main()
