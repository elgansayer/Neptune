"""Owned contract/decoder tests for the SND mailbox probe; no original bytes or CPU execution."""
from pathlib import Path
import collections
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_snd_mailbox as probe


def synthetic_disc():
    """Owned zero image with only the generic table-witness instruction words."""
    disc = bytearray(probe.CODE_END)
    disc[probe.TABLE_LEA:probe.TABLE_LEA + 4] = probe.TABLE_LEA_WORDS.to_bytes(4, 'big')
    disc[probe.COUNTER:probe.COUNTER + 2] = (0x0300).to_bytes(2, 'big')
    return bytes(disc)


def owned_tables():
    """Encode the declared dispatch map with generic jmp/rts words, including the 6-byte overlap."""
    code = bytearray(0x2000)
    declared = probe.declared_tables()
    for cmd in range(0x20):
        thunk = probe.LOW_TABLE + 4 * cmd
        target = declared[cmd]
        if target == 'rts':
            code[thunk:thunk + 2] = b'\x4e\x75'
        else:
            code[thunk:thunk + 4] = b'\x4e\xfa' + (target - thunk - 2).to_bytes(2, 'big', signed=True)
    for index in range(11):
        thunk = probe.HIGH_TABLE + 4 * index
        code[thunk:thunk + 4] = b'\x4e\xfa' + (declared[0x80 | index] - thunk - 2).to_bytes(2, 'big', signed=True)
    for thunk in (0x1B06, 0x1B0C, 0x1B12):  # absolute jumps whose address words overlap later slots
        code[thunk:thunk + 6] = b'\x4e\xf9' + probe.IGNORE.to_bytes(4, 'big')
    return bytes(code)


def ring_ram(records, live=0, offset=None):
    ram = bytearray(0x10000)
    for index, (cmd, stamp) in enumerate(records):
        base = probe.RING + 16 * index
        ram[base] = cmd
        ram[base + 2] = index + 1
        ram[base + 14:base + 16] = stamp.to_bytes(2, 'big')
    count = len(records)
    ram[probe.RING + 16 * count:probe.RING + 16 * count + 16] = b'\xff' * 16
    value = 16 * count if offset is None else offset
    ram[probe.HOST_OFFSET:probe.HOST_OFFSET + 2] = value.to_bytes(2, 'big')
    ram[probe.OFFSET:probe.OFFSET + 2] = value.to_bytes(2, 'big')
    ram[probe.STAMP:probe.STAMP + 2] = live.to_bytes(2, 'big')
    return ram


def synthetic_epoch(records, live, phase_stores=1, last_frame=99):
    commands = collections.Counter(cmd for cmd, _ in records)
    edges = [[probe.EXEC_CALLER, probe.EXEC_ENTRY, 'flow', 0, len(records), 1]]
    by_thunk = collections.Counter(probe.dispatch_thunk(cmd) for cmd, _ in records)
    for thunk, count in by_thunk.items():
        source = probe.LOW_JSR if thunk >= probe.LOW_TABLE else probe.HIGH_JSR
        edges.append([source, thunk, 'flow', 0, count, 1])
    interrupts = sum(stamp for _, stamp in records) + live
    low = sum(n for cmd, n in commands.items() if cmd < 0x80)
    words = [[probe.EXEC_ENTRY, len(records), 1, 0, 0], [0x1B4E, low, 1, 0, 0],
             [0x1AC2, len(records) - low, 1, 0, 0], [probe.INTERRUPT_COUNTER_STORE, interrupts, 1, 0, 0],
             [probe.COUNTER_STORE, phase_stores, 1, 0, 0]]
    return {'first_frame': 10, 'last_frame': last_frame, 'words': words, 'edges': edges,
            'exceptions': {probe.TIMER_VECTOR: interrupts}}


class FakeLibrary:
    def __init__(self, status=3):
        self.status = status

    def run(self, *args, **kwargs):
        return {'status_code': self.status, 'status': 'instruction-access', 'error_address': 0,
                'error_size': 0, 'pcs': [], 'steps': 0, 'events': [], 'registers': [0] * 18,
                'regions_after': [], 'code_unchanged': True}


