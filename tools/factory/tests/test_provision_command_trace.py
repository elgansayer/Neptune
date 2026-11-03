"""Owned patch/fusion/transfer fixtures; no emulator or original-game execution."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import provision_command_trace as p


OPS=(b'#if 1\r\n #define FUSE_DELAY_SLOT_NOP() \\\r\n   z->PC += 2;\r\n'
     b' // Triplet fusion:\r\n #define KEEP_TRIPLET(x) (x)\r\n #else\r\n #define KEEP_TRIPLET(x) (x)\r\n #endif\r\n'+p.READ16+b'\r\n'
     b' BEGIN_OP(MOV_W_REG_REGINDIR)\r\n const uint32_t ea=8, val=z->R[1];\r\n MemWrite16(ea, val);\r\n END_OP\r\n')


def fixture(root):
    contents={name:b'owned source\n' for name in p.SOURCES}
    contents['mednafen/ss/ss.c']=b'#include "sh7095.inc"\n'
    contents['mednafen/ss/sh7095.inc']=b''.join(b'FORCE_INLINE void '+n+b'(SH7095* z)\n{\n const uint32_t instr = (uint16_t)z->Pipe_ID;\n}\n'
        for n in (b'SH7095_Step_w0_C0',b'SH7095_Step_w0_C1'))
    contents['mednafen/ss/sh7095_ops.inc']=OPS
    contents['link.T']=b'{ global: retro_*; local: *; };\n'
    for name,data in contents.items():
        q=root/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data)
    return contents


class CommandObserverPatch(unittest.TestCase):
    def test_patch_component_preserves_fusion_and_has_distinct_exports(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);contents=fixture(root);header=root/'owned.h';header.write_bytes(b'/* owned fixture only */\n')
            hashes={n:p.digest(v) for n,v in contents.items()}
            with patch.object(p,'SOURCES',hashes):report=p.prepare(root,header)
            self.assertFalse(report['native_tool_ready']);self.assertFalse(report['original_game_bytes_executed'])
            self.assertEqual((root/'mednafen/ss/neptune_command_trace.h').read_bytes(),header.read_bytes())
            self.assertEqual((root/'mednafen/ss/sh7095.inc').read_bytes().count(b'neptune_command_step(z);'),2)
            actual=(root/'mednafen/ss/sh7095_ops.inc').read_bytes()
            self.assertEqual(actual,p.observed_ops(OPS));self.assertIn(b'#define KEEP_TRIPLET(x) (x)',actual)
            self.assertEqual(actual.count(b'neptune_command_read(z,'),1);self.assertEqual(actual.count(b'neptune_command_write(z,'),1)
            exports=(root/'link.T').read_bytes();self.assertIn(b'neptune_command_records;',exports);self.assertNotIn(b'neptune_init_',exports)
            for n in ('Makefile','mednafen/ss/sh7095.h'):self.assertEqual((root/n).read_bytes(),contents[n])

    def test_wrong_source_fails_before_any_file_is_modified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);contents=fixture(root);header=root/'owned.h';header.write_bytes(b'owned')
            hashes={n:p.digest(v) for n,v in contents.items()};hashes['Makefile']='0'*64
            with patch.object(p,'SOURCES',hashes),self.assertRaisesRegex(ValueError,'differs'):p.prepare(root,header)
            for n,b in contents.items():self.assertEqual((root/n).read_bytes(),b)
            self.assertFalse((root/'mednafen/ss/neptune_command_trace.h').exists())

    def test_ambiguous_transfer_or_fusion_anchors_fail(self):
        for raw in (OPS.replace(p.READ16,b''),OPS+p.READ16,OPS.replace(b'MemWrite16(ea, val);',b''),OPS.replace(b'   z->PC += 2;',b'')):
            with self.assertRaises(ValueError):p.observed_ops(raw)

    def test_existing_destination_and_symlinked_header_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);contents=fixture(root);header=root/'owned.h';header.write_bytes(b'owned');link=root/'link.h';link.symlink_to(header)
            with patch.object(p,'SOURCES',{n:p.digest(v) for n,v in contents.items()}):
                with self.assertRaises(ValueError):p.prepare(root,link)
                dest=root/'mednafen/ss/neptune_command_trace.h';dest.write_bytes(b'existing')
                with self.assertRaisesRegex(ValueError,'fresh'):p.prepare(root,header)
                self.assertEqual(dest.read_bytes(),b'existing')

    def test_compiled_transfers_evaluate_address_once_and_keep_cpu_ram_and_bus_counts(self):
        compiler=shutil.which('cc')
        if not compiler:self.fail('Real C compiler required for transfer nonmutation fixture')
        prefix=r'''
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
typedef struct { uint32_t R[2],PC,WB_until[2],MA_until; } CPU;
static uint16_t ram[16];static unsigned reads,writes,evals,hook_reads,hook_writes;
static uint32_t hook_addr,hook_value,hook_reg;
static void read16(uint32_t a,uint16_t* v) { reads++;*v=ram[a/2]; }
static void write16(uint32_t a,uint32_t v) { writes++;ram[a/2]=(uint16_t)v; }
static void neptune_command_read(const CPU* z,uint32_t a,uint16_t v) { assert(a==4 && v==0xff80 && z->R[0]==0xffffff80);hook_reads++;hook_addr=a;hook_value=v;hook_reg=z->R[0]; }
static void neptune_command_write(const CPU* z,uint32_t a,uint16_t v) { hook_writes++;hook_addr=a;hook_value=v;hook_reg=z->R[0]; }
static void neptune_command_fused_nop(const CPU* z) { (void)z; }
#define MemRead16(a,v) read16((a),&(v))
#define MemWrite16(a,v) write16((a),(v))
#define WB_WRITE(r,v) { z->R[(r)]=(v); z->WB_until[(r)]=z->MA_until+1; }
#define BEGIN_OP(n) static void store(CPU* z,int which) {
#define END_OP }
'''
        suffix=r'''
static void load(CPU* z,int which) { WB_READ16(0,(evals++,z->R[0])); }
int main(void) {
 for(int which=0;which<2;which++) {
  CPU cpu={{4,0x12345678},99,{5,6},40};ram[2]=0xff80;ram[4]=0x1111;
  reads=writes=evals=hook_reads=hook_writes=0;hook_addr=hook_value=hook_reg=0;
  load(&cpu,which);store(&cpu,which);
  printf("%u %u %u %u %u %u %u %u %u %u %u %u %u %u %u\n",cpu.R[0],cpu.R[1],cpu.PC,cpu.WB_until[0],cpu.WB_until[1],cpu.MA_until,ram[2],ram[4],reads,writes,evals,hook_reads,hook_writes,hook_value,hook_reg);
 }return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            results=[]
            for n,ops in enumerate((OPS,p.observed_ops(OPS))):
                source=Path(d)/('fixture'+str(n)+'.c');binary=Path(d)/('fixture'+str(n));source.write_bytes(prefix.encode()+ops+suffix.encode())
                subprocess.run([compiler,'-std=c11','-Werror',str(source),'-o',str(binary)],check=True,capture_output=True,timeout=30)
                r=subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=5)
                results.append([[int(x) for x in line.split()] for line in r.stdout.splitlines()])
            self.assertEqual(len(results[0]),2)
            for baseline,observed in zip(*results):
                self.assertEqual(observed[:11],baseline[:11]);self.assertEqual(observed[8:11],[1,1,1])
                self.assertEqual(observed[0],0xFFFFFF80);self.assertEqual(observed[7],0x5678)
            self.assertEqual(results[1][0][11:],[1,1,0x5678,0xFFFFFF80])
            self.assertEqual(results[1][1][11:],[0,0,0,0])


if __name__=='__main__':unittest.main()
