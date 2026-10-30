"""Independent synthetic CIL cases; real-assembly receipt is separate."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_pacing as p


def instruction(offset, op, operand=None):
    return NS(offset=offset, opcode=NS(name=op), operand=operand, size=1)


def machine(operations):
    body = NS(instructions=[instruction(i, *op) for i, op in enumerate(operations)],
              exception_handlers=[], header_size=0)
    result = p.Original.__new__(p.Original)
    result.bodies = {1: body}
    result.fields = {0x29: 0, 0x2A: [1, 2], 0x2B: 0, 0x2C: 1, 0x2D: object()}
    result.exits = 0
    return result


class PacingInterpreter(unittest.TestCase):
    def test_real_assembly_required_before_loading_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.dll"
            path.write_bytes(b"fake")
            with self.assertRaisesRegex(ValueError, "pinned"):
                p.load(path)
            path.write_bytes(bytes(129536))
            with self.assertRaisesRegex(ValueError, "pinned"):
                p.load(path)

    def test_signed_int32_boundaries(self):
        self.assertEqual(p.signed32(2147483648), -2147483648)
        self.assertEqual(p.signed32(-2147483649), 2147483647)

    def test_stack_order_for_field_write(self):
        m = machine([("ldarg.0",), ("ldc.i4.2",), ("stfld", NS(value=0x04000029)), ("ret",)])
        m.run(1)
        self.assertEqual(m.fields[0x29], 2)

    def test_increment_mutates_reference_and_returns_new_value(self):
        m = machine([("ldarg.0",), ("ldflda", NS(value=0x04000029)),
                     ("call", NS(value=0x0A000083)), ("ret",)])
        self.assertEqual(m.run(1), 1)
        self.assertEqual(m.run(1), 2)

    def test_branch_equality_distinguishes_ble_from_blt(self):
        m = machine([("ldc.i4.0",), ("ldc.i4.0",), ("ble.s", 5),
                     ("ldc.i4.2",), ("ret",), ("ldc.i4.1",), ("ret",)])
        self.assertEqual(m.run(1), 1)
        m.bodies[1].instructions[2].opcode.name = "blt.s"
        self.assertEqual(m.run(1), 2)

    def test_unknown_call_and_opcode_fail(self):
        for op in [("call", NS(value=0x0A000099)), ("nop",)]:
            with self.assertRaises(ValueError):
                machine([op, ("ret",)]).run(1)

    def test_bad_jump_and_loop_cannot_report_success(self):
        for target in (-1, 100, 0):
            with self.assertRaises(ValueError):
                machine([("br.s", target)]).run(1)

    def test_unbalanced_stack_and_finally_fail(self):
        for ops in [[("ldc.i4.1",), ("ldc.i4.2",), ("ret",)],
                    [("endfinally",)], [("leave.s", 0)]]:
            with self.assertRaises(ValueError):
                machine(ops).run(1)


if __name__ == "__main__":
    unittest.main()
