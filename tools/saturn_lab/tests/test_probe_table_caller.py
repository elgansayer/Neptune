"""Owned contract-fence fixtures, not original game execution or captures."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_table_caller as probe


def owned_zero_fixture():
    # Explicit declared initial poison and zero-input prefix observation.
    before = {f"r{i}": 0xA5A50000 + i * 257 for i in range(16)}
    before.update(r15=0x060FFFF0, sr=0x3F3, gbr=0x13572468, vbr=0x24681350,
                  mach=0x2468ACE0, macl=0x13579BDF, pr=0xFACEB00C)
    registers = dict(before)
    registers.update(r0=0x060B30C4, r2=152, r3=0, r4=0, r5=0, r6=0x060B30C4,
                     r11=0x060C029D, r12=0, r13=0x060C029C, r14=0x00207F74,
                     r15=0x060FFFD8, sr=0x3F2, pr=0x0600BAFA)
    return {"registers": registers,
            "writes": [[0x060FFFF0 - offset, 4, before[name]] for offset, name in
                       ((4, "r14"), (8, "r13"), (12, "r12"), (16, "r11"),
                        (20, "r10"), (24, "pr"), (28, "macl"))],
            "data_reads": [[address, 1, 0] for address in
                           (0x060C029C, 0x060C029D, 0x060C029C, 0x060C029D, 0x060C029C)],
            "stack_reads": [[0x060FFFD4, 4, 0x13579BDF]],
            "calls": [[0x0600B934, 0, 0, 0x0600BAEE, 0x060FFFD8, 0x13579BDF],
                      [0x0600B950, 0, 0, 0x0600BAFA, 0x060FFFD8, 0x13579BDF]],
            "pcs": (list(range(0x0600BAC4, 0x0600BAE0, 2))
                    + list(range(0x0600BAE4, 0x0600BAEE, 2))
                    + list(range(0x0600B934, 0x0600B950, 2))
                    + list(range(0x0600BAEE, 0x0600BAFA, 2))
                    + list(range(0x0600B950, 0x0600B966, 2))),
            "stop": 0x0600BAFA, "unaffected_bytes_equal": True}


class CallerContractTests(unittest.TestCase):
    def test_owned_zero_observation_and_prefix_not_return(self):
        observed = owned_zero_fixture()
        self.assertEqual(len(observed["pcs"]), 50)
        probe.validate_observation(0, 0, observed)
        self.assertEqual(observed["registers"]["r15"], probe.SP - 24)
        self.assertNotEqual(observed["registers"]["pr"], 0xFACEB00C)

    def test_missing_changed_and_extra_observations_are_rejected(self):
        for key in ("registers", "writes", "data_reads", "stack_reads", "calls", "pcs", "stop",
                    "unaffected_bytes_equal"):
            with self.subTest(missing=key):
                observed = owned_zero_fixture()
                del observed[key]
                with self.assertRaises(ValueError):
                    probe.validate_observation(0, 0, observed)
        changes = (
            lambda o: o["registers"].update(r7=0),
            lambda o: o["registers"].update(macl=0),
            lambda o: o["registers"].update(sr=0),
            lambda o: o["writes"].append([probe.DATA_BASE, 4, 0]),
            lambda o: o["writes"].reverse(),
            lambda o: o["stack_reads"].append([probe.SP - 28, 4, 0x13579BDF]),
            lambda o: o["calls"][0].__setitem__(3, 0x0600BAEC),
            lambda o: o["calls"].pop(),
            lambda o: o["pcs"].remove(0x0600BAEC),
            lambda o: o["pcs"].append(probe.STOP),
            lambda o: o.update(unaffected_bytes_equal=False),
        )
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                observed = copy.deepcopy(owned_zero_fixture())
                change(observed)
                with self.assertRaises(ValueError):
                    probe.validate_observation(0, 0, observed)

    def test_bytes_only_and_declared_reset_boundary(self):
        for category, slot in ((-1, 0), (0, 256), (True, 0), (0, "0")):
            with self.assertRaises(ValueError):
                probe.contract(category, slot)
        self.assertEqual(probe.contract(8, 255)["effective_bytes"], [8, 255])
        self.assertEqual(probe.contract(9, 255)["effective_bytes"], [0, 0])
        self.assertEqual(len(probe.expected_pcs(9)), 52)

    def test_failed_input_retained_and_report_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kernel, report = root / "invalid.bin", root / "report.json"
            kernel.write_bytes(b"owned invalid input")
            args = ["--kernel", str(kernel), "--saturn-recomp", str(root), "--report", str(report)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(args), 1)
            saved = report.read_bytes()
            self.assertEqual(json.loads(saved)["status"], "failure")
            self.assertNotIn("cases", json.loads(saved))
            with self.assertRaises(FileExistsError):
                probe.main(args)
            self.assertEqual(report.read_bytes(), saved)

    def test_negative_control_budget_failure_is_not_semantic_acceptance(self):
        class BudgetFailure:
            def __init__(self, *_):
                pass

            def run(self, *_):
                raise ValueError("Original prefix exceeded instruction budget")

        with patch.object(probe, "Experiment", BudgetFailure):
            with self.assertRaisesRegex(ValueError, "terminal semantic comparison"):
                probe.instruction_controls(bytes(probe.pinned.SIZE), None)


if __name__ == "__main__":
    unittest.main()
