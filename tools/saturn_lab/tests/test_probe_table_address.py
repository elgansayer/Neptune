"""Synthetic contracts only: no original game code or reference output is bundled."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_kernel as pinned
import probe_table_address as probe


def observation(n, m):
    # Test-owned algebraic implementation, not an original SH-2 substitute.
    return {"result": (0x00207F74 + n * 1520 + m * 152) & 0xFFFFFFFF,
            "instructions": 2, "pcs": [probe.ENTRY, probe.ENTRY + 2],
            "changed_registers": ["r0"], "return_sentinel_reached": True}


def synthetic_interpreter(mode="normal"):
    instances = []

    class Memory:
        def add(self, base, length, data):
            self.base, self.length = base, length
            self.data = data

        def read(self, address, size):
            if not self.base <= address <= self.base + self.length - size:
                raise MemoryError("Synthetic unmapped address")
            return int.from_bytes(self.data[address - self.base:address - self.base + size], "big")

    class CPU:
        def __init__(self, memory):
            self.mem, self.r = memory, [0] * 16
            self.sr = self.gbr = self.vbr = self.mach = self.macl = self.pr = self.steps = self.pc = 0
            instances.append(self)

        def exec(self, instruction, pc, in_slot=False):
            if instruction == "calculate":
                if mode == "write":
                    self.mem.write(0x060FFFF0, 4, 123)
                elif mode == "unmapped-read":
                    self.mem.read(0x05D00000, 2)
                self.r[0] = (0x00207F74 + self.r[4] * 1520 + self.r[5] * 152) & 0xFFFFFFFF

        def call(self, entry, max_steps, **registers):
            if self.steps != 0 or self.r[0] != 0xA5A5A5A5:
                raise AssertionError("Every case must receive a fresh poisoned CPU")
            self.asserted_bound = max_steps
            for name, value in registers.items():
                self.r[int(name[1:])] = value
            if mode == "nonreturn":
                raise RuntimeError("Synthetic original did not return")
            if mode == "overflow":
                for _ in range(max_steps + 1):
                    self.steps += 1
                    self.exec("nop", entry)
            self.steps = 1
            self.exec("calculate", entry)
            self.steps = 2
            self.exec("return", entry + 2 if mode != "bad-pc" else 0x05D00000, in_slot=True)
            self.pc = 0xFFFFFFF0 if mode != "wrong-return" else 0
            return self.r[0]

    return types.SimpleNamespace(Memory=Memory, CPU=CPU, RETURN_SENTINEL=0xFFFFFFF0, instances=instances)


def stack_interpreter(mode="normal"):
    """Owned spill/restore simulation for memory/ABI fences, not original opcodes."""
    class Memory:
        def __init__(self):
            self.regions = []

        def add(self, base, size, data):
            buffer = bytearray(data)
            self.regions.append((base, base + size, buffer))
            return buffer

        def find(self, address, size):
            physical = address & 0x1FFFFFFF if address >> 28 == 2 else address
            for base, end, buffer in self.regions:
                if base <= physical and physical + size <= end:
                    return buffer, physical - base
            raise MemoryError("Owned fixture unmapped address")

        def read(self, address, size):
            buffer, offset = self.find(address, size)
            return int.from_bytes(buffer[offset:offset + size], "big")

        def write(self, address, size, value):
            buffer, offset = self.find(address, size)
            buffer[offset:offset + size] = value.to_bytes(size, "big")

    class CPU:
        def __init__(self, memory):
            self.mem, self.r = memory, [0] * 16
            self.sr = self.gbr = self.vbr = self.mach = self.macl = self.pr = self.steps = self.pc = 0

        def exec(self, instruction, pc, in_slot=False):
            if instruction == "spill":
                self.r[15] -= 4
                address = self.r[15] if mode != "escaped-write" else pinned.BASE
                self.mem.write(address, 4, self.macl if mode != "wrong-spill" else self.macl ^ 1)
                if mode == "extra-write":
                    self.mem.write(address, 4, self.macl)
            elif instruction == "calculate":
                self.macl = (self.r[4] * 1520 + self.r[5] * 152) & 0xFFFFFFFF
                self.r[0] = (self.macl + 0x00207F74) & 0xFFFFFFFF
                self.sr = (self.sr & ~1) | (((5 * self.r[4]) & 0xFFFFFFFF) >> 31)
                if mode == "changed-register":
                    self.r[7] = 0
                if mode == "changed-condition":
                    self.sr ^= 2
                if mode == "changed-canary":
                    self.mem.regions[1][2][0] ^= 1
                if mode == "changed-kernel":
                    self.mem.regions[0][2][0] ^= 1
            elif instruction == "restore":
                address = self.r[15] if mode != "other-read" else self.r[15] - 4
                if mode == "mirror-read":
                    address |= 0x20000000
                if mode != "missing-restore":
                    self.macl = self.mem.read(address, 4)
                    if mode == "extra-read":
                        self.mem.read(address, 4)
                    if mode != "wrong-sp":
                        self.r[15] += 4

        def call(self, entry, max_steps, **registers):
            for index, instruction in enumerate(("spill", "calculate", "return", "restore")):
                self.steps += 1
                self.exec(instruction, entry + 2 * index, in_slot=instruction == "restore")
            self.pc = 0xFFFFFFF0
            return self.r[0]

    return types.SimpleNamespace(Memory=Memory, CPU=CPU, RETURN_SENTINEL=0xFFFFFFF0)


class TableAddressProbeTests(unittest.TestCase):
    def test_complete_ordinary_and_constructed_selection_and_fixed_examples(self):
        self.assertEqual(probe.candidate(0, 0), 0x00207F74)
        self.assertEqual(probe.candidate(1, 0), 0x00208564)
        self.assertEqual(probe.candidate(0, 1), 0x0020800C)
        self.assertEqual(probe.candidate(0xFFFFFFFF, 0), 0x00207984)
        result = probe.exercise(observation)
        self.assertEqual(result["cases"], 196)
        self.assertEqual(result["case_domains"], {"upstream_sample_domain": 100, "constructed_32_bit_boundaries": 96})
        self.assertEqual(result["mutation_rejections"], {"changed_stride": 194, "changed_base": 196, "swapped_arguments": 174})

    def test_wrong_stride_base_and_argument_order_fail(self):
        for kind in ("stride", "base", "arguments"):
            def wrong(n, m):
                result = observation(n, m)
                if kind == "stride":
                    result["result"] = ((10 * n + m) * 151 + 0x00207F74) & 0xFFFFFFFF
                elif kind == "base":
                    result["result"] = (result["result"] + 4) & 0xFFFFFFFF
                else:
                    result["result"] = (0x00207F74 + m * 1520 + n * 152) & 0xFFFFFFFF
                return result
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "Result mismatch"):
                probe.exercise(wrong)

    def test_missing_empty_duplicate_or_invalid_argument_coverage_fails(self):
        normal = probe.inputs()
        bad_argument = normal.copy()
        bad_argument[0] = (normal[0][0], True, normal[0][2])
        for cases in ([], normal[:-1], normal[:-1] + [normal[0]], bad_argument):
            with self.subTest(length=len(cases)), patch.object(probe, "inputs", return_value=cases):
                with self.assertRaises(ValueError):
                    probe.exercise(observation)

    def test_steps_pcs_registers_and_return_must_be_real_bounded_evidence(self):
        changes = [("instructions", 0), ("instructions", True), ("instructions", 257),
                   ("pcs", []), ("pcs", [probe.ENTRY, 0x05D00000]),
                   ("pcs", [probe.ENTRY, probe.ENTRY + 1]),
                   ("changed_registers", ["invented"]), ("changed_registers", ["r0", "r0"]),
                   ("return_sentinel_reached", False), ("result", True)]
        for key, value in changes:
            def wrong(n, m):
                result = observation(n, m)
                result[key] = value
                return result
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                probe.exercise(wrong)

    def test_synthetic_cpu_calls_are_fresh_and_include_delay_slot_evidence(self):
        module = synthetic_interpreter()
        result = probe.execute(bytes(pinned.SIZE), module)
        self.assertEqual(len(module.instances), 196)
        self.assertEqual(len({id(cpu) for cpu in module.instances}), 196)
        self.assertEqual(result["executed_pcs"], [f"0x{probe.ENTRY:08x}", f"0x{probe.ENTRY + 2:08x}"])
        self.assertEqual(result["writes"], 0)
        self.assertEqual(result["observed_changed_registers"], ["r0"])
        self.assertTrue(all(cpu.asserted_bound == probe.MAX_STEPS for cpu in module.instances))

    def test_writes_unmapped_reads_nonreturn_and_overflow_fail(self):
        for mode, failure in (("write", ValueError), ("unmapped-read", MemoryError),
                              ("nonreturn", RuntimeError), ("overflow", RuntimeError),
                              ("bad-pc", ValueError), ("wrong-return", ValueError)):
            with self.subTest(mode=mode), self.assertRaises(failure):
                probe.execute(bytes(pinned.SIZE), synthetic_interpreter(mode))

    def test_explicit_stack_mode_checks_poisoned_spill_restore_and_full_footprint(self):
        result = probe.execute(bytes(pinned.SIZE), stack_interpreter(), bounded_stack=True)
        self.assertEqual(result["cases"], 196)
        self.assertEqual(result["writes"], 196)
        contract = result["memory_contract"]
        self.assertTrue(contract["sp_and_macl_preserved"])
        self.assertTrue(contract["other_stack_bytes_unchanged"])
        self.assertEqual(contract["only_stack_access"], {"address": "0x060fffec", "bytes": 4,
                                                       "writes_per_case": 1, "reads_per_case": 1})
        self.assertEqual(len(contract["witnesses_sha256"]), 64)

    def test_default_mode_still_rejects_the_same_constructed_stack_write(self):
        with self.assertRaisesRegex(ValueError, "pure-function"):
            probe.execute(bytes(pinned.SIZE), stack_interpreter())

    def test_stack_access_abi_condition_and_unaffected_memory_mutations_fail(self):
        for mode in ("escaped-write", "wrong-spill", "extra-write", "missing-restore", "wrong-sp",
                     "other-read", "mirror-read", "extra-read", "changed-register", "changed-condition",
                     "changed-canary", "changed-kernel"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                probe.execute(bytes(pinned.SIZE), stack_interpreter(mode), bounded_stack=True)

    def test_incomplete_kernel_is_not_executed(self):
        with self.assertRaisesRegex(ValueError, "complete kernel"):
            probe.execute(b"synthetic", synthetic_interpreter())

    def test_cli_failure_is_durable_private_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(temporary)
            report = root / "report.json"
            args = ["--kernel", str(root / "missing"), "--saturn-recomp", str(root), "--report", str(report)]
            self.assertEqual(probe.main(args), 1)
            first = report.read_bytes()
            result = json.loads(first)
            self.assertEqual(result["status"], "failure")
            self.assertEqual(result["error"]["type"], "FileNotFoundError")
            self.assertEqual(result["error"]["phase"], "kernel_identity")
            self.assertNotIn("results", result)
            self.assertNotIn(temporary, first.decode())
            self.assertEqual(probe.main(args), 1)
            self.assertEqual(report.read_bytes(), first)

    def test_report_is_private_under_permissive_umask(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary)
            previous = os.umask(0)
            try:
                self.assertEqual(probe.main(["--kernel", str(root / "missing"), "--saturn-recomp", str(root),
                                             "--report", str(root / "report.json")]), 1)
            finally:
                os.umask(previous)
            self.assertEqual((root / "report.json").stat().st_mode & 0o777, 0o600)

    def test_wrong_original_hash_stops_before_interpreter_or_cpu(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary)
            (root / "wrong-kernel").write_bytes(bytes(pinned.SIZE))
            with patch.object(pinned, "interpreter", side_effect=AssertionError("must not load")) as loader:
                result = probe.main(["--kernel", str(root / "wrong-kernel"), "--saturn-recomp", str(root),
                                     "--report", str(root / "report.json")])
            self.assertEqual(result, 1)
            loader.assert_not_called()
            self.assertEqual(json.loads((root / "report.json").read_text())["error"]["type"], "ValueError")

    def test_changed_interpreter_source_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temporary)
            source = root / "src/saturnrecomp"
            source.mkdir(parents=True)
            (source / "hw.py").write_text("raise AssertionError('must not execute changed source')\n")
            with patch.object(pinned, "kernel_bytes", return_value=bytes(pinned.SIZE)):
                result = probe.main(["--kernel", str(root / "original-unavailable"), "--saturn-recomp", str(root),
                                     "--report", str(root / "report.json")])
            self.assertEqual(result, 1)
            self.assertEqual(json.loads((root / "report.json").read_text())["error"]["type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