class SelfPatchContractTests(unittest.TestCase):
    def test_zero_configuration_patches_every_site_in_routine_order(self):
        result = probe.patch_contract(0, 0x12345678, 0xAAAA, 0x2700, synthetic_disc())
        writes = [e[1] for e in result['events'] if e[0] == 2]
        self.assertEqual(writes, [0x10E4, 0x10E8, 0x2BE6, 0x1AAE, 0x116C, 0x1168, 0x1170])
        self.assertTrue(all(e[3] == probe.NOP2 for e in result['events'] if e[0] == 2))
        self.assertEqual(len(result['pcs']), 30)
        regs = result['registers']
        self.assertEqual(regs[0], 0x12345600)
        self.assertEqual(regs[8], 0x1170)
        self.assertEqual(regs[17], 0x2704)  # Z set, X from bit 2 clear

    def test_all_ones_configuration_patches_nothing(self):
        result = probe.patch_contract(0xFF, 0, 0xAAAA, 0x271F, synthetic_disc())
        self.assertEqual([e for e in result['events'] if e[0] == 2], [])
        self.assertEqual(len(result['pcs']), 17)
        self.assertEqual(result['registers'][0], 0x7F)
        self.assertEqual(result['registers'][8], 0xAAAA)
        self.assertEqual(result['registers'][17], 0x2710)  # X from bit 2, Z clear

    def test_each_used_bit_controls_exactly_one_site(self):
        for bit, site, longs in probe.PATCH_SITES:
            result = probe.patch_contract(0xFF & ~(1 << bit), 0, 0, 0x2700, synthetic_disc())
            self.assertEqual(result['patched_sites'], [site])
            self.assertEqual(sum(1 for e in result['events'] if e[0] == 2), longs)
        for unused in (0, 2):
            self.assertEqual(probe.patch_contract(0xFF & ~(1 << unused), 0, 0, 0x2700, synthetic_disc())
                             ['patched_sites'], [])

    def test_case_and_control_selection(self):
        cases = probe.patch_cases()
        self.assertEqual(len(cases), 512)
        self.assertEqual(len(set(cases)), 512)
        self.assertEqual(len(cases[::17]), 31)
        image = bytes(probe.CODE_END)
        for name, offset, replacement in probe.PATCH_CONTROLS:
            with self.subTest(name=name):
                self.assertNotEqual(probe.apply(bytes([0xFF]) * probe.CODE_END, offset, replacement), image)


