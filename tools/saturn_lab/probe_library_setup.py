#!/usr/bin/env python3
"""Original context initialization, field stores, index arithmetic and96D74 prefix.

OriginalA681A is an explicit unfinished handoff, never a substituted return.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_task_init as task

pinned,records,guard=task.pinned,task.records,task.short
MASK=0xFFFFFFFF
INIT,FIELD56,FIELD44=0x060A5EEC,0x060A5F22,0x060A5F2E
INDEX12,INDEX24,CALLER,TARGET=0x060A56CA,0x060A56D8,0x06096D74,0x060A681A
ENTRIES={'init':INIT,'field56':FIELD56,'field44':FIELD44,'index12':INDEX12,'index24':INDEX24,
         'caller-null':CALLER,'caller-prefix':CALLER}
FAMILIES=tuple(ENTRIES)
LITERALS={0x06096E24:INIT,0x06096E28:TARGET}
WIDE=(0x100,0xFFFF,0x80000000,0x7FFFFFFF,MASK,0xDEADBEEF,0x12345678)


class EvidenceFailure(ValueError):
    def __init__(self,reason,partial):
        super().__init__(reason);self.partial=partial


class Model(records.Model):
    def read(self,address,size):
        if size==4 and address in LITERALS:
            value=LITERALS[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def field56(self):
        r=self.reg
        self.step(FIELD56);r['r0']=self.read(r['r4']+56,4)
        self.step(FIELD56+2);self.write(r['r4']+56,4,r['r5'])
        self.step(FIELD56+4);r['r5']=0
        self.step(FIELD56+6);self.write(r['r4']+36,4,0)
        self.step(FIELD56+8)
        self.step(FIELD56+10,True);self.write(r['r4']+40,4,0)
        r['pc']=r['pr']

    def field44(self):
        self.step(FIELD44)
        self.step(FIELD44+2,True);self.write(self.reg['r4']+44,4,self.reg['r5'])
        self.reg['pc']=self.reg['pr']

    def init(self):
        r=self.reg
        self.step(INIT);self.push(r['r14'])
        self.step(INIT+2);r['r3']=1
        self.step(INIT+4);self.push(r['r13'])
        self.step(INIT+6);r['r14']=r['r4']
        self.step(INIT+8);self.push(r['pr'])
        self.step(INIT+10);r['r13']=0
        self.step(INIT+12);self.write(r['r14'],4,0)
        self.step(INIT+14);r['r5']=1
        for pc,offset,value in ((0x060A5EFC,4,0),(0x060A5EFE,8,0),(0x060A5F00,12,0),
                                (0x060A5F02,16,0),(0x060A5F04,20,1),(0x060A5F06,24,0),
                                (0x060A5F08,28,0),(0x060A5F0A,32,0)):
            self.step(pc);self.write(r['r14']+offset,4,value)
        self.step(0x060A5F0C);r['pr']=0x060A5F10
        self.step(0x060A5F0E,True);r['r4']=r['r14']
        self.field44()
        self.step(0x060A5F10);self.write(r['r14']+52,4,0)
        self.step(0x060A5F12);r['r5']=3
        self.step(0x060A5F14);r['pr']=0x060A5F18
        self.step(0x060A5F16,True);r['r4']=r['r14']
        self.field56()
        self.step(0x060A5F18);r['pr']=self.pop()
        self.step(0x060A5F1A);r['r0']=r['r14']
        self.step(0x060A5F1C);r['r13']=self.pop()
        self.step(0x060A5F1E)
        self.step(0x060A5F20,True);r['r14']=self.pop()
        r['pc']=r['pr']

    def index(self,wide):
        r=self.reg;pc=INDEX24 if wide else INDEX12
        self.step(pc);r['r0']=r['r4']
        self.step(pc+2);r['r3']=r['r4']
        self.step(pc+4);self.t(r['r0']>>31);r['r0']=(r['r0']*2)&MASK
        self.step(pc+6);r['r0']=(r['r0']+r['r3'])&MASK
        self.step(pc+8);r['r0']=(r['r0']*4)&MASK
        if wide:
            self.step(pc+10);self.t(r['r0']>>31);r['r0']=(r['r0']*2)&MASK
        self.step(pc+(12 if wide else 10))
        self.step(pc+(14 if wide else 12),True);r['r0']=(r['r0']+r['r5'])&MASK
        r['pc']=r['pr']

    def caller(self):
        r=self.reg
        self.step(CALLER);self.push(r['r14'])
        self.step(CALLER+2);r['r14']=r['r4']
        self.step(CALLER+4);self.push(r['pr'])
        self.step(CALLER+6);self.t(r['r14']==0)
        self.step(CALLER+8);r['r15']-=8
        self.step(CALLER+10);self.write(r['r15'],4,r['r5'])
        self.step(CALLER+12);self.write(r['r15']+4,4,r['r6'])
        self.step(CALLER+14)
        if r['sr']&1:
            self.step(0x06096D84);r['r0']=0
            self.step(0x06096D86);r['r15']+=8
            self.step(0x06096D88);r['pr']=self.pop()
            self.step(0x06096D8A)
            self.step(0x06096D8C,True);r['r14']=self.pop()
            r['pc']=r['pr'];return
        self.step(0x06096D8E);r['r4']=r['r14']
        self.step(0x06096D90);r['r3']=self.read(0x06096E24,4)
        self.step(0x06096D92);r['pr']=0x06096D96
        self.step(0x06096D94,True);r['r4']+=108
        self.init()
        self.step(0x06096D96);r['r4']=r['r14']
        self.step(0x06096D98);r['r3']=self.read(0x06096E28,4)
        self.step(0x06096D9A);r['r6']=self.read(r['r15']+4,4)
        self.step(0x06096D9C);r['r5']=self.read(r['r15'],4)
        self.step(0x06096D9E);r['pr']=0x06096DA2
        self.step(0x06096DA0,True);r['r4']+=12
        r['pc']=TARGET


def cases(family):
    if family not in ENTRIES:raise ValueError('Unknown setup family')
    if family.startswith('index'):
        indices=(*range(256),0x15555555,0x15555556,0x2AAAAAAA,0x2AAAAAAB,0x3FFFFFFF,
                 0x40000000,0x7FFFFFFF,0x80000000,MASK)
        return [(family,v,0,index,base) for v,index,base in itertools.product(
            range(2),indices,(0,1,0x060BF198,0x80000000,MASK))]
    if family.startswith('caller'):
        return [(family,v,s,a,b) for v,s,a,b in itertools.product(range(2),(0,37,255),
            (0,1,0x060BF198,0x80000000,MASK),(0,1,16,24,25,0x80000000,MASK))]
    rows=[(family,v,s,value,(0,MASK,0x80000000)[(0,37,255).index(s)])
          for v,s,value in itertools.product(range(2),(0,37,255),(*range(256),*WIDE))]
    if family=='field56':
        rows += [(family,v,37,value,old) for v,value,old in itertools.product(
            range(2),(0,1,MASK,0x80000000,0x12345678),(0,1,MASK,0x7FFFFFFF,0x80000000,0xDEADBEEF))]
    return list(dict.fromkeys(rows))


def contract(case):
    family,variant,seed,a,b=case
    if (family not in ENTRIES or type(variant) is not int or variant not in (0,1) or
            type(seed) is not int or seed not in (0,37,255) or
            any(type(value) is not int or not 0<=value<=MASK for value in (a,b))):
        raise ValueError('Outside declared setup contract')
    block=0x060D0000+variant*0x2000
    arg=a if family.startswith('index') else 0 if family=='caller-null' else block
    before=records.initial(ENTRIES[family],arg,variant);before['r15']-=0x100+variant*0x1000
    before['r5']=b if family.startswith('index') else a
    if family.startswith('caller'):before['r6']=b
    canary=lambda n:bytes((seed+37*i)&255 for i in range(n))
    caller=family.startswith('caller');size=168 if caller else 60
    body=bytearray(canary(size));old_offset=44 if family=='field44' else 56
    if not caller:body[old_offset:old_offset+4]=b.to_bytes(4,'big')
    depth=28 if family=='caller-prefix' else 16 if family=='caller-null' else 12 if family=='init' else 0
    sp=before['r15'];write=family in ('init','field56','field44','caller-prefix')
    regions=[(block-16,canary(16),False),(block,bytes(body),write),(block+size,canary(16),False),
             (sp-64,canary(64-depth),False)]
    if depth:regions.append((sp-depth,canary(depth),True))
    regions.append((sp,canary(64),False))
    model=Model(before,[(lo,buf) for lo,buf,_ in regions])
    if family.startswith('index'):model.index(family=='index24')
    elif caller:model.caller()
    else:getattr(model,family)()
    expected=[buf for _,buf,_ in regions];scalar=body[:]
    if family in ('init','caller-prefix'):
        start=108 if caller else 0
        for offset in (*range(0,20,4),24,28,32,36,40,52):scalar[start+offset:start+offset+4]=bytes(4)
        for offset,value in ((20,1),(44,1),(56,3)):scalar[start+offset:start+offset+4]=value.to_bytes(4,'big')
    elif family=='field56':
        scalar[56:60]=a.to_bytes(4,'big');scalar[36:44]=bytes(8)
    elif family=='field44':scalar[44:48]=a.to_bytes(4,'big')
    expected[1]=bytes(scalar)
    if depth:
        words=((0x06096D96,before['r13'],block,a,b,before['pr'],before['r14']) if family=='caller-prefix' else
               (a,b,before['pr'],before['r14']) if family=='caller-null' else
               (before['pr'],before['r13'],before['r14']))
        expected[4]=b''.join(value.to_bytes(4,'big') for value in words)
    if expected!=[bytes(buf) for buf in model.buffers]:raise ValueError('Independent scalar setup memory/stack differs')
    result=((12 if family=='index12' else 24)*a+b)&MASK if family.startswith('index') else (
        block+108 if family=='caller-prefix' else 0 if family=='caller-null' else block if family=='init'
        else b if family=='field56' else before['r0'])
    if model.reg['r0']!=result:raise ValueError('Independent scalar setup result differs')
    return model,regions


def observe(data,emu,family,before,regions):
    ranges=(((INDEX12,INDEX24),) if family=='index12' else ((INDEX24,0x060A56E8),) if family=='index24' else
            ((FIELD56,FIELD44),) if family=='field56' else ((FIELD44,0x060A5F32),) if family=='field44' else
            ((INIT,0x060A5F32),))
    if family.startswith('caller'):ranges+=((CALLER,0x06096DA2),)
    return guard.observe(data,emu,before['pc'],regions,before,ranges=ranges,literals=tuple(LITERALS),
                         aliases=(),terminals={before['pr']:'returned',TARGET:'handoff'},budget=64)


def run_case(data,emu,case):
    model,regions=contract(case);actual=observe(data,emu,case[0],model.before,regions)
    status='handoff' if case[0]=='caller-prefix' else 'returned';reason=None
    if actual['status']!=status:reason='Setup missed original boundary: '+str(actual['error'])
    elif actual['registers']!=model.reg:reason='Setup register/PC/SR/PR/MAC differs'
    elif actual['trace']!=model.trace or actual['steps']!=len(model.trace):reason='Setup original PC/delay trace differs'
    elif actual['events']!=model.events:reason='Setup ordered transactions differ'
    elif actual['regions_after']!=[bytes(buf) for buf in model.buffers] or not actual['original_unaffected_bytes_equal']:
        reason='Setup output/stack/canaries/other original bytes differ'
    if reason:raise task.CaseFailure(reason,case,actual)
    return {'case':list(case),'status':status,'instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],
            'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    selected=cases(family);rows=[]
    if not selected:raise ValueError('Require nonempty original selection')
    for case in selected:
        try:rows.append(run_case(data,emu,case))
        except task.CaseFailure as error:
            error.completed_results=rows
            raise
    positive={'cases':len(rows),'complete_returns':sum(r['status']=='returned' for r in rows),
              'unfinished_handoffs':sum(r['status']=='handoff' for r in rows),'results':rows,
              'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
              'original_game_bytes_executed':True}
    mutations={'init':(('lost-default20',0x060A5F04,9),('lost-field44-delay',FIELD44+2,9),
                       ('lost-clear40-delay',FIELD56+10,9),('lost-state52',0x060A5F10,9),('lost-R14-delay',0x060A5F20,9)),
        'field56':(('lost-field56',FIELD56+2,9),('lost-clear36',FIELD56+6,9),
                   ('lost-clear40-delay',FIELD56+10,9),('wrong-old-field',FIELD56,0x504D)),
        'field44':(('lost-store-delay',FIELD44+2,9),('wrong-store-source',FIELD44+2,0x143B)),
        'caller-null':(('lost-null-result',0x06096D84,9),('lost-R14-delay',0x06096D8C,9)),
        'caller-prefix':(('lost-context-offset-delay',0x06096D94,9),('lost-descriptor-reload',0x06096D9C,9),
                         ('wrong-argument-offset-delay',0x06096DA0,0x7410),('lost-saved-root-PR',0x06096D78,9))}
    if family.startswith('index'):
        entry=ENTRIES[family];delay=entry+(12 if family=='index12' else 14)
        selected_mutations=(('lost-times4',entry+8,9),('wrong-index-addend',entry+2,0x6353),('lost-base-delay',delay,9))
    else:selected_mutations=mutations[family]
    chosen=list(dict.fromkeys(selected[:16]+selected[::max(1,len(selected)//48)]+selected[-16:]));controls={}
    for name,pc,word in selected_mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=word.to_bytes(2,'big')
        count,first=0,None
        for case in chosen:
            try:run_case(changed,emu,case)
            except task.CaseFailure as error:
                fault=error.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=error.evidence
        if not count:
            raise EvidenceFailure('No non-budget setup mutation rejection: '+name,
                {**positive,'instruction_controls':controls,'failed_control':{'name':name,'pc':pc,'tested':len(chosen)}})
        controls[name]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,
                        'mutated_kernel_sha256':pinned.digest(changed)}
    return {**positive,'instruction_controls':controls}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-library-setup-contracts.v1','status':'failure','selection':args.family,
            'kernel_sha256':pinned.KERNEL_SHA256,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2',
            'load_address':pinned.BASE,'lifetime':'resident-kernel','original_game_bytes_executed':False,
            'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,
            'source_sha256':{Path(p).name:pinned.digest(Path(p).read_bytes()) for p in
                (__file__,task.__file__,records.__file__,pinned.__file__,guard.__file__)},
            'programme_status':'active; incomplete','limitations':['Constructed context/slot/stack and argument corpus',
                '96D74 positive prefix stops at realA681A handoff; no A681A/callback/device body or fabricated return',
                'Full95E5A/89C8 semantics and whole-module/hardware/gameplay/Godot parity unresolved']}
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
            if isinstance(error,EvidenceFailure):report.update(error.partial)
            if isinstance(error,task.CaseFailure):
                report['failure_evidence']=error.evidence;report['original_game_bytes_executed']=True
                report['completed_before_failure']=getattr(error,'completed_results',[])
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
