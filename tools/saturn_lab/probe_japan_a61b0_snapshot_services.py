#!/usr/bin/env python3
"""Execute Japan A61B0 with frame-1200 service stubs/data and matching BIOS ROM."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

BASE=0x0600A000;SIZE=786432;KERNEL_SHA='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x060A61B0,0x060A6280
STATE_SHA='c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f'
CORE_SHA='c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e'
RAM_SHA='3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff'
BIOS_SHA='dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac'
BIOS_BASE=0x20000000;BIOS_MAP_BASE=0;BIOS_SIZE=524288
WORKRAM_BASE=0x06000000;WORKRAM_SIZE=0x100000
SCU_D0EN=0x25FE0010;GLOBAL_UINT=0x060FCD14;GLOBAL_SINT=0x060FCD20;GLOBAL_FLAGS=0x060FCD2C
SYS_TABLE=0x06000900;SYS_SLOTS={0:0x06000300,1:0x06000304,2:0x06000310,3:0x06000314}
SERVICE={0:(75,0x060A62D8),1:(74,0x060A6348),2:(73,0x060A63B8)}
STACK=0x06008000;LIMIT=256;MAX_STATE=16*1024*1024;MAX_BIOS=524288;MASK=0xffffffff
R4_VALUES=(0,1,2);SEEDS=(0,1)
ALLOWED_STUB_PCS=((0x06000774,0x06000784),(0x06000784,0x06000794),(0x06000794,0x060007A4))
LITERAL_RANGES=((0x060A61E8,0x060A6204),(0x060A62B4,0x060A62D8),(0x060007A4,0x060007B0))

def sha(data):return hashlib.sha256(data).hexdigest()
def corpus():return [(index,seed) for index in R4_VALUES for seed in SEEDS]
def allowed_pc(pc):
    if ENTRY<=pc<END:
        return not any(a<=pc<b for a,b in LITERAL_RANGES[:2])
    return any(a<=pc<b for a,b in ALLOWED_STUB_PCS) and not any(a<=pc<b for a,b in LITERAL_RANGES[2:])

def execute(kernel,ram,bios,emu,index,seed,sr_raw=0x101,mutation=None):
    if index not in R4_VALUES or seed not in SEEDS:raise ValueError('A61B0 index/seed outside declared domain')
    if ram[ENTRY-WORKRAM_BASE:END-WORKRAM_BASE]!=kernel[ENTRY-BASE:END-BASE]:
        raise ValueError('captured A61B0 bytes differ from original Japan kernel')
    work=bytearray(ram);rom=bytearray(bios);events=[]
    selected,handler=SERVICE[index]
    sys_index=SYS_TABLE+selected*4;vbr=0x06000000;vbr_entry=vbr+selected*4
    bios_entry=BIOS_BASE+0x600+selected*4
    initial_get=int.from_bytes(work[sys_index-WORKRAM_BASE:sys_index-WORKRAM_BASE+4],'big')
    initial_sint=int.from_bytes(work[vbr_entry-WORKRAM_BASE:vbr_entry-WORKRAM_BASE+4],'big')
    bios_handler=int.from_bytes(rom[bios_entry-BIOS_BASE:bios_entry-BIOS_BASE+4],'big')
    if mutation is not None:
        address,value=mutation
        if address!=bios_entry or not 0<=value<=MASK:raise ValueError('only selected BIOS vector entry mutation is supported')
        rom[address-BIOS_BASE:address-BIOS_BASE+4]=value.to_bytes(4,'big')
        bios_handler=value
    # Keep all runtime tables/handlers from the same captured frame.
    if int.from_bytes(work[0x06000304-WORKRAM_BASE:0x06000308-WORKRAM_BASE],'big')!=0x0600077C:
        raise ValueError('captured SYS_GETUINT slot differs')
    if int.from_bytes(work[0x06000314-WORKRAM_BASE:0x06000318-WORKRAM_BASE],'big')!=0x06000774:
        raise ValueError('captured SYS_GETSINT slot differs')
    if bios_handler==0:raise ValueError('matching BIOS vector table entry is empty')
    stack_lo=STACK-40;stack_hi=STACK
    def wr(a,n):return WORKRAM_BASE<=a and a+n<=WORKRAM_BASE+WORKRAM_SIZE
    def stack_addr(a,n):return stack_lo<=a and a+n<=stack_hi
    def exact_global(a,n):return (a,n) in ((GLOBAL_UINT+index*4,4),(GLOBAL_SINT+index*4,4),(GLOBAL_FLAGS+index,1))
    def code_fetch_ok(a,n):return n==2 and allowed_pc(a)
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if not code_fetch_ok(address,n):raise ValueError(f'fetch outside A61B0/snapshot-stub composition: {address:08x}/{n}')
            elif wr(address,n):
                value=super().read(address,n);events.append(['workram-read',address,n,value]);return value
            elif BIOS_BASE<=address and address+n<=BIOS_BASE+BIOS_SIZE and n==4:
                value=super().read(address,n);events.append(['bios-read',address,n,value]);return value
            else:raise ValueError(f'unexpected A61B0 composed read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if stack_addr(address,n):
                events.append(['stack-write',address,n,value&MASK]);return super().write(address,n,value)
            if exact_global(address,n) or (address==sys_index and n==4) or (address==vbr_entry and n==4):
                events.append(['workram-write',address,n,value&MASK]);return super().write(address,n,value)
            if n==4 and SCU_D0EN<=address<SCU_D0EN+0x100:
                events.append(['scu-write-intent',address,n,value&MASK]);return
            raise ValueError(f'unexpected A61B0 composed write {address:08x}/{n}')
    mem=Memory();work_mem=mem.add(WORKRAM_BASE,WORKRAM_SIZE,work);bios_mem=mem.add(BIOS_MAP_BASE,BIOS_SIZE,rom)
    class CPU(emu.CPU):
        def __init__(self,m):super().__init__(m);self.executed=[]
        def fetch(self,pc):
            mem.fetching=True
            try:return super().fetch(pc)
            finally:mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not allowed_pc(pc):raise ValueError(f'A61B0 service PC/budget escaped at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem);cpu.vbr=vbr;cpu.r=[(0x3B000000+i*0x01020305+seed*0x10001)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=index;cpu.r[15]=STACK;cpu.sr=sr_raw
    before=cpu.r.copy();result=cpu.call(ENTRY,max_steps=LIMIT)
    if result!=cpu.r[0]:raise ValueError('A61B0 final call-result field differs')
    expected_entry=initial_get
    actual_global_uint=int.from_bytes(work_mem[GLOBAL_UINT+index*4-WORKRAM_BASE:GLOBAL_UINT+index*4-WORKRAM_BASE+4],'big')
    actual_global_sint=int.from_bytes(work_mem[GLOBAL_SINT+index*4-WORKRAM_BASE:GLOBAL_SINT+index*4-WORKRAM_BASE+4],'big')
    actual_flag=work_mem[GLOBAL_FLAGS+index-WORKRAM_BASE]
    actual_sys=int.from_bytes(work_mem[sys_index-WORKRAM_BASE:sys_index-WORKRAM_BASE+4],'big')
    actual_vbr=int.from_bytes(work_mem[vbr_entry-WORKRAM_BASE:vbr_entry-WORKRAM_BASE+4],'big')
    expected_events=[['scu-write-intent',SCU_D0EN+index*32,4,0x101]]
    actual_scu=[e for e in events if e[0]=='scu-write-intent']
    if actual_scu!=expected_events:raise ValueError(f'A61B0 D0EN intent differs: {actual_scu!r}')
    if actual_global_uint!=expected_entry or actual_global_sint!=initial_sint or actual_flag!=1:
        raise ValueError('A61B0 global status publication differs')
    if actual_sys!=handler or actual_vbr!=bios_handler:
        raise ValueError(f'A61B0 system/vector table update differs: sys={actual_sys:08x}/{handler:08x} vbr={actual_vbr:08x}/{bios_handler:08x} index={index} service={selected} events={events!r}')
    if cpu.r[15]!=STACK or cpu.pr!=emu.RETURN_SENTINEL:raise ValueError('A61B0 final SP/PR differs')
    if (cpu.sr&~1)!=(sr_raw&0x3f2):raise ValueError(f'A61B0 non-T SR fields were not restored under pinned SH-2 mask: {cpu.sr:08x}')
    for reg in (8,9,10,11,12,13,14):
        if cpu.r[reg]!=before[reg]:raise ValueError(f'A61B0 preserved GPR r{reg} changed')
    if mutation is not None and actual_vbr!=bios_handler:
        raise ValueError('mutated BIOS vector entry escaped A61B0 final vector check')
    return {'index':index,'seed':seed,'selected_service':selected,'handler':handler,
        'initial_getuint_value':initial_get,'initial_vector_value':initial_sint,'bios_default_handler':bios_handler,
        'final_sys_table_word':actual_sys,'final_vbr_word':actual_vbr,'global_uint_value':actual_global_uint,
        'global_sint_value':actual_global_sint,'global_flag':actual_flag,'scu_write_intents':actual_scu,
        'events':events,'event_sha256':sha(json.dumps(events,separators=(',',':')).encode()),'steps':cpu.steps,
        'pcs_sha256':sha(b''.join(x.to_bytes(4,'big') for x in cpu.executed)),
        'workram_sha256':sha(bytes(work_mem)),'bios_sha256':sha(bytes(bios_mem))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--bios',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-a61b0-snapshot-services.v1','status':'failure','kernel_sha256':KERNEL_SHA,
        'state_sha256':STATE_SHA,'bios_sha256':BIOS_SHA,'entry':hex(ENTRY),'range':[hex(ENTRY),hex(END)],
        'limits':['Original Japan A61B0 bytes plus frame1200 captured runtime stubs/data and matching BIOS ROM table','SCU write captured as intent only; no device effects or natural caller/runtime-PC proof']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                meta=json.loads(a.checkpoint.read_text());ident=meta.get('identity',{})
                if meta.get('frame')!=1200 or ident.get('core_sha256')!=CORE_SHA or meta.get('state_sha256')!=STATE_SHA:
                    raise ValueError('frame1200 state/checkpoint identity differs')
                kernel=pinned.read_bounded(a.kernel,SIZE);state=pinned.read_bounded(a.state,MAX_STATE);bios=pinned.read_bounded(a.bios,MAX_BIOS)
                if len(kernel)!=SIZE or sha(kernel)!=KERNEL_SHA:raise ValueError('Japan kernel identity mismatch')
                if sha(state)!=STATE_SHA:raise ValueError('frame1200 state hash mismatch')
                if len(bios)!=BIOS_SIZE or sha(bios)!=BIOS_SHA:raise ValueError('BIOS 1.01 Japan identity mismatch')
                parsed=sg.parse(state);raw=sg.field(parsed,'MAIN','WorkRAMH',WORKRAM_SIZE);ram=sg.cpu_words(raw,'little')
                if sha(ram)!=RAM_SHA:raise ValueError('normalized frame1200 WorkRAM-H identity mismatch')
                ctrl=sg.field(parsed,'SH2-M','CtrlRegs',12)
                snapshot_sr=int.from_bytes(ctrl[:4],'little');snapshot_vbr=int.from_bytes(ctrl[8:12],'little')
                if snapshot_vbr!=0x06000000:raise ValueError('frame1200 VBR differs from WorkRAM-H base')
                emu=pinned.interpreter(a.saturn_recomp);rows=[]
                for index,seed in corpus():
                    one=execute(kernel,ram,bios,emu,index,seed,sr_raw=snapshot_sr);two=execute(kernel,ram,bios,emu,index,seed,sr_raw=snapshot_sr)
                    if one!=two:raise ValueError('repeated A61B0 snapshot-service execution differs')
                    rows.append(one)
                mutation_controls=[]
                for index in R4_VALUES:
                    selected,_=SERVICE[index];address=BIOS_BASE+0x600+selected*4
                    baseline=execute(kernel,ram,bios,emu,index,0,sr_raw=snapshot_sr)
                    original=int.from_bytes(bios[address-BIOS_BASE:address-BIOS_BASE+4],'big')
                    altered=original^1
                    control=execute(kernel,ram,bios,emu,index,0,sr_raw=snapshot_sr,mutation=(address,altered))
                    if control['final_vbr_word']!=altered or control['final_vbr_word']==baseline['final_vbr_word']:
                        raise ValueError('selected BIOS-vector mutation was not reflected in final VBR write')
                    mutation_controls.append({'index':index,'address':hex(address),'original':hex(original),'mutated':hex(altered),'observed_final_vbr':hex(control['final_vbr_word'])})
                report.update(status='success',original_game_bytes_executed=True,snapshot_runtime_bytes_executed=True,
                    cases=len(rows),executions_per_case=2,results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=mutation_controls,
                    normalized_workram_sha256=RAM_SHA,snapshot_sr=hex(snapshot_sr),snapshot_vbr=hex(snapshot_vbr),
                    source_code_sha256=sha(kernel[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='A61B0 executes with frame1200 snapshot service stubs/tables and matching BIOS 1.01 Japan vector table. Per index 0..2 it GETs and updates system/VBR tables, publishes globals, emits D0EN=0x101 intent, restores SR and returns. Snapshot data and synthetic ABI do not prove natural runtime execution.')
            except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e:print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