class ExecutorContractTests(unittest.TestCase):
    def test_outcome_partition_of_all_command_bytes(self):
        kinds = collections.Counter(probe.exec_outcome(c)[0] for c in range(256))
        self.assertEqual(kinds, {'ignored': 207, 'low-handler': 18, 'low-ignored': 13, 'high-handler': 11,
                                 'high-device': 2, 'high-ignored': 2, 'low-noop': 1, 'high-ori': 1,
                                 'high-rts': 1})
        self.assertEqual(probe.exec_outcome(0x90), ('high-handler', 0x1D10))
        self.assertEqual(probe.exec_outcome(0x01), ('low-handler', 0x2364))
        self.assertEqual(probe.exec_outcome(0x0F), ('low-ignored', None))

    def test_offset_is_masked_before_increment(self):
        slots = probe.slot_bytes(0x40, 0)
        ring = probe.ring_bytes()
        high = probe.exec_contract(0x40, 0xFFF0, 7, 0, slots, ring, 0x40, 0x2000)
        self.assertEqual(high['offset_after'], 0x800)
        self.assertEqual(high['ring_after'][0x7F0:0x800], slots[:14] + (7).to_bytes(2, 'big'))
        self.assertEqual(high['ring_after'][:16], b'\xff' * 16)
        wrapped = probe.exec_contract(0x40, 0x800, 7, 0, slots, ring, 0x40, 0x2000)
        self.assertEqual(wrapped['offset_after'], 0x10)
        self.assertEqual(wrapped['ring_after'][16:32], b'\xff' * 16)

    def test_handler_stop_registers_and_flags(self):
        slots, ring = probe.slot_bytes(0x01, 3), probe.ring_bytes()
        low = probe.exec_contract(0x01, 0x590, 1, 3, slots, ring, 0x01, 0x2000)
        regs = low['registers']
        self.assertEqual(low['stop'], 0x2364)
        self.assertEqual(regs[15], probe.EXEC_SP - 12)
        self.assertEqual(regs[12], probe.A6_NATURAL)
        self.assertEqual(regs[7] & 0xFFFF, 4)
        self.assertEqual(regs[8], probe.SLOTS + 0x32)
        self.assertEqual(regs[17], 0x2000)
        high = probe.exec_contract(0x80, 0, 1, 0, probe.slot_bytes(0x80, 0), ring, 0x80, 0x271F)
        self.assertEqual((high['stop'], high['registers'][15], high['registers'][17]),
                         (0x1D10, probe.EXEC_SP - 4, 0x2704))

    def test_returning_paths_and_device_guard(self):
        ring = probe.ring_bytes()
        noop = probe.exec_contract(0x00, 0, 0, 0, probe.slot_bytes(0, 0), ring, 0, 0x2000)
        self.assertEqual((noop['stop'], noop['registers'][15], noop['registers'][17]),
                         (probe.EXEC_RETURN, probe.EXEC_SP + 4, 0x2004))
        ignored = probe.exec_contract(0x40, 0, 0, 0, probe.slot_bytes(0x40, 0), ring, 0xFFFFFF40, 0x2000)
        self.assertEqual(ignored['registers'][17], 0x2008)  # N from D0 bit 15
        ori = probe.exec_contract(0x8D, 0, 0, 0, probe.slot_bytes(0x8D, 0), ring, 0x8D, 0x2000)
        self.assertEqual(ori['registers'][0], 0xEF)
        device = probe.exec_contract(0x8C, 0, 0, 0, probe.slot_bytes(0x8C, 0), ring, 0x8C, 0x2000)
        self.assertEqual((device['status'], device['error']), (5, (0x100000, 1)))
        self.assertEqual(device['events'][-1], [1, 0xDEF9, 1, probe.device_bytes()[1]])

    def test_case_product_and_control_selection(self):
        cases = probe.exec_cases()
        self.assertEqual(len(cases), 256 * 6 * 3 * 2)
        self.assertEqual(len(set(cases)), len(cases))
        controlled = cases[::5]
        self.assertTrue({c[0] for c in controlled} >= {0x20, 0x91})
        self.assertTrue({c[1] & 0x400 for c in controlled} == {0, 0x400})

    def test_owned_thunk_tables_decode_and_mutation_is_seen(self):
        code = owned_tables()
        self.assertEqual(probe.static_tables(code), probe.declared_tables())
        changed = bytearray(code)
        changed[probe.LOW_TABLE + 6] ^= 0x02
        self.assertNotEqual(probe.static_tables(bytes(changed)), probe.declared_tables())

    def test_native_guard_cannot_be_success(self):
        with self.assertRaisesRegex(ValueError, 'Executor outcome differs'):
            probe.run_exec(bytes(probe.CODE_END), FakeLibrary(), *probe.exec_cases()[0])
        with self.assertRaisesRegex(ValueError, 'Native guard'):
            probe.run_patch(bytes(probe.CODE_END), FakeLibrary(), synthetic_disc(), 0, 0, 0x2700)

    def test_surviving_mutation_and_noop_control_fail(self):
        with self.assertRaisesRegex(ValueError, 'survived'):
            probe.control('x', 0x10, 'ffff', bytes(0x40), lambda m, c: None, [1])
        with self.assertRaisesRegex(ValueError, 'does not change'):
            probe.apply(bytes(0x40), 0x10, '0000')

    def test_applied_writes_only_inside_region(self):
        out = probe.applied(0x100, bytes(8), [[2, 0x102, 2, 0xABCD], [1, 0x100, 4, 1], [2, 0x200, 4, 5]])
        self.assertEqual(out, bytes([0, 0, 0xAB, 0xCD, 0, 0, 0, 0]))


