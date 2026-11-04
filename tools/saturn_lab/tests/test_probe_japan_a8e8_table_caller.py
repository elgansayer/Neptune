import unittest
import probe_japan_a8e8_table_caller as probe


class A8E8CallerTests(unittest.TestCase):
    def test_original_ranges_aliases_and_exit_edges_are_bounded(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600A8E8, 0x0600A946))
        self.assertEqual(probe.EXIT, {0x0600A79C: "error_loop", 0x0600ACE8: "scheduler_handoff"})
        self.assertEqual(probe.ALIASES, {
            0x2600A018: 0x0600A018, 0x2600A01C: 0x0600A01C,
            0x2600A020: 0x0600A020, 0x2600A024: 0x0600A024,
            0x2600A030: 0x0600A030,
        })

    def test_vbr_slots_select_distinct_rows_and_count_edges(self):
        self.assertEqual(len(probe.CASES), 4)
        for case in probe.CASES.values():
            self.assertEqual(len(case["indices"]), 2)
            self.assertNotEqual(*case["indices"])
            self.assertTrue(all(0 <= index < 18 for index in case["indices"]))
        self.assertEqual(probe.CASES["free_slot_exhausted"]["count"], 1)

    def test_composed_table_model_includes_aacc_latch_store(self):
        case = probe.CASES["callback_latch_success"]
        for index in case["indices"]:
            result = probe.modeled_table(case, index)
            target = case["fields"][index][82]
            self.assertEqual(result[target * 88:target * 88 + 4], b"\x00\x00\x00\x01")


if __name__ == "__main__":
    unittest.main()
