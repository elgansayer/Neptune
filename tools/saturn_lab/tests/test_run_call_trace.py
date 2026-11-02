"""Owned metadata/state fixtures only; no private media or emulator is bundled."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_call_trace as experiment


class ExperimentTests(unittest.TestCase):
    def test_wrong_lock_stops_before_importing_reference_callback_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = root / "lock.json"
            lock.write_text("{}")
            with patch.object(experiment.importlib.util, "spec_from_file_location", side_effect=AssertionError("must not import")) as loader:
                with self.assertRaisesRegex(ValueError, "before importing"):
                    experiment.reference(root, lock, "0" * 64)
            loader.assert_not_called()

    def test_duplicate_metadata_and_symlinked_reference_paths_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "meta.json"
            path.write_text('{"same":1,"same":2}')
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                experiment.read_json(path)
            (root / "link").symlink_to(path)
            for name in ("../escape", "/absolute", "link", "a\\b"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    experiment.confined(root, name)

    def test_missing_inputs_record_failure_and_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = types.SimpleNamespace(frames=1, pairs=1, output=root / "out", mode="reference",
                                         reference_root=root, lock=root / "missing", expected_lock="0" * 64)
            with self.assertRaises(FileNotFoundError):
                experiment.run(args)
            report = args.output / "result.json"
            raw = report.read_bytes()
            self.assertEqual(json.loads(raw)["status"], "failure")
            self.assertEqual(json.loads(raw)["error"]["phase"], "input_identity")
            with self.assertRaises(ValueError):
                experiment.run(args)
            self.assertEqual(report.read_bytes(), raw)

    def test_resident_code_literals_and_producer_word_order_are_checked(self):
        kernel = bytearray(experiment.probe_kernel.SIZE)
        high = bytearray(0x100000)
        for address, size in ((0x0600B934, 28), (0x0600B96C, 2), (0x0600B984, 4)):
            original = bytes(range(1, size + 1))
            kernel[address - experiment.probe_kernel.BASE:address - experiment.probe_kernel.BASE + size] = original
            high[address - 0x06000000:address - 0x06000000 + size] = original
        def state(memory):
            native = experiment.state_graphics.cpu_words(memory, "little")
            name = b"WorkRAMH"
            fields = bytes([len(name)]) + name + struct.pack("<I", len(native)) + native
            section = b"MAIN".ljust(32, b"\0") + struct.pack("<I", len(fields)) + fields
            return b"MDFNSVST" + bytes(8) + struct.pack("<II", experiment.state_graphics.VERSION, 32 + len(section)) + bytes(8) + section
        self.assertEqual(len(experiment.resident(state(high), bytes(kernel))), 3)
        high[0xB934] ^= 1
        with self.assertRaisesRegex(ValueError, "witness"):
            experiment.resident(state(high), bytes(kernel))

    def test_comparison_requires_six_distinct_complete_runs(self):
        for paths in ([], [Path("same")] * 6):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                experiment.compare(paths)

    def test_cleanup_failure_cannot_leave_a_successful_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "checkpoint").write_text("owned fixture")
            (root / "core").write_text("owned fixture, not a library")
            class Driver:
                def __init__(self, *args):
                    self.polls, self.delivered = [0] * 12, [set() for _ in range(12)]
                def load(self, *args): return {"fps": 60.0}
                def restore(self, state): pass
                def save_state(self): return b"owned synthetic state"
                def step(self, masks):
                    frame = self.frame
                    self.frame += 1
                    return {"frame": frame, "video": {}, "audio_sha256": "0" * 64,
                            "audio_frames": 1, "inputs": masks}
                def close(self): raise RuntimeError("owned cleanup failure")
            module = types.SimpleNamespace(Core=Driver, read_checkpoint=lambda *_: ({"frame": 0, "last_video": {}, "state_sha256": "0" * 64}, b"owned"),
                                           digest=lambda x: hashlib.sha256(json.dumps(x).encode()).hexdigest())
            args = types.SimpleNamespace(frames=1, pairs=1, output=root / "out", mode="reference",
                                         reference_root=root, lock=root / "unused", expected_lock="0" * 64,
                                         checkpoint=root / "checkpoint", kernel=root / "unused")
            lock = {"inputs": {"emulator": "core", "disc": "disc.cue"}}
            profile = {"system_directory": "system", "options": {}, "log_shim": {"path": "shim"}, "controller_devices": [1] * 12}
            with patch.object(experiment, "reference", return_value=(module, lock, profile, {}, b"seed")), \
                 patch.object(experiment.probe_kernel, "kernel_bytes", return_value=b"owned"), \
                 patch.object(experiment.os, "statvfs", return_value=types.SimpleNamespace(f_flag=experiment.os.ST_RDONLY)), \
                 patch.object(experiment, "resident", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "cleanup"):
                    experiment.run(args)
            result = json.loads((args.output / "result.json").read_text())
            self.assertEqual(result["status"], "failure")
            self.assertEqual(result["cleanup_error"]["reason"], "owned cleanup failure")
