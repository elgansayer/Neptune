"""Compile/read owned CPU states. No game or BIOS instructions execute here."""
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
import provision_init_trace_abi as trace
import provision_init_trace as preparation

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
#include "neptune_init_trace.h"
void fixture_reset(void) {
 memset(&neptune_init_trace,0,sizeof(neptune_init_trace));memset(ram,0,sizeof(ram));
 setting_sh2_jit=0;WorkRAMH=ram;
}
void fixture_word(uint32_t address,uint32_t value) {
 uint32_t i=(address-0x06000000)>>1;ram[i]=(uint16_t)(value>>16);ram[i+1]=(uint16_t)value;
}
void fixture_source(const uint16_t* words) {
 uint32_t starts[5]={0x623A,0x89AC,0x8BF0,0x95B04,0xA6790},counts[5]={3,95,32,2296,146},n=0;
 for(uint32_t b=0;b<5;b++) for(uint32_t i=0;i<counts[b];i++) ram[(starts[b]>>1)+i]=words[n++];
}
void fixture_set(uint32_t kind,uint32_t value) {
 switch(kind) {
 case 1:setting_sh2_jit=value;break;
 case 2:neptune_init_trace.count=value;break;
 case 3:neptune_init_trace.master_dispatches=value;break;
 case 4:neptune_init_trace.steps=value;break;
 case 5:neptune_init_trace.depth=value;break;
 case 6:WorkRAMH=value?ram:0;break;
 }
}
uint32_t fixture_step(const NeptuneInitRecord* in,uint32_t pc,uint32_t pipe,uint32_t fused) {
 SH7095 z,before;memset(&z,0,sizeof(z));memcpy(z.R,in->r,sizeof(z.R));z.PC=pc;z.Pipe_ID=pipe;
 z.SR=in->sr;z.GBR=in->gbr;z.VBR=in->vbr;z.MACH=in->mach;z.MACL=in->macl;z.PR=in->pr;z.timestamp=in->timestamp;
 memcpy(&before,&z,sizeof(z));memcpy(before_ram,ram,sizeof(ram));
 if(fused) neptune_init_fused_nop(&z);else neptune_init_step(&z);
 return !memcmp(&z,&before,sizeof(z)) && !memcmp(ram,before_ram,sizeof(ram));
}
'''
OPCODES = {0x060089C8: 0x2FE6, 0x06095B04: 0x2FE6, 0x060089AC: 0x0009,
           0x060089F8: 0xBFD8, 0x060089FA: 0x0009, 0x060089FC: 0x0009,
           0x06008A14: 0x420B, 0x06008A16: 0xE410, 0x06008A18: 0x0009,
           0x06095B5A: 0x430B, 0x06095B5C: 0xE500, 0x06095B5E: 0x0009,
           0x06095B76: 0x420B, 0x06095B78: 0x0009, 0x06095B7A: 0x0009, 0x060A6790: 0x2FE6,
           0x06095B96: 0x422B, 0x06095B98: 0x6EF6, 0x06096C60: 0x2FE6,
           0x06008A66: 0x000B, 0x06008A68: 0x6EF6, 0x06095BCA: 0x000B,
           0x06095BCC: 0x6EF6, 0x06096CAC: 0x000B, 0x06096CAE: 0x6EF6}


@unittest.skipUnless(shutil.which('cc'), 'C compiler required for owned native fixture')
class InitTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.directory = Path(cls.temp.name)
        shutil.copy2(ROOT/'provision_init_trace.h', cls.directory/'neptune_init_trace.h')
        (cls.directory/'fixture.c').write_text(FIXTURE)
        subprocess.run(['cc', '-std=c11', '-shared', '-fPIC', '-O2', '-Wall', '-Werror', 'fixture.c', '-o', 'fixture.so'],
                       cwd=cls.directory, check=True, capture_output=True)
        cls.dll = C.CDLL(str(cls.directory/'fixture.so'))
        cls.dll.fixture_source.argtypes = [C.POINTER(C.c_uint16)]
        cls.dll.fixture_step.argtypes = [C.POINTER(trace.Record), C.c_uint32, C.c_uint32, C.c_uint32]
        cls.dll.fixture_step.restype = C.c_uint32

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.dll.fixture_reset(); self.cpu = trace.Record(); self.tick = 0
        self.cpu.r[:] = [0x12340000+i*0x101 for i in range(16)]; self.cpu.r[15] = 0x060FF000
        self.cpu.sr, self.cpu.mach, self.cpu.macl = 0x3F3, 0x13579BDF, 0x2468ACE0
        self.cpu.gbr, self.cpu.vbr = 0x00200000, 0x06000000
        self.witness = [OPCODES.get(start+2*i, (0x5000+i) & 0xFFFF)
                        for start, count in trace.WITNESS_RANGES for i in range(count)]
        self.dll.fixture_source((C.c_uint16*trace.WITNESS_WORDS)(*self.witness))
        self.observer = trace.Trace(self.dll)
        self.sp, self.r14 = self.cpu.r[15], self.cpu.r[14]

    def step(self, pc, opcode=None, delay=False, fused=False):
        self.tick += 1; self.cpu.timestamp = self.tick
        if opcode is None: opcode = OPCODES.get(pc, 0x0009)
        pipe = opcode | (0xF5000000 if fused else 0x80000000 if delay else 0)
        raw_pc = pc if delay or fused else pc+4
        self.assertEqual(self.dll.fixture_step(C.byref(self.cpu), raw_pc, pipe, int(fused)), 1,
                         'Observer wrote owned CPU or RAM')

    def begin(self, profile=2):
        self.profile = profile; self.cpu.pr = trace.ROOTS[profile][1]
        self.observer.start(profile, 1, self.witness); self.observer.frame(100)
        self.step(trace.ROOTS[profile][0])
        self.cpu.r[15] -= 12 if profile == 1 else 16

    def call(self, pc, destination, fused=False):
        opcode = OPCODES[pc]; sp = self.cpu.r[15]
        if opcode >> 12 != 0xB: self.cpu.r[(opcode >> 8) & 15] = destination
        self.step(pc); self.cpu.pr = pc+4
        self.step(destination if fused else destination+2, OPCODES[pc+2], delay=not fused, fused=fused)
        self.step(destination)
        return sp

    def returned(self, pc, sp):
        self.cpu.r[15] = sp; self.cpu.pr = pc; self.step(pc)

    def finish_root(self, rts=None):
        rts = rts or (0x06008A66 if self.profile == 1 else 0x06095BCA)
        self.cpu.r[15] = self.sp-4; self.cpu.pr = trace.ROOTS[self.profile][1]
        self.dll.fixture_word(self.sp-4, self.r14)
        self.step(rts); self.step(self.cpu.pr+2, 0x6EF6, delay=True)
        self.cpu.r[15] += 4; self.cpu.r[14] = self.r14; self.step(self.cpu.pr)
        return self.observer.finish()

    def test_both_roots_with_real_observer_state_machine_and_nonmutation(self):
        for profile in (1, 2):
            with self.subTest(profile=profile):
                self.setUp(); self.begin(profile)
                result = self.finish_root()
                self.assertEqual([r['kind'] for r in result['records']], [1, 8, 9, 10])
                self.assertEqual(result['completed_roots'], 1)
                self.assertIsNone(result['records'][0]['library'])
                self.assertEqual(self.observer.witness(), self.witness)

    def test_nested_named_calls_and_actual_fused_nop_hook(self):
        self.begin(1)
        sp = self.call(0x060089F8, 0x060089AC, fused=True); self.returned(0x060089FC, sp)
        outer = self.call(0x06008A14, 0x06095B04)
        self.cpu.r[15] -= 16
        inner = self.call(0x06095B5A, 0x06001000); self.returned(0x06095B5E, inner)
        inner = self.call(0x06095B76, 0x060A6790, fused=True); self.returned(0x06095B7A, inner)
        self.returned(0x06008A18, outer)
        result = self.finish_root()
        self.assertEqual(result['status']['fused_nops'], 2)
        self.assertEqual(sum(row['kind'] == 2 for row in result['records']), 4)
        self.assertEqual(max(row['depth'] for row in result['records']), 2)

    def test_actual_tail_transfer_restores_stack_then_returns_from_original_status_handler(self):
        self.begin(2); self.cpu.r[15] = self.sp-4; self.cpu.pr = trace.ROOTS[2][1]
        self.cpu.r[2] = 0x06096C60; self.step(0x06095B96)
        self.step(0x06096C62, 0x6EF6, delay=True); self.cpu.r[15] += 4
        self.step(0x06096C60)
        result = self.finish_root(0x06096CAC)
        self.assertEqual([r['kind'] for r in result['records']], [1, 6, 3, 7, 8, 9, 10])
        self.assertEqual(result['records'][1]['return_pc'], 0x06008A18)

    def test_library_tail_within_parent_returns_to_its_own_caller_then_full_parent(self):
        self.begin(1); outer = self.call(0x06008A14, 0x06095B04)
        self.cpu.r[15] = outer-4; self.cpu.pr = 0x06008A18; self.cpu.r[2] = 0x06096C60
        self.step(0x06095B96); self.step(0x06096C62, 0x6EF6, delay=True)
        self.cpu.r[15] += 4; self.step(0x06096C60)
        self.returned(0x06008A18, outer)
        result = self.finish_root()
        tail = next(row for row in result['records'] if row['kind'] == 6)
        self.assertEqual(tail['return_pc'], 0x06008A18)
        self.assertNotEqual(tail['return_pc'], result['records'][-1]['pc'])

    def test_direct_ram_snapshots_include_only_valid_tagged_library_data(self):
        block = 0x060D0000
        self.dll.fixture_word(0x060FA8BC, block)
        self.dll.fixture_word(block+0xC4, 0xFEEDBEEF)
        self.dll.fixture_word(block+0x438, 0x12345678)
        self.dll.fixture_word(block+0xC60+23*0xA8, 0x87654321)
        self.begin(); result = self.finish_root()
        first = result['records'][0]
        self.assertEqual(first['library'][0xC4//4], 0xFEEDBEEF)
        self.assertEqual(first['tables'][0], 0x12345678)
        self.assertEqual(first['slots'][23], 0x87654321)

    def test_semantic_record_mutations_cannot_pass_as_root_or_call_evidence(self):
        self.begin(); sp = self.call(0x06095B76, 0x060A6790, fused=True); self.returned(0x06095B7A, sp)
        self.finish_root(); records, status = self.observer.snapshot()
        for index, field in ((0, 'pr'), (1, 'target'), (2, 'opcode'), (3, 'pr'), (4, 'depth'),
                             (-3, 'pc'), (-2, 'opcode'), (-1, 'steps'), (-1, 'stack_address')):
            changed = [trace.Record.from_buffer_copy(row) for row in records]
            setattr(changed[index], field, getattr(changed[index], field)^4)
            with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                trace.validate(changed, status, self.witness)
        for index, register in ((3, 15), (-1, 14), (-1, 15)):
            changed = [trace.Record.from_buffer_copy(row) for row in records]; changed[index].r[register] ^= 4
            with self.assertRaises(ValueError): trace.validate(changed, status, self.witness)

    def test_missing_delay_wrong_link_and_source_change_fail_closed(self):
        for failure in ('delay', 'link', 'source'):
            self.setUp(); self.begin(); self.cpu.r[2] = 0x060A6790; self.step(0x06095B76)
            if failure != 'delay':
                self.cpu.pr = 0x06095B7A; self.step(0x060A6792, 0x0009, delay=True)
            if failure == 'link': self.cpu.pr ^= 4
            if failure == 'source': self.dll.fixture_word(0x06095B04, 0)
            self.step(0x060A6790)
            self.assertGreater(self.observer.status().errors, 0)
            with self.assertRaises(ValueError): self.observer.finish()

    def test_source_mismatch_recovery_and_fused_hook_rejection_are_retained(self):
        self.dll.fixture_word(0x06095B04, 0)
        self.observer.start(2, 1, self.witness); self.observer.frame(100); self.cpu.pr = 0x06008A18
        self.step(0x06095B04)
        self.assertEqual(self.observer.status().source_mismatch_candidates, 1)
        self.assertIsNotNone(self.observer.witness(True))
        self.dll.fixture_source((C.c_uint16*trace.WITNESS_WORDS)(*self.witness)); self.step(0x06095B04)
        self.assertEqual(self.observer.status().pending, 1)
        self.step(0x060A6790, 0x0009, fused=True)
        self.assertEqual(self.observer.status().errors, 0)
        self.cpu.timestamp += 1
        self.assertEqual(self.dll.fixture_step(C.byref(self.cpu), 0x060A6790, 0x80000009, 1), 1)
        self.assertEqual(self.observer.status().last_error, 2)

    def test_budget_depth_overflow_counter_frame_and_empty_failures(self):
        for kind, value, error in ((2, trace.CAPACITY, 5), (3, 0xFFFFFFFF, 7),
                                   (4, trace.STEP_LIMIT, 4), (5, trace.DEPTH, 8)):
            self.setUp(); self.begin(); self.dll.fixture_set(kind, value)
            self.cpu.r[2] = 0x060A6790; self.step(0x06095B76)
            self.assertEqual(self.observer.status().last_error, error)
            with self.assertRaises(ValueError): self.observer.finish()
        self.setUp(); self.begin()
        for frame in range(101, 220): self.observer.frame(frame)
        with self.assertRaises(ValueError): self.observer.frame(220)
        self.setUp(); self.observer.start(1, 1, self.witness); self.step(0x060089C8)
        self.assertEqual(self.observer.status().last_error, 1)

    def test_invalid_abi_arguments_jit_and_native_no_media_smoke(self):
        self.assertEqual(trace.probe_library(self.directory/'fixture.so')['abi'], 1)
        self.setUp(); self.dll.fixture_set(1, 1)
        with self.assertRaises(ValueError): self.observer.start(1, 1, self.witness)
        self.assertEqual(self.dll.neptune_init_status(C.byref(trace.Status()), C.sizeof(trace.Status())-4), 0)
        for profile, roots, words in ((3, 1, self.witness), (1, 2, self.witness), (1, 1, self.witness[:-1])):
            with self.assertRaises(ValueError): self.observer.start(profile, roots, words)

    def test_invalid_library_pointer_is_tagged_unavailable_and_fabricated_values_are_rejected(self):
        for address in (0x00200000, 0x060FFFFC, 0x060D0001):
            self.setUp(); self.dll.fixture_word(0x060FA8BC, address)
            self.begin(); result = self.finish_root()
            self.assertEqual(result['records'][0]['library_address'], address)
            self.assertIsNone(result['records'][0]['library'])
            rows, status = self.observer.snapshot(); rows[0].library[0] = 1
            with self.assertRaises(ValueError): trace.validate(rows, status, self.witness)


class PreparationTests(unittest.TestCase):
    def fixture(self, root):
        contents = {name: b'owned source' for name in preparation.SOURCES}
        contents['mednafen/ss/ss.c'] = b'#include "sh7095.inc"\n'
        contents['mednafen/ss/sh7095.inc'] = b'\n'.join(
            b'FORCE_INLINE void '+name+b'(SH7095* z)\n{\n const uint32_t instr = (uint16_t)z->Pipe_ID;\n}'
            for name in (b'SH7095_Step_w0_C0', b'SH7095_Step_w0_C1'))
        contents['link.T'] = b'global: retro_*;\n'
        contents['mednafen/ss/sh7095_ops.inc'] = b' #define FUSE_DELAY_SLOT_NOP() \\\r\n   z->PC += 2; \\\r\n // Triplet fusion:\r\n'
        for name, data in contents.items():
            path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        return contents

    def test_actual_patcher_fences_source_and_preserves_other_observer_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); contents = self.fixture(root)
            with self.assertRaises(ValueError): preparation.prepare(root)
            self.assertTrue(all((root/name).read_bytes() == data for name, data in contents.items()))
            hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
            with patch.object(preparation, 'SOURCES', hashes): result = preparation.prepare(root)
            self.assertEqual(result['observer_abi'], 1)
            self.assertEqual(result['source_witness_words'], trace.WITNESS_WORDS)
            self.assertEqual((root/'mednafen/ss/sh7095.inc').read_bytes().count(b'neptune_init_step(z);'), 2)
            self.assertEqual((root/'mednafen/ss/sh7095_ops.inc').read_bytes().count(b'if(!which) neptune_init_fused_nop(z);'), 1)
            self.assertNotIn(b'neptune_context_', (root/'link.T').read_bytes())
            self.assertNotIn(b'neptune_call_', (root/'link.T').read_bytes())
            self.assertIn(b'GPL-2.0-or-later', (root/'mednafen/ss/neptune_init_trace.h').read_bytes())

    def test_duplicate_master_anchor_fails_before_any_source_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); contents = self.fixture(root)
            name = 'mednafen/ss/sh7095.inc'; contents[name] *= 2; (root/name).write_bytes(contents[name])
            hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
            with patch.object(preparation, 'SOURCES', hashes), self.assertRaisesRegex(ValueError, 'dispatch'):
                preparation.prepare(root)
            self.assertTrue(all((root/name).read_bytes() == data for name, data in contents.items()))
            self.assertFalse((root/'mednafen/ss/neptune_init_trace.h').exists())


if __name__ == '__main__': unittest.main()
