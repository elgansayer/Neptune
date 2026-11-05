"""Owned synthetic Beetle-format states only: no original game, BIOS or captured RAM."""
import contextlib
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sample_workram as sw
import state_graphics as sg

COUNTER, PAD, WORD = 0x06006038, 0x06006104, 0x060B2D20


def state_bytes(ram_be: bytes) -> bytes:
    swapped = bytearray(len(ram_be))
    swapped[0::2], swapped[1::2] = ram_be[1::2], ram_be[0::2]   # Beetle stores little-endian words
    record = bytes([8]) + b"WorkRAMH" + struct.pack("<I", len(swapped)) + bytes(swapped)
    section = b"MAIN".ljust(32, b"\0") + struct.pack("<I", len(record)) + record
    return b"MDFNSVST" + bytes(8) + struct.pack("<II", sg.VERSION, 32 + len(section)) + bytes(8) + section


def write_checkpoint(root: Path, name: str, frame: int, values: dict, restore=None, frames=None, extra=b""):
    ram = bytearray(sw.WORKRAM_H_SIZE)
    for address, (value, size) in values.items():
        offset = address - sw.WORKRAM_H_BASE
        ram[offset:offset + size] = value.to_bytes(size, "big")
    if extra:
        ram[0x6368:0x6368 + len(extra)] = extra
    data = state_bytes(bytes(ram))
    directory = root / name
    directory.mkdir()
    (directory / "checkpoint.state").write_bytes(data)
    (directory / "checkpoint.json").write_text(json.dumps({
        "frame": frame, "state_path": "checkpoint.state", "state_bytes": len(data),
        "state_sha256": hashlib.sha256(data).hexdigest()}))
    if restore is not None:
        command = ["python3", "frontend.py", "_worker", "run", "--frames", str(frames),
                   "--restore", str(root / restore / "checkpoint.json")]
        (directory / "process.json").write_text(json.dumps({"command": command}))
    return directory


VALUES = {"counter": (COUNTER, 4), "pad": (PAD, 4), "word": (WORD, 2)}


class LineageSamples(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def chain(self, wrong_restore=False, wrong_frames=False):
        write_checkpoint(self.root, "a", 100, {COUNTER: (10, 4), PAD: (5, 4), WORD: (0xFFFF, 2)})
        write_checkpoint(self.root, "b", 160, {COUNTER: (70, 4), PAD: (35, 4), WORD: (0x0001, 2)},
                         restore="a", frames=60)
        write_checkpoint(self.root, "c", 190, {COUNTER: (100, 4), PAD: (50, 4), WORD: (0x0001, 2)},
                         restore="a" if wrong_restore else "b", frames=31 if wrong_frames else 30)
        return [sw.load_checkpoint(self.root / name) for name in "abc"]

    def test_verified_deltas_wrap_and_rate_expectations(self):
        checkpoints = self.chain()
        report = sw.sample(checkpoints, VALUES, expectations={"counter": Fraction(1)})
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual([p["deltas"] for p in report["pairs"]],
                         [{"counter": 60, "pad": 30, "word": 2}, {"counter": 30, "pad": 15, "word": 0}])
        self.assertTrue(sw.sample(checkpoints, VALUES, expectations={"pad": Fraction(1, 2)})["passed"])
        for name, rate in (("counter", Fraction(2)), ("pad", Fraction(1)), ("counter", Fraction(1, 2))):
            failed = sw.sample(checkpoints, VALUES, expectations={name: rate})
            self.assertFalse(failed["passed"], (name, rate))

    def test_unproven_lineage_reports_no_deltas(self):
        for kwargs in ({"wrong_restore": True}, {"wrong_frames": True}):
            with self.subTest(**kwargs):
                self.tearDown()
                self.setUp()
                report = sw.sample(self.chain(**kwargs), VALUES, expectations={"counter": Fraction(1)})
                last = report["pairs"][1]
                self.assertFalse(last["lineage"]["verified"])
                self.assertNotIn("deltas", last)
        write = self.root / "solo"
        write_checkpoint(self.root, "solo", 5, {})
        lone = sw.sample([sw.load_checkpoint(self.root / "a"), sw.load_checkpoint(write)], VALUES,
                         expectations={"counter": Fraction(1)})
        self.assertFalse(lone["passed"])
        self.assertIn("no verified pair", lone["failures"][0])

    def test_witness_and_bounds(self):
        kernel = bytes(range(64))
        good = write_checkpoint(self.root, "good", 1, {}, extra=kernel[0x368 - 0x340:0x368 - 0x340 + 10])
        state = sw.load_checkpoint(good)
        self.assertTrue(sw.witness(state["ram"], kernel, 0x06006340, 0x06006368, 10))
        self.assertFalse(sw.witness(state["ram"], kernel, 0x06006340, 0x06006368, 12))
        report = sw.sample([state], VALUES, kernel, 0x06006340, [(0x06006368, 12)])
        self.assertFalse(report["passed"])
        with self.assertRaises(ValueError):
            sw.witness(state["ram"], kernel, 0x06006340, 0x06006380, 8)
        with self.assertRaises(ValueError):
            sw.read_value(state["ram"], COUNTER + 2, 4)
        with self.assertRaises(ValueError):
            sw.read_value(state["ram"], 0x06100000, 2)
        self.assertEqual(sw.read_value(state["ram"], 0x26006368, 2), sw.read_value(state["ram"], 0x06006368, 2))

    def test_tampered_state_is_refused(self):
        directory = write_checkpoint(self.root, "t", 1, {})
        raw = bytearray((directory / "checkpoint.state").read_bytes())
        raw[-1] ^= 1
        (directory / "checkpoint.state").write_bytes(bytes(raw))
        with self.assertRaises(ValueError):
            sw.load_checkpoint(directory)

    def test_cli_exit_codes_and_exclusive_reports(self):
        self.chain()
        args = ["--checkpoint", str(self.root / "a"), "--checkpoint", str(self.root / "b"),
                "--value", "counter=06006038:4", "--value", "pad=06006104:4"]
        out = self.root / "ok.json"
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            self.assertEqual(sw.main(args + ["--expect-rate", "counter=1/1", "--report", str(out)]), 0)
            self.assertEqual(sw.main(args + ["--expect-rate", "counter=2/1", "--report", str(self.root / "bad.json")]), 1)
            self.assertEqual(sw.main(args + ["--expect-rate", "other=1/1", "--report", str(self.root / "x.json")]), 1)
            self.assertEqual(sw.main(args + ["--witness", "06006368:4", "--report", str(self.root / "y.json")]), 1)
            with self.assertRaises(FileExistsError):
                sw.main(args + ["--report", str(out)])
        report = json.loads(out.read_text())
        self.assertEqual(report["pairs"][0]["deltas"], {"counter": 60, "pad": 30})
        self.assertEqual(report["expectations"], {"counter": "1"})
        self.assertFalse((self.root / "x.json").exists())


if __name__ == "__main__":
    unittest.main()
