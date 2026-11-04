#!/usr/bin/env python3
"""Original A81FE field store, A7C20 query and A7BB0 request-state paths.

The actual A85E4 service entry is a non-executable pending boundary.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_task_init as task

pinned,records,guard=task.pinned,task.records,task.short
MASK=0xFFFFFFFF
CELL=0x060FC084
STORE,POLL,REQUEST,TARGET=0x060A81FE,0x060A7C20,0x060A7BB0,0x060A85E4
FAMILIES=('store','poll','request')
LITERALS={0x060A8388:CELL,0x060A7CFC:CELL,0x060A7BEC:CELL}
HALFWORDS={0x060A7CF6:0x338,0x060A7CF8:0x33C,0x060A7BDC:0x338}


class EvidenceFailure(ValueError):
    def __init__(self,reason,partial):super().__init__(reason);self.partial=partial


class Model(records.Model):
    def read(self,address,size):
        source=LITERALS if size==4 else HALFWORDS if size==2 else {}
        if address in source:
            value=source[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def store(self):
        r=self.reg;self.step(STORE);r['r2']=self.read(0x060A8388,4)
        self.step(STORE+2);r['r3']=self.read(r['r2'],4)
        self.step(STORE+4);self.step(STORE+6,True);self.write(r['r3']+60,4,r['r4']);r['pc']=r['pr']

    def poll(self):
        r=self.reg;self.step(POLL);r['r3']=self.read(0x060A7CFC,4)
        self.step(POLL+2);r['r5']=self.read(r['r3'],4)
        self.step(POLL+4);r['r0']=self.read(0x060A7CF6,2)
        self.step(POLL+6);r['r0']=self.read(r['r5']+r['r0'],4)
        self.step(POLL+8);self.t(r['r0']==0)
        self.step(POLL+10)
        if not r['sr']&1:
            self.step(0x060A7C2C);r['r0']=self.read(0x060A7CF8,2)
            self.step(0x060A7C2E);r['r2']=self.read(r['r5']+r['r0'],4)
            self.step(0x060A7C30);self.t(r['r4']==r['r2'])
            self.step(0x060A7C32)
            if r['sr']&1:
                self.step(0x060A7C34);self.step(0x060A7C36,True);r['r0']=0;r['pc']=r['pr'];return
        self.step(0x060A7C38);r['r0']=1
        self.step(0x060A7C3A);self.step(0x060A7C3C,True);r['pc']=r['pr']

    def request(self):
        r=self.reg;self.step(REQUEST);self.push(r['pr'])
        self.step(REQUEST+2);r['r15']-=4
        self.step(REQUEST+4);r['r1']=self.read(0x060A7BEC,4)
        self.step(REQUEST+6);r['r7']=self.read(r['r1'],4)
        self.step(REQUEST+8);r['r0']=self.read(0x060A7BDC,2)
        self.step(REQUEST+10);r['r0']=self.read(r['r7']+r['r0'],4)
        self.step(REQUEST+12);self.t(r['r0']==0)
        self.step(REQUEST+14)
        if not r['sr']&1:
            self.step(0x060A7BC0);r['r15']+=4
            self.step(0x060A7BC2);r['pr']=self.pop()
            self.step(0x060A7BC4);self.step(0x060A7BC6,True);r['r0']=MASK;r['pc']=r['pr'];return
        self.step(0x060A7BC8);r['r3']=self.read(r['r7']+52,4)
        self.step(0x060A7BCA);self.t(r['r4']==r['r3'])
        self.step(0x060A7BCC)
        if r['sr']&1:
            self.step(0x060A7BCE);r['r15']+=4
            self.step(0x060A7BD0);r['pr']=self.pop()
            self.step(0x060A7BD2);self.step(0x060A7BD4,True);r['r0']=(-5)&MASK;r['pc']=r['pr'];return
        self.step(0x060A7BF8);r['r0']=self.read(0x060A7CF6,2)
        self.step(0x060A7BFA);r['r3']=1
        self.step(0x060A7BFC);self.write(r['r7']+r['r0'],4,1)
        self.step(0x060A7BFE);r['r0']+=4
        self.step(0x060A7C00);r['r2']=self.read(r['r1'],4)
        self.step(0x060A7C02);self.write(r['r2']+r['r0'],4,r['r4'])
        self.step(0x060A7C04);r['r3']=self.read(r['r1'],4)
        self.step(0x060A7C06);r['r0']+=4
        self.step(0x060A7C08);self.write(r['r3']+r['r0'],4,r['r5'])
        self.step(0x060A7C0A);r['r4']=r['r15']
        self.step(0x060A7C0C);r['r3']=self.read(r['r1'],4)
        self.step(0x060A7C0E);r['r0']+=4
        self.step(0x060A7C10);self.write(r['r3']+r['r0'],4,r['r6'])
        self.step(0x060A7C12);r['pr']=0x060A7C16
        self.step(0x060A7C14,True);r['pc']=TARGET


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown request-state family')
    words=(*range(256),0x30000,0x80000000,0x7FFFFFFF,MASK)
    if family=='store':return [(family,v,s,n,0,0,0,0) for v,s,n in itertools.product(range(2),(0,37,255),words)]
    if family=='poll':return [(family,v,s,flag,index,index if same else index^MASK,0,0) for v,s,flag,index,same in itertools.product(
        range(2),(0,37,255),(0,1,2,128,MASK,0x80000000),(0,1,23,24,MASK,0x80000000),(False,True))]
    return [(family,v,s,flag,index,index if same else index^MASK,a,b) for v,s,flag,index,same,a,b in itertools.product(
        range(2),(0,37,255),(0,1,2,MASK,0x80000000),(0,23,24,MASK),(False,True),(0,1,MASK),(0,MASK))]


def contract(case):
    family,v,seed,a,b,c,d,e=case
    if family not in FAMILIES or any(type(i) is not int for i in case[1:]) or v not in (0,1) or seed not in (0,37,255) or any(not 0<=i<=MASK for i in (a,b,c,d,e)):raise ValueError('Outside request-state contract')
    block=0x060D4000+v*0x2000;entry={'store':STORE,'poll':POLL,'request':REQUEST}[family]
    before=records.initial(entry,a if family=='store' else b,v);before['r15']-=0x100+v*0x1000;before.update(r5=d,r6=e)
    canary=lambda size:bytes((seed+37*i)&255 for i in range(size));word=lambda value:value.to_bytes(4,'big');body=bytearray(canary(0x350))
    body[0x338:0x33C]=word(a);body[0x33C:0x340]=word(c);body[52:56]=word(c)
    sp=before['r15'];depth=8 if family=='request' else 0
    regions=[(block-16,canary(16),False),(block,bytes(body),family!='poll'),(block+len(body),canary(16),False),
        (CELL-16,canary(16),False),(CELL,word(block),False),(CELL+4,canary(16),False),(sp-32,canary(32-depth),False)]
    if depth:regions.append((sp-depth,canary(depth),True))
    regions.append((sp,canary(32),False));regions += [(addr,value.to_bytes(2,'big'),False) for addr,value in HALFWORDS.items()]
    m=Model(before,[(addr,buf) for addr,buf,_ in regions]);getattr(m,family)();expected=[buf for _,buf,_ in regions]
    if family=='store':body[60:64]=word(a);value=before['r0']
    elif family=='poll':value=0 if a!=0 and b==c else 1
    elif a!=0:value=MASK
    elif b==c:value=(-5)&MASK
    else:
        body[0x338:0x348]=b''.join(map(word,(1,b,d,e)));value=m.reg['r0']
        if m.reg['pc']!=TARGET or m.reg['r4']!=sp-8 or m.reg['pr']!=0x060A7C16:raise ValueError('Actual request pending linkage model differs')
    expected[1]=bytes(body)
    if depth:expected[7]=canary(8)[:4]+word(before['pr'])
    if [bytes(buf) for buf in m.buffers]!=expected or m.reg['r0']!=value:raise ValueError('Independent request-state memory/result differs')
    if len(m.trace)>64:raise ValueError('Outside chosen64 original128 guard')
    return m,regions


def observe(data,emu,before,regions):
    ranges=((STORE,STORE+8),(POLL,0x060A7C3E),(REQUEST,0x060A7BD6),(0x060A7BF8,0x060A7C16))
    terminals={before['pr']:'returned'}
    if before['pc']==REQUEST:terminals[TARGET]='handoff'
    return guard.observe(data,emu,before['pc'],regions,before,ranges=ranges,literals=tuple(LITERALS),aliases=(),terminals=terminals,budget=64)


def run_case(data,emu,case):
    m,r=contract(case);a=observe(data,emu,m.before,r);expected='handoff' if m.reg['pc']==TARGET else 'returned';reason=None
    if a['status']!=expected:reason='Request-state missed original boundary: '+str(a['error'])
    elif a['registers']!=m.reg:reason='Request-state register/PC/fullSR/PR/MAC differs'
    elif a['trace']!=m.trace or a['steps']!=len(m.trace):reason='Request-state PC/delay trace differs'
    elif a['events']!=m.events:reason='Request-state ordered transactions differ'
    elif a['regions_after']!=[bytes(b) for b in m.buffers] or not a['original_unaffected_bytes_equal']:reason='Request-state mapped bytes/canaries/unaffected source differs'
    if reason:raise task.CaseFailure(reason,case,a)
    return {'case':list(case),'status':expected,'instructions':a['steps'],'after_registers':a['registers'],'trace':a['trace'],
        'data_events':a['events'],'regions_after_sha256':[pinned.digest(b) for b in a['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    selected=cases(family);rows=[]
    for c in selected:
        try:rows.append(run_case(data,emu,c))
        except task.CaseFailure as e:e.completed_results=rows;raise
    positive={'cases':len(rows),'complete_returns':sum(r['status']=='returned' for r in rows),'unfinished_handoffs':sum(r['status']=='handoff' for r in rows),
        'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'original_game_bytes_executed':True}
    mutations={'store':[('lost-field-store-delay',STORE+6,9),('wrong-field-offset',STORE+6,0x134E)],
        'poll':[('wrong-query-field',POLL+12,0xE03C),('wrong-result-delay',POLL+22,0xE001)],
        'request':[('wrong-busy-result-delay',0x060A7BC6,0xE0FE),('wrong-same-result-delay',0x060A7BD4,0xE0FA),('lost-request-flag',0x060A7BFC,9),('lost-index-field',0x060A7C02,9),('lost-first-argument',0x060A7C08,9),('lost-last-argument',0x060A7C10,9)]}[family]
    chosen=list(dict.fromkeys(selected[:16]+selected[::max(1,len(selected)//48)]+selected[-16:]));controls={}
    for _,pc,_ in mutations:
        if not any(any(a==pc for a,_ in contract(c)[0].trace) for c in chosen):chosen.append(next(c for c in selected if any(a==pc for a,_ in contract(c)[0].trace)))
    for label,pc,value in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=value.to_bytes(2,'big');count=0;first=None
        for c in chosen:
            try:run_case(changed,emu,c)
            except task.CaseFailure as e:
                fault=e.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=e.evidence
        if not count:raise EvidenceFailure('Missing request-state semantic control: '+label,{**positive,'instruction_controls':controls})
        controls[label]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,'mutated_kernel_sha256':pinned.digest(changed)}
    return {**positive,'instruction_controls':controls}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True)
    p.add_argument('--family',choices=FAMILIES,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args(argv)
    report={'schema':'neptune.original-library-request-state.v1','status':'failure','selection':args.family,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
        'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,'original_game_bytes_executed':False,'programme_status':'active; incomplete',
        'source_sha256':{Path(f).name:pinned.digest(Path(f).read_bytes()) for f in (__file__,records.__file__,task.__file__,pinned.__file__,guard.__file__)},
        'limitations':['Constructed explicit high-RAM request object/stack; chosen64 budget within unchanged128 guard',
            'A85E4 is a nonexecutable pending entry; no fabricated service return or device RAM',
            'No fullA7BB0/cleanup/naturalinterior/hardware/gameplay/Godot/whole-program parity claim']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: require fresh report path');return 1
    with os.fdopen(fd,'w') as out:
        try:
            data=pinned.kernel_bytes(args.kernel);emu=pinned.interpreter(args.saturn_recomp);report['original_game_bytes_executed']=None
            report.update(execute(data,emu,args.family),status='success')
            if pinned.digest(args.kernel.read_bytes())!=pinned.digest(data):raise ValueError('Original file changed')
            report['original_file_unchanged']=True
        except Exception as e:
            report.update(status='failure',error={'type':type(e).__name__,'reason':str(e)})
            if isinstance(e,EvidenceFailure):report.update(e.partial)
            if isinstance(e,task.CaseFailure):report.update(failure_evidence=e.evidence,original_game_bytes_executed=True,completed_before_failure=getattr(e,'completed_results',[]))
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}));return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
