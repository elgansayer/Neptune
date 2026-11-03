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
import provision_command_trace_abi as abi
import provision as provisioner


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
    def test_separate_recipe_keys_all_command_observer_sources(self):
        root=Path(__file__).resolve().parents[3]
        recipe,inputs,key=provisioner.identity('beetle-saturn-command-trace',root)
        self.assertEqual(recipe['kind'],'beetle-command-trace')
        self.assertEqual(recipe['commit'],p.REVISION)
        self.assertIn('tools/factory/provision_command_trace.h',inputs['installer_sources'])
        self.assertIn('tools/factory/provision_command_trace_abi.py',inputs['installer_sources'])
        self.assertNotEqual(key,provisioner.identity('beetle-saturn-init-trace',root)[2])

    def test_command_abi_layout_and_bounds(self):
        self.assertEqual(abi.WITNESS_WORDS,424)
        self.assertEqual(CAPACITY:=abi.CAPACITY,128)
        self.assertEqual(abi.ROOTS[1],(0x060AE698,0x060A4FAC))
        self.assertEqual(abi.C.sizeof(abi.Record),288)
        self.assertEqual(abi.C.sizeof(abi.Status),100)
        self.assertEqual(len(abi.WITNESS_RANGES),5)

    def test_header_compiles_exports_and_fails_closed_on_bad_arguments(self):
        compiler=shutil.which('cc')
        if not compiler:self.fail('Real C compiler required for command ABI fixture')
        root=Path(__file__).resolve().parents[1]
        header=(root/'provision_command_trace.h').read_text()
        # Compile the production header as a shared object against an owned SH-2 shape.
        prefix='''#include <stdint.h>\n#define INLINE inline\ntypedef struct {uint32_t R[16],PC,Pipe_ID,SR,GBR,VBR,MACH,MACL,PR;int32_t timestamp;} SH7095;\nstatic uint16_t work[0x80000];static uint16_t* WorkRAMH=work;static int setting_sh2_jit=0;\n'''
        source=Path(__import__('tempfile').mkdtemp())/'fixture.c'
        source.write_text(prefix+header+'\nvoid fixture_corrupt(void){WorkRAMH[(0x06095904-0x06000000)>>1]=1;}\n')
        binary=source.with_suffix('.so')
        subprocess.run([compiler,'-std=c11','-shared','-fPIC','-Werror','-x','c',str(source),'-o',str(binary)],check=True,capture_output=True,timeout=30)
        smoke=abi.probe_library(binary)
        self.assertEqual((smoke['abi'],smoke['record_bytes'],smoke['capacity'],smoke['witness_words']),(2,288,128,424))
        dll=abi.C.CDLL(str(binary));trace=abi.Trace(dll)
        self.assertEqual(dll.neptune_command_begin(0,None,abi.WITNESS_WORDS),0)
        zeros=[0]*abi.WITNESS_WORDS
        self.assertEqual(dll.neptune_command_begin(1,None,abi.WITNESS_WORDS),0)
        self.assertEqual(dll.neptune_command_begin(1,(abi.C.c_uint16*abi.WITNESS_WORDS)(),abi.WITNESS_WORDS-1),0)
        trace.start(1,zeros);trace.frame(1200)
        self.assertEqual(trace.witness(),zeros);self.assertEqual(trace.witness('current'),zeros)
        self.assertEqual(trace.witness(True),None)
        with self.assertRaisesRegex(ValueError,'skipped'):
            trace.frame(1202)
        dll.fixture_corrupt()
        with self.assertRaisesRegex(ValueError,'Final command source witness'):
            trace.finish()

    def test_header_accepts_only_a_complete_owned_call_service_transfer_root_trace(self):
        compiler=shutil.which('cc')
        if not compiler:self.fail('Real C compiler required for command semantic fixture')
        header=(Path(__file__).resolve().parents[1]/'provision_command_trace.h').read_text()
        harness=r'''
static SH7095 cpu;
static uint16_t expected[NEPTUNE_COMMAND_WITNESS];
void fixture_run(void) {
 neptune_command_begin(1,expected,NEPTUNE_COMMAND_WITNESS);neptune_command_frame(1200);
 cpu.R[15]=0x06001000;cpu.R[14]=0x06001234;cpu.R[0]=0x060A4FAC;cpu.R[5]=0x06002000;cpu.R[6]=0x06002008;cpu.PR=0x060AE698;
 cpu.PC=0x060AE698;cpu.Pipe_ID=0x0000400B;neptune_command_step(&cpu);
 cpu.PC=0x060A4FAE;cpu.Pipe_ID=0x80006003;neptune_command_step(&cpu);
 cpu.PC=0x060A4FB0;cpu.Pipe_ID=0x00004F22;neptune_command_step(&cpu);
 cpu.PC=0x06095996;cpu.Pipe_ID=0x00006013;neptune_command_step(&cpu);
 cpu.PC=0x060959CE;cpu.Pipe_ID=0x00006013;neptune_command_step(&cpu);
 cpu.PC=0x060959E2;cpu.Pipe_ID=0x00006013;neptune_command_step(&cpu);
 neptune_command_read(&cpu,0x25890008,0x1234);
 cpu.PC=0x06095A86;cpu.Pipe_ID=0x00006013;neptune_command_step(&cpu);
 cpu.PC=0x060959B2;cpu.Pipe_ID=0x00006013;neptune_command_step(&cpu);
 cpu.PC=0x060959CC;cpu.Pipe_ID=0x00006013;neptune_command_step(&cpu);
 cpu.PC=0x060A4FBE;cpu.Pipe_ID=0x0000000B;neptune_command_step(&cpu);
 cpu.PC=0x060A4FBE;cpu.Pipe_ID=0xF5000009;neptune_command_fused_nop(&cpu);
 cpu.PC=0x060AE69C;cpu.Pipe_ID=0x00006013;neptune_command_step(&cpu);
}
'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'semantic.c';binary=Path(d)/'semantic.so'
            prefix='''#include <stdint.h>\n#define INLINE inline\ntypedef struct {uint32_t R[16],PC,Pipe_ID,SR,GBR,VBR,MACH,MACL,PR;int32_t timestamp;} SH7095;\nstatic uint16_t work[0x80000];static uint16_t* WorkRAMH=work;static int setting_sh2_jit=0;\n'''
            source.write_text(prefix+header+harness)
            subprocess.run([compiler,'-std=c11','-shared','-fPIC','-Werror','-x','c',str(source),'-o',str(binary)],check=True,capture_output=True,timeout=30)
            dll=abi.C.CDLL(str(binary));trace=abi.Trace(dll);dll.fixture_run()
            rows,status=trace.snapshot()
            self.assertEqual((status.errors,status.dropped,status.pending,status.completed),(0,0,0,1),[(r.kind,hex(r.pc),hex(r.pr)) for r in rows])
            kinds=[row.kind for row in rows]
            self.assertEqual(kinds[0:3],[8,9,1]);self.assertIn(2,kinds);self.assertEqual(kinds[-1],7)
            self.assertEqual(rows[-1].pc,0x060AE698)
            self.assertTrue(rows[2].command_valid);self.assertFalse(rows[2].response_valid)
            self.assertTrue(any(row.kind==4 and row.response_valid for row in rows))
            witness=(abi.C.c_uint16*abi.WITNESS_WORDS)()
            for i in range(abi.WITNESS_WORDS): witness[i]=0
            # The fixture invokes the production ABI's complete-result validator.
            result=abi.validate(rows,status,list(witness))
            self.assertEqual(result['schema'],'neptune.original-command-trace.v2')

    def test_lossless_repeat_runs_preserve_each_transfer_and_keep_128_slot_guard(self):
        compiler=shutil.which('cc')
        if not compiler:self.fail('Real C compiler required for repeat-run fixture')
        header=(Path(__file__).resolve().parents[1]/'provision_command_trace.h').read_text()
        prefix='''#include <stdint.h>\n#define INLINE inline\ntypedef struct {uint32_t R[16],PC,Pipe_ID,SR,GBR,VBR,MACH,MACL,PR;int32_t timestamp;} SH7095;\nstatic uint16_t work[0x80000];static uint16_t* WorkRAMH=work;static int setting_sh2_jit=0;\n'''
        harness=r'''
static SH7095 cpu;static uint16_t expected[NEPTUNE_COMMAND_WITNESS];
void fixture_runs(NeptuneCommandStatus* status,NeptuneCommandRecord* rows) {
 neptune_command_begin(2,expected,NEPTUNE_COMMAND_WITNESS);neptune_command_frame(1801);
 cpu.R[15]=0x06001000;neptune_command_trace.current_pc=0x060958EC;neptune_command_trace.current_opcode=0x6031;
 for(int i=0;i<40;i++){cpu.R[14]=i;cpu.timestamp=i*33;neptune_command_read(&cpu,0x25890008,0x0BC1);}
 cpu.R[4]=2;cpu.R[14]=40;cpu.timestamp=1320;neptune_command_read(&cpu,0x25890008,0x0BC1);
 cpu.R[14]=42;cpu.timestamp=1386;neptune_command_read(&cpu,0x25890008,0x0BC1);
 cpu.R[14]=44;cpu.timestamp=1452;neptune_command_read(&cpu,0x25890008,0x0BC1);
 neptune_command_stop();neptune_command_status(status,sizeof(*status));neptune_command_records(rows,NEPTUNE_COMMAND_CAPACITY);
}
void fixture_full_guard(NeptuneCommandStatus* status) {
 neptune_command_begin(2,expected,NEPTUNE_COMMAND_WITNESS);neptune_command_frame(1801);
 cpu.R[15]=0x06001000;neptune_command_trace.current_pc=0x060958EC;neptune_command_trace.current_opcode=0x6031;
 for(uint32_t i=0;i<129;i++){cpu.R[0]=i;cpu.timestamp=(int32_t)i;neptune_command_read(&cpu,(i&1)?0x2589000C:0x25890008,0x0BC1);}
 neptune_command_status(status,sizeof(*status));
}
'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'runs.c';binary=Path(d)/'runs.so';source.write_text(prefix+header+harness)
            subprocess.run([compiler,'-std=c11','-shared','-fPIC','-Werror','-x','c',str(source),'-o',str(binary)],check=True,capture_output=True,timeout=30)
            dll=abi.C.CDLL(str(binary));status=abi.Status();rows=(abi.Record*abi.CAPACITY)();dll.fixture_runs(abi.C.byref(status),rows)
            stored=list(rows)[:status.count]
            self.assertEqual((status.abi,status.capacity,status.count,status.logical_records,status.transfer_count),(2,128,2,43,43))
            self.assertEqual([(r.sequence,r.repeat_count,r.timestamp,r.timestamp_step) for r in stored],[(0,40,0,33),(40,3,1320,66)])
            self.assertEqual((stored[0].r_step[14],stored[1].r_step[14]),(1,2))
            expanded=abi.expand_records(stored,status)
            self.assertEqual(len(expanded),43)
            self.assertEqual([(expanded[i].sequence,expanded[i].timestamp) for i in (0,39,40,41,42)],[(0,0),(39,1287),(40,1320),(41,1386),(42,1452)])
            self.assertEqual([expanded[i].r[14] for i in (0,39,40,41,42)],[0,39,40,42,44])
            self.assertEqual(sum(r.repeat_count for r in stored),status.logical_records)
            overflow=abi.Status();dll.fixture_full_guard(abi.C.byref(overflow))
            self.assertEqual((overflow.count,overflow.capacity,overflow.logical_records,overflow.transfer_count,overflow.dropped,overflow.last_error),(128,128,128,129,1,5))

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