class NaturalDecoderTests(unittest.TestCase):
    def test_ring_decode_and_cumulative_ticks(self):
        decoded = probe.decode_ring(ring_ram([(0x82, 5), (0x01, 7), (0x86, 0)], live=9))
        self.assertEqual(decoded['count'], 3)
        rows = probe.commands_from(decoded['entries'])
        self.assertEqual([r['cumulative_ticks'] for r in rows], [5, 12, 12])
        self.assertEqual(rows[1]['command'], 0x01)

    def test_ring_rejections(self):
        good = ring_ram([(0x82, 5), (0x01, 7)])
        cases = {'offsets': lambda r: r.__setitem__(slice(probe.OFFSET, probe.OFFSET + 2), b'\x00\x10'),
                 'marker': lambda r: r.__setitem__(probe.RING + 32, 0),
                 'tail': lambda r: r.__setitem__(probe.RING + 0x100, 1),
                 'empty': lambda r: r.__setitem__(probe.RING, 0)}
        for name, change in cases.items():
            with self.subTest(name=name):
                ram = bytearray(good)
                change(ram)
                with self.assertRaises(ValueError):
                    probe.decode_ring(ram)
        with self.assertRaises(ValueError):
            probe.decode_ring(ring_ram([(1, 1)], offset=0x808))

    def test_natural_cross_checks_and_rejections(self):
        records = [(0x82, 5), (0x0D, 0), (0x01, 9), (0x01, 2)]
        early, late = ring_ram(records[:2], live=3), ring_ram(records, live=4)
        for ram, phase in ((early, 0x0000), (late, 0x0000)):
            ram[probe.COUNTER:probe.COUNTER + 2] = phase.to_bytes(2, 'big')
        snaps = {50: bytes(early), 100: bytes(late)}
        epoch = synthetic_epoch(records, 4, phase_stores=1)
        checks = probe.natural_checks(snaps, epoch, 0x0300)
        self.assertEqual(checks['by_command'], {'0x01': 2, '0x0D': 1, '0x82': 1})
        self.assertEqual(checks['vector26_interrupts'], 20)
        bad_count = synthetic_epoch(records, 4)
        bad_count['edges'][1][4] += 1
        bad_time = synthetic_epoch(records, 5)
        bad_phase = synthetic_epoch(records, 4, phase_stores=2)
        for epoch_case in (bad_count, bad_time, bad_phase):
            with self.assertRaises(ValueError):
                probe.natural_checks(snaps, epoch_case, 0x0300)
        swapped = bytearray(early)
        swapped[probe.RING + 15] ^= 1
        with self.assertRaisesRegex(ValueError, 'prefix'):
            probe.natural_checks({50: bytes(swapped), 100: bytes(late)}, epoch, 0x0300)

    def test_resident_derivation_and_runtime_table(self):
        disc = synthetic_disc()
        derived = probe.patch_contract(0, 0, 0, 0x2700, disc)['image']
        ram = bytearray(0x10000)
        ram[:probe.CODE_END] = derived
        ram[probe.TABLE + 1] = 4
        path = probe.patch_contract(0, 0, 0, 0x2700, disc)['pcs']
        chain = [probe.PATCH_CALLER] + path + [probe.PATCH_RETURN]
        epoch = {'words': [[pc, 1, 1, int.from_bytes(derived[pc:pc + 2], 'big'), 0] for pc in path],
                 'edges': [[a, b, 'flow', 0, 1, 1] for a, b in zip(chain, chain[1:])]}
        result = probe.natural_patch_checks({7: bytes(ram)}, epoch, disc, derived, 0)
        self.assertEqual(result['derived_code_bytes_changed'], 28)
        self.assertEqual(result['runtime_table_nonzero_bytes'], {'7': 1})
        outside = bytearray(ram)
        outside[probe.TABLE_END] = 1
        with self.assertRaisesRegex(ValueError, 'derived self-patched'):
            probe.natural_patch_checks({7: bytes(outside)}, epoch, disc, derived, 0)
        executed = {'words': epoch['words'] + [[probe.TABLE, 1, 1, 0, 0]], 'edges': epoch['edges']}
        with self.assertRaisesRegex(ValueError, 'runtime record table'):
            probe.natural_patch_checks({7: bytes(ram)}, executed, disc, derived, 0)
        with self.assertRaisesRegex(ValueError, 'configuration'):
            probe.natural_patch_checks({7: bytes(ram)}, epoch, disc, derived, 0x80)

    def test_report_requires_fresh_path(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / 'report.json'
            existing.write_text('{}')
            self.assertEqual(probe.main(['--source-file', str(existing), '--prepared', directory,
                                         '--run', directory, '--report', str(existing)]), 1)
            self.assertEqual(existing.read_text(), '{}')


if __name__ == '__main__':
    unittest.main()
