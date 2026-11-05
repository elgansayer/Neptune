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
import probe_japan_f040_setbit as probe


RETURN = 0xFFFFFFF0


def synthetic_kernel(words=None):
    """Test-owned SH-2 bytes; never original game code."""
    size = 786432
    data = bytearray(size)
    for offset, word in (words or {}).items():
        data[offset:offset + 2] = word.to_bytes(2, "big")
    return bytes(data)


def synthetic_ram(kernel):
    """A captured WorkRAM-shaped image that agrees with the synthetic kernel."""
    ram = bytearray(probe.RAM_SIZE)
    ram[probe.KERNEL_BASE - probe.BASE:probe.KERNEL_BASE - probe.BASE + len(kernel)] = kernel
    return bytes(ram)


def synthetic_interpreter(mode="r4", calls=4, pointer=0x060FC5A0):
    """A stand-in CPU that emulates the observed F040 helper call train.

    It is a test-owned algebraic model of the reported behaviour, not an
    original SH-2 substitute and not evidence about the original game.
    """
    class Memory:
        def __init__(self):
            self.regions = []

        def add(self, base, size, data=None):
            buffer = bytearray(size)
            if data:
                buffer[:len(data)] = data
            self.regions.append((base, base + size, buffer))
            return buffer

        def find(self, address, size):
            for base, end, buffer in self.regions:
                if base <= address and address + size <= end:
                    return buffer, address - base
            raise MemoryError("Synthetic unmapped address")

        def read(self, address, size):
            buffer, offset = self.find(address, size)
            return int.from_bytes(buffer[offset:offset + size], "big")

        def write(self, address, size, value):
            buffer, offset = self.find(address, size)
            buffer[offset:offset + size] = (value & ((1 << (size * 8)) - 1)).to_bytes(size, "big")

    class CPU:
        def __init__(self, memory):
            self.mem, self.r = memory, [0] * 16
            self.sr = self.gbr = self.vbr = self.mach = self.macl = self.pr = self.steps = self.pc = 0
            self.helper_calls = 0

        def fetch(self, pc):
            self.mem.read(pc, 2)
            return pc

        def exec(self, instruction, pc, in_slot=False):
            if pc == probe.ENTRY:
                self.r[2] = pointer
                self.r[4] = 0x1F
                self.r[5] = 1
                self.pc = probe.HELPER_ENTRY
                return
            if pc == probe.HELPER_ENTRY:
                self.helper_calls += 1
                address = self.r[2]
                word = self.mem.read(address, 4)
                bit = 31 if mode == "constant" else (self.r[4] & 0x1F)
                self.mem.write(address, 4, word | (1 << bit))
                self.pc = probe.HELPER_INNER
                return
            if pc == probe.HELPER_INNER:
                self.r[4] = (self.r[4] - 2) & 0xFFFFFFFF
                self.pc = 0x0609DC74
                return
            if pc == 0x0609DC74:
                if self.helper_calls >= calls:
                    self.pc = RETURN
                    return
                self.r[5] = (self.r[5] * 4) & 0xFFFFFFFF
                self.pc = probe.HELPER_ENTRY
                return
            self.pc = (pc + 2) & 0xFFFFFFFF

        def step(self):
            self.steps += 1
            self.exec(self.fetch(self.pc), self.pc)

    return types.SimpleNamespace(Memory=Memory, CPU=CPU, RETURN_SENTINEL=RETURN)


def observation(call_index, r4_entry, r4_inner, r5_entry, r5_inner, bits):
    return {"call_index": call_index, "r4_entry": r4_entry, "r4_inner": r4_inner,
            "r5_entry": r5_entry, "r5_inner": r5_inner, "set_bits": bits}


