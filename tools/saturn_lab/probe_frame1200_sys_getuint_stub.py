#!/usr/bin/env python3
"""Execute a captured frame-1200 SYS_GETUINT runtime stub, not game-kernel bytes."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

ENTRY,END=0x0600077C,0x06000784
LITERAL=0x060007A4;TABLE=0x06000900;INDEX=75;TABLE_ENTRY=TABLE+INDEX*4
EXPECTED_TABLE=0x0600083C
STATE_SHA='c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f'
WORKRAM_SHA='3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff'
CORE_SHA='c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e'
STATE_MAX=16*1024*1024;LIMIT=12;MASK=0xffffffff;SEEDS=tuple(range(16))

def sha(data):return hashlib.sha256(data).hexdigest()
def corpus():return list(SEEDS)

def execute(ram,emu,seed,mutation=None):
    if seed not in SEEDS:raise ValueError('captured-stub seed outside declared domain')
    code=bytearray(ram[ENTRY-0x06000000:END-0x06000000])
    lit=int.from_bytes(ram[LITERAL-0x06000000:LITERAL-0x06000000+4],'big')
    table=int.from_bytes(ram[TABLE_ENTRY-0x06000000:TABLE_ENTRY-0x06000000+4],'big')
    if lit!=TABLE:raise ValueError('captured SYS_GETUINT table-base literal differs')
    if table!=EXPECTED_TABLE:raise ValueError('captured SYS_GETUINT index-75 value differs')
    if mutation is not None:
        address,value=mutation
        if address!=TABLE_ENTRY or not 0<=value<=MASK:raise ValueError('unsupported runtime-table mutation')
        table=value
    reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not ENTRY<=address<END:raise ValueError(f'fetch outside captured GETUINT stub: {address:08x}/{n}')
            elif address==LITERAL and n==4:
                reads.append(['literal',address,n,lit]);return lit
            elif address==TABLE_ENTRY and n==4:
                reads.append(['table-entry',address,n,table]);return table
            else:raise ValueError(f'unexpected captured-stub read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            writes.append([address,n,value&MASK]);raise ValueError(f'unexpected captured-stub write {address:08x}/{n}')
    mem=Memory();mem.add(ENTRY,len(code),code)
    class CPU(emu.CPU):
        def __init__(self,m):super().__init__(m);self.executed=[]
        def fetch(self,pc):
            mem.fetching=True
            try:return super().fetch(pc)
            finally:mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'captured GETUINT PC/budget escaped at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem);cpu.r=[(0x51000000+i*0x01020305+seed*0x01010101)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=INDEX;cpu.r[15]=0x06002000
    before=cpu.r.copy();result=cpu.call(ENTRY,max_steps=LIMIT)
    if mutation is None:
        if reads!=[['literal',LITERAL,4,TABLE],['table-entry',TABLE_ENTRY,4,table]]:
            raise ValueError(f'captured SYS_GETUINT read sequence differs: {reads!r}')
        if writes:raise ValueError('captured SYS_GETUINT unexpectedly wrote memory')
        if result!=EXPECTED_TABLE or cpu.r[0]!=EXPECTED_TABLE:raise ValueError('captured SYS_GETUINT return differs')
        if cpu.r[4]!=INDEX*4 or cpu.r[15]!=before[15] or cpu.pr!=emu.RETURN_SENTINEL:
            raise ValueError('captured SYS_GETUINT register/return contract differs')
        for reg in (1,2,3,5,6,7,8,9,10,11,12,13,14):
            if cpu.r[reg]!=before[reg]:raise ValueError(f'captured SYS_GETUINT preserved r{reg} changed')
        if cpu.steps!=4:raise ValueError(f'captured SYS_GETUINT step count differs: {cpu.steps}')
    elif result!=EXPECTED_TABLE:
        raise ValueError(f'captured SYS_GETUINT return differs: {result:08x}')
    return {'seed':seed,'index':INDEX,'table_base':TABLE,'table_entry':TABLE_ENTRY,
        'result':result,'reads':reads,'writes':writes,'steps':cpu.steps,
        'pc_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.frame1200-sys-getuint-stub.v1','status':'failure','execution_class':'captured-runtime-snapshot bytes; not original game-kernel execution'}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                metadata=json.loads(a.checkpoint.read_text())
                identity=metadata.get('identity',{})
                if metadata.get('frame')!=1200 or identity.get('core_sha256')!=CORE_SHA:raise ValueError('frame-1200 checkpoint/core identity differs')
                state=pinned.read_bounded(a.state,STATE_MAX)
                if sha(state)!=STATE_SHA or metadata.get('state_sha256')!=STATE_SHA:raise ValueError('frame-1200 state identity differs')
                parsed=sg.parse(state);raw=sg.field(parsed,'MAIN','WorkRAMH',0x100000)
                ram=sg.cpu_words(raw,'little')
                if sha(ram)!=WORKRAM_SHA:raise ValueError('normalized captured WorkRAM-H identity differs')
                emu=pinned.interpreter(a.saturn_recomp);rows=[]
                for seed in corpus():
                    x=execute(ram,emu,seed);y=execute(ram,emu,seed)
                    if x!=y:raise ValueError('repeated captured SYS_GETUINT execution differs')
                    rows.append(x)
                try:execute(ram,emu,0,(TABLE_ENTRY,0x06000840))
                except ValueError as e:
                    if 'captured sys_getuint return differs' not in str(e).lower():raise
                    rejected=True
                else:raise ValueError('mutated captured system-table entry was accepted')
                report.update(status='success',captured_runtime_bytes_executed=True,original_game_bytes_executed=False,
                    state_sha256=STATE_SHA,core_sha256=CORE_SHA,workram_h_sha256=WORKRAM_SHA,
                    entry=hex(ENTRY),code_range=[hex(ENTRY),hex(END)],code_sha256=sha(ram[ENTRY-0x06000000:END-0x06000000]),
                    literal=hex(LITERAL),table_entry=hex(TABLE_ENTRY),cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),probe_sha256=sha(Path(__file__).read_bytes()),
                    mutation_control={'table_entry':hex(TABLE_ENTRY),'replacement':'0x06000840','rejected':rejected},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='Executed the eight captured runtime bytes at 0600077C; they load table base 06000900, multiply R4=75 by four, and return the captured word at 06000A2C. This is snapshot-derived stub behavior, not proof the PC ran at frame1200 or BIOS provenance/lifetime.')
            except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e:print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
