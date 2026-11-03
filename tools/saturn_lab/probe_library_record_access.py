#!/usr/bin/env python3
"""Original949E0 overlap-aware byte move and95D34/95D9C record access.

Explicit high-RAM tables, destinations and null callbacks; real callee returns.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_library_name as name
import probe_library_setup as setup

pinned,records,task,longer=name.pinned,name.records,name.task,name.longer
MASK=name.MASK
MOVE,POINTER,COPY=0x060949E0,0x06095D34,0x06095D9C
FAMILIES=('move','name-pointer','descriptor-copy')
LITERALS={0x06095DFC:name.status.CELL,0x06095E00:setup.INDEX24,
          0x06095E04:setup.INDEX12,0x06095E08:MOVE}
HALFWORDS={0x06095DF0:0x98,**name.status.HALFWORDS}


class Model(name.status.Model):
    def read(self,address,size):
        source=LITERALS if size==4 else HALFWORDS if size==2 else {}
        if address in source:
            value=source[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def move(self):
        r=self.reg
        self.step(MOVE);self.t(r['r4']==r['r5'])
        self.step(MOVE+2)
        if not r['sr']&1:
            self.step(MOVE+4);r['r7']=0
            self.step(MOVE+6);self.t(r['r4']>=r['r5'])
            self.step(MOVE+8)
            backward=bool(r['sr']&1)
            if backward:
                self.step(0x06094A04);r['r1']=r['r4']
                self.step(0x06094A06);r['r1']=(r['r1']+r['r6'])&MASK
                self.step(0x06094A08);r['r0']=r['r5']
                self.step(0x06094A0A);r['r0']=(r['r0']+r['r6'])&MASK
                self.step(0x06094A0C);r['r5']=0
                self.step(0x06094A0E);self.t(r['r7']>=r['r6'])
                self.step(0x06094A10)
                if not r['sr']&1:
                    while True:
                        self.step(0x06094A12);r['r0']-=1
                        self.step(0x06094A14);r['r3']=records.signed(self.read(r['r0'],1),8)&MASK
                        self.step(0x06094A16);r['r5']+=1
                        self.step(0x06094A18);r['r1']-=1;self.write(r['r1'],1,r['r3'])
                        self.step(0x06094A1A);self.t(r['r5']>=r['r6'])
                        self.step(0x06094A1C)
                        if r['sr']&1:break
            else:
                self.step(0x060949EA);r['r1']=r['r4']
                self.step(0x060949EC);r['r0']=r['r5']
                self.step(0x060949EE);r['r5']=0
                self.step(0x060949F0);self.t(r['r7']>=r['r6'])
                self.step(0x060949F2)
                if not r['sr']&1:
                    while True:
                        self.step(0x060949F4);r['r3']=records.signed(self.read(r['r0'],1),8)&MASK;r['r0']+=1
                        self.step(0x060949F6);r['r5']+=1
                        self.step(0x060949F8);self.write(r['r1'],1,r['r3'])
                        self.step(0x060949FA);self.t(r['r5']>=r['r6'])
                        self.step(0x060949FC);r['r1']+=1
                        self.step(0x060949FE)
                        if r['sr']&1:break
                    self.step(0x06094A00);self.step(0x06094A02,True)
        self.step(0x06094A1E);self.step(0x06094A20,True);r['r0']=r['r4'];r['pc']=r['pr']

    def epilogue(self,pc):
        r=self.reg;self.step(pc);r['r15']+=4
        self.step(pc+2);r['pr']=self.pop()
        self.step(pc+4);self.step(pc+6,True);r['r14']=self.pop();r['pc']=r['pr']

    def pointer(self):
        r=self.reg
        self.step(POINTER);self.push(r['r14'])
        self.step(POINTER+2);self.push(r['pr'])
        self.step(POINTER+4);r['r3']=self.read(0x06095DFC,4)
        self.step(POINTER+6);r['r15']-=4
        self.step(POINTER+8);r['r2']=self.read(0x06095DF0,2)
        self.step(POINTER+10);r['r14']=self.read(r['r3'],4)
        self.step(POINTER+12);r['r14']+=r['r2']
        self.step(POINTER+14);r['r0']=self.read(r['r14']+8,4)
        self.step(POINTER+16);self.t(r['r0']==0)
        self.step(POINTER+18)
        valid=False
        if not r['sr']&1:
            self.step(POINTER+20);r['r0']=self.read(r['r14'],4)
            self.step(POINTER+22);self.t(r['r0']==1)
            self.step(POINTER+24);valid=bool(r['sr']&1)
        if not valid:
            self.step(0x06095D4E);r['pr']=0x06095D52
            self.step(0x06095D50,True);r['r4']=(-8)&MASK
            self.status();self.step(0x06095D52);r['r0']=0;self.epilogue(0x06095D54);return
        self.step(0x06095D5C);self.t(records.signed(r['r4'],32)>=0)
        self.step(0x06095D5E)
        valid_index=False
        if r['sr']&1:
            self.step(0x06095D60);r['r3']=self.read(r['r14']+12,4)
            self.step(0x06095D62);self.t(records.signed(r['r3'],32)>records.signed(r['r4'],32))
            self.step(0x06095D64);valid_index=bool(r['sr']&1)
        if not valid_index:
            self.step(0x06095D66);r['pr']=0x06095D6A
            self.step(0x06095D68,True);r['r4']=(-9)&MASK
            self.status();self.step(0x06095D6A);r['r0']=0;self.epilogue(0x06095D6C);return
        self.step(0x06095D74);r['r2']=self.read(0x06095E00,4)
        self.step(0x06095D76);r['pr']=0x06095D7A
        self.step(0x06095D78,True);r['r5']=self.read(r['r14']+8,4)
        setup.Model.index(self,True)
        self.step(0x06095D7A);self.write(r['r15'],4,r['r0'])
        self.step(0x06095D7C);r['pr']=0x06095D80
        self.step(0x06095D7E,True);r['r4']=0
        self.status()
        self.step(0x06095D80);r['r4']=r['r0']
        self.step(0x06095D82);self.t(records.signed(r['r4'],32)>=0)
        self.step(0x06095D84)
        if not r['sr']&1:
            self.step(0x06095D86);r['r0']=0;self.epilogue(0x06095D88);return
        self.step(0x06095D90);r['r0']=self.read(r['r15'],4)
        self.step(0x06095D92);r['r0']+=12;self.epilogue(0x06095D94)

    def copy(self):
        r=self.reg
        self.step(COPY);self.push(r['r14'])
        self.step(COPY+2);self.push(r['pr'])
        self.step(COPY+4);r['r3']=self.read(0x06095DFC,4)
        self.step(COPY+6);r['r15']-=4
        self.step(COPY+8);r['r2']=self.read(0x06095DF0,2)
        self.step(COPY+10);self.write(r['r15'],4,r['r5'])
        self.step(COPY+12);r['r14']=self.read(r['r3'],4)
        self.step(COPY+14);r['r14']+=r['r2']
        self.step(COPY+16);r['r0']=self.read(r['r14']+8,4)
        self.step(COPY+18);self.t(r['r0']==0)
        self.step(COPY+20)
        valid=False
        if not r['sr']&1:
            self.step(COPY+22);self.t(records.signed(r['r4'],32)>=0)
            self.step(COPY+24)
            if r['sr']&1:
                self.step(COPY+26);r['r0']=self.read(r['r14']+12,4)
                self.step(COPY+28);self.t(records.signed(r['r4'],32)>=records.signed(r['r0'],32))
                self.step(COPY+30);valid=not bool(r['sr']&1)
        if not valid:
            self.step(0x06095DBC);r['r4']=(-10)&MASK
            self.step(0x06095DBE);r['r15']+=4
            self.step(0x06095DC0);r['pr']=self.pop()
            self.step(0x06095DC2);self.step(0x06095DC4,True);r['r14']=self.pop()
            self.status();return
        self.step(0x06095DC6);r['r0']=self.read(r['r14'],4)
        self.step(0x06095DC8);self.t(r['r0']==1)
        self.step(0x06095DCA);wide=bool(r['sr']&1)
        if wide:
            self.step(0x06095DCC);r['r3']=self.read(0x06095E00,4)
            self.step(0x06095DCE);r['pr']=0x06095DD2
            self.step(0x06095DD0,True);r['r5']=self.read(r['r14']+8,4)
            setup.Model.index(self,True)
            self.step(0x06095DD2);self.step(0x06095DD4,True)
        else:
            self.step(0x06095DD6);r['r3']=self.read(0x06095E04,4)
            self.step(0x06095DD8);r['pr']=0x06095DDC
            self.step(0x06095DDA,True);r['r5']=self.read(r['r14']+8,4)
            setup.Model.index(self,False)
        self.step(0x06095DDC);r['r4']=self.read(r['r15'],4)
        self.step(0x06095DDE);r['r5']=r['r0']
        self.step(0x06095DE0);r['r3']=self.read(0x06095E08,4)
        self.step(0x06095DE2);r['pr']=0x06095DE6
        self.step(0x06095DE4,True);r['r6']=12
        self.move()
        self.step(0x06095DE6);r['r4']=0
        self.step(0x06095DE8);r['r15']+=4
        self.step(0x06095DEA);r['pr']=self.pop()
        self.step(0x06095DEC);self.step(0x06095DEE,True);r['r14']=self.pop();self.status()


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown record access family')
    if family=='move':return [(family,v,s,n,64+a,64+a+d) for v,s,n,a,d in itertools.product(
        range(2),(0,37,255),(*range(33),48),range(4),(-16,-1,0,1,16,64))]
    rows=[(family,v,s,n,i,mode,g,d) for v,s,n,mode,g in itertools.product(range(2),(0,255),(0,1,4,24,26,MASK,0x80000000),
         (1,0,2,MASK,-1),(0,(-16)&MASK,(-14)&MASK,(-13)&MASK,1))
         for i in sorted({0,max(0,n-1) if n<=26 else 0,n,25,MASK,0x80000000})
         for d in ((1000,-4,0,4,12) if family=='descriptor-copy' and mode!=-1 and 0<=i<n<=26 else (1000,))]
    return list(dict.fromkeys(rows))


def contract(case):
    family,v,seed,n,*rest=case
    if family not in FAMILIES or any(type(x) is not int for x in case[1:]) or v not in (0,1) or seed not in (0,37,255):raise ValueError('Outside record access inputs')
    block=0x060D0000+v*0x2000;table=0x060D4000+v*0x2000;dst=0x060D8000+v*0x2000
    canary=lambda length:bytes((seed+37*i)&255 for i in range(length));word=lambda x:(x&MASK).to_bytes(4,'big')
    before=records.initial(MOVE if family=='move' else POINTER if family=='name-pointer' else COPY,0,v)
    before['r15']-=0x100+v*0x1000;sp=before['r15'];lib=bytearray(canary(0xC4));lib[0xB8:0xBC]=bytes(4)
    tb=bytearray(canary(28*24+32));dest=bytearray(canary(64));g=0;table_write=False;depth=0 if family=='move' else 24
    if family=='move':
        if len(rest)!=2 or not 0<=n<=48 or any(not 0<=i<=len(tb)-n for i in rest):raise ValueError('Outside bounded move')
        src_off,dst_off=rest;before.update(r4=table+dst_off,r5=table+src_off,r6=n)
        expected_table=tb[:];expected_table[dst_off:dst_off+n]=tb[src_off:src_off+n];table_write=True;value=before['r4'];effective=None
    else:
        if len(rest)!=4:raise ValueError('Require record access tuple')
        index,mode,g,delta=rest
        if (n not in (0,1,4,24,26,MASK,0x80000000) or not 0<=index<=MASK or mode not in (1,0,2,MASK,-1) or
                not 0<=g<=MASK or delta not in (1000,-4,0,4,12)):raise ValueError('Outside bounded record table')
        lib[0x98:0xA8]=b''.join(map(word,(mode,32,0 if mode==-1 else table+16,n)))
        valid=mode!=-1 and 0<=records.signed(index,32)<records.signed(n,32)
        stride=24 if mode==1 else 12;source=16+index*stride if valid else 16
        if delta!=1000:
            if not valid:raise ValueError('Overlap requires valid record')
            before['r5']=table+source+delta;table_write=True
        else:before['r5']=dst
        before['r4']=index;expected_table=tb[:]
        if family=='name-pointer':
            error=-8 if mode!=1 else -9 if not valid else 0
            effective=name.status.effective(g,error)
            value=table+source+12 if error==0 and records.signed(effective,32)>=0 else 0
        else:
            error=0 if valid else -10;effective=name.status.effective(g,error);value=effective
            if valid:
                if delta==1000:dest[:12]=tb[source:source+12]
                else:expected_table[source+delta:source+delta+12]=tb[source:source+12]
    regions=[(table-16,canary(16),False),(table,bytes(tb),table_write),(table+len(tb),canary(16),False),
        (dst-16,canary(16),False),(dst,canary(64),family=='descriptor-copy'),(dst+64,canary(16),False),
        (block-16,canary(16),False),(block,bytes(lib),family!='move'),(block+len(lib),canary(16),False),
        (name.status.CELL-16,canary(16),False),(name.status.CELL,word(block),False),(name.status.CELL+4,canary(16),False),
        (name.status.STATUS_WORD-16,canary(16),False),(name.status.STATUS_WORD,word(g),False),(name.status.STATUS_WORD+4,canary(16),False),
        (sp-64,canary(64-depth),False)]
    if depth:regions.append((sp-depth,canary(depth),True))
    regions.append((sp,canary(64),False));regions += [(a,val.to_bytes(2,'big'),False) for a,val in HALFWORDS.items()]
    model=Model(before,[(a,b) for a,b,_ in regions]);getattr(model,'pointer' if family=='name-pointer' else 'copy' if family=='descriptor-copy' else 'move')()
    expected=[b for _,b,_ in regions];expected[1]=bytes(expected_table);expected[4]=bytes(dest)
    if effective is not None:lib[0xC0:0xC4]=word(effective);expected[7]=bytes(lib)
    if model.reg['r0']!=value:raise ValueError('Independent record access result differs')
    for i in range(len(regions)):
        if i!=16 or depth==0:
            if bytes(model.buffers[i])!=expected[i]:raise ValueError('Independent record copy/readonly/canary bytes differ')
    if len(model.trace)>512:raise ValueError('Outside bounded512 instruction budget')
    return model,regions


def observe(data,emu,before,regions,short=False):
    ranges=((MOVE,0x06094A22),(POINTER,0x06095DF0),(setup.INDEX12,0x060A56E8),(name.status.STATUS,0x06096CB0))
    return (name.status.guard if short else longer).observe(data,emu,before['pc'],regions,before,ranges=ranges,
        literals=tuple({**name.status.LITERALS,**LITERALS}),aliases=(),terminals={before['pr']:'returned'},budget=128 if short else 512)


def run_case(data,emu,case):
    m,r=contract(case);a=observe(data,emu,m.before,r);reason=None
    if a['status']!='returned':reason='Record access missed actual return: '+str(a['error'])
    elif a['registers']!=m.reg:reason='Record access register/fullSR/PR/MAC differs'
    elif a['trace']!=m.trace or a['steps']!=len(m.trace):reason='Record access PC/delay trace differs'
    elif a['events']!=m.events:reason='Record access ordered transactions differ'
    elif a['regions_after']!=[bytes(b) for b in m.buffers] or not a['original_unaffected_bytes_equal']:reason='Record access mapped bytes/canaries/unaffected original differs'
    if reason:raise task.CaseFailure(reason,case,a)
    return {'case':list(case),'status':'returned','instructions':a['steps'],'after_registers':a['registers'],'trace':a['trace'],
        'data_events':a['events'],'regions_after_sha256':[pinned.digest(b) for b in a['regions_after']],'all_visible_state_checked':True}


def execute(data,emu,family):
    selected=cases(family);rows=[]
    for c in selected:
        try:rows.append(run_case(data,emu,c))
        except task.CaseFailure as e:e.completed_results=rows;raise
    positive={'cases':len(rows),'complete_returns':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'original_game_bytes_executed':True}
    mutations={'move':[('move-result-delay',0x06094A20,9),('forward-byte-store',0x060949F8,9),('backward-byte-store',0x06094A18,9)],
        'name-pointer':[('name-field-offset',0x06095D92,0x700B),('index-stride-delay',setup.INDEX24+14,9),('root-restore-delay',0x06095D9A,9),('error-store-delay',0x06096C96,9)],
        'descriptor-copy':[('move-length-delay',0x06095DE4,0xE60B),('mode-selection',0x06095DC8,0x8800),('destination-reload',0x06095DDC,9),('error-store-delay',0x06096C96,9)]}[family]
    chosen=list(dict.fromkeys(selected[:16]+selected[::max(1,len(selected)//64)]+selected[-16:]));controls={}
    for _,pc,_ in mutations:
        if not any(any(a==pc for a,_ in contract(c)[0].trace) for c in chosen):
            chosen.append(next(c for c in selected if any(a==pc for a,_ in contract(c)[0].trace)))
    for label,pc,value in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=value.to_bytes(2,'big');count=0;first=None
        for c in chosen:
            try:run_case(changed,emu,c)
            except task.CaseFailure as e:
                fault=e.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=e.evidence
        if not count:raise name.EvidenceFailure('Missing record access semantic rejection: '+label,{**positive,'instruction_controls':controls,'failed_control':label})
        controls[label]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,'mutated_kernel_sha256':pinned.digest(changed)}
    result={**positive,'instruction_controls':controls};largest=max(selected,key=lambda c:len(contract(c)[0].trace));m,r=contract(largest)
    if len(m.trace)>128:
        a=observe(data,emu,m.before,r,True)
        if a['status']!='failed' or 'budget exceeded' not in str(a['error']):raise name.EvidenceFailure('Missing old128 record access refusal',result)
        result['short128_refusal']={k:v for k,v in a.items() if k!='regions_after'};result['short128_refusal']['regions_after_sha256']=[pinned.digest(b) for b in a['regions_after']]
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True)
    p.add_argument('--family',choices=FAMILIES,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args(argv)
    report={'schema':'neptune.original-library-record-access.v1','status':'failure','selection':args.family,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
        'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,'original_game_bytes_executed':False,'programme_status':'active; incomplete',
        'source_sha256':{Path(f).name:pinned.digest(Path(f).read_bytes()) for f in (__file__,name.__file__,name.status.__file__,setup.__file__,records.__file__,task.__file__,pinned.__file__,name.status.guard.__file__,longer.__file__)},
        'limitations':['Constructed table/destination/stack; selected overlap/indices/modes/statuses; callback null',
            'All callee returns original; no invented devices/aliases/ticks; original128 and separate1024 guards unchanged; chosen512 budget',
            'Natural interior, successful services/callbacks/whole-library/module/gameplay/hardware/Godot parity unresolved']}
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
            if isinstance(e,name.EvidenceFailure):report.update(e.partial)
            if isinstance(e,task.CaseFailure):report.update(failure_evidence=e.evidence,original_game_bytes_executed=True,completed_before_failure=getattr(e,'completed_results',[]))
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}));return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