class F040SetBitHelperTests(unittest.TestCase):
    def test_changed_bits_reports_only_newly_set_bits(self):
        self.assertEqual(probe.changed_bits(0x00000000, 0x80000000), [31])
        self.assertEqual(probe.changed_bits(0x00000001, 0x00000005), [2])
        self.assertEqual(probe.changed_bits(0x80000000, 0x80000000), [])
        self.assertEqual(probe.changed_bits(0xFFFFFFFF, 0x00000000), [])

    def test_word_changes_and_classification_split_stack_from_data(self):
        pre = bytes(probe.RAM_SIZE)
        live = bytearray(pre)
        live[probe.STACK_LO - probe.BASE:probe.STACK_LO - probe.BASE + 4] = (7).to_bytes(4, "big")
        live[0x060FC5A0 - probe.BASE:0x060FC5A0 - probe.BASE + 4] = (0x80000000).to_bytes(4, "big")
        changes = probe.word_changes(pre, live, {probe.STACK_LO, 0x060FC5A0})
        self.assertEqual([change["address"] for change in changes],
                         ["0x06001ee4", "0x060fc5a0"])
        stack, data = probe.classify_changes(changes)
        self.assertEqual([change["address"] for change in stack], ["0x06001ee4"])
        self.assertEqual([change["address"] for change in data], ["0x060fc5a0"])
        self.assertEqual(data[0]["set_bits"], [31])

    def test_rule_evaluation_accepts_only_the_matching_rule(self):
        observations = [observation(0, 0x1F, 0x1F, 1, 1, [31]),
                        observation(1, 0x1D, 0x1D, 4, 4, [29])]
        results = probe.evaluate_rules(observations)
        self.assertTrue(results["constant_bit31"]["consistent"] is False)
        self.assertTrue(results["r4_entry_low5"]["consistent"])
        self.assertTrue(results["r4_inner_low5"]["consistent"])
        self.assertTrue(results["r5_entry_low5"]["consistent"] is False)
        self.assertEqual(results["r4_entry_low5"]["checked"], 2)
        self.assertEqual(results["constant_bit31"]["mismatches"][0]["observed_bits"], [29])

    def test_rule_evaluation_reports_no_evidence_instead_of_agreement(self):
        results = probe.evaluate_rules([observation(0, 0x1F, 0x1F, 1, 1, [])])
        for name, result in results.items():
            with self.subTest(rule=name):
                self.assertEqual(result["checked"], 0)
                self.assertFalse(result["consistent"])
        self.assertFalse(probe.evaluate_rules([])["r4_entry_low5"]["consistent"])

    def test_series_checks_report_the_accepted_register_progressions(self):
        observations = [observation(0, 0x1F, 0x1F, 1, 1, [31]),
                        observation(1, 0x1D, 0x1D, 4, 4, [29])]
        checks = probe.series_checks(observations)
        self.assertEqual(checks["helper_call_count"], 2)
        self.assertTrue(checks["r4_inner_decreases_by_two"])
        self.assertTrue(checks["r5_entry_advances_by_four"])
        self.assertTrue(checks["r5_inner_advances_by_four"])
        self.assertTrue(checks["first_r4_inner_is_0x1f"])
        self.assertEqual(checks["r4_inner_series"], ["0x0000001f", "0x0000001d"])

    def test_synthetic_execution_observes_each_helper_call_and_its_result_word(self):
        kernel = synthetic_kernel()
        ram = synthetic_ram(kernel)
        run = probe.execute(kernel, ram, synthetic_interpreter("r4"), 0, 4096)
        self.assertEqual(run["helper_calls"].__len__(), 4)
        first = run["helper_calls"][0]
        self.assertEqual(first["result_address"], "0x060fc5a0")
        self.assertEqual(first["set_bits"], [31])
        self.assertEqual(first["r4_entry"], 0x1F)
        self.assertEqual(first["sp_entry"], probe.STACK)
        self.assertEqual(run["helper_calls"][1]["set_bits"], [29])
        self.assertEqual(run["helper_calls"][3]["set_bits"], [25])
        self.assertEqual(run["series"]["r4_inner_decreases_by_two"], True)
        self.assertEqual(run["series"]["r5_entry_advances_by_four"], True)
        results = probe.evaluate_rules(run["helper_calls"])
        self.assertTrue(results["r4_entry_low5"]["consistent"])
        self.assertFalse(results["constant_bit31"]["consistent"])

    def test_constructed_run_keeps_a_repeated_store_observable(self):
        kernel = synthetic_kernel()
        ram = synthetic_ram(kernel)
        module = synthetic_interpreter("r4")
        observed = probe.execute(kernel, ram, module, 0, 4096)
        addresses = probe.result_addresses(observed)
        self.assertEqual(addresses, {index: 0x060FC5A0 for index in range(4)})
        constructed = probe.execute(kernel, ram, synthetic_interpreter("r4"), 0, 4096,
                                   construct=addresses)
        self.assertEqual(len(constructed["constructed_writes"]), 4)
        self.assertEqual(constructed["constructed_writes"][0]["word"], "0x00000000")
        self.assertEqual([call["set_bits"] for call in constructed["helper_calls"]],
                         [[31], [29], [27], [25]])

    def test_constant_bit_behaviour_is_distinguished_from_the_r4_rule(self):
        kernel = synthetic_kernel()
        ram = synthetic_ram(kernel)
        module = synthetic_interpreter("constant")
        observed = probe.execute(kernel, ram, module, 0, 4096)
        self.assertEqual([call["set_bits"] for call in observed["helper_calls"]],
                         [[31], [], [], []])
        addresses = probe.result_addresses(observed)
        constructed = probe.execute(kernel, ram, synthetic_interpreter("constant"), 0, 4096,
                                   construct=addresses)
        results = probe.evaluate_rules(constructed["helper_calls"])
        self.assertTrue(results["constant_bit31"]["consistent"])
        self.assertFalse(results["r4_entry_low5"]["consistent"])
        self.assertFalse(results["r4_inner_low5"]["consistent"])

    def test_instruction_budget_stops_the_run_and_records_the_partial_calls(self):
        kernel = synthetic_kernel()
        ram = synthetic_ram(kernel)
        run = probe.execute(kernel, ram, synthetic_interpreter("r4"), 0, 8)
        self.assertEqual(run["stop"]["kind"], "instruction_budget")
        self.assertEqual(run["steps"], 8)
        self.assertEqual(len(run["helper_calls"]), 2)

    def test_fetch_fence_fails_the_run(self):
        kernel = synthetic_kernel()
        ram = synthetic_ram(kernel)
        altered = bytearray(kernel)
        offset = probe.HELPER_ENTRY - probe.KERNEL_BASE
        altered[offset] = 0x01
        with self.assertRaisesRegex(ValueError, "captured code differs"):
            probe.execute(bytes(altered), ram, synthetic_interpreter("r4"), 0, 4096)

    def test_constructed_address_outside_the_captured_workram_is_rejected(self):
        kernel = synthetic_kernel()
        ram = synthetic_ram(kernel)
        with self.assertRaisesRegex(ValueError, "outside captured WorkRAM"):
            probe.execute(kernel, ram, synthetic_interpreter("r4"), 0, 4096,
                          construct={0: 0x06100000})

    def test_anchors_report_a_caller_state_that_differs_from_the_accepted_evidence(self):
        kernel = synthetic_kernel()
        ram = synthetic_ram(kernel)
        observed = [probe.execute(kernel, ram, synthetic_interpreter("r4"), 0, 4096)]
        anchor = probe.anchors(ram, observed)
        self.assertFalse(anchor["data_slice_matches_accepted"])
        self.assertIn("data_slice_matches_accepted", anchor["failures"])
        self.assertIn("helper_entry_sp_matches_accepted", anchor["failures"])

    def test_cli_requires_a_fresh_private_report_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    probe.main(["--kernel", "unused", "--state", "unused",
                                "--checkpoint", "unused", "--saturn-recomp", "unused",
                                "--report", str(path), "--instruction-limit", "7"])
            self.assertFalse(path.exists())

    def test_cli_writes_a_failure_report_when_the_inputs_do_not_match(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Path(directory) / "kernel.bin"
            state = Path(directory) / "state.bin"
            checkpoint = Path(directory) / "checkpoint.json"
            report = Path(directory) / "report.json"
            kernel.write_bytes(synthetic_kernel())
            state.write_bytes(bytes(probe.RAM_SIZE))
            checkpoint.write_text(json.dumps({"frame": 1200}))
            with contextlib.redirect_stdout(io.StringIO()):
                status = probe.main(["--kernel", str(kernel), "--state", str(state),
                                     "--checkpoint", str(checkpoint),
                                     "--saturn-recomp", "unused", "--report", str(report)])
            self.assertEqual(status, 1)
            written = json.loads(report.read_text())
            self.assertEqual(written["status"], "failure")
            self.assertEqual(written["error"]["type"], "ValueError")
            self.assertEqual(oct(report.stat().st_mode & 0o777), "0o600")

    def test_probe_identity_constants_match_the_accepted_evidence(self):
        self.assertEqual(probe.KERNEL_SHA256,
                         "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb")
        self.assertEqual(probe.DATA_SLICE_SHA256,
                         "4d43fa36164881d49f7a766f9d71cb116edc4a02086e984171cffa9b4b6258e2")
        self.assertEqual((probe.DATA_SLICE_LO, probe.DATA_SLICE_HI), (0x060FC500, 0x060FC700))
        self.assertEqual(probe.HELPER_ENTRY_SP, 0x06001F24)
        self.assertEqual((probe.HELPER_ENTRY, probe.HELPER_END), (0x06095C24, 0x06095C8C))

    def test_owned_program_is_synthetic_and_matches_its_declared_expectations(self):
        kernel, ram = probe.owned_program()
        self.assertEqual(len(kernel), 786432)
        self.assertEqual(len(ram), probe.RAM_SIZE)
        self.assertNotEqual(probe.sha(kernel), probe.KERNEL_SHA256)
        self.assertNotEqual(probe.sha(ram), probe.WORKRAM_SHA256)
        region = ram[probe.KERNEL_BASE - probe.BASE:probe.KERNEL_BASE - probe.BASE + len(kernel)]
        self.assertEqual(region, kernel)
        offset = probe.HELPER_ENTRY - probe.KERNEL_BASE
        self.assertEqual(int.from_bytes(kernel[offset:offset + 2], "big"),
                         probe.OWNED_HELPER[0])
        r4_series = [0x1F - 2 * index for index in range(len(probe.OWNED_EXPECTED_BITS))]
        self.assertEqual([bits[0] for bits in probe.OWNED_EXPECTED_BITS],
                         [value & 0x1F for value in r4_series])

    def test_owned_smoke_fails_when_the_harness_misreports(self):
        def misreporting(kernel_bytes, ram_bytes, emu, seed, limit, construct=None):
            calls = [{"call_index": index, "set_bits": [31], "result_address": "0x060fc5a0",
                      "r4_entry": 0x1F, "r5_entry": 1} for index in range(4)]
            return {"stop": {"kind": "return_sentinel"}, "steps": 10, "helper_calls": calls}

        with patch.object(probe, "execute", side_effect=misreporting):
            with self.assertRaisesRegex(ValueError, "wrong changed bits"):
                probe.owned_smoke(object())


if __name__ == "__main__":
    unittest.main()
