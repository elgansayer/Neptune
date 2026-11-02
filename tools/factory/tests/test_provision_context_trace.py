"""Compile the observer against owned states; these are not game executions."""
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
import provision_context_trace_abi as trace
import provision_context_trace as preparation

FIXTURE = r'''
#include <stdint.h>
#include <string.h>
#define INLINE inline
static int setting_sh2_jit;
static uint16_t ram[0x80000], before_ram[0x80000];
static uint16_t* WorkRAMH=ram;
typedef struct {
 uint32_t R[16], PC, Pipe_ID, SR, GBR, VBR, MACH, MACL, PR;
 int32_t timestamp;
} SH7095;
#include "neptune_context_trace.h"
void fixture_reset(void) {
 memset(&neptune_context_trace,0,sizeof(neptune_context_trace));
 memset(ram,0,sizeof(ram)); setting_sh2_jit=0; WorkRAMH=ram;
}
void fixture_word(uint32_t address,uint32_t value) {
 uint32_t i=(address-0x06000000)>>1;ram[i]=(uint16_t)(value>>16);ram[i+1]=(uint16_t)value;
}
void fixture_source(const uint16_t* words) {
 uint32_t n=0,starts[3]={0x61C4,0x6B9C,0x6E00},counts[3]={35,278,26};
 for(uint32_t block=0;block<3;block++) for(uint32_t i=0;i<counts[block];i++) ram[(starts[block]>>1)+i]=words[n++];
}
void fixture_jit(uint32_t value) { setting_sh2_jit=value; }
void fixture_overflow(void) { neptune_context_trace.count=NEPTUNE_CTX_CAPACITY; }
void fixture_counter(void) { neptune_context_trace.master_dispatches=UINT32_MAX; }
uint32_t fixture_step_mode(const NeptuneContextRecord* input,uint32_t pc,uint32_t pipe,uint32_t fused) {
 SH7095 z,before; memset(&z,0,sizeof(z));memcpy(z.R,input->r,sizeof(z.R));
 z.SR=input->sr;z.GBR=input->gbr;z.VBR=input->vbr;z.MACH=input->mach;
 z.MACL=input->macl;z.PR=input->pr;z.timestamp=input->timestamp;z.PC=pc;z.Pipe_ID=pipe;
 memcpy(&before,&z,sizeof(z));memcpy(before_ram,ram,sizeof(ram));
 if(fused) neptune_context_fused_nop(&z);else neptune_context_step(&z);
 return memcmp(&before,&z,sizeof(z))==0 && memcmp(before_ram,ram,sizeof(ram))==0;
}
uint32_t fixture_step(const NeptuneContextRecord* input,uint32_t pc,uint32_t pipe) {
 return fixture_step_mode(input,pc,pipe,0);
}
uint32_t fixture_fused(const NeptuneContextRecord* input,uint32_t pc,uint32_t pipe) {
 return fixture_step_mode(input,pc,pipe,1);
}
'''


