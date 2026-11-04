#!/usr/bin/env python3
"""Original byte copy, two24-byte pools and real A6FE0 setup paths.

A777E is a non-executable handoff for the unfinished context-success prefix.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_library_slots as slots
import probe_library_arithmetic as arithmetic

pinned,records,short,longer=slots.pinned,slots.records,slots.short,slots.longer
task=slots.tables.task
MASK=0xFFFFFFFF
COPY,ALLOC0,ALLOC24,RELEASE24,CONTEXT=0x060945B4,0x060A77E0,0x060A777E,0x060A77B0,0x060A6FE0
CELL=0x060FC084
LITERALS={0x060A7950:CELL,0x060A7108:COPY,0x060A710C:ALLOC0,0x060A7110:ALLOC24}
ENTRIES={'copy':COPY,'alloc0':ALLOC0,'alloc24':ALLOC24,'release24':RELEASE24,
         'context-failure':CONTEXT,'context-prefix':CONTEXT}
FAMILIES=tuple(ENTRIES)


class Model(records.Model):
    def read(self,address,size):
        if size==4 and address in LITERALS:
            value=LITERALS[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def copy(self):
        r=self.reg
        for pc,name in ((COPY,'r2'),(COPY+2,'r3'),(COPY+4,'r4')):
            self.step(pc);self.push(r[name])
        self.step(COPY+6);self.t(r['r0']==0)
        self.step(COPY+8)
        if not r['sr']&1:
            self.step(COPY+10);r['r4']=r['r2']
            self.step(COPY+12);r['r4']=(r['r4']+r['r0'])&MASK
            while True:
                done=False
                for i in range(4):
                    pc=0x060945C2+i*8
                    self.step(pc);r['r0']=records.signed(self.read(r['r2'],1),8)&MASK;r['r2']+=1
                    self.step(pc+2);self.write(r['r1']+i,1,r['r0'])
                    self.step(pc+4);self.t(r['r4']>r['r2'])
                    if i==3:
                        self.step(pc+6);r['r1']+=4
                        self.step(pc+8);done=not bool(r['sr']&1)
                    else:
                        self.step(pc+6);done=not bool(r['sr']&1)
                    if done:break
                if done:break
        self.step(0x060945E4);r['r4']=self.pop()
        self.step(0x060945E6);r['r3']=self.pop()
        self.step(0x060945E8)
        self.step(0x060945EA,True);r['r2']=self.pop()
        r['pc']=r['pr']

    def allocate(self,second):
        r=self.reg;entry=ALLOC24 if second else ALLOC0
        if second:
            self.step(entry);r['r5']=0
            self.step(entry+2);r['r6']=self.read(0x060A7950,4)
        else:
            self.step(entry);r['r6']=self.read(0x060A7950,4)
            self.step(entry+2);r['r5']=0
        self.step(entry+4);r['r1']=1
        self.step(entry+6);r['r7']=24
        while True:
            if second:
                self.step(0x060A7786);r['r3']=self.read(r['r6'],4)
                self.step(0x060A7788);r['r3']+=24
                self.step(0x060A778A);r['r3']+=r['r5']
                self.step(0x060A778C);r['r2']=records.signed(self.read(r['r3'],1),8)&MASK
                self.step(0x060A778E);self.t(r['r2']==0)
                self.step(0x060A7790)
            else:
                self.step(0x060A77E8);r['r0']=self.read(r['r6'],4)
                self.step(0x060A77EA);r['r3']=records.signed(self.read(r['r0']+r['r5'],1),8)&MASK
                self.step(0x060A77EC);self.t(r['r3']==0)
                self.step(0x060A77EE)
            if r['sr']&1:
                if second:
                    self.step(0x060A7792);r['r3']=self.read(r['r6'],4)
                    self.step(0x060A7794);r['r3']+=24
                    self.step(0x060A7796);r['r3']+=r['r5']
                    self.step(0x060A7798);self.write(r['r3'],1,1)
                    self.step(0x060A779A);self.write(r['r4'],4,r['r5'])
                    self.step(0x060A779C)
                    self.step(0x060A779E,True);r['r0']=0
                else:
                    self.step(0x060A77F0);r['r0']=self.read(r['r6'],4)
                    self.step(0x060A77F2);self.write(r['r0']+r['r5'],1,1)
                    self.step(0x060A77F4);self.write(r['r4'],4,r['r5'])
                    self.step(0x060A77F6)
                    self.step(0x060A77F8,True);r['r0']=0
                break
            pc=0x060A77A0 if second else 0x060A77FA
            self.step(pc);r['r5']+=1
            self.step(pc+2);self.t(r['r5']>=r['r7'])
            self.step(pc+4)
            if r['sr']&1:
                if second:
                    self.step(0x060A77A6);r['r3']=MASK
                    self.step(0x060A77A8);self.write(r['r4'],4,MASK)
                    self.step(0x060A77AA);r['r0']=(-3)&MASK
                    self.step(0x060A77AC);self.step(0x060A77AE,True)
                else:
                    self.step(0x060A7800);r['r2']=MASK
                    self.step(0x060A7802);r['r0']=(-4)&MASK
                    self.step(0x060A7804);self.write(r['r4'],4,MASK)
                    self.step(0x060A7806);self.step(0x060A7808,True)
                break
        r['pc']=r['pr']

    def release(self):
        r=self.reg
        self.step(RELEASE24);self.t(records.signed(r['r4'],32)>=0)
        self.step(RELEASE24+2)
        valid=bool(r['sr']&1)
        if valid:
            self.step(0x060A77B4);r['r2']=24
            self.step(0x060A77B6);self.t(records.signed(r['r4'],32)>=24)
            self.step(0x060A77B8);valid=not bool(r['sr']&1)
        if not valid:
            self.step(0x060A77BA);self.step(0x060A77BC,True);r['r0']=(-6)&MASK
        else:
            self.step(0x060A77BE);r['r2']=self.read(0x060A7950,4)
            self.step(0x060A77C0);r['r5']=self.read(r['r2'],4)
            self.step(0x060A77C2);r['r0']=r['r5']
            self.step(0x060A77C4);r['r0']+=24
            self.step(0x060A77C6);r['r0']=records.signed(self.read(r['r0']+r['r4'],1),8)&MASK
            self.step(0x060A77C8);self.t(r['r0']==1)
            self.step(0x060A77CA)
            if not r['sr']&1:
                self.step(0x060A77CC);self.step(0x060A77CE,True);r['r0']=(-7)&MASK
            else:
                self.step(0x060A77D0);r['r2']=r['r5']
                self.step(0x060A77D2);r['r2']+=24
                self.step(0x060A77D4);r['r4']+=r['r2']
                self.step(0x060A77D6);r['r3']=0
                self.step(0x060A77D8);self.write(r['r4'],1,0)
                self.step(0x060A77DA);r['r0']=0
                self.step(0x060A77DC);self.step(0x060A77DE,True)
        r['pc']=r['pr']

    def context(self):
        r=self.reg
        self.step(CONTEXT);self.push(r['r14'])
        self.step(CONTEXT+2);r['r5']=r['r4']
        self.step(CONTEXT+4);self.push(r['r13'])
        self.step(CONTEXT+6);r['r14']=r['r4']
        self.step(CONTEXT+8);self.push(r['pr'])
        self.step(CONTEXT+10);r['r13']=0
        self.step(CONTEXT+12);r['r15']-=16
        self.step(CONTEXT+14);r['r14']+=28
        self.step(CONTEXT+16);self.write(r['r14'],4,0)
        self.step(CONTEXT+18);r['r3']=1
        self.step(CONTEXT+20);self.write(r['r14']+24,4,1)
        self.step(CONTEXT+22);r['r2']=r['r15']
        self.step(CONTEXT+24);r['r0']=records.signed(self.read(r['r5']+14,1),8)&MASK
        self.step(CONTEXT+26);r['r3']=r['r15']
        self.step(CONTEXT+28);r['r2']+=8
        self.step(CONTEXT+30);r['r3']+=8
        self.step(0x060A7000);self.write(r['r2'],1,r['r0'])
        self.step(0x060A7002);r['r0']=r['r13']
        for pc,offset in ((0x060A7004,1),(0x060A700A,2),(0x060A7010,3),(0x060A7016,4),(0x060A701C,5)):
            if offset>1:
                self.step(pc-4);r['r3']=r['r15']
                self.step(pc-2);r['r3']+=8
            self.step(pc);self.write(r['r3']+offset,1,0)
        self.step(0x060A701E);r['r1']=r['r14']
        self.step(0x060A7020);r['r3']=self.read(0x060A7108,4)
        self.step(0x060A7022);r['r2']=r['r15']
        self.step(0x060A7024);r['r1']+=16
        self.step(0x060A7026);r['r2']+=8
        self.step(0x060A7028);r['pr']=0x060A702C
        self.step(0x060A702A,True);r['r0']=6
        self.copy()
        self.step(0x060A702C);r['r3']=self.read(0x060A710C,4)
        self.step(0x060A702E);r['r2']=MASK
        self.step(0x060A7030);self.write(r['r14']+28,4,MASK)
        self.step(0x060A7032);r['r4']=r['r15']
        self.step(0x060A7034);self.write(r['r14']+36,4,0)
        self.step(0x060A7036);r['r4']+=4
        self.step(0x060A7038);self.write(r['r14']+32,4,0)
        self.step(0x060A703A);self.write(r['r14']+44,4,0)
        self.step(0x060A703C);r['pr']=0x060A7040
        self.step(0x060A703E,True);self.write(r['r14']+40,4,0)
        self.allocate(False)
        self.step(0x060A7040);self.t(r['r0']==0)
        self.step(0x060A7042)
        if not r['sr']&1:
            self.step(0x060A7044);self.step(0x060A7046,True);r['r0']=0
            self.step(0x060A70B2);r['r15']+=16
            self.step(0x060A70B4);r['pr']=self.pop()
            self.step(0x060A70B6);r['r13']=self.pop()
            self.step(0x060A70B8);self.step(0x060A70BA,True);r['r14']=self.pop()
            r['pc']=r['pr']
        else:
            self.step(0x060A7048);r['r3']=self.read(r['r15']+4,4)
            self.step(0x060A704A);r['r4']=r['r15']
            self.step(0x060A704C);self.write(r['r14']+4,4,r['r3'])
            self.step(0x060A704E);r['r3']=self.read(0x060A7110,4)
            self.step(0x060A7050);r['pr']=0x060A7054
            self.step(0x060A7052,True);r['pc']=ALLOC24


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown pool/copy family')
    if family=='copy':
        rows=[(family,v,s,n,delta) for v,s,n,delta in itertools.product(range(2),(0,37,255),
              (*range(33),MASK,MASK-1,MASK-31),(-16,-3,-1,0,1,3,16,64))]
        rows += [(family,v,s,n,64) for v,s,n in itertools.product(range(2),range(256),(1,4,6,8))]
    elif family.startswith('alloc'):
        masks=tuple(dict.fromkeys(((1<<i)-1 for i in range(25))))+tuple(0xFFFF00|i for i in range(256))+(0xAAAAAA,0x555555)
        rows=[(family,v,s,mask,old) for v,s,mask,old in itertools.product(range(2),(0,37,255),masks,(0,1,MASK))]
    elif family=='release24':
        rows=[(family,v,37,index,marker) for v,index,marker in itertools.product(range(2),range(24),range(256))]
        rows += [(family,v,s,index,1) for v,s,index in itertools.product(range(2),(0,37,255),(MASK,MASK-1,0x80000000,24,25,0x7FFFFFFF))]
    elif family=='context-failure':
        rows=[(family,v,s,flag,0xFFFFFF) for v,s,flag in itertools.product(range(2),(0,37,255),range(256))]
    else:
        rows=[(family,v,s,flag,(1<<i)-1) for v,s,flag,i in itertools.product(range(2),(0,37,255),
              (0,1,7,8,16,24,64,128,255),range(24))]
    return list(dict.fromkeys(rows))


def contract(case):
    family,v,seed,a,b=case
    if (family not in FAMILIES or type(v) is not int or v not in (0,1) or type(seed) is not int or not 0<=seed<=255 or
            type(a) is not int or type(b) is not int):raise ValueError('Outside explicit pool/copy contract')
    if (family=='copy' and (a not in (*range(33),MASK,MASK-1,MASK-31) or b not in (-16,-3,-1,0,1,3,16,64)) or
        family.startswith('alloc') and (not 0<=a<=0xFFFFFF or not 0<=b<=MASK) or
        family=='release24' and (not 0<=a<=MASK or not 0<=b<=255) or
        family.startswith('context') and (not 0<=a<=255 or not 0<=b<=0xFFFFFF) or
        family=='context-failure' and b!=0xFFFFFF or family=='context-prefix' and b==0xFFFFFF or
        family!='copy' and seed not in (0,37,255)):
        raise ValueError('Outside bounded pool/copy arguments')
    block=0x060D0000+v*0x2000;pool=0x060D8000+v*0x2000
    before=records.initial(ENTRIES[family],a if family=='release24' else block,v)
    before['r15']-=0x100+v*0x1000
    canary=lambda n:bytes((seed+37*i)&255 for i in range(n))
    size=160 if family=='copy' else 96 if family.startswith('context') else 4
    body=bytearray(canary(size));table=bytearray(canary(48))
    if family=='copy':before.update(r0=a,r2=block+32,r1=block+32+b)
    elif family.startswith('alloc') or family.startswith('context'):
        mask=b if family.startswith('context') else a;offset=24 if family=='alloc24' else 0
        marker=(1,128,255)[(0,37,255).index(seed)]
        for i in range(24):table[offset+i]=marker if mask>>i&1 else 0
        if family.startswith('alloc'):body[:]=b.to_bytes(4,'big')
        else:body[14]=a
    else:
        if a<24:table[24+a]=b
    depth=40 if family.startswith('context') else 12 if family=='copy' else 0
    sp=before['r15']
    regions=[(block-16,canary(16),False),(block,bytes(body),family!='release24'),(block+size,canary(16),False),
             (pool-16,canary(16),False),(pool,bytes(table),family!='copy'),(pool+48,canary(16),False),
             (CELL-16,canary(16),False),(CELL,pool.to_bytes(4,'big'),False),(CELL+4,canary(16),False),
             (sp-64,canary(64-depth),False)]
    if depth:regions.append((sp-depth,canary(depth),True))
    regions.append((sp,canary(64),False))
    model=Model(before,[(lo,buf) for lo,buf,_ in regions])
    if family=='copy':model.copy()
    elif family.startswith('alloc'):model.allocate(family=='alloc24')
    elif family=='release24':model.release()
    else:model.context()
    scalar=body[:];scalar_table=table[:]
    if family=='copy':
        count=1 if a>32 else a
        for i in range(count):scalar[32+b+i]=scalar[32+i]
        want=records.signed(scalar[32+b+count-1],8)&MASK if count else 0
        assert model.reg['r1']==before['r1']+(count//4)*4
        assert model.reg['sr']==((before['sr']&~1)|int(count==0))
    elif family.startswith('alloc') or family.startswith('context'):
        mask=b if family.startswith('context') else a;offset=24 if family=='alloc24' else 0
        free=next((i for i in range(24) if not mask>>i&1),None)
        if free is not None:scalar_table[offset+free]=1
        if family.startswith('alloc'):
            scalar[:]=(MASK if free is None else free).to_bytes(4,'big')
            want=(((-3 if offset else -4)&MASK) if free is None else 0)
        else:
            for pos,value in ((28,0),(52,1),(56,MASK),(60,0),(64,0),(68,0),(72,0)):
                scalar[pos:pos+4]=value.to_bytes(4,'big')
            scalar[44:50]=bytes([a,0,0,0,0,0])
            if free is not None:scalar[32:36]=free.to_bytes(4,'big')
            want=0
            assert model.reg['pc']==(ALLOC24 if free is not None else before['pr'])
    else:
        if a<24 and b==1:scalar_table[24+a]=0
        want=0 if a<24 and b==1 else (-7 if a<24 else -6)&MASK
    if (model.reg['r0']!=want or bytes(model.buffers[1])!=scalar or bytes(model.buffers[4])!=scalar_table):
        raise ValueError('Independent scalar pool/copy/context result differs')
    for i,(_,buf,write) in enumerate(regions):
        if not write and bytes(model.buffers[i])!=buf:raise ValueError('Expected model changed readonly canary')
    return model,regions


def observe(data,emu,family,before,regions,*,short_refusal=False):
    ranges={'copy':((COPY,0x060945EC),),'alloc0':((ALLOC0,0x060A780A),),
            'alloc24':((ALLOC24,RELEASE24),),'release24':((RELEASE24,ALLOC0),)}
    if family.startswith('context'):
        declared=((CONTEXT,0x060A7054),(0x060A70B2,0x060A70BC),(COPY,0x060945EC),(ALLOC0,0x060A780A))
    else:declared=ranges[family]
    profile=short if short_refusal or family=='release24' else longer
    terminals={before['pr']:'returned'}
    if family=='context-prefix':terminals[ALLOC24]='handoff'
    return profile.observe(data,emu,before['pc'],regions,before,ranges=declared,literals=tuple(LITERALS),aliases=(),
                           terminals=terminals,budget=128 if profile is short else 512 if family.startswith('context') else 256)


def run_case(data,emu,case):
    expected,regions=contract(case);actual=observe(data,emu,case[0],expected.before,regions)
    status='handoff' if case[0]=='context-prefix' else 'returned';reason=None
    if actual['status']!=status:reason='Original pool/copy/context boundary failed: '+str(actual['error'])
    elif actual['registers']!=expected.reg:reason='Pool/copy/context register/PC/SR/PR/MAC differs'
    elif actual['trace']!=expected.trace or actual['steps']!=len(expected.trace):reason='Pool/copy/context PC/delay trace differs'
    elif actual['events']!=expected.events:reason='Pool/copy/context ordered transactions differ'
    elif actual['regions_after']!=[bytes(buf) for buf in expected.buffers] or not actual['original_unaffected_bytes_equal']:
        reason='Pool/copy/context memory/canaries/source differs'
    if reason:raise task.CaseFailure(reason,case,actual)
    return {'case':list(case),'status':status,'instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],
            'regions_after_sha256':[pinned.digest(bytes(buf)) for buf in actual['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    rows=[];selected=cases(family)
    for case in selected:
        try:rows.append(run_case(data,emu,case))
        except task.CaseFailure as error:error.completed_results=rows;raise
    positive={'cases':len(rows),'complete_returns':sum(r['status']=='returned' for r in rows),
              'unfinished_handoffs':sum(r['status']=='handoff' for r in rows),'results':rows,
              'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'original_game_bytes_executed':True}
    controls={};mutations={
      'copy':(('lost-first-store',0x060945C4,9),('lost-four-byte-advance',0x060945E0,9),('lost-R2-delay',0x060945EA,9)),
      'alloc0':(('lost-marker-store',0x060A77F2,9),('lost-output-store',0x060A77F4,9),('wrong-limit',0x060A77E6,0xE717),('lost-zero-delay',0x060A77F8,9)),
      'alloc24':(('wrong-table-offset',0x060A7788,0x7314),('lost-marker-store',0x060A7798,9),('lost-output-store',0x060A779A,9),('wrong-limit',0x060A7784,0xE717)),
      'release24':(('wrong-valid-marker',0x060A77C8,0x8802),('lost-marker-clear',0x060A77D8,9),('wrong-index-limit',0x060A77B4,0xE217)),
      'context-failure':(('lost-state52',0x060A6FF4,9),('lost-copy',0x060945C4,9),('lost-state68-delay',0x060A703E,9),('lost-zero-result-delay',0x060A7046,9),('lost-R14-delay',0x060A70BA,9)),
      'context-prefix':(('lost-state52',0x060A6FF4,9),('lost-copy',0x060945C4,9),('lost-allocated-index',0x060A704C,9),('lost-first-pool-marker',0x060A77F2,9))}[family]
    chosen=list(dict.fromkeys(selected[:32]+selected[::max(1,len(selected)//64)]+selected[-32:]))
    for name,pc,word in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=word.to_bytes(2,'big');count=0;first=None
        for case in chosen:
            try:run_case(changed,emu,case)
            except task.CaseFailure as error:
                fault=error.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=error.evidence
        if not count:raise arithmetic.EvidenceFailure('No non-budget pool/copy mutation rejection: '+name,
             {**positive,'instruction_controls':controls,'failed_control':{'name':name,'pc':pc,'tested':len(chosen)}})
        controls[name]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,'mutated_kernel_sha256':pinned.digest(changed)}
    result={**positive,'instruction_controls':controls}
    if family in ('alloc0','alloc24','context-failure'):
        case=next(c for c in selected if c[4 if family.startswith('context') else 3]==0xFFFFFF)
        expected,regions=contract(case);actual=observe(data,emu,family,expected.before,regions,short_refusal=True)
        if actual['status']!='failed' or not actual['error'] or 'budget exceeded' not in actual['error']['reason']:
            raise arithmetic.EvidenceFailure('Expected original128 refusal missing',result)
        result['short128_refusal']={k:v for k,v in actual.items() if k!='regions_after'}
        result['short128_refusal']['regions_after_sha256']=[pinned.digest(buf) for buf in actual['regions_after']]
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-library-pools.v1','status':'failure','selection':args.family,
        'kernel_sha256':pinned.KERNEL_SHA256,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2',
        'load_address':pinned.BASE,'lifetime':'resident-kernel','original_game_bytes_executed':False,
        'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,
        'source_sha256':{Path(p).name:pinned.digest(Path(p).read_bytes()) for p in (__file__,records.__file__,pinned.__file__,short.__file__,longer.__file__)},
        'programme_status':'active; incomplete','limitations':['Constructed copy/pool/object/global/stack corpus; no natural interior traffic',
          'A6FE0 full return covers first-pool exhaustion only; successful first allocation stops at actual A777E handoff',
          'Later service/device/callback semantics, fullA681A/95E5A/89C8 and whole-program denominators remain open']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: require fresh report path');return 1
    with os.fdopen(fd,'w') as output:
        try:
            data=pinned.kernel_bytes(args.kernel);emu=pinned.interpreter(args.saturn_recomp)
            report['original_game_bytes_executed']=None;report.update(execute(data,emu,args.family),status='success')
            if pinned.digest(args.kernel.read_bytes())!=pinned.digest(data):raise ValueError('Original file changed')
            report['original_file_unchanged']=True
        except Exception as error:
            report['status']='failure';report['error']={'type':type(error).__name__,'reason':str(error)}
            if isinstance(error,arithmetic.EvidenceFailure):report.update(error.partial)
            if isinstance(error,task.CaseFailure):report.update(failure_evidence=error.evidence,original_game_bytes_executed=True,completed_before_failure=getattr(error,'completed_results',[]))
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
