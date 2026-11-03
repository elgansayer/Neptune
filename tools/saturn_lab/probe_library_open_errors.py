#!/usr/bin/env python3
"""Original95E5A complete errors through real selection/index/setup/status calls.

Non-null record table and callback-null reporting; first context pool exhausted.
No successful service/callback return is substituted.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_library_record_setup as record
import probe_library_status as status
import probe_library_slots as slots

pinned,records,longer=record.pinned,record.records,record.longer
MASK=0xFFFFFFFF
ENTRY=0x06095E5A
FAMILIES=('record12','record24','invalid-index','no-slot')
SIZE=slots.OFFSET+24*slots.STRIDE
LONGS={0x06095EF0:status.CELL,0x06095EFC:record.setup.INDEX12,0x06095F00:record.setup.INDEX24}
SHORTS={0x06095EEE:0x98}
STATUSES=tuple(x&MASK for x in (0,-16,-14,-13,-1,1,0x80000000))


class Model(record.Model,status.Model,slots.Model):
    def read(self,address,size):
        source=LONGS if size==4 else SHORTS if size==2 else {}
        if address in source:
            value=source[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def report_error(self,pc,value):
        r=self.reg
        self.step(pc);r['pr']=pc+4
        self.step(pc+2,True);r['r4']=value&MASK
        self.status()

    def finish(self):
        r=self.reg
        for pc,name in ((0x06095EE0,'pr'),(0x06095EE2,'r12'),(0x06095EE4,'r13')):
            self.step(pc);r[name]=self.pop()
        self.step(0x06095EE6);self.step(0x06095EE8,True);r['r14']=self.pop()
        r['pc']=r['pr']

    def open(self):
        r=self.reg
        for pc,name in ((ENTRY,'r14'),(ENTRY+2,'r13'),(ENTRY+4,'r12'),(ENTRY+6,'pr')):
            self.step(pc);self.push(r[name])
        self.step(0x06095E62);r['r3']=self.read(0x06095EF0,4)
        self.step(0x06095E64);r['r2']=self.read(0x06095EEE,2)
        self.step(0x06095E66);r['r14']=self.read(r['r3'],4)
        self.step(0x06095E68);r['r14']+=r['r2']
        self.step(0x06095E6A);r['r0']=self.read(r['r14']+8,4)
        self.step(0x06095E6C);self.t(r['r0']==0)
        self.step(0x06095E6E)
        self.step(0x06095E70,True);r['r13']=r['r4']
        if not r['r0']:raise ValueError('Null record table/service path unresolved')
        self.step(0x06095E72);self.t(records.signed(r['r13'],32)>=0)
        self.step(0x06095E74);valid=bool(r['sr']&1)
        if valid:
            self.step(0x06095E76);r['r0']=self.read(r['r14']+12,4)
            self.step(0x06095E78);self.t(records.signed(r['r13'],32)>=records.signed(r['r0'],32))
            self.step(0x06095E7A);valid=not bool(r['sr']&1)
        if not valid:
            self.report_error(0x06095E7C,-10)
            self.step(0x06095E80);self.step(0x06095E82,True);r['r0']=0
            self.finish();return
        self.step(0x06095E84);r['pr']=0x06095E88
        self.step(0x06095E86,True);self.select()
        self.step(0x06095E88);r['r12']=r['r0']
        self.step(0x06095E8A);self.t(r['r12']==0)
        self.step(0x06095E8C)
        if r['sr']&1:
            self.report_error(0x06095E8E,-19)
            self.step(0x06095E92);self.step(0x06095E94,True);r['r0']=0
            self.finish();return
        self.step(0x06095E96);r['r1']=self.read(r['r14']+8,4)
        self.step(0x06095E98);self.t(r['r1']==0)
        self.step(0x06095E9A)
        if not r['r1']:raise ValueError('Null record setup not modeled')
        self.step(0x06095EA0);r['r0']=self.read(r['r14'],4)
        self.step(0x06095EA2);self.t(r['r0']==0)
        self.step(0x06095EA4);wide=not bool(r['sr']&1)
        if wide:
            self.step(0x06095EB2);r['r5']=self.read(r['r14']+8,4)
            self.step(0x06095EB4);r['r3']=self.read(0x06095F00,4)
            self.step(0x06095EB6);r['pr']=0x06095EBA
            self.step(0x06095EB8,True);r['r4']=r['r13']
            self.index(True)
        else:
            self.step(0x06095EA6);r['r5']=self.read(r['r14']+8,4)
            self.step(0x06095EA8);r['r3']=self.read(0x06095EFC,4)
            self.step(0x06095EAA);r['pr']=0x06095EAE
            self.step(0x06095EAC,True);r['r4']=r['r13']
            self.index(False)
            self.step(0x06095EAE);self.step(0x06095EB0,True)
        self.step(0x06095EBA);r['r5']=r['r0']
        self.step(0x06095EBC);r['r6']=r['r13']
        self.step(0x06095EBE);r['pr']=0x06095EC2
        self.step(0x06095EC0,True);r['r4']=r['r12']
        self.complete_caller()
        self.step(0x06095EC2);r['r14']=r['r0']
        self.step(0x06095EC4);self.t(r['r14']==0)
        self.step(0x06095EC6)
        if not r['sr']&1:raise ValueError('Successful context/service result unresolved')
        self.report_error(0x06095EC8,-10)
        self.step(0x06095ECC);self.step(0x06095ECE,True)
        self.step(0x06095EDE);r['r0']=r['r14']
        self.finish()


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown original-open error family')
    rows=[]
    if family.startswith('record'):
        for v,flag,length,index,free in itertools.product(range(2),(0,8,16,24,64,128,152,255),
             (0,1,2047,2048,2049,4095,0x7FFFFFFF,0x80000000,MASK),(0,23),(0,23)):
            rows.append((family,v,37,0,24,(1<<free)-1,index,flag,length))
        rows += [(family,v,37,0,24,0,0,flag,2049) for v,flag in itertools.product(range(2),range(256))]
        rows += [(family,v,37,0,24,(1<<free)-1,index,flag,2049) for v,free,index,flag in
                 itertools.product(range(2),range(24),(0,23),(0,128,255))]
        rows += [(family,v,seed,s,24,(1<<free)-1,index,flag,2049) for v,seed,s,free,index,flag in
                 itertools.product(range(2),(0,255),STATUSES,(0,23),(0,23),(0,128,255))]
        rows += [(family,v,37,s,count,mask,19,flag,2049) for v,s,count,mask,flag in
                 itertools.product(range(2),(0,(-16)&MASK,0x80000000),(MASK,MASK-1,0x80000000),
                                   (0,0xFFFFFF),(0,128))]
    elif family=='invalid-index':
        rows=[(family,v,seed,s,count,mask,index,255,2049) for v,seed,s,count,mask,index in
              itertools.product(range(2),(0,255),STATUSES,(0,1,24,MASK),(0,0xFFFFFF),
                                (MASK,MASK-1,0x80000000,24,25,0x7FFFFFFF))]
    else:
        rows=[(family,v,seed,s,count,0xFFFFFF,0,255,2049) for v,seed,s,count in
              itertools.product(range(2),(0,37,255),STATUSES,range(25))]
    return list(dict.fromkeys(rows))


def contract(data,case):
    family,v,seed,global_status,count,mask,index,flag,length=case
    if (family not in FAMILIES or type(v) is not int or v not in (0,1) or type(seed) is not int or seed not in (0,37,255) or
        any(type(x) is not int or not 0<=x<=MASK for x in (global_status,count,mask,index,flag,length)) or
        count not in (*range(25),MASK,MASK-1,0x80000000) or mask>0xFFFFFF or flag>255):
        raise ValueError('Outside callback-null/nonnull-table/open-error contract')
    valid=0<=records.signed(index,32)<24
    free=(0 if records.signed(count,32)<0 else next((i for i in range(count) if not mask>>i&1),None))
    if ((family=='invalid-index')==valid or family=='no-slot' and free is not None or
        family.startswith('record') and free is None):raise ValueError('Selection does not match declared error branch')
    mode=(1,0x80000000,MASK)[(0,37,255).index(seed)] if family=='record24' else 0 if family=='record12' else v
    stride=24 if mode else 12
    block=0x060D0000+v*0x2000;table=0x060D4000+v*0x2000;pool=0x060D8000+v*0x2000
    before=records.initial(ENTRY,index,v);before['r15']-=0x100+v*0x1000
    canary=lambda n:bytes((seed+37*i)&255 for i in range(n))
    body=bytearray(canary(SIZE));body[:4]=count.to_bytes(4,'big')
    for offset,value in ((0x98,mode),(0xA0,table),(0xA4,24),(0xB8,0)):
        body[offset:offset+4]=value.to_bytes(4,'big')
    marker=(1,0x80000000,MASK)[(0,37,255).index(seed)]
    for i in range(24):body[slots.OFFSET+i*slots.STRIDE:slots.OFFSET+i*slots.STRIDE+4]=(marker if mask>>i&1 else 0).to_bytes(4,'big')
    entries=bytearray(canary(24*stride))
    for i in range(24):
        descriptor=(((0xDEADBEEF if v else 0x12345678)^(i*0x01010101))&MASK).to_bytes(4,'big')+length.to_bytes(4,'big')+bytes([255^i,128^i,(0x55 if v else 0xAA)^i,flag])
        entries[i*stride:i*stride+12]=descriptor
    descriptor=bytes(entries[(index if valid else 0)*stride:(index if valid else 0)*stride+12])
    table_bytes=bytes([1 if seed==0 else 128 if seed==37 else 255])*24+canary(24)
    sp=before['r15'];depth=100 if family.startswith('record') else 28
    regions=[(block-16,canary(16),False),(block,bytes(body),True),(block+SIZE,canary(16),False),
             (table-16,canary(16),False),(table,bytes(entries),False),(table+len(entries),canary(16),False),
             (pool-16,canary(16),False),(pool,table_bytes,False),(pool+48,canary(16),False),
             (status.CELL-16,canary(16),False),(status.CELL,block.to_bytes(4,'big'),False),(status.CELL+4,canary(16),False),
             (status.STATUS_WORD-16,canary(16),False),(status.STATUS_WORD,global_status.to_bytes(4,'big')+pool.to_bytes(4,'big'),False),
             (status.STATUS_WORD+8,canary(16),False),(sp-160,canary(160-depth),False),
             (sp-depth,canary(depth),True),(sp,canary(64),False)]
    shorts={**record.SHORTS,**record.arithmetic.SHORTS,**status.HALFWORDS,**slots.HALFWORDS,**SHORTS}
    for a,value in shorts.items():
        raw=data[a-pinned.BASE:a-pinned.BASE+2]
        if raw!=value.to_bytes(2,'big'):raise ValueError('Original open/dependency literal changed')
        regions.append((a,raw,False))
    m=Model(before,[(lo,buf) for lo,buf,_ in regions]);m.open();scalar=body[:]
    error=-10 if not valid or free is not None else -19
    effective=status.effective(global_status,error&MASK);scalar[0xC0:0xC4]=effective.to_bytes(4,'big')
    expected_mac=before['macl']
    if valid and free is not None:
        start=slots.OFFSET+free*slots.STRIDE;scalar[start:start+4]=(1).to_bytes(4,'big')
        for offset in (*range(0,20,4),24,28,32,36,40,52):scalar[start+108+offset:start+112+offset]=bytes(4)
        for offset,value in ((20,1),(44,1),(56,3)):scalar[start+108+offset:start+112+offset]=value.to_bytes(4,'big')
        effective_length=(record.arithmetic.scalar((length+2047)&MASK,2048)[0]*2048)&MASK if flag&128 else length
        fmt=2352 if flag&64 else (0 if flag&8 else 2324) if flag&16 else 2048
        for offset,value in ((0,index),(4,int.from_bytes(descriptor[:4],'big')),(8,effective_length),(16,fmt),
             (20,((effective_length+2047)&MASK)>>11),(24,(-effective_length)&2047 if fmt else 0),
             (28,0),(52,1),(56,MASK),(60,0),(64,0),(68,0),(72,0)):
            scalar[start+12+offset:start+16+offset]=value.to_bytes(4,'big')
        scalar[start+24:start+28]=descriptor[8:12]
        scalar[start+56:start+62]=bytes([descriptor[10],0,0,0,0,0])
        if flag&128:expected_mac=effective_length
    if (m.buffers[1]!=scalar or m.reg['r0']!=0 or m.reg['pc']!=before['pr'] or m.reg['r15']!=before['r15'] or
        m.reg['macl']!=expected_mac or m.reg['sr']&1!=1):raise ValueError('Independent scalar open error/side-effect contract differs')
    for i,(_,buf,write) in enumerate(regions):
        if not write and bytes(m.buffers[i])!=buf:raise ValueError('Expected open model modified readonly source/canary')
    return m,regions


def observe(data,emu,family,before,regions,*,short_refusal=False):
    ranges=((ENTRY,0x06095EEA),(slots.SELECT,slots.RELEASE),(status.STATUS,0x06096CB0))
    if family.startswith('record'):
        ranges+=((record.setup.INDEX12,0x060A56E8),(record.setup.INIT,0x060A5F32),
            (record.setup.CALLER,0x06096DB2),(record.ENTRY,0x060A689E),(0x060A68B8,0x060A6902),
            (record.arithmetic.QUOTIENT,0x060941B6),(record.arithmetic.REMAINDER,0x06094326),
            (record.arithmetic.FORMAT,0x060A6DB2),(0x060A6DC4,0x060A6DE6),
            (record.pools.CONTEXT,0x060A7048),(0x060A70B2,0x060A70BC),
            (record.pools.COPY,0x060945EC),(record.pools.ALLOC0,0x060A780A))
    longs={**LONGS,**record.LONGS,**record.arithmetic.LONGS,**record.pools.LITERALS,
           **record.setup.LITERALS,**status.LITERALS,0x06096BE0:status.CELL}
    profile=slots.short if short_refusal else longer
    return profile.observe(data,emu,ENTRY,regions,before,ranges=ranges,literals=tuple(longs),aliases=(),
                           terminals={before['pr']:'returned'},budget=128 if short_refusal else 1024)


def run_case(data,emu,case):
    m,r=contract(data,case);a=observe(data,emu,case[0],m.before,r);reason=None
    if a['status']!='returned':reason='Original95E5A error return failed: '+str(a['error'])
    elif a['registers']!=m.reg:reason='Open error register/PC/SR/PR/MAC differs'
    elif a['trace']!=m.trace or a['steps']!=len(m.trace):reason='Open error original PC/delay path differs'
    elif a['events']!=m.events:reason='Open error ordered transactions differ'
    elif a['regions_after']!=[bytes(b) for b in m.buffers] or not a['original_unaffected_bytes_equal']:reason='Open error memory/source/canaries differ'
    if reason:raise record.pools.task.CaseFailure(reason,case,a)
    return {'case':list(case),'status':'returned','instructions':a['steps'],'after_registers':a['registers'],
            'trace':a['trace'],'data_events':a['events'],'regions_after_sha256':[pinned.digest(b) for b in a['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    selected=cases(family);rows=[]
    for c in selected:
        try:rows.append(run_case(data,emu,c))
        except record.pools.task.CaseFailure as e:e.completed_results=rows;raise
    positive={'cases':len(rows),'complete_returns':len(rows),'results':rows,'original_game_bytes_executed':True,
              'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode())}
    mutations=[('lost-library-error-store',0x06096C96,9),('lost-root-R14-delay',0x06095EE8,9)]
    if family=='invalid-index':mutations += [('wrong-invalid-code-delay',0x06095E7E,0xE4F5)]
    elif family=='no-slot':mutations += [('wrong-exhausted-code-delay',0x06095E90,0xE4EC)]
    else:mutations += [('lost-selected-marker',0x06096BC8,9),('lost-slot-argument-delay',0x06095EC0,9),
            ('lost-record-length-store',0x060A686C,9),('lost-failure-code-delay',0x06095ECA,0xE4F5),
            ('lost-index-multiplier',record.setup.INDEX24+10 if family=='record24' else record.setup.INDEX12+8,9)]
    chosen=list(dict.fromkeys(selected[:16]+selected[::max(1,len(selected)//64)]+selected[-16:]));controls={}
    for name,pc,word in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=word.to_bytes(2,'big');count=0;first=None
        for c in chosen:
            try:run_case(changed,emu,c)
            except record.pools.task.CaseFailure as e:
                fault=e.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=e.evidence
        if not count:raise record.arithmetic.EvidenceFailure('Missing95E5A semantic control: '+name,{**positive,'instruction_controls':controls})
        controls[name]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,'mutated_kernel_sha256':pinned.digest(changed)}
    result={**positive,'instruction_controls':controls}
    if family!='invalid-index':
        c=max(selected,key=lambda c:len(contract(data,c)[0].trace));m,r=contract(data,c);a=observe(data,emu,family,m.before,r,short_refusal=True)
        if a['status']!='failed' or not a['error'] or 'budget exceeded' not in a['error']['reason']:
            raise record.arithmetic.EvidenceFailure('Missing original128 open refusal',result)
        refusal={k:v for k,v in a.items() if k!='regions_after'};refusal['regions_after_sha256']=[pinned.digest(b) for b in a['regions_after']]
        result['short128_refusal']=refusal
    return {**result,'instruction_controls':controls}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,required=True);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-library-open-errors.v1','status':'failure','selection':args.family,
      'kernel_sha256':pinned.KERNEL_SHA256,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,
      'lifetime':'resident-kernel','original_game_bytes_executed':False,'interpreter_revision':pinned.INTERPRETER_REVISION,
      'interpreter_sources':pinned.SOURCE_HASHES,'programme_status':'active; incomplete',
      'source_sha256':{Path(p).name:pinned.digest(Path(p).read_bytes()) for p in (__file__,record.__file__,status.__file__,slots.__file__,records.__file__,pinned.__file__,slots.short.__file__,longer.__file__)},
      'limitations':['Constructed nonnull record table,callbacknull and exhausted contextpool; only selected complete error paths',
         'Actual nested selection/index/initializer/record/arithmetic/format/context/copy/pool/status calls; no substituted returns',
         'Successful95E5A/contextservices,nullrecord/A7F4E,callbacks/full89C8 and all-program/hardware/gameplay/Godot parity unresolved']}
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
            if isinstance(e,record.arithmetic.EvidenceFailure):report.update(e.partial)
            if isinstance(e,record.pools.task.CaseFailure):report.update(failure_evidence=e.evidence,original_game_bytes_executed=True,completed_before_failure=getattr(e,'completed_results',[]))
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
