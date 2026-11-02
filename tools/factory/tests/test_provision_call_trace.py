"""Real C observer ABI with owned CPU states; this fixture is not an emulator."""
import ctypes as C
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import provision_call_trace_abi as trace
import provision_call_trace as preparation

FIXTURE = r'''
#include <stdint.h>
#include <string.h>
#define INLINE inline
static int setting_sh2_jit;
typedef struct {
 uint32_t R[16], PC, Pipe_ID, SR, GBR, VBR, MACH, MACL, PR;
 int32_t timestamp;
} SH7095;
#include "neptune_call_trace.h"
void fixture_reset(void) { memset(&neptune_call_trace, 0, sizeof(neptune_call_trace)); setting_sh2_jit = 0; }
void fixture_jit(uint32_t enabled) { setting_sh2_jit = enabled; }
void fixture_overflow(void) { neptune_call_trace.count = NEPTUNE_TRACE_RECORDS; }
void fixture_dispatch_overflow(void) { neptune_call_trace.master_dispatches = UINT32_MAX; }
uint32_t fixture_step(const NeptuneCallRecord* input, uint32_t raw_pc, uint32_t pipe) {
 SH7095 z, before;
 memset(&z, 0, sizeof(z));
 memcpy(z.R, input->r, sizeof(z.R));
 z.PC = raw_pc; z.Pipe_ID = pipe; z.timestamp = input->timestamp;
 z.SR = input->sr; z.GBR = input->gbr; z.VBR = input->vbr;
 z.MACH = input->mach; z.MACL = input->macl; z.PR = input->pr;
 memcpy(&before, &z, sizeof(z));
 neptune_call_step(&z);
 return memcmp(&before, &z, sizeof(z)) == 0;
}
'''


class ObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        shutil.copy2(ROOT / "provision_call_trace.h", root / "neptune_call_trace.h")
        (root / "fixture.c").write_text(FIXTURE)
        subprocess.run(["cc", "-std=c11", "-shared", "-fPIC", "-O2", "-Wall", "-Werror",
                        str(root / "fixture.c"), "-o", str(root / "observer.so")], check=True,
                       capture_output=True, text=True, timeout=30)
        cls.dll = C.CDLL(str(root / "observer.so"))
        cls.dll.fixture_step.argtypes = [C.POINTER(trace.Record), C.c_uint32, C.c_uint32]
        cls.dll.fixture_step.restype = C.c_uint32

    def setUp(self):
        self.dll.fixture_reset()
        self.binding = trace.Trace(self.dll)
        self.state = trace.Record()
        for i in range(16):
            self.state.r[i] = 0xA5A5A5A5
        self.state.r[4], self.state.r[5], self.state.r[15] = 2, 1, 0x060FFF00
        self.state.pr, self.state.macl, self.state.sr = 0x0600BAEE, 0x12345678, 0x3F0

    def step(self, pc, opcode=9, *, delay=False, exception=False):
        pipe = opcode | (0xFF000000 if exception else (0x80000000 if delay else 0))
        self.assertEqual(self.dll.fixture_step(C.byref(self.state), pc, pipe), 1, "Observer must not mutate CPU state")

    def entry(self):
        self.step(trace.ENTRY + 4, 0x4F12)

    def complete(self):
        self.entry()
        for _ in range(11):
            self.step(trace.ENTRY + 6)
        self.step(0x0600B950, 0x000B)
        self.step(self.state.pr + 2, 0x4F16, delay=True)
        self.state.r[0] = ((10 * 2 + 1) * 152 + 0x00207F74) & 0xFFFFFFFF
        self.state.r[2], self.state.r[3], self.state.r[6] = 152, 2, 0x00207F74
        self.step(self.state.pr + 4)

    def test_c_abi_and_normal_pc_delay_boundaries_preserve_cpu_state(self):
        self.binding.start(1)
        self.binding.frame(30360)
        self.complete()
        result = self.binding.finish()
        self.assertEqual(result["pairs"], 1)
        before, after = result["records"]
        self.assertEqual(before["pc"], trace.ENTRY)
        self.assertEqual(after["pc"], before["pr"])
        self.assertEqual(after["dispatch_steps"], 14)
        self.assertEqual(after["macl"], 0x12345678)
        self.assertEqual(result["status"]["master_dispatches"], 15)

    def test_dispatch_coverage_distinguishes_empty_execution_and_counter_overflow(self):
        self.binding.start(1)
        self.binding.frame(0)
        self.step(0x06006004)
        status = self.binding.status()
        self.assertEqual((status.master_dispatches, status.completed, status.errors), (1, 0, 0))
        with self.assertRaises(ValueError):
            self.binding.finish()
        self.setUp()
        self.binding.start(1)
        self.binding.frame(0)
        self.dll.fixture_dispatch_overflow()
        self.step(0x06006004)
        self.assertEqual(self.binding.status().errors, 1)
        with self.assertRaises(ValueError):
            self.binding.finish()

    def test_real_c_library_probe_exercises_fences_without_claiming_cpu_execution(self):
        result = trace.probe_library(Path(self.temp.name) / "observer.so")
        self.assertEqual(result["record_bytes"], 120)
        self.assertTrue(result["rejected_invalid_entry_budget_and_frame"])
        self.assertIn("no media", result["scope"])

    def test_delay_and_exception_pseudo_ops_cannot_create_false_entries(self):
        self.binding.start(1)
        self.binding.frame(0)
        self.step(trace.ENTRY + 4, 0x4F12, delay=True)
        self.step(trace.ENTRY + 4, 0x4F12, exception=True)
        self.assertEqual(self.binding.status().count, 0)
        with self.assertRaises(ValueError):
            self.binding.finish()

    def test_wrong_mode_pair_budget_duplicate_start_and_clock_fail_closed(self):
        for pairs in (0, 65, True):
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                self.binding.start(pairs)
        self.dll.fixture_jit(1)
        with self.assertRaises(ValueError):
            self.binding.start(1)
        self.dll.fixture_jit(0)
        self.binding.start(1)
        with self.assertRaises(ValueError):
            self.binding.start(1)
        self.binding.frame(8)
        with self.assertRaises(ValueError):
            self.binding.frame(10)
        self.assertEqual(self.binding.status().errors, 1)

    def test_missing_frame_or_return_and_reentry_are_not_complete(self):
        for mode in ("no-frame", "no-return", "reentry", "no-rts", "no-restore"):
            with self.subTest(mode=mode):
                self.setUp()
                self.binding.start(1)
                if mode != "no-frame":
                    self.binding.frame(0)
                self.entry()
                if mode == "reentry":
                    self.entry()
                if mode == "no-restore":
                    self.step(0x0600B950, 0x000B)
                if mode in ("no-rts", "no-restore"):
                    self.step(self.state.pr + 4)
                with self.assertRaises(ValueError):
                    self.binding.finish()

    def test_step_budget_and_overflow_are_retained_not_silent_truncation(self):
        self.binding.start(1)
        self.binding.frame(0)
        self.entry()
        for _ in range(trace.STEP_LIMIT):
            self.step(trace.ENTRY + 6)
        self.assertEqual(self.binding.status().errors, 1)
        with self.assertRaises(ValueError):
            self.binding.finish()
        self.setUp()
        self.binding.start(1)
        self.binding.frame(0)
        self.dll.fixture_overflow()
        self.entry()
        self.assertEqual(self.binding.status().dropped, 1)
        with self.assertRaises(ValueError):
            self.binding.finish()

    def test_short_buffers_and_natural_result_state_mutations_cannot_pass(self):
        self.binding.start(1)
        self.binding.frame(0)
        self.complete()
        status = self.binding.status()
        records = (trace.Record * trace.CAPACITY)()
        self.assertEqual(self.dll.neptune_call_records(records, 1), 0xFFFFFFFF)
        self.assertEqual(self.dll.neptune_call_status(C.byref(status), C.sizeof(status) - 4), 0)
        self.assertEqual(self.dll.neptune_call_records(records, trace.CAPACITY), 2)
        trace.validate(list(records)[:2], status)
        for field in ("r0", "sp", "macl", "cpu", "sequence", "pc", "timestamp"):
            changed = [trace.Record.from_buffer_copy(record) for record in records[:2]]
            if field == "r0": changed[1].r[0] ^= 4
            elif field == "sp": changed[1].r[15] -= 4
            elif field == "macl": changed[1].macl ^= 1
            elif field == "timestamp": changed[1].timestamp = -1
            else: setattr(changed[1], field, getattr(changed[1], field) ^ 1)
            with self.subTest(field=field), self.assertRaises(ValueError):
                trace.validate(changed, status)


class PatchTests(unittest.TestCase):
    def test_all_source_hashes_are_checked_before_any_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in preparation.SOURCES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"owned mismatching source")
            before = {name: (root / name).read_bytes() for name in preparation.SOURCES}
            with self.assertRaises(ValueError):
                preparation.prepare(root)
            self.assertEqual({name: (root / name).read_bytes() for name in preparation.SOURCES}, before)
            self.assertFalse((root / "mednafen/ss/neptune_call_trace.h").exists())

    def test_owned_patch_fixture_covers_both_master_paths_and_export_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = {name: b"owned source" for name in preparation.SOURCES}
            content["mednafen/ss/ss.c"] = b'#include "sh7095.inc"\n'
            content["mednafen/ss/sh7095.inc"] = b"\n".join(
                b"FORCE_INLINE void SH7095_Step_" + name + b"(SH7095* z)\n{\n const uint32_t instr = (uint16_t)z->Pipe_ID;\n}\n"
                for name in (b"w0_C0", b"w0_C1"))
            content["link.T"] = b"{ global: retro_*; local: *; };\n"
            for name, data in content.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            with patch.object(preparation, "SOURCES", {name: hashlib.sha256(data).hexdigest() for name, data in content.items()}):
                result = preparation.prepare(root)
                self.assertEqual((root / "mednafen/ss/sh7095.inc").read_bytes().count(b"neptune_call_step(z);"), 2)
                self.assertIn(b"neptune_call_records;", (root / "link.T").read_bytes())
                self.assertEqual(result["maximum_pairs"], 64)
                with self.assertRaises(ValueError):
                    preparation.prepare(root)
