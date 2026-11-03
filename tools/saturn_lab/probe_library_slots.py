#!/usr/bin/env python3
"""Original96B9C slot selection and96BCE marker release; constructed high RAM."""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_library_tables as tables

pinned,records,short,longer = tables.pinned,tables.records,tables.short,tables.longer
SELECT,RELEASE,CELL = 0x06096B9C,0x06096BCE,tables.CELL
MASK,MAX_COUNT,STRIDE,OFFSET = 0xFFFFFFFF,24,0xA8,0xC60
HALFWORDS = {0x06096BD6:OFFSET,0x06096BD8:STRIDE}
FAMILIES = ('select','release')


class Model(records.Model):
    def read(self,address,size):
        if size==4 and address==0x06096BE0:value=CELL
        elif size==2 and address in HALFWORDS:value=HALFWORDS[address]
        else:return super().read(address,size)
        self.events.append([1,address,size,value]);return value

    def select(self):
        r=self.reg
        self.step(SELECT);r['r3']=self.read(0x06096BE0,4)
        self.step(SELECT+2);r['r7']=0
        self.step(SELECT+4);r['r4']=self.read(0x06096BD6,2)
        self.step(SELECT+6);r['r6']=self.read(r['r3'],4)
        self.step(SELECT+8);r['r4']+=r['r6']
        self.step(SELECT+10)
        self.step(SELECT+12,True);r['r5']=r['r7']
        while True:
            self.step(0x06096BB6);r['r3']=self.read(r['r6'],4)
            self.step(0x06096BB8);self.t(records.signed(r['r5'],32)>=records.signed(r['r3'],32))
            self.step(0x06096BBA)
            if r['sr']&1:break
            self.step(0x06096BAA);r['r0']=self.read(r['r4'],4)
            self.step(0x06096BAC);self.t(r['r0']==0)
            self.step(0x06096BAE)
            if r['sr']&1:break
            self.step(0x06096BB0);r['r2']=self.read(0x06096BD8,2)
            self.step(0x06096BB2);r['r5']+=1
            self.step(0x06096BB4);r['r4']+=r['r2']
        self.step(0x06096BBC);r['r1']=self.read(r['r6'],4)
        self.step(0x06096BBE);self.t(r['r1']==r['r5'])
        self.step(0x06096BC0)
        if r['sr']&1:
            self.step(0x06096BC2)
            self.step(0x06096BC4,True);r['r4']=r['r7']
        else:
            self.step(0x06096BC6);r['r3']=1
            self.step(0x06096BC8);self.write(r['r4'],4,r['r3'])
        self.step(0x06096BCA)
        self.step(0x06096BCC,True);r['r0']=r['r4']
        r['pc']=r['pr']

    def release(self):
        r=self.reg
        self.step(RELEASE);r['r3']=0
        self.step(RELEASE+2)
        self.step(RELEASE+4,True);self.write(r['r4'],4,r['r3'])
        r['pc']=r['pr']


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown slot family')
    rows=[]
    for variant,seed in itertools.product(range(2),(0,37,255)):
        if family=='release':
            rows += [(family,variant,seed,index,value) for index,value in itertools.product(range(24),(0,1,MASK))]
            continue
        for count in range(25):
            active=(1<<count)-1;tail=0xAAAAAA & ~active
            for free in range(count+1):
                used=active if free==count else active ^ (1<<free)
                rows.append((family,variant,seed,count,tail|used))
        rows += [(family,variant,seed,8,(0xAAAAAA & ~255)|mask) for mask in range(256)]
        rows += [(family,variant,seed,count,mask) for count,mask in itertools.product(
            (MASK,MASK-1,0x80000000),(0,0xFFFFFF,0xAAAAAA))]
    return list(dict.fromkeys(rows))


def contract(data,case):
    family,variant,seed,a,b=case
    if family not in FAMILIES:raise ValueError('Unknown slot family')
    if (type(variant) is not int or variant not in (0,1) or type(seed) is not int or seed not in (0,37,255) or
            type(a) is not int or type(b) is not int or not 0<=b<=MASK or
            family=='select' and (a not in (*range(25),MASK,MASK-1,0x80000000) or b>0xFFFFFF) or
            family=='release' and not 0<=a<24):
        raise ValueError('Outside explicit bounded slot contract')
    block=tables.BLOCK+variant*0x2000
    before=records.initial(SELECT if family=='select' else RELEASE,
                           0xDEADBEEF if family=='select' else block+OFFSET+a*STRIDE,variant)
    before['r15']-=0x100+variant*0x1000
    canary=lambda n:bytes((seed+37*i)&255 for i in range(n))
    body=bytearray(canary(tables.BLOCK_SIZE))
    body[:4]=(a if family=='select' else 24).to_bytes(4,'big')
    if family=='select':
        marker=(1,0x80000000,MASK)[(0,37,255).index(seed)]
        for i in range(24):body[OFFSET+i*STRIDE:OFFSET+i*STRIDE+4]=(marker if b>>i&1 else 0).to_bytes(4,'big')
    else:body[OFFSET+a*STRIDE:OFFSET+a*STRIDE+4]=b.to_bytes(4,'big')
    sp=before['r15']
    regions=[(CELL-16,canary(16),False),(CELL,block.to_bytes(4,'big'),False),(CELL+4,canary(16),False),
             (block-16,canary(16),False),(block,bytes(body),True),(block+len(body),canary(16),False),
             (sp-64,canary(128),False)]
    for address,value in HALFWORDS.items():
        raw=data[address-pinned.BASE:address-pinned.BASE+2]
        if raw!=value.to_bytes(2,'big'):raise ValueError('Original slot offset/stride literal differs')
        regions.append((address,raw,False))
    model=Model(before,[(lo,buf) for lo,buf,_ in regions]);getattr(model,family)()
    scalar=body[:]
    if family=='release':scalar[OFFSET+a*STRIDE:OFFSET+a*STRIDE+4]=bytes(4)
    else:
        count=records.signed(a,32)
        free=0 if count<0 else next((i for i in range(count) if not b>>i&1),None)
        if free is not None:scalar[OFFSET+free*STRIDE:OFFSET+free*STRIDE+4]=(1).to_bytes(4,'big')
        expected=0 if free is None else block+OFFSET+free*STRIDE
        if model.reg['r0']!=expected:raise ValueError('Independent scalar slot result differs')
    if model.buffers[4]!=scalar:raise ValueError('Independent scalar slot memory differs')
    return model,regions


