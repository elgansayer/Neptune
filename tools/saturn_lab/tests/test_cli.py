"""Synthetic bytes test inventory/locking contracts, not Saturn emulation."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "cli.py"
SPEC = importlib.util.spec_from_file_location("saturn_lab", CLI)
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


class InputLocks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "disc").mkdir()
        (self.root / "disc/game.cue").write_text('FILE "track 01.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\nFILE "track 02.bin" BINARY\n  TRACK 02 AUDIO\n    INDEX 01 00:00:00\n')
        (self.root / "disc/track 01.bin").write_bytes(b"synthetic data track")
        (self.root / "disc/track 02.bin").write_bytes(b"synthetic audio track")
        (self.root / "bios.bin").write_bytes(b"synthetic BIOS")
        (self.root / "core.so").write_bytes(b"synthetic emulator")
        (self.root / "settings.json").write_text('{"rtc": "fixed", "core_version": "test-only"}')

    def lock(self):
        return lab.create_lock(self.root, "disc/game.cue", "bios.bin", "core.so", "settings.json", "usa")

    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, str(CLI), *map(str, arguments)], capture_output=True, text=True)

    def test_multitrack_lock_covers_all_inputs_and_is_repeatable(self):
        manifest = self.lock()
        self.assertEqual(manifest, self.lock())
        self.assertEqual(lab.verify_lock(self.root, manifest), 6)

    def test_changed_track_fails_verification(self):
        manifest = self.lock()
        (self.root / "disc/track 02.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(lab.LabError, "differs"):
            lab.verify_lock(self.root, manifest)

    def test_missing_track_fails_before_lock(self):
        (self.root / "disc/track 02.bin").unlink()
        with self.assertRaisesRegex(lab.LabError, "Missing"):
            self.lock()

    def test_removed_track_record_is_not_a_valid_lock(self):
        manifest = self.lock()
        manifest["files"] = [x for x in manifest["files"] if x["path"] != "disc/track 02.bin"]
        with self.assertRaisesRegex(lab.LabError, "exactly cover"):
            lab.verify_lock(self.root, manifest)

    def test_duplicate_record_is_rejected(self):
        manifest = self.lock()
        manifest["files"].append(copy.deepcopy(manifest["files"][0]))
        with self.assertRaisesRegex(lab.LabError, "Duplicate"):
            lab.verify_lock(self.root, manifest)

    def test_cue_parent_absolute_and_symlink_paths_are_rejected(self):
        for filename in ("../bios.bin", str(self.root / "bios.bin"), "C:\\disc\\track.bin"):
            with self.subTest(filename=filename):
                (self.root / "disc/game.cue").write_text(f'FILE "{filename}" BINARY\n')
                with self.assertRaises(lab.LabError):
                    self.lock()
        (self.root / "disc/link.bin").symlink_to(self.root / "bios.bin")
        (self.root / "disc/game.cue").write_text('FILE "link.bin" BINARY\n')
        with self.assertRaisesRegex(lab.LabError, "Symlink"):
            self.lock()

    def test_symlink_parent_directory_is_rejected(self):
        (self.root / "linked").symlink_to(self.root / "disc", target_is_directory=True)
        with self.assertRaisesRegex(lab.LabError, "Symlink"):
            lab.confined_file(self.root, "linked/game.cue")

    def test_empty_cue_and_unsupported_track_type_fail(self):
        for contents in ('REM no tracks\n', 'FILE "track 01.bin" WAVE\n', 'FILE "unterminated\n'):
            with self.subTest(contents=contents):
                (self.root / "disc/game.cue").write_text(contents)
                with self.assertRaises(lab.LabError):
                    self.lock()

    def test_bare_bin_is_not_accepted_as_complete_disc(self):
        with self.assertRaisesRegex(lab.LabError, "BIN/CUE"):
            lab.disc_files(self.root, "disc/track 01.bin")

    def test_chd_identity_supported_without_claiming_decoding(self):
        (self.root / "game.chd").write_bytes(b"synthetic CHD identity test only")
        manifest = lab.create_lock(self.root, "game.chd", "bios.bin", "core.so", "settings.json", "japan")
        self.assertEqual(lab.verify_lock(self.root, manifest), 4)

    def test_empty_or_array_settings_rejected(self):
        for content in ("{}", "[]"):
            (self.root / "settings.json").write_text(content)
            with self.assertRaisesRegex(lab.LabError, "non-empty"):
                self.lock()

    def test_malformed_manifest_fails_cleanly(self):
        for manifest in ([], {}, {"schema": "future"}):
            with self.assertRaises(lab.LabError):
                lab.verify_lock(self.root, manifest)
        manifest = self.lock()
        manifest["files"][0]["bytes"] = True
        with self.assertRaisesRegex(lab.LabError, "size"):
            lab.verify_lock(self.root, manifest)

    def test_cli_roundtrip_and_failure_exit(self):
        path = self.root / "inputs.lock.json"
        result = self.run_cli("lock", "--root", self.root, "--disc", "disc/game.cue", "--bios", "bios.bin", "--emulator", "core.so", "--settings", "settings.json", "--region", "usa", "--output", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_cli("verify", "--root", self.root, "--lock", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.root / "core.so").write_bytes(b"changed emulator")
        result = self.run_cli("verify", "--root", self.root, "--lock", path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs", result.stderr)

    def test_output_cannot_overwrite_selected_input(self):
        original = (self.root / "bios.bin").read_bytes()
        result = self.run_cli("lock", "--root", self.root, "--disc", "disc/game.cue", "--bios", "bios.bin", "--emulator", "core.so", "--settings", "settings.json", "--region", "usa", "--output", self.root / "bios.bin")
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.root / "bios.bin").read_bytes(), original)


class AssetInventory(unittest.TestCase):
    def test_output_preserves_unrelated_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "asset.bin"
            output.write_bytes(b"original asset bytes")
            with self.assertRaisesRegex(lab.LabError, "unrelated"):
                lab.output_json({"schema": "neptune.asset-inventory.v1"}, output)
            self.assertEqual(output.read_bytes(), b"original asset bytes")
            link = root / "link.json"
            link.symlink_to(output)
            with self.assertRaisesRegex(lab.LabError, "symlink"):
                lab.output_json({"schema": "neptune.asset-inventory.v1"}, link)

    def test_output_preserves_json_with_another_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "settings.json"
            output.write_text('{"rtc": "fixed"}')
            with self.assertRaisesRegex(lab.LabError, "unrelated"):
                lab.output_json({"schema": "neptune.asset-inventory.v1"}, output)
            self.assertEqual(json.loads(output.read_text()), {"rtc": "fixed"})

    def test_inventory_reports_duplicates_and_excludes_its_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "a.bin").write_bytes(b"same")
            (root / "nested/b.bin").write_bytes(b"same")
            (root / ".git").mkdir()
            (root / ".git/ignored").write_bytes(b"metadata")
            output = root / "inventory.json"
            first = lab.inventory(root, output)
            lab.output_json(first, output)
            second = lab.inventory(root, output)
            self.assertEqual(first, second)
            self.assertEqual(first["file_count"], 2)
            self.assertEqual(first["duplicate_groups"], [["a.bin", "nested/b.bin"]])
            self.assertEqual(json.loads(output.read_text()), first)

    def test_symlink_file_or_directory_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "file").write_text("test")
            (root / "link").symlink_to(root / "file")
            with self.assertRaises(lab.LabError):
                lab.inventory(root)
            (root / "link").unlink()
            (root / "link").symlink_to(root, target_is_directory=True)
            with self.assertRaises(lab.LabError):
                lab.inventory(root)


if __name__ == "__main__":
    unittest.main()
