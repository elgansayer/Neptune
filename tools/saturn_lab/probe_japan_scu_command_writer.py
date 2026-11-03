#!/usr/bin/env python3
"""Execute original A6150 and record SCU MMIO write intents without modeling SCU behavior."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x060A6150,0x060A61B0
LIT_D0R,LIT_D0W,LIT_D0C=0x060A61EC,0x060A61F0,0x060A61F4
SCU_D0R,SCU_D0W,SCU_D0C=0x25FE0000,0x25FE0004,0x25FE0008
DESC=0x06004000; DESC_SIZE=40; LIMIT=64; MASK=0xffffffff
FLAGS=(0,1,2,3); CHANNELS=(0,1,3,7); SEEDS=(0,1)

def sha(data): return hashlib.sha256(data).hexdigest()
def corpus(): return [(flags,ch,seed) for flags in FLAGS for ch in CHANNELS for seed in SEEDS]

def execute(data,emu,flags,channel,seed,mutation=None):
    if flags not in FLAGS or channel not in CHANNELS or seed not in SEEDS:
        raise ValueError('SCU descriptor flags/channel/seed outside declared domain')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY: raise ValueError('original A6150 range incomplete')
    literals={LIT_D0R:int.from_bytes(data[LIT_D0R-BASE:LIT_D0R-BASE+4],'big'),
        LIT_D0W:int.from_bytes(data[LIT_D0W-BASE:LIT_D0W-BASE+4],'big'),
        LIT_D0C:int.from_bytes(data[LIT_D0C-BASE:LIT_D0C-BASE+4],'big')}
    if literals!={LIT_D0R:SCU_D0R,LIT_D0W:SCU_D0W,LIT_D0C:SCU_D0C}:
        raise ValueError('original SCU register literal identities differ')
    if mutation:
        address,value=mutation
        if address!=LIT_D0R or not 0<=value<=MASK: raise ValueError('unsupported SCU literal mutation')
        literals[address]=value
    desc=bytearray(((0x31+seed*17+i*37)&255) for i in range(DESC_SIZE))
    words=[(0x10293847+seed*0x11111111+i*0x01020305)&MASK for i in range(10)]
    words[9]=flags
    for i,value in enumerate(words): desc[i*4:i*4+4]=value.to_bytes(4,'big')
    original_desc=bytes(desc); events=[]
    allowed_scu=lambda address,n: n==4 and SCU_D0R<=address<SCU_D0R+0x100
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not ENTRY<=address<END: raise ValueError(f'fetch outside A6150: {address:08x}/{n}')
            elif address in literals and n==4:
                value=literals[address]; events.append(['literal',address,4,value]); return value
            elif DESC<=address and address+n<=DESC+DESC_SIZE and n==4 and (address-DESC)%4==0:
                value=super().read(address,n); events.append(['descriptor',address-DESC,4,value]); return value
            else: raise ValueError(f'unexpected A6150 read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if allowed_scu(address,n):
                events.append(['scu-write-intent',address,n,value&MASK]); return
            raise ValueError(f'unexpected A6150 write {address:08x}/{n}')
    mem=Memory(); mem.add(ENTRY,len(code),code); desc_mem=mem.add(DESC,DESC_SIZE,desc)
    class CPU(emu.CPU):
        def __init__(self,m): super().__init__(m); self.executed=[]
        def fetch(self,pc):
            mem.fetching=True
            try: return super().fetch(pc)
            finally: mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END: raise ValueError(f'A6150 PC/budget escaped at {pc:08x}')
            self.executed.append(pc); return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem); cpu.r=[(0x65000000+i*0x01010101+seed*0x101+channel)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF; cpu.r[4]=DESC; cpu.r[5]=channel; cpu.r[15]=0x06002000; cpu.sr=0x3f0
    before=cpu.r.copy(); cpu.call(ENTRY,max_steps=LIMIT)
    # Caller-visible write intent follows the SCU channel stride and descriptor bit mask.
    stride=channel*32; expected=[]
    expected += [['descriptor',36,4,flags]]
    if flags&1: expected += [['descriptor',0,4,words[0]],['literal',LIT_D0R,4,SCU_D0R],['scu-write-intent',SCU_D0R+stride,4,words[0]]]
    expected += [['descriptor',36,4,flags]]
    if flags&2: expected += [['descriptor',4,4,words[1]],['literal',LIT_D0W,4,SCU_D0W],['scu-write-intent',SCU_D0W+stride,4,words[1]]]
    expected += [['descriptor',8,4,words[2]],['literal',LIT_D0C,4,SCU_D0C],['scu-write-intent',SCU_D0C+stride,4,words[2]]]
    expected += [['descriptor',12,4,words[3]],['descriptor',16,4,words[4]],
        ['scu-write-intent',SCU_D0C+stride+4,4,words[3]|words[4]],
        ['descriptor',24,4,words[6]],['descriptor',20,4,words[5]],['descriptor',28,4,words[7]],['descriptor',32,4,words[8]]]
    tail=(words[6]<<16|words[5]|words[7]<<8|words[8])&MASK
    expected += [['scu-write-intent',SCU_D0C+stride+12,4,tail]]
    if mutation is not None and events!=expected:
        raise ValueError(f'exact descriptor/MMIO intent sequence differs under mutation: {events!r}')
    if mutation is None:
        if events!=expected: raise ValueError(f'exact descriptor/MMIO intent sequence differs: actual={events!r} expected={expected!r}')
        if bytes(desc_mem)!=original_desc: raise ValueError('descriptor was modified')
        if cpu.r[15]!=0x06002000 or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr&0x3fe!=0x3f0: raise ValueError(f'A6150 return state differs: sp={cpu.r[15]:08x} pr={cpu.pr:08x} sr={cpu.sr:08x}')
        for reg in (4,5,8,9,10,11,12,13,14):
            if cpu.r[reg]!=before[reg]: raise ValueError(f'preserved GPR r{reg} changed')
    return {'flags':flags,'channel':channel,'seed':seed,'events':events,'steps':cpu.steps,
        'pc_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed)),
        'descriptor_sha256':sha(bytes(desc_mem))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--kernel',type=Path,required=True); p.add_argument('--saturn-recomp',type=Path,required=True); p.add_argument('--report',type=Path,required=True); a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-scu-command-writer.v1','status':'failure','kernel_sha256':KERNEL,
        'entry':hex(ENTRY),'range':[hex(ENTRY),hex(END)],'mmio_model':'write-intent sink only; no SCU device semantics'}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL: raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp); rows=[]
                for flags,ch,seed in corpus():
                    x=execute(data,emu,flags,ch,seed); y=execute(data,emu,flags,ch,seed)
                    if x!=y: raise ValueError('repeated A6150 execution differs')
                    rows.append(x)
                try: execute(data,emu,1,0,0,(LIT_D0R,0x25FE0080))
                except ValueError as e:
                    if 'exact descriptor/mmio intent sequence differs' not in str(e).lower(): raise
                    rejected=True
                else: raise ValueError('mutated SCU base escaped the exact-write check')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(data[ENTRY-BASE:END-BASE]),
                    source_literals_sha256=sha(b''.join(data[x-BASE:x-BASE+4] for x in (LIT_D0R,LIT_D0W,LIT_D0C))),
                    probe_sha256=sha(Path(__file__).read_bytes()),
                    mutation_control={'literal':hex(LIT_D0R),'replacement':'0x25FE0080','rejected':rejected},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='A6150 reads a 40-byte descriptor and emits exact SCU D0R/D0W/D0C write intents at channel stride 32. MMIO is captured in a rejecting event sink; no SCU side effects or device timing are modeled.')
            except Exception as e: report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e: print(f'FAIL: fresh report path required: {e}'); return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__': raise SystemExit(main())
