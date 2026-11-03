#!/usr/bin/env python3
"""Original A681A/96D74 nonnull-record returns through real pool exhaustion.

All nested arithmetic, format, context, copy and allocator calls execute original
instructions. Null records and later successful context services are unresolved.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_library_pools as pools
import probe_library_arithmetic as arithmetic
import probe_library_setup as setup

pinned,records,longer=pools.pinned,pools.records,pools.longer
MASK=0xFFFFFFFF
ENTRY=0x060A681A
FAMILIES=('record-failure','caller-failure')
LONGS={0x060A68B4:arithmetic.QUOTIENT,0x060A6A5C:arithmetic.REMAINDER,0x060A6A60:pools.CONTEXT}
SHORTS={0x060A68A2:2048,0x060A68A4:2047}


class Model(pools.Model,arithmetic.Model,setup.Model):
    def read(self,address,size):
        literals=LONGS if size==4 else SHORTS if size==2 else {}
        if address in literals:
            value=literals[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def record(self):
        r=self.reg
        self.step(ENTRY);self.push(r['r14'])
        self.step(ENTRY+2);self.push(r['r13'])
        self.step(ENTRY+4);r['r13']=r['r5']
        self.step(ENTRY+6);self.push(r['r12'])
        self.step(ENTRY+8);self.t(r['r13']==0)
        self.step(ENTRY+10);self.push(r['r11'])
        self.step(ENTRY+12);r['r12']=r['r4']
        self.step(ENTRY+14);self.push(r['r10'])
        self.step(ENTRY+16);self.push(r['r9'])
        self.step(ENTRY+18);self.push(r['pr'])
        self.step(ENTRY+20);r['r9']=r['r6']
        self.step(ENTRY+22);r['r10']=self.read(0x060A68A2,2)
        self.step(ENTRY+24)
        self.step(ENTRY+26,True);r['r14']=r['r4']
        if not r['r13']:raise ValueError('Null record service path not modeled')
        self.step(0x060A684E);r['r0']=records.signed(self.read(r['r13']+11,1),8)&MASK
        self.step(0x060A6850);r['r0']&=255
        self.step(0x060A6852);self.t(not(r['r0']&128))
        self.step(0x060A6854)
        self.step(0x060A6856,True);r['r11']=self.read(r['r13']+4,4)
        if not r['sr']&1:
            self.step(0x060A6858);r['r1']=self.read(0x060A68A4,2)
            self.step(0x060A685A);r['r1']=(r['r1']+r['r11'])&MASK
            self.step(0x060A685C);r['r3']=self.read(0x060A68B4,4)
            self.step(0x060A685E);r['pr']=0x060A6862
            self.step(0x060A6860,True);r['r0']=r['r10']
            self.divide(False)
            self.step(0x060A6862);r['macl']=(r['r10']*r['r0'])&MASK
            self.step(0x060A6864);r['r11']=r['macl']
        self.step(0x060A6866);self.write(r['r14'],4,r['r9'])
        self.step(0x060A6868);r['r2']=self.read(r['r13'],4)
        self.step(0x060A686A);self.write(r['r14']+4,4,r['r2'])
        self.step(0x060A686C);self.write(r['r14']+8,4,r['r11'])
        for pc,offset in ((0x060A686E,8),(0x060A6872,9),(0x060A6876,10),(0x060A687A,11)):
            self.step(pc);r['r0']=records.signed(self.read(r['r13']+offset,1),8)&MASK
            self.step(pc+2);self.write(r['r14']+offset+4,1,r['r0'])
        self.step(0x060A687E);r['r0']=records.signed(self.read(r['r13']+11,1),8)&MASK
        self.step(0x060A6880);r['pr']=0x060A6884
        self.step(0x060A6882,True);r['r4']=r['r0']&255
        self.format()
        self.step(0x060A6884);self.write(r['r14']+16,4,r['r0'])
        self.step(0x060A6886);r['r2']=self.read(0x060A68A4,2)
        self.step(0x060A6888);r['r2']=(r['r2']+r['r11'])&MASK
        self.step(0x060A688A);r['r2']>>=8
        self.step(0x060A688C);r['r2']>>=2
        self.step(0x060A688E);old=r['r2'];r['r2']>>=1;self.t(old&1)
        self.step(0x060A6890);self.write(r['r14']+20,4,r['r2'])
        self.step(0x060A6892);r['r0']=self.read(r['r14']+16,4)
        self.step(0x060A6894);self.t(r['r0']==0)
        self.step(0x060A6896)
        self.step(0x060A6898,True);r['r13']=0
        if r['sr']&1:
            self.step(0x060A689A)
            self.step(0x060A689C,True);self.write(r['r14']+24,4,0)
        else:
            self.step(0x060A68B8);r['r2']=self.read(0x060A6A5C,4)
            self.step(0x060A68BA);r['r1']=r['r11']
            self.step(0x060A68BC);r['pr']=0x060A68C0
            self.step(0x060A68BE,True);r['r0']=r['r10']
            self.divide(True)
            self.step(0x060A68C0);r['r3']=self.read(0x060A6A5C,4)
            self.step(0x060A68C2);r['r1']=r['r10']
            self.step(0x060A68C4);r['r1']=(r['r1']-r['r0'])&MASK
            self.step(0x060A68C6);r['pr']=0x060A68CA
            self.step(0x060A68C8,True);r['r0']=r['r10']
            self.divide(True)
            self.step(0x060A68CA);self.write(r['r14']+24,4,r['r0'])
        self.step(0x060A68CC);r['r2']=self.read(0x060A6A60,4)
        self.step(0x060A68CE);r['pr']=0x060A68D2
        self.step(0x060A68D0,True);r['r4']=r['r12']
        self.context()
        self.step(0x060A68D2);self.t(r['r0']==0)
        self.step(0x060A68D4)
        if not r['sr']&1:raise ValueError('Context success is outside first-pool exhaustion contract')
        self.step(0x060A68D6);self.step(0x060A68D8,True);r['r0']=0
        for pc,name in ((0x060A68F2,'pr'),(0x060A68F4,'r9'),(0x060A68F6,'r10'),
                        (0x060A68F8,'r11'),(0x060A68FA,'r12'),(0x060A68FC,'r13')):
            self.step(pc);r[name]=self.pop()
        self.step(0x060A68FE);self.step(0x060A6900,True);r['r14']=self.pop()
        r['pc']=r['pr']

    def complete_caller(self):
        self.caller();self.record();r=self.reg
        self.step(0x06096DA2);r['r4']=r['r0']
        self.step(0x06096DA4);self.t(r['r4']==0)
        self.step(0x06096DA6)
        if not r['sr']&1:raise ValueError('Successful record setup not modeled')
        self.step(0x06096DA8);r['r0']=0
        self.step(0x06096DAA);r['r15']+=8
        self.step(0x06096DAC);r['pr']=self.pop()
        self.step(0x06096DAE);self.step(0x06096DB0,True);r['r14']=self.pop()
        r['pc']=r['pr']


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown record-setup family')
    lengths=(0,1,2047,2048,2049,4095,4096,0x7FFFF800,0x7FFFFFFF,0x80000000,0x80000001,MASK)
    flags=(0,8,16,24,64,128,152,192,255)
    rows=[(family,v,37,flag,length,index) for v,flag,length,index in itertools.product(range(2),flags,lengths,(0,19,MASK))]
    rows += [(family,v,s,flag,2049,19) for v,s,flag in itertools.product(range(2),(0,255),range(256))]
    return list(dict.fromkeys(rows))


def contract(data,case):
    family,v,seed,flag,length,index=case
    if (family not in FAMILIES or type(v) is not int or v not in (0,1) or type(seed) is not int or seed not in (0,37,255) or
        type(flag) is not int or not 0<=flag<=255 or any(type(x) is not int or not 0<=x<=MASK for x in (length,index))):
        raise ValueError('Outside nonnull record/exhausted-pool contract')
    caller=family=='caller-failure';block=0x060D0000+v*0x2000;desc=0x060D4000+v*0x2000;pool=0x060D8000+v*0x2000
    size=168 if caller else 96;start=12 if caller else 0
    before=records.initial(setup.CALLER if caller else ENTRY,block,v);before['r15']-=0x100+v*0x1000
    before['r5']=desc;before['r6']=index
    canary=lambda n:bytes((seed+37*i)&255 for i in range(n))
    body=bytearray(canary(size));descriptor=(0xDEADBEEF if v else 0x12345678).to_bytes(4,'big')+length.to_bytes(4,'big')+bytes([255,128,0x55 if v else 0xAA,flag])
    table=bytes([1 if seed==0 else 128 if seed==37 else 255])*24+canary(24)
    sp=before['r15'];depth=84 if caller else 68
    regions=[(block-16,canary(16),False),(block,bytes(body),True),(block+size,canary(16),False),
             (desc-16,canary(16),False),(desc,descriptor,False),(desc+12,canary(16),False),
             (pool-16,canary(16),False),(pool,table,False),(pool+48,canary(16),False),
             (pools.CELL-16,canary(16),False),(pools.CELL,pool.to_bytes(4,'big'),False),(pools.CELL+4,canary(16),False),
             (sp-128,canary(128-depth),False),(sp-depth,canary(depth),True),(sp,canary(64),False)]
    for address,value in {**SHORTS,**arithmetic.SHORTS}.items():
        raw=data[address-pinned.BASE:address-pinned.BASE+2]
        if raw!=value.to_bytes(2,'big'):raise ValueError('Original record/format literal changed')
        regions.append((address,raw,False))
    m=Model(before,[(lo,buf) for lo,buf,_ in regions]);m.complete_caller() if caller else m.record()
    scalar=body[:]
    effective=(arithmetic.scalar((length+2047)&MASK,2048)[0]*2048)&MASK if flag&128 else length
    fmt=2352 if flag&64 else (0 if flag&8 else 2324) if flag&16 else 2048
    for offset,value in ((0,index),(4,int.from_bytes(descriptor[:4],'big')),(8,effective),(16,fmt),
                         (20,((effective+2047)&MASK)>>11),(24,(-effective)&2047 if fmt else 0),
                         (28,0),(52,1),(56,MASK),(60,0),(64,0),(68,0),(72,0)):
        scalar[start+offset:start+offset+4]=value.to_bytes(4,'big')
    scalar[start+12:start+16]=descriptor[8:12];scalar[start+44:start+50]=bytes([descriptor[10],0,0,0,0,0])
    if caller:
        for offset in (*range(0,20,4),24,28,32,36,40,52):scalar[108+offset:112+offset]=bytes(4)
        for offset,value in ((20,1),(44,1),(56,3)):scalar[108+offset:112+offset]=value.to_bytes(4,'big')
    if m.buffers[1]!=scalar or m.reg['r0']!=0 or m.reg['pc']!=before['pr'] or m.reg['r15']!=before['r15']:
        raise ValueError('Independent composed header/context/default/return contract differs')
    for i,(_,buf,write) in enumerate(regions):
        if not write and bytes(m.buffers[i])!=buf:raise ValueError('Composed model modified readonly inputs')
    return m,regions


def observe(data,emu,family,before,regions,*,short_refusal=False):
    ranges=((ENTRY,0x060A689E),(0x060A68B8,0x060A6902),
            (arithmetic.QUOTIENT,0x060941B6),(arithmetic.REMAINDER,0x06094326),
            (arithmetic.FORMAT,0x060A6DB2),(0x060A6DC4,0x060A6DE6),
            (pools.CONTEXT,0x060A7048),(0x060A70B2,0x060A70BC),(pools.COPY,0x060945EC),(pools.ALLOC0,0x060A780A))
    if family=='caller-failure':ranges+=((setup.INIT,0x060A5F32),(setup.CALLER,0x06096DB2))
    literals=tuple({**LONGS,**arithmetic.LONGS,**pools.LITERALS,**setup.LITERALS})
    profile=pools.short if short_refusal else longer
    return profile.observe(data,emu,before['pc'],regions,before,ranges=ranges,literals=literals,aliases=(),
                           terminals={before['pr']:'returned'},budget=128 if short_refusal else 768)


def run_case(data,emu,case):
    m,r=contract(data,case);a=observe(data,emu,case[0],m.before,r);reason=None
    if a['status']!='returned':reason='Original composed return failed: '+str(a['error'])
    elif a['registers']!=m.reg:reason='Composed register/PC/SR/PR/MAC differs'
    elif a['trace']!=m.trace or a['steps']!=len(m.trace):reason='Composed original PC/delay path differs'
    elif a['events']!=m.events:reason='Composed ordered transactions differ'
    elif a['regions_after']!=[bytes(b) for b in m.buffers] or not a['original_unaffected_bytes_equal']:reason='Composed memory/source/canaries differ'
    if reason:raise pools.task.CaseFailure(reason,case,a)
    return {'case':list(case),'status':'returned','instructions':a['steps'],'after_registers':a['registers'],
            'trace':a['trace'],'data_events':a['events'],'regions_after_sha256':[pinned.digest(b) for b in a['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    selected=cases(family);rows=[]
    for c in selected:
        try:rows.append(run_case(data,emu,c))
        except pools.task.CaseFailure as e:e.completed_results=rows;raise
    positive={'cases':len(rows),'complete_returns':len(rows),'results':rows,'original_game_bytes_executed':True,
              'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode())}
    mutations=[('lost-length-store',0x060A686C,9),('lost-format-store',0x060A6884,9),
               ('lost-padding-store',0x060A68CA,9),('lost-flag-copy',0x060945C4,9),('lost-context-state52',0x060A6FF4,9)]
    if family=='caller-failure':mutations.append(('lost-root-R14-delay',0x06096DB0,9))
    else:mutations.append(('lost-record-R14-delay',0x060A6900,9))
    chosen=list(dict.fromkeys(selected[:16]+selected[::max(1,len(selected)//64)]+selected[-16:]));controls={}
    for name,pc,word in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=word.to_bytes(2,'big');count=0;first=None
        for c in chosen:
            try:run_case(changed,emu,c)
            except pools.task.CaseFailure as e:
                fault=e.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=e.evidence
        if not count:raise arithmetic.EvidenceFailure('Missing composed semantic control: '+name,{**positive,'instruction_controls':controls})
        controls[name]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,'mutated_kernel_sha256':pinned.digest(changed)}
    case=selected[0];m,r=contract(data,case);a=observe(data,emu,family,m.before,r,short_refusal=True)
    if a['status']!='failed' or not a['error'] or 'budget exceeded' not in a['error']['reason']:
        raise arithmetic.EvidenceFailure('Missing original128 composed refusal',positive)
    refusal={k:v for k,v in a.items() if k!='regions_after'};refusal['regions_after_sha256']=[pinned.digest(b) for b in a['regions_after']]
    return {**positive,'instruction_controls':controls,'short128_refusal':refusal}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,required=True);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-library-record-setup.v1','status':'failure','selection':args.family,
      'kernel_sha256':pinned.KERNEL_SHA256,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,
      'lifetime':'resident-kernel','original_game_bytes_executed':False,'interpreter_revision':pinned.INTERPRETER_REVISION,
      'interpreter_sources':pinned.SOURCE_HASHES,'programme_status':'active; incomplete',
      'source_sha256':{Path(p).name:pinned.digest(Path(p).read_bytes()) for p in (__file__,pools.__file__,arithmetic.__file__,setup.__file__,records.__file__,pinned.__file__,pools.short.__file__,longer.__file__)},
      'limitations':['Non-null constructed descriptor; first24-byte pool exhausted; only these complete return paths',
         'All nested calls execute original instructions; no successful service/MMIO/callback behavior substituted',
         'Null record/A7F4E, successful A6FE0, full95E5A/89C8 and whole-program/hardware/gameplay/Godot parity unresolved']}
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
            if isinstance(e,arithmetic.EvidenceFailure):report.update(e.partial)
            if isinstance(e,pools.task.CaseFailure):report.update(failure_evidence=e.evidence,original_game_bytes_executed=True,completed_before_failure=getattr(e,'completed_results',[]))
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
