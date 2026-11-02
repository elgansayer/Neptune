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
    def six_owned_runs(self, root):
        """Artefact-validation fixture, never claimed as original execution."""
        observer = experiment.observer
        before, after = observer.Record(), observer.Record()
        before.kind, before.pc, before.opcode = 1, observer.ENTRY, 0x4F12
        before.frame, before.dispatch_steps, before.pr = 100, 1, 0x0600BAEE
        before.r[4], before.r[5], before.r[15], before.macl = 2, 1, 0x060FFF00, 123
        after = observer.Record.from_buffer_copy(before)
        after.kind, after.sequence, after.pc, after.dispatch_steps = 2, 1, before.pr, 14
        after.r[0] = (10 * 2 + 1) * 152 + 0x00207F74
        after.r[2], after.r[3], after.r[6] = 152, 2, 0x00207F74
        status = observer.Status()
        for name, value in dict(abi=2, record_bytes=120, capacity=128, count=2,
                                completed=1, frame_known=1, frame=102,
                                step_limit=4096, master_dispatches=100).items():
            setattr(status, name, value)
        trace = observer.validate([before, after], status)
        digest = lambda value: experiment.sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
        frames = [{"frame": 100 + index, "inputs": [8 if index == 0 else 0] + [0] * 11,
                   "video": {"sha256": "1" * 64}, "audio_sha256": "2" * 64, "audio_frames": 1}
                  for index in range(3)]
        paths = []
        for mode in ("reference", "disabled", "enabled"):
            for repeat in range(2):
                path = root / f"{mode}-{repeat}"
                path.mkdir()
                paths.append(path)
                report = dict(schema="neptune.explicit-call-trace-experiment.v2", status="success", mode=mode,
                              driver_sha256="3" * 64, source_modules={}, reference_identity={},
                              reference_lock_file_sha256="4" * 64, reference_checkpoint_file_sha256="5" * 64,
                              reference_state_sha256="6" * 64, reference_frame=100, frames=3,
                              port_zero_start_frames=1, av={}, imported_state_bytes=10,
                              imported_state_sha256="7" * 64, resident_code_before=[], resident_code_after=[],
                              input_polls=[3] * 12, delivered_masks=[[0, 8]] + [[0]] * 11,
                              final_state_sha256=experiment.sha(b"owned final state"),
                              frame_observations_sha256=digest(frames), video_sha256=digest([f["video"] for f in frames]),
                              audio_sha256=digest([(f["audio_sha256"], f["audio_frames"]) for f in frames]),
                              audio_frames=3, emulation_wall_seconds=1.0,
                              selected_core_sha256=experiment.REFERENCE_CORE if mode == "reference" else "8" * 64)
                if mode != "reference": report["prepared_recipe_sha256"] = "9" * 64
                if mode == "enabled":
                    raw = (json.dumps(trace, indent=2, sort_keys=True) + "\n").encode()
                    (path / "call-trace.json").write_bytes(raw)
                    report.update(pairs=1, trace_sha256=experiment.sha(raw))
                (path / "result.json").write_text(json.dumps(report))
                (path / "observations.json").write_text(json.dumps({"av": {}, "frames": frames}))
                (path / "final.state").write_bytes(b"owned final state")
        return paths

    def test_complete_comparison_and_native_observation_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.six_owned_runs(Path(temporary))
            self.assertEqual(experiment.compare(paths)["pairs_per_enabled_run"], 1)
            target = paths[-1]
            for filename in ("final.state", "observations.json", "call-trace.json"):
                file = target / filename
                original = file.read_bytes()
                file.write_bytes(original.replace(b"owned", b"wrong", 1) if filename == "final.state" else b"{}")
                with self.subTest(filename=filename), self.assertRaises((ValueError, KeyError)):
                    experiment.compare(paths)
                file.write_bytes(original)
            file = target / "call-trace.json"
            trace = json.loads(file.read_text())
            for field in ("master_dispatches", "completed"):
                altered = json.loads(json.dumps(trace))
                altered["status"][field] = 0
                with self.subTest(field=field), self.assertRaises(ValueError):
                    experiment.decoded_trace(altered)
            altered = json.loads(json.dumps(trace))
            altered["records"][1]["r"][0] ^= 1
            with self.assertRaisesRegex(ValueError, "result"):
                experiment.decoded_trace(altered)

    def test_declared_start_pulse_cannot_be_replaced_by_rehashed_other_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.six_owned_runs(Path(temporary))
            target = paths[-1]
            observation = json.loads((target / "observations.json").read_text())
            observation["frames"][0]["inputs"][0] = 16
            (target / "observations.json").write_text(json.dumps(observation))
            report = json.loads((target / "result.json").read_text())
            report["frame_observations_sha256"] = experiment.sha(json.dumps(observation["frames"], sort_keys=True, separators=(",", ":")).encode())
            (target / "result.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "controller input"):
                experiment.compare(paths)

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
            args = types.SimpleNamespace(frames=1, pairs=1, start_frames=0, output=root / "out", mode="reference",
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
            args = types.SimpleNamespace(frames=1, pairs=1, start_frames=0, output=root / "out", mode="reference",
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
