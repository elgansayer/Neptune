#!/usr/bin/env python3
"""Original bounded byte comparison, flagged table search and95CBC lookup.

Constructed high RAM and null callbacks; no BIOS/device or callee substitutions.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_library_status as status
import sh2_selection_profile as longer

pinned, records, task = status.pinned, status.records, status.task
MASK = 0xFFFFFFFF
COMPARE, SEARCH, LOOKUP = 0x06095158, 0x060A5676, 0x06095CBC
FAMILIES = ('compare', 'search', 'lookup', 'lookup-invalid')
LITERALS = {0x060A5824:COMPARE, 0x06095CE4:status.CELL,
            0x06095DF4:SEARCH, 0x06095DF8:status.STATUS}
HALFWORDS = {0x06095CE0:0x98, **status.HALFWORDS}


class EvidenceFailure(ValueError):
    def __init__(self,reason,partial):
        super().__init__(reason);self.partial=partial


def compare_bytes(left, right, count):
    for a,b in zip(left[:count],right[:count]):
        if a != b or a == 0:return a-b
    return 0


class Model(status.Model):
    def read(self,address,size):
        source=LITERALS if size==4 else HALFWORDS if size==2 else {}
        if address in source:
            value=source[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def compare(self):
        r=self.reg
        self.step(COMPARE);r['r7']=r['r5']
        self.step(COMPARE+2);self.t(r['r6']==0)
        self.step(COMPARE+4)
        if r['sr']&1:
            self.step(COMPARE+6);self.step(COMPARE+8,True);r['r0']=0
            r['pc']=r['pr'];return
        self.step(0x06095162);r['r5']=0
        self.step(0x06095164);r['r3']=0
        self.step(0x06095166);self.t(r['r3']>=r['r6'])
        self.step(0x06095168)
        while True:
            self.step(0x0609516A);r['r3']=records.signed(self.read(r['r4'],1),8)&MASK;r['r4']+=1
            self.step(0x0609516C);r['r2']=records.signed(self.read(r['r7'],1),8)&MASK;r['r7']+=1
            self.step(0x0609516E);self.t(r['r2']==r['r3'])
            self.step(0x06095170)
            if not r['sr']&1:break
            self.step(0x06095172);r['r2']=r['r4']
            self.step(0x06095174);r['r2']-=1
            self.step(0x06095176);r['r3']=records.signed(self.read(r['r2'],1),8)&MASK
            self.step(0x06095178);self.t(r['r3']==0)
            self.step(0x0609517A)
            if r['sr']&1:break
            self.step(0x0609517C);r['r5']+=1
            self.step(0x0609517E);self.t(r['r5']>=r['r6'])
            self.step(0x06095180)
            if r['sr']&1:break
        self.step(0x06095182);r['r0']=r['r4']
        self.step(0x06095184);r['r0']-=1
        self.step(0x06095186);r['r7']-=1
        self.step(0x06095188);r['r0']=records.signed(self.read(r['r0'],1),8)&MASK
        self.step(0x0609518A);r['r0']&=255
        self.step(0x0609518C);r['r3']=records.signed(self.read(r['r7'],1),8)&MASK
        self.step(0x0609518E);r['r3']&=255
        self.step(0x06095190);r['r0']=(r['r0']-r['r3'])&MASK
        self.step(0x06095192);self.step(0x06095194,True);r['pc']=r['pr']

    def search(self):
        r=self.reg
        self.step(SEARCH);self.push(r['r14'])
        self.step(SEARCH+2);self.push(r['r13'])
        self.step(SEARCH+4);r['r13']=r['r4']
        self.step(SEARCH+6);self.push(r['r12'])
        self.step(SEARCH+8);r['r4']=0
        self.step(SEARCH+10);self.push(r['r11'])
        self.step(SEARCH+12);r['r14']=0
        self.step(SEARCH+14);self.push(r['r10'])
        self.step(SEARCH+16);r['r11']=r['r6']
        self.step(SEARCH+18);self.push(r['pr'])
        self.step(SEARCH+20);self.t(0>=records.signed(r['r11'],32))
        self.step(SEARCH+22);r['r10']=self.read(0x060A5824,4)
        self.step(SEARCH+24);r['r15']-=4
        self.step(SEARCH+26);self.write(r['r15'],4,r['r5'])
        self.step(SEARCH+28);self.step(SEARCH+30,True);r['r12']=1
        found=False
        if not r['sr']&1:
            while True:
                self.step(0x060A5696);r['r6']=12
                self.step(0x060A5698);r['r4']=self.read(r['r15'],4)
                self.step(0x060A569A);r['r5']=r['r13']
                self.step(0x060A569C);r['pr']=0x060A56A0
                self.step(0x060A569E,True);r['r5']+=12
                self.compare()
                self.step(0x060A56A0);self.t(r['r0']==0)
                self.step(0x060A56A2)
                if r['sr']&1:
                    self.step(0x060A56A4);self.step(0x060A56A6,True);r['r0']=r['r14'];found=True;break
                self.step(0x060A56A8);r['r0']=records.signed(self.read(r['r13']+11,1),8)&MASK
                self.step(0x060A56AA);r['r0']&=255
                self.step(0x060A56AC);self.t((r['r12']&r['r0'])==0)
                self.step(0x060A56AE)
                if not r['sr']&1:break
                self.step(0x060A56B0);r['r14']+=1
                self.step(0x060A56B2);self.t(records.signed(r['r14'],32)>=records.signed(r['r11'],32))
                self.step(0x060A56B4);self.step(0x060A56B6,True);r['r13']+=24
                if r['sr']&1:break
        if not found:self.step(0x060A56B8);r['r0']=MASK
        self.step(0x060A56BA);r['r15']+=4
        for pc,name in ((0x060A56BC,'pr'),(0x060A56BE,'r10'),(0x060A56C0,'r11'),(0x060A56C2,'r12'),(0x060A56C4,'r13')):
            self.step(pc);r[name]=self.pop()
        self.step(0x060A56C6);self.step(0x060A56C8,True);r['r14']=self.pop();r['pc']=r['pr']

    def lookup(self):
        r=self.reg
        self.step(LOOKUP);self.push(r['r14'])
        self.step(LOOKUP+2);self.push(r['pr'])
        self.step(LOOKUP+4);r['r3']=self.read(0x06095CE4,4)
        self.step(LOOKUP+6);r['r15']-=4
        self.step(LOOKUP+8);r['r2']=self.read(0x06095CE0,2)
        self.step(LOOKUP+10);self.write(r['r15'],4,r['r4'])
        self.step(LOOKUP+12);r['r14']=self.read(r['r3'],4)
        self.step(LOOKUP+14);r['r14']+=r['r2']
        self.step(LOOKUP+16);r['r0']=self.read(r['r14']+8,4)
        self.step(LOOKUP+18);self.t(r['r0']==0)
        self.step(LOOKUP+20)
        valid=False
        if not r['sr']&1:
            self.step(LOOKUP+22);r['r0']=self.read(r['r14'],4)
            self.step(LOOKUP+24);self.t(r['r0']==1)
            self.step(LOOKUP+26);valid=bool(r['sr']&1)
        if not valid:
            self.step(0x06095CD8);self.step(0x06095CDA,True);r['r4']=(-8)&MASK
        else:
            self.step(0x06095CF8);r['r6']=self.read(r['r14']+4,4)
            self.step(0x06095CFA);r['r5']=self.read(r['r15'],4)
            self.step(0x06095CFC);r['r3']=self.read(0x06095DF4,4)
            self.step(0x06095CFE);r['pr']=0x06095D02
            self.step(0x06095D00,True);r['r4']=self.read(r['r14']+8,4)
            self.search()
            self.step(0x06095D02);r['r14']=r['r0']
            self.step(0x06095D04);self.t(records.signed(r['r14'],32)>=0)
            self.step(0x06095D06)
            if not r['sr']&1:self.step(0x06095D08);r['r4']=(-9)&MASK
            else:
                self.step(0x06095D14);r['r2']=self.read(0x06095DF8,4)
                self.step(0x06095D16);r['pr']=0x06095D1A
                self.step(0x06095D18,True);r['r4']=0
                self.status()
                self.step(0x06095D1A);r['r4']=r['r0']
                self.step(0x06095D1C);self.t(records.signed(r['r4'],32)>=0)
                self.step(0x06095D1E)
                if r['sr']&1:
                    self.step(0x06095D2A);r['r0']=r['r14']
                    tail=0x06095D2C
                else:
                    self.step(0x06095D20);r['r0']=r['r4'];tail=0x06095D22
                self.step(tail);r['r15']+=4
                self.step(tail+2);r['pr']=self.pop()
                self.step(tail+4);self.step(tail+6,True);r['r14']=self.pop();r['pc']=r['pr'];return
        self.step(0x06095D0A);r['r15']+=4
        self.step(0x06095D0C);r['r3']=self.read(0x06095DF8,4)
        self.step(0x06095D0E);r['pr']=self.pop()
        self.step(0x06095D10);self.step(0x06095D12,True);r['r14']=self.pop()
        self.status()


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown name family')
    if family=='compare':
        rows=[(family,v,s,12,0,b,255-b,-1) for v,s,b in itertools.product(range(2),(0,255),range(256))]
        rows += [(family,v,37,n,pos,0x80,0x7F,zero) for v,n in itertools.product(range(2),(*range(17),32,48))
                 for pos in sorted({-1,0,max(0,n-1),n}) for zero in (-1,0,max(0,n-1))]
        return list(dict.fromkeys(rows))
    modes=(0,2,MASK,-1) if family=='lookup-invalid' else (1,)
    statuses=(0,(-16)&MASK,(-14)&MASK,(-13)&MASK,1) if family.startswith('lookup') else (0,)
    if family=='lookup-invalid':
        return [(family,v,s,4,2,-1,0,g,m) for v,s,g,m in itertools.product(range(2),(0,255),statuses,modes)]
    rows=[]
    for n in (0,1,2,4,8,MASK,0x80000000):
        for v,s,hit,stop,prefix,g in itertools.product(range(2),(0,255),range(-1,n) if 0<n<=8 else (-1,),
                (-1,0,n-1) if 0<n<=8 else (-1,), (0,5,11) if n<=4 else (0,),statuses):
            rows.append((family,v,s,n,hit,stop,prefix,g,1))
    return list(dict.fromkeys(rows))


def contract(case):
    family,v,seed,n,*rest=case
    if (family not in FAMILIES or any(type(i) is not int for i in case[1:]) or
            v not in (0,1) or seed not in (0,37,255)):raise ValueError('Outside name contract')
    if family=='compare':
        if len(rest)!=4:raise ValueError('Require comparison tuple')
        pos,a,b,zero=rest
        if not (0<=n<=48 and -1<=pos<64 and -1<=zero<64 and 0<=a<=255 and 0<=b<=255):
            raise ValueError('Outside bounded byte comparison')
    else:
        if len(rest)!=5:raise ValueError('Require table tuple')
        hit,stop,prefix,g,mode=rest
        if (n not in (0,1,2,4,8,MASK,0x80000000) or not 0<=prefix<12 or not 0<=g<=MASK or
                not -1<=hit<(n if 0<n<=8 else 0) or not -1<=stop<(n if 0<n<=8 else 0) or
                mode not in ((0,2,MASK,-1) if family=='lookup-invalid' else (1,))):
            raise ValueError('Outside bounded flagged name table')
    block=0x060D0000+v*0x2000;table=0x060D4000+v*0x2000;query=0x060D8000+v*0x2000
    entry=COMPARE if family=='compare' else SEARCH if family=='search' else LOOKUP
    before=records.initial(entry,query,v);before['r15']-=0x100+v*0x1000;sp=before['r15']
    canary=lambda size:bytes((seed+37*i)&255 for i in range(size))
    word=lambda value:(value&MASK).to_bytes(4,'big')
    lib=bytearray(canary(0xC4));lib[0xB8:0xBC]=bytes(4)
    if family=='compare':
        pos,a,b,zero=rest;left=bytearray(b'Q'*64);right=left[:]
        if pos>=0:left[pos]=a;right[pos]=b
        if zero>=0:left[zero]=right[zero]=0
        expected_result=compare_bytes(left,right,n)&MASK
        before.update(r5=table,r6=n);tb=bytes(right);qb=bytes(left);depth=0;g=0
    else:
        hit,stop,prefix,g,mode=rest;size=n if 0<n<=8 else 1
        qb=b'Q'*12;buf=bytearray(canary(size*24))
        for i in range(size):
            name=bytearray(qb);name[prefix]=ord('R')
            if i==hit:name=bytearray(qb)
            buf[i*24+12:(i+1)*24]=name
            buf[i*24+11]=(seed&0xFE)|int(i==stop)
        tb=bytes(buf);selected=-1
        if records.signed(n,32)>0:
            for i in range(size):
                if compare_bytes(qb,tb[i*24+12:(i+1)*24],12)==0:selected=i;break
                if tb[i*24+11]&1:break
        valid=mode==1
        error=0 if selected>=0 else (-9)&MASK
        if not valid:error=(-8)&MASK
        effective=status.effective(g,error)
        expected_result=selected&MASK if family=='search' else selected if valid and selected>=0 and records.signed(effective,32)>=0 else effective
        lib[0x98:0xA8]=b''.join(map(word,(mode,n,0 if mode==-1 else table,0x76543210)))
        if family=='search':before.update(r4=table,r5=query,r6=n)
        depth=28 if family=='search' else 40
    regions=[(query-16,canary(16),False),(query,qb,False),(query+len(qb),canary(16),False),
             (table-16,canary(16),False),(table,tb,False),(table+len(tb),canary(16),False),
             (block-16,canary(16),False),(block,bytes(lib),family.startswith('lookup')),(block+len(lib),canary(16),False),
             (status.CELL-16,canary(16),False),(status.CELL,word(block),False),(status.CELL+4,canary(16),False),
             (status.STATUS_WORD-16,canary(16),False),(status.STATUS_WORD,word(g),False),(status.STATUS_WORD+4,canary(16),False),
             (sp-80,canary(80-depth),False)]
    if depth:regions.append((sp-depth,canary(depth),True))
    regions.append((sp,canary(64),False))
    regions += [(a,val.to_bytes(2,'big'),False) for a,val in HALFWORDS.items()]
    model=Model(before,[(a,b) for a,b,_ in regions]);getattr(model,'lookup' if family.startswith('lookup') else family)()
    if model.reg['r0']!=expected_result:raise ValueError('Independent unsigned byte/search/status result differs')
    expected=[b for _,b,_ in regions]
    if family.startswith('lookup'):
        lib[0xC0:0xC4]=word(effective);expected[7]=bytes(lib)
    for i,(_,_,write) in enumerate(regions):
        if not write or i==7:
            if bytes(model.buffers[i])!=expected[i]:raise ValueError('Independent output/unaffected input differs')
    if not model.trace or len(model.trace)>1024:raise ValueError('Selection outside unchanged1024 profile')
    return model,regions


def observe(data,emu,before,regions,budget=1024,short=False):
    ranges=((COMPARE,0x06095196),(SEARCH,0x060A56CA),(LOOKUP,0x06095CDC),
            (0x06095CF8,0x06095D34),(status.STATUS,0x06096CB0))
    return (status.guard if short else longer).observe(data,emu,before['pc'],regions,before,ranges=ranges,
        literals=tuple({**status.LITERALS,**LITERALS}),aliases=(),terminals={before['pr']:'returned'},budget=budget)


def run_case(data,emu,case):
    model,regions=contract(case);a=observe(data,emu,model.before,regions);reason=None
    if a['status']!='returned':reason='Original name path missed return: '+str(a['error'])
    elif a['registers']!=model.reg:reason='Name register/PC/fullSR/PR/MAC differs'
    elif a['trace']!=model.trace or a['steps']!=len(model.trace):reason='Name original PC/delay trace differs'
    elif a['events']!=model.events:reason='Name ordered data transactions differ'
    elif a['regions_after']!=[bytes(b) for b in model.buffers] or not a['original_unaffected_bytes_equal']:
        reason='Name output/stack/canaries/unaffected source differs'
    if reason:raise task.CaseFailure(reason,case,a)
    return {'case':list(case),'status':'returned','instructions':a['steps'],'after_registers':a['registers'],
            'trace':a['trace'],'data_events':a['events'],'regions_after_sha256':[pinned.digest(b) for b in a['regions_after']],
            'all_visible_state_checked':True}


def control_cases(selected):
    chosen=selected[:16]+selected[::max(1,len(selected)//48)]+selected[-16:]
    if selected[0][0]=='compare':chosen += [c for c in selected if c[3]==0][:4]
    return list(dict.fromkeys(chosen))


def execute(data,emu,family):
    selected=cases(family);rows=[]
    for case in selected:
        try:rows.append(run_case(data,emu,case))
        except task.CaseFailure as e:e.completed_results=rows;raise
    mutations=[('unsigned-left',0x0609518A,9),('zero-result-delay',0x06095160,0xE001),('difference',0x06095190,9)] if family=='compare' else [
        ('name-offset-delay',0x060A569E,0x750B),('record-stride-delay',0x060A56B6,0x7D0C),('end-flag-mask',0x060A5694,0xEC02),('root-restore-delay',0x060A56C8,9)]
    if family.startswith('lookup'):mutations += [('error-store-delay',0x06096C96,9),('lookup-restore-delay',0x06095D12,9)]
    if family=='lookup-invalid':mutations=[('invalid-error-delay',0x06095CDA,0xE4F7),('lookup-restore-delay',0x06095D12,9),('error-store-delay',0x06096C96,9)]
    positive={'cases':len(rows),'complete_returns':len(rows),'results':rows,
              'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'original_game_bytes_executed':True}
    chosen=control_cases(selected);controls={}
    for name,pc,value in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=value.to_bytes(2,'big');count=0;first=None
        for case in chosen:
            try:run_case(changed,emu,case)
            except task.CaseFailure as e:
                fault=e.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=e.evidence
        if not count:raise EvidenceFailure('No nonbudget name mutation rejection: '+name,
            {**positive,'instruction_controls':controls,'failed_control':{'name':name,'pc':pc,'tested':len(chosen)}})
        controls[name]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,'mutated_kernel_sha256':pinned.digest(changed)}
    result={**positive,'instruction_controls':controls}
    largest=max(selected,key=lambda c:len(contract(c)[0].trace));m,regions=contract(largest)
    if len(m.trace)>128:
        a=observe(data,emu,m.before,regions,budget=128,short=True)
        if a['status']!='failed' or 'budget exceeded' not in str(a['error']):raise EvidenceFailure('Old128 refusal differs',result)
        result['short128_refusal']={k:v for k,v in a.items() if k!='regions_after'}
        result['short128_refusal']['regions_after_sha256']=[pinned.digest(b) for b in a['regions_after']]
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True)
    p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--family',choices=FAMILIES,required=True)
    p.add_argument('--report',type=Path,required=True);args=p.parse_args(argv)
    report={'schema':'neptune.original-library-name.v1','status':'failure','selection':args.family,
            'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
            'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,
            'original_game_bytes_executed':False,'programme_status':'active; incomplete',
            'source_sha256':{Path(f).name:pinned.digest(Path(f).read_bytes()) for f in (__file__,status.__file__,records.__file__,task.__file__,pinned.__file__,status.guard.__file__,longer.__file__)},
            'limitations':['Constructed compare0..48bytes/table0..8records, signed negative counts and null callbacks',
                'Natural26-entry lookup boundary retained separately; no interior/timing/gameplay/whole-program parity claim',
                'No callee substitutions/device RAM/aliases; old128 and existing1024 guards unchanged']}
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
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
