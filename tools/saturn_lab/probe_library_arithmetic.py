#!/usr/bin/env python3
"""Original9410C quotient/94268 remainder andA6DA6 format selection.

Expected DIV1 uses an independent carry/borrow reduction of Renesas
REJ09B0171-0500O,6.1.17-19. Actual execution uses the unchanged pinned CPU.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_task_init as task

pinned,records,guard=task.pinned,task.records,task.short
MASK=0xFFFFFFFF
QUOTIENT,REMAINDER,FORMAT,ERROR_CELL=0x0609410C,0x06094268,0x060A6DA6,0x060FA8B4
FAMILIES=('quotient','remainder','format')
ENTRIES=dict(zip(FAMILIES,(QUOTIENT,REMAINDER,FORMAT)))
LONGS={0x060941B8:ERROR_CELL,0x060941BC:0x44E,0x06094328:ERROR_CELL,0x0609432C:0x44E}
SHORTS={0x060A6DB2:0x930,0x060A6E8E:0x914,0x060A6E90:0x800}
ISA_URL='https://www.renesas.com/en/document/mah/sh-1sh-2sh-dsp-software-manual'


def div1(value,divisor,sr):
    """One mathematical carry/borrow relation, independent of vendor CPU code."""
    q,m,t=(sr>>8)&1,(sr>>9)&1,sr&1
    sign=value>>31;shifted=((value<<1)|t)&MASK
    if q==m:
        wide=shifted-divisor;carry=int(wide<0)
    else:
        wide=shifted+divisor;carry=int(wide>MASK)
    q=sign^carry^m
    return wide&MASK,(sr&~0x101)|(q<<8)|int(q==m)


def scalar(numerator,divisor):
    n,d=records.signed(numerator,32),records.signed(divisor,32)
    if not d:return 0,0
    quotient=(abs(n)//abs(d))*(-1 if (n<0)^(d<0) else 1)
    return quotient&MASK,(n-quotient*d)&MASK


class Model(records.Model):
    def read(self,address,size):
        source=LONGS if size==4 else SHORTS if size==2 else {}
        if address in source:
            value=source[address];self.events.append([1,address,size,value]);return value
        return super().read(address,size)

    def div0s(self,m,n):
        q,mode=self.reg[n]>>31,self.reg[m]>>31
        self.reg['sr']=(self.reg['sr']&~0x301)|(q<<8)|(mode<<9)|(q^mode)

    def subc(self,m,n):
        value=self.reg[n]-self.reg[m]-(self.reg['sr']&1)
        self.reg[n]=value&MASK;self.t(value<0)

    def rotcl(self,n):
        old,t=self.reg[n],self.reg['sr']&1
        self.reg[n]=((old<<1)|t)&MASK;self.t(old>>31)

    def divide(self,remainder):
        r=self.reg;entry=REMAINDER if remainder else QUOTIENT
        self.step(entry);self.t(r['r0']==0)
        self.step(entry+2);self.push(r['r2'])
        self.step(entry+4)
        if r['sr']&1:
            pc=0x0609431A if remainder else 0x060941AA
            self.step(pc);r['r1']=self.read(0x06094328 if remainder else 0x060941B8,4)
            self.step(pc+2);r['r2']=self.read(0x0609432C if remainder else 0x060941BC,4)
            self.step(pc+4);r['r0']=0
            self.step(pc+6);self.write(r['r1'],4,r['r2'])
            self.step(pc+8)
            self.step(pc+10,True);r['r2']=self.pop()
            r['pc']=r['pr'];return
        self.step(entry+6);self.push(r['r3'])
        self.step(entry+8);r['r2']=0
        if remainder:
            self.step(0x06094272);self.push(r['r4'])
            self.step(0x06094274);self.div0s('r2','r1')
            self.step(0x06094276);r['r4']=r['sr']&1
            self.step(0x06094278);self.subc('r3','r3')
            self.step(0x0609427A);self.subc('r2','r1')
            self.step(0x0609427C);self.div0s('r0','r3')
            first=0x0609427E
        else:
            self.step(0x06094116);self.div0s('r2','r1')
            self.step(0x06094118);self.subc('r3','r3')
            self.step(0x0609411A);self.subc('r2','r1')
            self.step(0x0609411C);self.div0s('r0','r3')
            first=0x0609411E
        for i in range(32):
            self.step(first+4*i);self.rotcl('r1')
            self.step(first+4*i+2);r['r3'],r['sr']=div1(r['r3'],r['r0'],r['sr'])
        if not remainder:
            self.step(0x0609419E);self.rotcl('r1')
            self.step(0x060941A0);value=r['r1']+r['r2']+(r['sr']&1);r['r1']=value&MASK;self.t(value>MASK)
            self.step(0x060941A2);r['r0']=r['r1']
            self.step(0x060941A4);r['r3']=self.pop()
            self.step(0x060941A6)
            self.step(0x060941A8,True);r['r2']=self.pop()
        else:
            self.step(0x060942FE);self.div0s('r2','r3')
            self.step(0x06094300);r['r2']=r['sr']&1
            self.step(0x06094302);r['r2']^=r['r4']
            self.step(0x06094304);old,t=r['r2'],r['sr']&1;r['r2']=(old>>1)|(t<<31);self.t(old&1)
            self.step(0x06094306)
            if r['sr']&1:
                self.step(0x06094308);self.div0s('r0','r3')
                self.step(0x0609430A);old=r['r3'];r['r3']=(records.signed(old,32)>>1)&MASK;self.t(old&1)
                self.step(0x0609430C);r['r3'],r['sr']=div1(r['r3'],r['r0'],r['sr'])
            self.step(0x0609430E);r['r3']=(r['r3']+r['r4'])&MASK
            self.step(0x06094310);r['r0']=r['r3']
            self.step(0x06094312);r['r4']=self.pop()
            self.step(0x06094314);r['r3']=self.pop()
            self.step(0x06094316)
            self.step(0x06094318,True);r['r2']=self.pop()
        r['pc']=r['pr']

    def format(self):
        r=self.reg
        self.step(FORMAT);r['r3']=64
        self.step(FORMAT+2);self.t(not(r['r4']&64))
        self.step(FORMAT+4)
        if not r['sr']&1:
            self.step(0x060A6DAC);r['r4']=self.read(0x060A6DB2,2)
            self.step(0x060A6DAE);self.step(0x060A6DB0,True)
        else:
            self.step(0x060A6DC4);r['r5']=8
            self.step(0x060A6DC6);r['r2']=16
            self.step(0x060A6DC8);self.t(not(r['r4']&16))
            self.step(0x060A6DCA)
            self.step(0x060A6DCC,True);r['r5']&=r['r4']
            if r['sr']&1:
                self.step(0x060A6DDC);r['r6']=self.read(0x060A6E90,2)
                self.step(0x060A6DDE);self.t(r['r5']==0)
                self.step(0x060A6DE0);r['r4']=r['r6']
            else:
                self.step(0x060A6DCE);self.t(r['r5']==0)
                self.step(0x060A6DD0)
                if r['sr']&1:
                    self.step(0x060A6DD6);r['r4']=self.read(0x060A6E8E,2)
                    self.step(0x060A6DD8);self.step(0x060A6DDA,True)
                else:
                    self.step(0x060A6DD2)
                    self.step(0x060A6DD4,True);r['r4']=0
        self.step(0x060A6DE2)
        self.step(0x060A6DE4,True);r['r0']=r['r4']
        r['pc']=r['pr']


def cases(family):
    if family not in FAMILIES:raise ValueError('Unknown arithmetic/format family')
    if family=='format':
        return [(family,v,(0,255)[v],high|low,0,(7,0)[v]) for v,high,low in itertools.product(
            range(2),(0,0x100,0x10000,0x80000000,0xFFFFFF00,0x7FFFFF00),range(256))]
    nums=tuple(n&MASK for n in range(-128,128))+(0x100,0xFFFF,0x10000,0xFFFF0000,0x80000000,
          0x80000001,0x7FFFFFFF,0x7FFFFFFE,0xDEADBEEF,0x55555555,0xAAAAAAAA,0x40000000)
    divisors=tuple(n&MASK for n in (0,1,-1,2,-2,3,-3,8,-8,2048,-2048,0x7FFFFFFF,0x80000000))
    rows=[(family,v,(0,255)[v],n,d,(7,0)[v]) for v,n,d in itertools.product(range(2),nums,divisors)]
    rows += [(family,v,37,n,0,flags) for v,n,flags in itertools.product(range(2),(0,1,MASK,0x80000000),range(8))]
    return list(dict.fromkeys(rows))


def contract(data,case):
    family,variant,seed,a,b,flags=case
    if (family not in FAMILIES or type(variant) is not int or variant not in (0,1) or
            type(seed) is not int or seed not in (0,37,255) or type(flags) is not int or not 0<=flags<8 or
            any(type(value) is not int or not 0<=value<=MASK for value in (a,b))):
        raise ValueError('Outside arithmetic/format contract')
    before=records.initial(ENTRIES[family],a if family=='format' else 0xDEADBEEF,variant)
    before['r15']-=0x100+variant*0x1000
    before['sr']=(before['sr']&~0x301)|(flags&1)|((flags&6)<<7)
    if family!='format':before['r0'],before['r1']=b,a
    canary=lambda n:bytes((seed+37*i)&255 for i in range(n))
    depth=0 if family=='format' else 4 if b==0 else 12 if family=='remainder' else 8
    sp=before['r15']
    regions=[(ERROR_CELL-16,canary(16),False),(ERROR_CELL,canary(4),family!='format' and b==0),
             (ERROR_CELL+4,canary(16),False),(sp-64,canary(64-depth),False)]
    if depth:regions.append((sp-depth,canary(depth),True))
    regions.append((sp,canary(64),False))
    if family=='format':
        for address,value in SHORTS.items():
            raw=data[address-pinned.BASE:address-pinned.BASE+2]
            if raw!=value.to_bytes(2,'big'):raise ValueError('Original format literal differs')
            regions.append((address,raw,False))
    model=Model(before,[(lo,buf) for lo,buf,_ in regions])
    if family=='format':model.format()
    else:model.divide(family=='remainder')
    expected=[buf for _,buf,_ in regions]
    if family=='format':
        result=0x930 if a&64 else ((0 if a&8 else 0x914) if a&16 else 0x800)
    else:
        quotient,remainder=scalar(a,b);result=remainder if family=='remainder' else quotient
        words=(before['r2'],) if b==0 else (before['r4'],before['r3'],before['r2']) if family=='remainder' else (before['r3'],before['r2'])
        expected[4]=b''.join(value.to_bytes(4,'big') for value in words)
        if b==0:
            expected[1]=(0x44E).to_bytes(4,'big')
            if model.reg['sr']!=(before['sr']|1):raise ValueError('Zero-divisor SR contract differs')
        else:
            adjust=(a^b)>>31;pre=(quotient-adjust)&MASK
            partial=(adjust<<31)|(pre>>1)
            if model.reg['r1']!=(partial if family=='remainder' else quotient):
                raise ValueError('Independent quotient-register contract differs')
            if family=='quotient':
                q=(b>>31)^int(not(pre&1));t=int(quotient==0 and bool(adjust))
                sr=(before['sr']&~0x301)|((b>>31)<<9)|(q<<8)|t
                if model.reg['sr']!=sr:raise ValueError('Independent quotient SR formula differs')
    if result!=model.reg['r0'] or expected!=[bytes(buf) for buf in model.buffers]:
        raise ValueError('Independent scalar arithmetic/format result/memory differs')
    return model,regions


def observe(data,emu,family,before,regions):
    ranges=(((QUOTIENT,0x060941B6),) if family=='quotient' else ((REMAINDER,0x06094326),)
            if family=='remainder' else ((FORMAT,0x060A6DB2),(0x060A6DC4,0x060A6DE6)))
    return guard.observe(data,emu,before['pc'],regions,before,ranges=ranges,literals=tuple(LONGS),
                         aliases=(),terminals={before['pr']:'returned'},budget=128)


def run_case(data,emu,case):
    model,regions=contract(data,case);actual=observe(data,emu,case[0],model.before,regions);reason=None
    if actual['status']!='returned':reason='Original arithmetic/format failed: '+str(actual['error'])
    elif actual['registers']!=model.reg:reason='Arithmetic/format register/PC/SR/PR/MAC differs'
    elif actual['trace']!=model.trace or actual['steps']!=len(model.trace):reason='Arithmetic/format PC/delay trace differs'
    elif actual['events']!=model.events:reason='Arithmetic/format ordered transactions differ'
    elif actual['regions_after']!=[bytes(buf) for buf in model.buffers] or not actual['original_unaffected_bytes_equal']:
        reason='Arithmetic/format output/stack/canaries/source differs'
    if reason:raise task.CaseFailure(reason,case,actual)
    return {'case':list(case),'status':'returned','instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],
            'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']],'all_visible_state_checked':True}


class EvidenceFailure(ValueError):
    def __init__(self,reason,partial):super().__init__(reason);self.partial=partial


def execute(data,emu,family):
    selected=cases(family);rows=[]
    for case in selected:
        try:rows.append(run_case(data,emu,case))
        except task.CaseFailure as error:error.completed_results=rows;raise
    if not rows:raise ValueError('Require nonempty original arithmetic cases')
    positive={'cases':len(rows),'complete_returns':len(rows),'results':rows,
        'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'original_game_bytes_executed':True}
    mutations=({'quotient':(('lost-first-DIV1',0x06094120,9),('lost-final-carry',0x060941A0,9),
            ('lost-R2-delay',0x060941A8,9),('lost-zero-error-store',0x060941B0,9)),
        'remainder':(('lost-first-DIV1',0x06094280,9),('lost-sign-adjust',0x0609430E,9),
            ('lost-R4-restore',0x06094312,9),('lost-R2-delay',0x06094318,9),('lost-zero-error-store',0x06094320,9)),
        'format':(('changed-bit64-mask',FORMAT,0xE320),('lost-bit8-delay',0x060A6DCC,9),
            ('lost-invalid-zero-delay',0x060A6DD4,9),('lost-result-delay',0x060A6DE4,9))})[family]
    chosen=list(dict.fromkeys(selected[:32]+selected[::max(1,len(selected)//64)]+selected[-64:]));controls={}
    for name,pc,word in mutations:
        changed=bytearray(data);changed[pc-pinned.BASE:pc-pinned.BASE+2]=word.to_bytes(2,'big')
        count,first=0,None
        for case in chosen:
            try:run_case(changed,emu,case)
            except task.CaseFailure as error:
                fault=error.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']:continue
                count+=1
                if first is None:first=error.evidence
        if not count:raise EvidenceFailure('No non-budget arithmetic mutation rejection: '+name,
             {**positive,'instruction_controls':controls,'failed_control':{'name':name,'pc':pc,'tested':len(chosen)}})
        controls[name]={'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,
                        'mutated_kernel_sha256':pinned.digest(changed)}
    return {**positive,'instruction_controls':controls}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-library-arithmetic.v1','status':'failure','selection':args.family,
        'kernel_sha256':pinned.KERNEL_SHA256,'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2',
        'load_address':pinned.BASE,'lifetime':'resident-kernel','original_game_bytes_executed':False,
        'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,
        'primary_ISA':ISA_URL,'manual':'REJ09B0171-0500O,6.1.17-19','vendor_CPU_unchanged':True,
        'source_sha256':{Path(p).name:pinned.digest(Path(p).read_bytes()) for p in
             (__file__,task.__file__,records.__file__,pinned.__file__,guard.__file__)},
        'programme_status':'active; incomplete','limitations':['Constructed arguments/error-cell/stack; full32-bit input domain not exhaustively executed',
             'Primary-ISA bit model plus independent signed scalar model; no physical hardware timing claim',
             'FullA681A/95E5A/89C8, device/service/context behavior and whole-program denominators unresolved']}
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
                report.update(failure_evidence=error.evidence,original_game_bytes_executed=True,
                              completed_before_failure=getattr(error,'completed_results',[]))
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
