import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_record_flag_bytes as probe


class JapanRecordFlagBytesTests(unittest.TestCase):
    def test_source_bounds_and_ten_independent_flag_bits(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060AB1B4, 0x060AB31A))
        self.assertEqual((probe.TARGET, probe.TARGET + 8), (0x06003000, 0x06003008))
        self.assertEqual(len(probe.FLAG_BITS), 10)
        self.assertEqual(len(set(probe.FLAG_BITS)), 10)
        flags = {sum(bit for i, bit in enumerate(probe.FLAG_BITS)
                     if word & (1 << i)) for word in range(1 << len(probe.FLAG_BITS))}
        self.assertEqual(len(flags), 1024)

    def test_complete_constructed_corpus_is_unique_and_bounded(self):
        cases = list(probe.corpus())
        self.assertEqual(len(cases), 24576)
        self.assertEqual(len(set(cases)), 24576)
        self.assertEqual({case[1] for case in cases},
                         {0, probe.ALL_FLAGS, probe.ALTERNATING_FLAGS})

    def test_byte_oracle_applies_active_gate_operation_in_field_order(self):
        initial = bytes((0xF0, 0x0F, 0xAA, 0x55, 0x81, 0x18, 0xC3, 0x3C))
        expected_offsets = [1, 0, 3, 2, 5, 4, 7, 6]
        for choices, offset in probe.FIELD_MASKS:
            r5 = choices[0]
            for r4 in (0, choices[0], probe.ALL_FLAGS):
                updated, events = probe.expected_bytes(initial, r5, r4, 0x55, 0xF0)
                operation = (initial[offset] | 0x55) if r4 & sum(choices) else (initial[offset] & 0xF0)
                self.assertEqual(updated[offset], operation)
                self.assertEqual(events, [(offset, operation)])
        full, events = probe.expected_bytes(initial, probe.ALL_FLAGS, probe.ALL_FLAGS,
                                            0x55, 0xF0)
        self.assertEqual([offset for offset, _ in events], expected_offsets)
        self.assertEqual(full, bytes(value | 0x55 for value in initial))


if __name__ == "__main__":
    unittest.main()