@unittest.skipUnless(shutil.which("cc"), "C compiler needed for actual native fixture")
class ContextTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        shutil.copy2(ROOT / "provision_context_trace.h", cls.directory / "neptune_context_trace.h")
        (cls.directory / "fixture.c").write_text(FIXTURE)
        subprocess.run(["cc", "-std=c11", "-shared", "-fPIC", "-O2", "-Wall", "-Werror",
                        "fixture.c", "-o", "fixture.so"], cwd=cls.directory, check=True, capture_output=True)
        cls.dll = C.CDLL(str(cls.directory / "fixture.so"))
        cls.dll.fixture_step.argtypes = [C.POINTER(trace.Record), C.c_uint32, C.c_uint32]
        cls.dll.fixture_step.restype = C.c_uint32
        cls.dll.fixture_fused.argtypes = cls.dll.fixture_step.argtypes
        cls.dll.fixture_fused.restype = C.c_uint32
        cls.dll.fixture_source.argtypes = [C.POINTER(C.c_uint16)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.dll.fixture_reset()
        self.witness = [0xA000 + i for i in range(trace.WITNESS_WORDS)]
        self.dll.fixture_source((C.c_uint16 * trace.WITNESS_WORDS)(*self.witness))
        self.observer = trace.Trace(self.dll)
        self.cpu = trace.Record()
        self.cpu.r[:] = [0x06001000 + 4*i for i in range(16)]
        self.cpu.r[15] = 0x060FF000
        self.cpu.sr, self.cpu.gbr, self.cpu.vbr = 0x3F3, 0x06001234, 0x06000000
        self.cpu.mach, self.cpu.macl, self.cpu.pr = 0x1234, 0xABCD, 0x06009000
        self.tick = 0
        self.task = trace.TABLE + 32
        self.store(0x06006020, [trace.TABLE])
        self.store(trace.ROOT, [0x11110000 + i for i in range(12)])
        self.store(trace.ROOT + 32, [0x060FE000, 0x06006C00, 0x8888, 0x9999])
        self.store(self.task, [0x22220000 + i for i in range(12)])
        self.store(self.task + 32, [0x060FD000, 0x06008000, 0xAAAA, 0xBBBB])

    def store(self, address, words):
        for i, word in enumerate(words):
            self.dll.fixture_word(address + 4*i, word)

    def step(self, pc, opcode=0x0009, delay=False, raw=False):
        self.tick += 1
        self.cpu.timestamp = self.tick
        self.assertEqual(self.dll.fixture_step(C.byref(self.cpu), pc if raw or delay else pc+4,
                                               opcode | (0x80000000 if delay else 0)), 1,
                         "Observer modified owned CPU or RAM")

    def begin(self, profile=1, pairs=1):
        self.observer.start(profile, pairs, self.witness)
        self.observer.frame(100)

    def entry(self, profile):
        self.step({1: 0x06006BE4, 2: 0x06006C00, 3: 0x06006D36}[profile],
                  {1: 0x2FE6, 2: 0xD084, 3: 0x0022}[profile])

    def fused(self, target, opcode=0xF5000009):
        self.tick += 1
        self.cpu.timestamp = self.tick
        self.assertEqual(self.dll.fixture_fused(C.byref(self.cpu), target, opcode), 1)

    def cycle(self, profile, fused=False):
        self.entry(profile)
        if profile != 2:
            self.step(0x06006BFC if profile == 1 else 0x06006D82, 0x430B)
            if profile == 1 and fused:
                self.fused(0x060061C4)
            else:
                self.step(0x060061C6, 0x0009 if profile == 1 else 0x7420, delay=True)
            self.cpu.r[4] = trace.ROOT if profile == 1 else self.task
            self.cpu.r[15] -= 44 if profile == 1 else 16
            self.cpu.pr = 0x06006C00 if profile == 1 else 0x06006D86
            self.step(0x060061C4, 0x1480)
            context = [self.cpu.r[8], *list(self.cpu.r)[8:16], self.cpu.pr, self.cpu.mach, self.cpu.macl]
            self.store(self.cpu.r[4], context)
            for pc in range(0x060061C6, 0x060061E2, 2):
                self.step(pc)
            self.step(0x060061E2, 0x000B)
            self.step(self.cpu.pr + 2, 0xE000, delay=True)
            self.cpu.r[0] = 0
            self.step(self.cpu.pr)
        self.step(0x06006D90 if profile == 3 else 0x06006D32, 0x430B if profile == 3 else 0x412B)
        if profile == 3 and fused:
            self.fused(0x060061E6)
        else:
            self.step(0x060061E8, 0x0009 if profile == 3 else 0x6EF6, delay=True)
        self.cpu.r[4] = trace.ROOT if profile == 3 else self.task
        self.step(0x060061E6, 0x5841)
        context = list(self.observer.snapshot()[0][-1].context)
        for pc in range(0x060061E8, 0x06006206, 2):
            self.step(pc)
        self.step(0x06006206, 0x000B)
        self.step(context[9] + 2, 0x6053, delay=True)
        self.cpu.r[0], self.cpu.r[4] = self.cpu.r[5], context[0]
        self.cpu.r[8:16] = context[1:9]
        self.cpu.pr, self.cpu.mach, self.cpu.macl = context[9:12]
        self.step(context[9])

    def test_three_profiles_and_semantic_mutations(self):
        for profile in (1, 2, 3):
            with self.subTest(profile=profile):
                self.setUp()
                self.begin(profile)
                self.cycle(profile)
                result = self.observer.finish()
                self.assertEqual(result["completed_cycles"], 1)
                self.assertEqual(self.observer.witness(), self.witness)
                records, status = self.observer.snapshot()
                for field in ("pr", "sr", "mach", "macl", "context_address", "stack_address", "dispatch_steps"):
                    changed = [trace.Record.from_buffer_copy(r) for r in records]
                    setattr(changed[-1], field, getattr(changed[-1], field) ^ 4)
                    with self.subTest(field=field), self.assertRaises(ValueError):
                        trace.validate(changed, status)
                for register in (0, 4, 8, 15):
                    changed = [trace.Record.from_buffer_copy(r) for r in records]
                    changed[-1].r[register] ^= 4
                    with self.subTest(register=register), self.assertRaises(ValueError):
                        trace.validate(changed, status)

    def test_repeated_cycles_bounded_and_no_observer_mutation(self):
        self.begin(2, 16)
        for _ in range(16):
            self.cycle(2)
        self.assertEqual(self.observer.finish()["completed_cycles"], 16)
        self.assertEqual(self.observer.status().count, 48)

    def test_actual_fused_nop_boundary_preserves_cpu_and_ram(self):
        for profile in (1, 3):
            with self.subTest(profile=profile):
                self.setUp()
                self.begin(profile)
                self.cycle(profile, fused=True)
                self.assertEqual(self.observer.finish()["status"]["fused_nops"], 1)

    def test_fused_hook_rejects_other_opcode_without_inventing_a_delay(self):
        self.begin()
        self.entry(1)
        self.fused(0x060061C4, 0x80007420)
        self.assertEqual(self.observer.status().last_error, 2)

    def test_wrong_delay_is_not_normal_pc_entry(self):
        self.begin()
        self.step(0x06006BE8, 0x2FE6, delay=True)
        self.assertEqual(self.observer.status().count, 0)
        self.entry(1)
        self.step(0x06006BFC, 0x430B)
        self.step(0x060061C6, 0x7420, delay=True)
        self.cpu.r[4], self.cpu.pr = trace.ROOT, 0x06006C00
        self.step(0x060061C4, 0x1480)
        self.assertEqual(self.observer.status().last_error, 2)

    def test_missing_frame_jit_buffers_and_incomplete(self):
        self.observer.start(1, 1, self.witness)
        self.entry(1)
        self.assertEqual(self.observer.status().last_error, 1)
        with self.assertRaises(ValueError):
            self.observer.finish()
        self.dll.fixture_reset()
        self.dll.fixture_jit(1)
        with self.assertRaises(ValueError):
            trace.Trace(self.dll).start(1, 1, self.witness)
        status = trace.Status()
        self.assertEqual(self.dll.neptune_context_status(C.byref(status), C.sizeof(status)-4), 0)
        records = (trace.Record * trace.CAPACITY)()
        self.assertEqual(self.dll.neptune_context_records(records, 129), 0xFFFFFFFF)
        self.assertIsNone(self.observer.witness(True))

    def test_source_mismatch_before_entry_retained_then_recovery(self):
        self.begin(2)
        self.store(0x060061C4, [0xDEADBEEF])
        self.entry(2)
        status = self.observer.status()
        self.assertEqual((status.count, status.errors, status.source_mismatch_candidates), (0, 0, 1))
        self.assertEqual(self.observer.witness(True)[:2], [0xDEAD, 0xBEEF])
        self.dll.fixture_source((C.c_uint16 * trace.WITNESS_WORDS)(*self.witness))
        self.cycle(2)
        self.observer.finish()

    def test_source_changed_inflight_is_error(self):
        self.begin(2)
        self.entry(2)
        self.store(0x060061C4, [0xDEADBEEF])
        self.step(0x06006D32, 0x412B)
        self.step(0x060061E8, 0x6EF6, delay=True)
        self.cpu.r[4] = self.task
        self.step(0x060061E6, 0x5841)
        self.assertEqual(self.observer.status().last_error, 6)

    def test_budget_overflow_counter_unknown_pointer_and_interruption(self):
        for failure in ("budget", "overflow", "counter", "address", "interrupt"):
            with self.subTest(failure=failure):
                self.setUp()
                self.begin(2 if failure != "address" else 3)
                if failure == "address":
                    self.store(0x06006020, [0xFFFFFFFF])
                    self.entry(3)
                    self.assertEqual(self.observer.status().last_error, 3)
                    continue
                if failure == "overflow":
                    self.dll.fixture_overflow()
                if failure == "counter":
                    self.dll.fixture_counter()
                self.entry(2)
                if failure == "budget":
                    for _ in range(trace.STEP_LIMIT):
                        self.step(0x06006C02)
                    self.assertEqual(self.observer.status().last_error, 4)
                elif failure == "interrupt":
                    self.step(0, 0xFF000000, raw=True)
                    self.assertEqual(self.observer.status().outside_inspected, 1)
                else:
                    self.assertEqual(self.observer.status().last_error, 5 if failure == "overflow" else 7)
                with self.assertRaises(ValueError):
                    self.observer.finish()

    def test_real_fixture_no_media_probe(self):
        self.assertEqual(trace.probe_library(self.directory / "fixture.so")["record_bytes"], 1996)

    def test_patch_checks_all_source_hashes_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contents = {name: b"owned source\n" for name in preparation.SOURCES}
            contents["mednafen/ss/ss.c"] = b'#include "sh7095.inc"\n'
            contents["mednafen/ss/sh7095.inc"] = b"\n".join(
                b"FORCE_INLINE void " + name + b"(SH7095* z)\n{\n const uint32_t instr = (uint16_t)z->Pipe_ID;\n}"
                for name in (b"SH7095_Step_w0_C0", b"SH7095_Step_w0_C1"))
            contents["link.T"] = b"global: retro_*;\n"
            contents["mednafen/ss/sh7095_ops.inc"] = (
                b" #define FUSE_DELAY_SLOT_NOP() \\\r\n"
                b"   z->PC += 2; \\\r\n"
                b" // Triplet fusion:\r\n")
            for name, data in contents.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            with self.assertRaises(ValueError):
                preparation.prepare(root)
            self.assertFalse((root / "mednafen/ss/neptune_context_trace.h").exists())
            hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
            with patch.object(preparation, "SOURCES", hashes):
                result = preparation.prepare(root)
            self.assertEqual(result["source_witness_words"], 339)
            self.assertEqual((root / "mednafen/ss/sh7095.inc").read_bytes().count(b"neptune_context_step(z);"), 2)
            self.assertEqual((root / "mednafen/ss/sh7095_ops.inc").read_bytes().count(b"if(!which) neptune_context_fused_nop(z);"), 1)
            self.assertNotIn(b"neptune_call_begin", (root / "link.T").read_bytes())
