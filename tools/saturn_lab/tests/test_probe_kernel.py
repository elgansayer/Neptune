"""Synthetic contract checks. None of these tests contains or executes game code."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_kernel as probe


class KernelProbeTests(unittest.TestCase):
    def test_input_coverage_and_priority_table(self):
        table = [0, 4, 2, 2, 3, 3, 3, 3, 1, 1, 2, 2, 3, 3, 3, 3]
        result = probe.exercise(lambda value: (table[(value >> 12) & 15], 12))
        self.assertEqual(result["cases"], 256)
        self.assertEqual(result["mutation_rejections"], {"changed_return": 128, "changed_priority": 96})

    def test_wrong_priority_fails(self):
        with self.assertRaisesRegex(ValueError, "Mismatch"):
            probe.exercise(lambda value: (1 if value & 0x8000 else probe.candidate(value), 12))

    def test_constant_return_fails(self):
        with self.assertRaisesRegex(ValueError, "Mismatch"):
            probe.exercise(lambda value: (0, 3))

    def test_empty_input_cannot_pass(self):
        with patch.object(probe, "inputs", return_value=[]), self.assertRaises(ValueError):
            probe.exercise(lambda value: (0, 3))

    def test_steps_must_be_real_and_bounded(self):
        for count in (0, -1, 257, True):
            with self.subTest(count=count), self.assertRaises(ValueError):
                probe.exercise(lambda value: (probe.candidate(value), count))

    def test_cpu_failure_is_not_success(self):
        def broken(value):
            raise RuntimeError("no return after 256 steps")
        with self.assertRaisesRegex(RuntimeError, "no return"):
            probe.exercise(broken)

    def test_wrong_kernel_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kernel"
            for size in (0, probe.SIZE - 1, probe.SIZE, probe.SIZE + 1):
                path.write_bytes(b"\0" * size)
                with self.subTest(size=size), self.assertRaises(ValueError):
                    probe.kernel_bytes(path)

    def test_hash_mismatch_stops_before_loading_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "saturnrecomp"
            src.mkdir(parents=True)
            (src / "hw.py").write_text("raise AssertionError('must not run')")
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                probe.interpreter(root)

    def test_report_records_failure_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(tmp)
            report = root / "report.json"
            args = ["--kernel", str(root / "missing"), "--saturn-recomp", str(root), "--report", str(report)]
            self.assertEqual(probe.main(args), 1)
            before = report.read_bytes()
            self.assertEqual(json.loads(before)["status"], "failure")
            self.assertNotIn("results", json.loads(before))
            self.assertEqual(probe.main(args), 1)
            self.assertEqual(report.read_bytes(), before)

    def test_write_is_rejected(self):
        class Memory:
            def add(self, *args):
                pass
        class CPU:
            def __init__(self, memory):
                self.memory = memory
            def call(self, *args, **kwargs):
                self.memory.write(0x05D00000, 2, 3)
        with self.assertRaisesRegex(ValueError, "Unexpected write"):
            probe.execute(b"synthetic", types.SimpleNamespace(Memory=Memory, CPU=CPU))


if __name__ == "__main__":
    unittest.main()