def observe(data,emu,family,before,regions,*,short_refusal=False):
    profile=longer if family=='select' and not short_refusal else short
    return profile.observe(data,emu,before['pc'],regions,before,
        ranges=((SELECT,0x06096BCE),) if family=='select' else ((RELEASE,RELEASE+6),),
        literals=(0x06096BE0,),aliases=(),terminals={before['pr']:'returned'},
        budget=256 if profile is longer else 128)


def run_case(data,emu,case):
    model,regions=contract(data,case);actual=observe(data,emu,case[0],model.before,regions)
    reason=None
    if actual['status']!='returned':reason='Original slot function failed: '+str(actual['error'])
    elif actual['registers']!=model.reg:reason='Slot register/PC/SR/PR/MAC differs'
    elif actual['trace']!=model.trace or actual['steps']!=len(model.trace):reason='Slot PC/delay trace differs'
    elif actual['events']!=model.events:reason='Slot transactions differ'
    elif actual['regions_after']!=[bytes(buf) for buf in model.buffers] or not actual['original_unaffected_bytes_equal']:
        reason='Slot memory/canaries/other original bytes differ'
    if reason:raise tables.task.CaseFailure(reason,case,actual)
    return {'case':list(case),'status':'returned','instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],
            'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    selected=cases(family);rows=[run_case(data,emu,case) for case in selected]
    mutations=([('lost-zero-marker-write',0x06096BC8,9),('changed-used-marker',0x06096BC6,0xE302),
                ('lost-full-null-delay',0x06096BC4,9),('changed-used-slot-stride',0x06096BB4,0x7404),
                ('lost-result-delay',0x06096BCC,9)] if family=='select' else
               [('changed-clear-value',RELEASE,0xE301),('lost-clear-delay',RELEASE+4,9)])
    chosen=selected[::max(1,len(selected)//64)];controls={}
    for name,pc,word in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=word.to_bytes(2,'big')
        count,first=0,None
        for case in chosen:
            try:run_case(changed,emu,case)
            except tables.task.CaseFailure as error:
                fault=error.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=error.evidence
        if not count:raise ValueError('No non-budget slot mutation rejection: '+name)
        controls[name]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first}
    result={'cases':len(rows),'complete_returns':len(rows),'results':rows,'instruction_controls':controls,
            'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'original_game_bytes_executed':True}
    if family=='select':
        case=next(case for case in selected if case[3:]==(24,0xFFFFFF))
        model,regions=contract(data,case);actual=observe(data,emu,family,model.before,regions,short_refusal=True)
        if actual['status']!='failed' or not actual['error'] or 'budget exceeded' not in actual['error']['reason']:
            raise ValueError('Original128 short refusal not retained')
        result['short128_refusal']={k:v for k,v in actual.items() if k!='regions_after'}
        result['short128_refusal']['regions_after_sha256']=[pinned.digest(buf) for buf in actual['regions_after']]
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-library-slot-contracts.v1','status':'failure','selection':args.family,
            'kernel_sha256':pinned.KERNEL_SHA256,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2',
            'load_address':pinned.BASE,'lifetime':'resident-kernel','original_game_bytes_executed':False,
            'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,
            'source_sha256':{Path(p).name:pinned.digest(Path(p).read_bytes()) for p in
                (__file__,tables.__file__,tables.task.__file__,records.__file__,pinned.__file__,short.__file__,longer.__file__)},
            'programme_status':'active; incomplete','limitations':['Constructed slot tables/stack; no natural96B9C interior trace yet',
                 'Counts0..24 and three signed-negative adversarial values; larger positive counts not accepted',
                 'No callback/BIOS/MMIO; full95E5A/89C8 semantics and hardware/gameplay parity unresolved']}
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
            if isinstance(error,tables.task.CaseFailure):report['failure_evidence']=error.evidence;report['original_game_bytes_executed']=True
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
