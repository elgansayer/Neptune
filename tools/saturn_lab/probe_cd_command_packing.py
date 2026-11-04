#!/usr/bin/env python3
"""Original AE676/AE908 command packing and A4FAC/A4FBE call preparation.

A4FAC or95992 are actual non-executable pending entries, never service stubs.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_library_request_state as request

pinned,records,task,guard=request.pinned,request.records,request.task,request.guard
MASK=0xFFFFFFFF
PACK48,PACK62,SERVICE,INNER,TARGET=0x060AE676,0x060AE908,0x060A4FAC,0x060A4FBE,0x06095992
FAMILIES=('pack48','pack62','service48','service62')
LITERALS={0x060AE6A0:SERVICE,0x060AEA34:SERVICE,0x060A5090:TARGET}
HALFWORDS={0x060AEA30:0x80}


class Model(records.Model):
    def read(self,address,size):
        source=LITERALS if size==4 else HALFWORDS if size==2 else {}
        if address in source:
            value=source[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def pack48(self):
        r=self.reg
        self.step(PACK48);r['r6']=0
        self.step(PACK48+2);self.push(r['r14'])
        self.step(PACK48+4);r['r3']=0x48
        self.step(PACK48+6);self.push(r['pr'])
        self.step(PACK48+8);r['r0']=r['r4']
        self.step(PACK48+10);r['r15']-=8
        self.step(PACK48+12);r['r14']=r['r15']
        self.step(PACK48+14);self.write(r['r14'],4,0)
        self.step(PACK48+16);self.write(r['r14']+4,4,0)
        self.step(PACK48+18);self.write(r['r14'],1,r['r3'])
        self.step(PACK48+20);self.write(r['r14']+1,1,r['r0'])
        self.step(PACK48+22);r['r3']=self.read(0x060AE6A0,4)
        self.step(PACK48+24);r['r0']=r['r5']
        self.step(PACK48+26);self.write(r['r14']+4,1,r['r0'])
        self.step(PACK48+28);r['r5']=r['r14']
        self.step(PACK48+30);r['pr']=0x060AE698
        self.step(PACK48+32,True);r['r4']=64;r['pc']=SERVICE

    def pack62(self):
        r=self.reg
        self.step(PACK62);self.push(r['r14'])
        self.step(PACK62+2);r['r7']=0
        self.step(PACK62+4);self.push(r['pr'])
        self.step(PACK62+6);r['r3']=0x62
        self.step(PACK62+8);r['r15']-=8
        self.step(PACK62+10);r['r14']=r['r15']
        self.step(PACK62+12);self.write(r['r14'],4,0)
        self.step(PACK62+14);r['r0']=r['r5']
        self.step(PACK62+16);self.write(r['r14']+4,4,0)
        self.step(PACK62+18);self.write(r['r14'],1,r['r3'])
        self.step(PACK62+20);self.write(r['r14']+2,2,r['r0'])
        self.step(PACK62+22);r['r0']=r['r4']
        self.step(PACK62+24);r['r3']=self.read(0x060AEA34,4)
        self.step(PACK62+26);self.write(r['r14']+4,1,r['r0'])
        self.step(PACK62+28);r['r4']=self.read(0x060AEA30,2)
        self.step(PACK62+30);r['r0']=r['r6']
        self.step(PACK62+32);self.write(r['r14']+6,2,r['r0'])
        self.step(PACK62+34);r['pr']=0x060AE92E
        self.step(PACK62+36,True);r['r5']=r['r14'];r['pc']=SERVICE

    def service(self):
        r=self.reg
        self.step(SERVICE);self.push(r['pr'])
        self.step(SERVICE+2);r['r15']-=8
        self.step(SERVICE+4);r['r6']=r['r15']
        self.step(SERVICE+6);r['pr']=0x060A4FB6
        self.step(SERVICE+8,True);r['r7']=1
        self.step(INNER);self.push(r['r14'])
        self.step(INNER+2);self.push(r['r13'])
        self.step(INNER+4);r['r13']=r['r6']
        self.step(INNER+6);r['r3']=self.read(0x060A5090,4)
        self.step(INNER+8);self.push(r['pr'])
        self.step(INNER+10);r['r15']-=8
        self.step(INNER+12);self.write(r['r15'],4,r['r7'])
        self.step(INNER+14);r['pr']=0x060A4FD0
        self.step(INNER+16,True);r['r6']=r['r13'];r['pc']=TARGET


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown command-packing family')
    words=(*range(256),0x100,0xFF00,0xFFFF,0x10000,0x7FFFFFFF,0x80000000,MASK,0x12345678)
    rows=[(family,v,s,n,((n*0x10101)^MASK)&MASK,n^0xA5A55A5A) for v,s,n in itertools.product(range(2),(0,37,255),words)]
    wide=(0,1,0xFF,0x100,0xFFFF,0x10000,0x80000000,MASK)
    if family.endswith('48'):
        rows += [(family,v,s,a,b,0xDEADBEEF) for v,s,a,b in itertools.product(range(2),(0,37,255),wide,wide)]
    else:rows += [(family,v,37,a,b,c) for v,a,b,c in itertools.product(range(2),wide,wide,wide)]
    return list(dict.fromkeys(rows))


def contract(case):
    family,v,seed,a,b,c=case
    if (family not in FAMILIES or any(type(n) is not int for n in case[1:]) or v not in (0,1) or seed not in (0,37,255) or
            any(not 0<=n<=MASK for n in (a,b,c))):raise ValueError('Outside bounded command-packing contract')
    wide=family.endswith('62');composed=family.startswith('service');entry=PACK62 if wide else PACK48
    before=records.initial(entry,a,v);before['r15']-=0x100+v*0x1000;before.update(r5=b,r6=c);sp=before['r15']
    canary=lambda size:bytes((seed+37*i)&255 for i in range(size));word=lambda value:value.to_bytes(4,'big')
    depth=48 if composed else 16
    regions=[(sp-80,canary(80-depth),False),(sp-depth,canary(depth),True),(sp,canary(64),False),
             (0x060AEA30,b'\x00\x80',False)]
    m=Model(before,[(a,b) for a,b,_ in regions]);getattr(m,'pack62' if wide else 'pack48')()
    if composed:m.service()
    # Independent scalar packet and pending-frame layout, including untouched locals.
    packet=bytes((0x62,0,(b>>8)&255,b&255,a&255,0,(c>>8)&255,c&255)) if wide else bytes((0x48,a&255,0,0,b&255,0,0,0))
    saved_link=0x060AE92E if wide else 0x060AE698
    frame=bytearray(regions[1][1]);frame[-16:-8]=packet;frame[-8:-4]=word(before['pr']);frame[-4:]=word(before['r14'])
    if composed:
        frame[:4]=word(1);frame[8:12]=word(0x060A4FB6);frame[12:16]=word(before['r13'])
        frame[16:20]=word(sp-16);frame[28:32]=word(saved_link)
    if bytes(m.buffers[1])!=bytes(frame):raise ValueError('Independent command/response/local/saved-frame bytes differ')
    for i in (0,2,3):
        if bytes(m.buffers[i])!=regions[i][1]:raise ValueError('Independent readonly input/canary differs')
    expected={'pc':TARGET if composed else SERVICE,'pr':0x060A4FD0 if composed else saved_link,'r15':sp-depth,
              'r4':128 if wide else 64,'r5':sp-16,'r14':sp-16,'r0':c if wide else b,
              'r3':TARGET if composed else SERVICE,'r6':sp-28 if composed else c if wide else 0,
              'r7':1 if composed else 0 if wide else before['r7'],'r13':sp-28 if composed else before['r13']}
    for key,value in expected.items():
        if m.reg[key]!=value:raise ValueError('Independent pending ABI differs: '+key)
    for key in ('sr','macl','mach','gbr','vbr'):
        if m.reg[key]!=before[key]:raise ValueError('Command preparation changed preserved scalar state')
    if len(m.trace)>64:raise ValueError('Outside chosen64 original128 guard')
    return m,regions


def observe(data,emu,before,regions,composed):
    ranges=((PACK48,0x060AE698),(PACK62,0x060AE92E))
    if composed:ranges+=((SERVICE,0x060A4FB6),(INNER,0x060A4FD0))
    terminal=TARGET if composed else SERVICE
    return guard.observe(data,emu,before['pc'],regions,before,ranges=ranges,literals=tuple(LITERALS),aliases=(),
                         terminals={terminal:'handoff'},budget=64)


def run_case(data,emu,case):
    m,r=contract(case);a=observe(data,emu,m.before,r,case[0].startswith('service'));reason=None
    if a['status']!='handoff':reason='Command packing missed actual pending entry: '+str(a['error'])
    elif a['registers']!=m.reg:reason='Command packing registers/PC/fullSR/PR/MAC differ'
    elif a['trace']!=m.trace or a['steps']!=len(m.trace):reason='Command packing PC/delay trace differs'
    elif a['events']!=m.events:reason='Command packing ordered transactions differ'
    elif a['regions_after']!=[bytes(b) for b in m.buffers] or not a['original_unaffected_bytes_equal']:reason='Command packing frame/canaries/unaffected original differs'
    if reason:raise task.CaseFailure(reason,case,a)
    return {'case':list(case),'status':'handoff','instructions':a['steps'],'after_registers':a['registers'],'trace':a['trace'],
            'data_events':a['events'],'regions_after_sha256':[pinned.digest(b) for b in a['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    selected=cases(family);rows=[]
    for c in selected:
        try:rows.append(run_case(data,emu,c))
        except task.CaseFailure as e:e.completed_results=rows;raise
    positive={'cases':len(rows),'complete_returns':0,'unfinished_handoffs':len(rows),'results':rows,
        'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'original_game_bytes_executed':True}
    mutations=([('wrong-command-byte',PACK48+4,0xE347),('wrong-byte-field',PACK48+20,0x80E2),('wrong-index-field',PACK48+26,0x80E5),('wrong-service-argument-delay',PACK48+32,0xE441)] if family.endswith('48') else
        [('wrong-command-byte',PACK62+6,0xE361),('wrong-word-field',PACK62+20,0x81E2),('wrong-index-field',PACK62+26,0x80E5),('wrong-last-word-field',PACK62+32,0x81E2),('wrong-command-pointer-delay',PACK62+36,0x65D3)])
    if family.startswith('service'):mutations += [('wrong-wrapper-mode-delay',SERVICE+8,0xE702),('wrong-response-pointer-delay',INNER+16,0x66E3),('lost-inner-saved-PR',INNER+8,9)]
    chosen=list(dict.fromkeys(selected[:16]+selected[::max(1,len(selected)//48)]+selected[-16:]));controls={}
    for label,pc,value in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=value.to_bytes(2,'big');count=0;first=None
        for c in chosen:
            try:run_case(changed,emu,c)
            except task.CaseFailure as e:
                fault=e.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=e.evidence
        if not count:raise request.EvidenceFailure('Missing command-packing semantic control: '+label,{**positive,'instruction_controls':controls})
        controls[label]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,'mutated_kernel_sha256':pinned.digest(changed)}
    return {**positive,'instruction_controls':controls}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True)
    p.add_argument('--family',choices=FAMILIES,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args(argv)
    report={'schema':'neptune.original-cd-command-packing.v1','status':'failure','selection':args.family,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
        'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,'original_game_bytes_executed':False,'programme_status':'active; incomplete',
        'source_sha256':{Path(f).name:pinned.digest(Path(f).read_bytes()) for f in (__file__,request.__file__,records.__file__,task.__file__,pinned.__file__,guard.__file__)},
        'limitations':['Constructed highRAM stack and register arguments; command/response/local byte fields explicit',
            'A4FAC or95992 remain unfinished nonexecutable pending entries; no fabricated service returns/deviceRAM',
            'Original128 guard unchanged, chosen64; no naturalinterior/hardwaretiming/gameplay/Godot/whole-program parity claim']}
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
            if isinstance(e,request.EvidenceFailure):report.update(e.partial)
            if isinstance(e,task.CaseFailure):report.update(failure_evidence=e.evidence,original_game_bytes_executed=True,completed_before_failure=getattr(e,'completed_results',[]))
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}));return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
