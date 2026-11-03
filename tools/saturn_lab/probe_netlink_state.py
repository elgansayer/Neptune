#!/usr/bin/env python3
"""Independent original NLSND state/ramp/device calls; frozen SCSP and bounded RAM.

This is a measured constructed-input contract, not natural audio/gameplay timing.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import analyze_sound_driver as sound
import m68k_scsp_state as native
import probe_kernel as pinned
import probe_netlink_pointer as leaf
import probe_netlink_records as records
import probe_netlink_ramp as ramp
import probe_command_dispatch as dispatch

STATE,EFFECT=0x51B2,0x535E
RANGES=((STATE,0x5414),(0x5494,0x54B6),(0x54FE,0x5586),(0x59F0,0x5A1A),
        (0x5AA2,0x5AC4),(0x5B4C,0x5B6E),(0x5BF6,0x5C18),(0x5CA0,0x5CE4))
TABLES=tuple((RANGES[i][1],RANGES[i+1][0]) for i in range(7))+((0x5CE4,0x5D70),)
MODES=('effects','state','helper','handler','dispatcher')
FULL_RANGES=RANGES+((0x41D4,0x4208),(0x1E56,0x1E62),(0x40FA,0x40FE),(0x17F2,0x18F2))


def signed(value,bits):
    value &= (1<<bits)-1
    return value-(1<<bits) if value>>(bits-1) else value


def word(before,value):return (before&0xFFFF0000)|(value&65535)

def byte(before,value):return (before&0xFFFFFF00)|(value&255)


def entries():return dict(effects=EFFECT,state=STATE,helper=0x41D4,handler=0x1E56,dispatcher=dispatch.ENTRY)

def base_case(mode='state'):
    return dict(mode=mode,sr=0x271F,variant=0,alias=True,pending=False,flags=0,
                current=(32,63,64),target=(64,32,63),steps=(1,254,3),
                magnitude=(1,2,3),remaining=(32,31,1),offsets=(0,0),gate=0xC0)


class Contract:
    """Semantic operations and explicit transactions, never an opcode interpreter."""
    def __init__(self,code,case,device):
        self.case=case;self.reference=code;self.device=device;self.events=[];self.pcs=[]
        if (case['mode'] not in MODES or case['sr'] not in records.SR_VALUES or
                type(case['variant']) is not int or case['variant'] not in (0,1) or
                type(case['alias']) is not bool or type(case['pending']) is not bool or
                type(case['flags']) is not int or not 0<=case['flags']<=255 or
                type(case['gate']) is not int or not 0<=case['gate']<=255):
            raise ValueError('Undeclared state case')
        for name,limit in [('current',127),('target',127),('steps',255),('magnitude',255),('remaining',255)]:
            if len(case[name])!=3 or any(type(v) is not int or not 0<=v<=limit for v in case[name]):
                raise ValueError('Undeclared '+name)
        if (len(case['offsets'])!=2 or any(type(v) is not int for v in case['offsets']) or
                case['offsets'][0] not in (0,2,16,36) or
                case['offsets'][1] not in (0,2,16,52)):
            raise ValueError('Undeclared device offsets')
        self.base=0x10000 if case['variant'] else 0x8000;self.record=self.base+0x28
        entry=entries()[case['mode']]
        self.regs=records.base_regs(entry,case['sr'])
        if case['variant']:self.regs[:15]=[r^0xFFFFFFFF for r in self.regs[:15]]
        self.regs[14]=self.record if case['alias'] or case['mode']=='effects' else 0x18000
        for i in range(3):
            self.regs[2+i]=byte(self.regs[2+i],case['target'][i])
            self.regs[5+i]=(self.regs[5+i]&0xFFFF0000)|case['current'][i]
        
        if case['mode'] in ('helper','handler','dispatcher'):
            for i in range(3):self.regs[i]=byte(self.regs[i],case['target'][i])
            self.regs[8]=0x28000
            self.regs[7]=(self.regs[7]&0xFFFFFF00)|0x11
        self.before=list(self.regs);self.extend=case['sr']&16
        context=bytearray((i*37+case['flags']+case['variant'])&255 for i in range(160))
        context[8+4]=case['gate'];context[8+6:8+8]=bytes(case['offsets'])
        context[8+8:8+15]=bytes((*case['target'],0x80 if case['pending'] else 0,*case['steps']))
        for i in range(3):
            for offset,values in ((0,case['current']),(0xC,case['target']),(0x12,case['target']),
                                  (6,case['steps']),(0x1A,case['steps']),(0x20,case['remaining']),
                                  (0x26,case['magnitude'])):
                context[8+0x28+offset+2*i]=values[i]
        context[8+0x28+0x2C]=case['flags']
        self.regions=[(0x412,self.base.to_bytes(4,'big'),False),
                      (self.base-8,bytes(context),True),
                      (leaf.SP-256,bytes([0xCD])*256+leaf.STOP.to_bytes(4,'big'),True),
                      *[(lo,code[lo:hi],False) for lo,hi in TABLES]]
        if not case['alias'] and case['mode']!='effects':
            caller=bytearray([0xAD]*64);caller[0x2C]=case['flags']^0xAA
            self.regions.append((0x18000,bytes(caller),False))
        self.regions.append((0x28000,bytes(case['target']),False))
        self.buffers=[bytearray(data) for _,data,_ in self.regions]

    def peek(self,address,size=1):
        for (lo,data,_),buffer in zip(self.regions,self.buffers):
            if lo<=address and address+size<=lo+len(data):return int.from_bytes(buffer[address-lo:address-lo+size],'big')
        raise ValueError('Oracle read outside explicit data')

    def access(self,kind,address,size,value=None):
        if address>=0x100700:
            if size!=2 or address&1:raise ValueError('Oracle unsupported device access')
            if kind==2:self.device=native.device.transition(self.device,address,value)
            elif address<0x100780:value=self.device['coef'][(address-0x100700)//2]<<3
            elif address<0x1007C0:value=self.device['madrs'][(address-0x100780)//2]
            else:raise ValueError('Oracle unsupported device read')
        elif kind==1:value=self.peek(address,size)
        else:
            for (lo,data,writable),buffer in zip(self.regions,self.buffers):
                if lo<=address and address+size<=lo+len(data):
                    if not writable:raise ValueError('Oracle write outside writable RAM')
                    buffer[address-lo:address-lo+size]=value.to_bytes(size,'big');break
            else:raise ValueError('Oracle unmapped write')
        self.events.append([kind,address,size,value]);return value

    def read(self,offset):return self.access(1,self.record+offset,1)
    def write(self,offset,value):self.access(2,self.record+offset,1,value)
    def bit(self,offset,mask,set_bit):
        old=self.read(offset);self.write(offset,old|mask if set_bit else old&~mask);return old
    def push(self,value):self.regs[15]-=4;self.access(2,self.regs[15],4,value)
    def pop(self):
        value=self.access(1,self.regs[15],4);self.regs[15]+=4;return value
    def ret(self):self.regs[16]=self.pop()
    def flags(self,value,bits):
        self.regs[17]=(self.case['sr']&~31)|self.extend|(8 if value&(1<<(bits-1)) else 4 if value==0 else 0)

    def prepare_ramp(self):
        # Reuse the accepted independent5290 contract by translating its RAM and
        # return address into this caller. Do not regenerate it from native output.
        current=tuple(self.regs[5+i]&255 for i in range(3))
        target=tuple(self.peek(self.record+0x12+2*i) for i in range(3))
        steps=tuple(self.peek(self.record+0x1A+2*i) for i in range(3))
        _,after,regions,_,events,pcs=ramp.contract(self.case['sr'],0,self.peek(self.record+0x2C),current,target,steps)
        ret=self.peek(self.regs[15],4);self.pcs+=pcs
        for kind,address,size,value in events:
            at=self.regs[15] if address==leaf.SP else address-0x8000+self.record
            observed=self.access(kind,at,size,ret if address==leaf.SP else value)
            if kind==1 and observed!=(ret if address==leaf.SP else value):raise ValueError('Ramp caller input differs')
        self.regs[0]=after[0]
        for i in range(1,5):self.regs[i]=byte(self.regs[i],after[i])
        self.regs[15]+=4;self.regs[16]=ret;self.regs[17]=after[17];self.extend=after[17]&16

    def effects(self):
        self.pcs += [0x535E,0x5364,0x5368,0x536C,0x5370,0x5372,0x5376,0x5378,0x537C,0x537E]
        self.regs[10]=self.access(1,0x412,4)
        self.regs[12]=0x100700+self.access(1,self.regs[10]+6,1)
        self.regs[11]=0x100780+self.access(1,self.regs[10]+7,1)
        self.bit(0x2C,1,False)
        current=[]
        for i,at in enumerate((0x5384,0x53A8,0x53CC)):
            now,goal=self.regs[5+i]&255,self.regs[2+i]&255
            self.pcs += [at,at+2]
            if now!=goal:
                delta=self.read(6+2*i);magnitude=self.read(0x26+2*i)
                self.bit(0x2C,1,True);left=self.read(0x20+2*i)
                self.write(0x20+2*i,(left-magnitude)&255)
                now=(now+delta)&255 if left>magnitude else goal
                now &= 127
                self.pcs += [at+6,at+10,at+14,at+20,at+22,at+26]
                if left<=magnitude:self.pcs.append(at+30)
                self.pcs.append(at+32)
            self.regs[5+i]=byte(self.regs[5+i],now);current.append(now)
        a,b,c=current
        for i in range(3):self.write(2*i,current[i])
        self.pcs += [0x53F0,0x53F4,0x53F8,0x53FC,0x5402,0x5404,0x5406,0x540A,0x540C,0x5410]
        self.access(2,self.regs[12]+0x5A,2,self.access(1,0x5414+a,1)<<8)
        self.pcs += [0x5494,0x5496,0x549A]
        if c&64:self.pcs += [0x549E,0x54A2]
        folded_c=128-c if c&64 else c
        self.pcs += [0x54A4,0x54A6,0x54A8,0x54AC,0x54AE,0x54B2]
        self.access(2,self.regs[12]+0x4C,2,self.access(1,0x54B6+folded_c,1)<<8)
        self.pcs += [0x54FE,0x5500,0x5504]
        if c&64:self.pcs += [0x5508,0x550C]
        triangular_c=folded_c&63
        self.pcs += [0x550E,0x5510,0x5512,0x5516,0x551A]
        if triangular_c&32:
            triangular_c=(64-folded_c)&255;self.pcs += [0x551E,0x5522]
        self.regs[4]=triangular_c
        self.pcs += [0x5524,0x5526,0x552A]
        if b&64:self.pcs += [0x552E,0x5532]
        folded_b=128-b if b&64 else b;triangular_b=folded_b&63
        self.pcs += [0x5534,0x5536,0x5538,0x553C,0x5540]
        if triangular_b&32:
            triangular_b=(64-folded_b)&255;self.pcs += [0x5544,0x5548]
        self.pcs += [0x554A,0x554C,0x554E,0x5550,0x5552,0x5554,0x5556,0x555A,0x555E]
        address_delta=self.access(1,0x5586+33*triangular_b+triangular_c,1)
        if b&64:
            self.pcs += [0x5562,0x5566,0x556A,0x5570]
            self.access(2,self.regs[11]+8,2,(address_delta+self.access(1,self.regs[11],2))&65535)
            self.access(2,self.regs[11]+10,2,self.access(1,self.regs[11]+2,2))
        else:
            self.pcs += [0x5574,0x5578,0x557E,0x5582]
            accumulated=(address_delta+self.access(1,self.regs[11]+2,2))&65535
            self.access(2,self.regs[11]+8,2,self.access(1,self.regs[11],2))
            self.access(2,self.regs[11]+10,2,accumulated)
        self.pcs += [0x59F0,0x59F2,0x59F4]
        self.regs[3]=self.access(1,0x59C8+triangular_c,1)
        for at,table,dest in ((0x59F8,0x5A1A,0x4E),(0x5AA2,0x5AC4,0x50),
                              (0x5B4C,0x5B6E,0x52),(0x5BF6,0x5C18,0x54)):
            self.pcs += [at,at+2,at+4,at+8,at+12,at+14,at+18,at+20,at+24,at+26,at+30]
            self.mix(table,b,32,dest)
        self.pcs += [0x5CA0,0x5CA2,0x5CA4,0x5CA8,0x5CAC,0x5CAE,0x5CB2,0x5CB4,0x5CB8,0x5CBA]
        self.mix(0x5CE4,b,80,0x58)
        self.pcs += [0x5CBE,0x5CC2,0x5CC4,0x5CC6,0x5CC8,0x5CCC,0x5CD0,0x5CD2,0x5CD6,0x5CD8,0x5CDC,0x5CDE,0x5CE2]
        self.regs[1]=128-b;self.mix(0x5CE4,128-b,80,0x56);self.ret()

    def mix(self,table,index,centre,destination):
        self.regs[8]=index
        delta=self.access(1,table+index,1)-centre
        product=(delta*self.regs[3])&0xFFFFFFFF
        rounded=signed(((product&65535)+64)&65535,16)>>7
        unshifted=(rounded+centre)&65535;value=(unshifted<<8)&65535
        self.regs[0]=(product&0xFFFF0000)|value
        self.extend=16 if unshifted&0x100 else 0
        self.flags(value,16);self.access(2,self.regs[12]+destination,2,value)

    def state(self):
        saved=list(self.regs[:15])
        for reg in reversed(range(15)):
            self.regs[15]-=4;self.access(2,self.regs[15]+2,2,saved[reg]&65535)
            self.access(2,self.regs[15],2,saved[reg]>>16)
        self.regs[10]=self.access(1,0x412,4);self.regs[14]=self.regs[10]+0x28;self.regs[13]=self.regs[10]+8
        self.record=self.regs[14];self.regs[0]=self.access(1,self.regs[10]+7,1)
        self.pcs += [0x51B2,0x51B6,0x51BA,0x51BE,0x51C2,0x51C4,0x51C6,0x51CA,0x51CC,0x51D2]
        pending=self.access(1,self.regs[13]+3,1);self.access(2,self.regs[13]+3,1,pending&127)
        if pending&128:
            for i in range(5):self.write(0x12+2*i,self.access(1,self.regs[13]+i,1))
            self.pcs += [0x51D6,0x51DC,0x51E2,0x51E8,0x51EE,0x51F4]
            if not self.peek(self.record+0x1A):self.write(0x1A,1);self.pcs.append(0x51F8)
            for i,at in ((5,0x51FE),(6,0x5216)):
                self.write(0x12+2*i,self.access(1,self.regs[13]+i,1))
                raw=self.access(1,self.regs[13]+i,1);self.pcs += [at,at+6,at+10,at+14]
                if not raw&127:self.write(0x12+2*i,1);self.pcs.append(at+18)
            self.bit(0x2C,2,True);self.pcs.append(0x522E)
        for i in range(3):self.regs[2+i]=byte(self.regs[2+i],self.read(0xC+2*i))
        for i in range(3):self.regs[5+i]=self.read(2*i)
        self.pcs += [0x5234,0x5238,0x523C,0x5240,0x5242,0x5244,0x5246,0x524A,0x524E,0x5252,0x5258]
        active=bool(self.read(0x2C)&1)
        prepare=False
        if not active:
            old=self.bit(0x2C,2,False);prepare=bool(old&2);self.pcs += [0x525C,0x5262]
            if prepare:
                self.pcs.append(0x5266);self.push(0x526A);self.prepare_ramp()
        if active or prepare:
            self.pcs.append(0x526A);self.push(0x526E);self.effects()
        for i in range(3):self.access(2,self.regs[13]+8+i,1,self.read(2*i))
        self.pcs += [0x526E,0x5274,0x527A,0x5280]
        for reg in range(15):self.regs[reg]=self.pop()
        self.pcs += [0x5284,0x5286,0x528A,0x528E]
        self.regs[0]=self.access(1,self.regs[14]+0x2C,1)&3;self.flags(self.regs[0],8);self.ret()

    def command_helper(self):
        self.pcs += [0x41D4,0x41D8,0x41DC,0x41E0]
        self.regs[8]=self.access(1,0x412,4)
        gate=self.access(1,self.regs[8]+4,1)&0xC0
        self.regs[4]=byte(self.regs[4],gate)
        if gate:
            self.pcs += [0x41E4,0x41EA,0x41EC,0x41EE,0x41F0,0x41F4,0x41F8,0x41FC,0x4200]
            self.regs[8]+=8
            for value in [*(self.regs[i]&255 for i in range(3)),128,127,127]:
                self.access(2,self.regs[8],1,value);self.regs[8]+=1
            self.access(2,self.regs[8],1,127)
            self.push(0x4204);self.state();self.pcs.append(0x4204)
        self.pcs += [0x40FA,0x40FC];self.flags(self.regs[0]&65535,16);self.ret()

    def handler(self):
        self.pcs += [0x1E56,0x1E58,0x1E5A,0x1E5C]
        for i in range(3):
            self.regs[i]=byte(self.regs[i],self.access(1,self.regs[8],1));self.regs[8]+=1
        self.push(0x1E60);self.command_helper();self.pcs.append(0x1E60);self.ret()

    def dispatcher(self):
        self.pcs+=dispatch.contract(0x11,self.before[0]&65535,self.before[7]&0xFFFFFF00,
                                    self.case['sr'],self.before[14])[5]
        for reg in (14,13):
            self.regs[15]-=4;self.access(2,self.regs[15]+2,2,self.regs[reg]&65535)
            self.access(2,self.regs[15],2,self.regs[reg]>>16)
        self.push(0x1868);self.regs[7]=(self.regs[7]&0xFFFF0000)|0x44
        # The original two ADD.W index doublings cannot carry for command11.
        # Their X=0 survives the disabled helper's ANDI.B and final OR.W.
        self.extend=0
        self.regs[12]=self.regs[14];self.handler();self.pcs += [0x1868,0x186C]
        self.regs[13]=self.pop();self.regs[14]=self.pop();self.ret()

    def run(self):
        {'effects':self.effects,'state':self.state,'helper':self.command_helper,
         'handler':self.handler,'dispatcher':self.dispatcher}[self.case['mode']]()
        return self.regs,[bytes(b) for b in self.buffers],self.events,self.pcs,self.device


def run_case(code,library,case,executed_code=None):
    device=(0xFFFFFFFF,1) if case['variant'] else (0x12345678,0)
    library.configure(device);before_device=library.snapshot()
    contract=Contract(code,case,before_device)
    expected,after,events,pcs,device_after=contract.run()
    entry=entries()[case['mode']]
    actual=library.run(code if executed_code is None else executed_code,entry,leaf.STOP,FULL_RANGES,
                       contract.regions,contract.before,budget=512,device=device)
    records.check(actual,expected,after,events,pcs)
    if actual['device_before']!=before_device or actual['device_after']!=device_after:
        raise ValueError('Independent device state differs')
    return dict(case=case,registers=actual['registers'],events=actual['events'],pcs=actual['pcs'],
                instructions=actual['steps'],regions_after_sha256=[pinned.digest(b) for b in actual['regions_after']],
                model_cycles=actual['model_cycles'],device_after=actual['device_after'],code_unchanged=actual['code_unchanged'])


def cases():
    selected={}
    def add(case):selected[json.dumps(case,sort_keys=True)]=case
    for mode in MODES:
        gates=(0,63,64,128,192) if mode in ('helper','handler','dispatcher') else (192,)
        for sr,variant,alias,pending,flags,gate in itertools.product(records.SR_VALUES,(0,1),(False,True),
                                                                  (False,True),(0,1,2,3,255),gates):
            case=base_case(mode);case.update(sr=sr,variant=variant,alias=alias,pending=pending,flags=flags,gate=gate);add(case)
        for field,limit in [('current',128),('target',128),('steps',256),('magnitude',256),('remaining',256)]:
            for axis in range(3):
                for value in range(limit):
                    case=base_case(mode);values=list(case[field]);values[axis]=value;case[field]=tuple(values)
                    case.update(sr=records.SR_VALUES[value%4],variant=(value//4)%2,
                                alias=bool(value&8),pending=bool(value&16),flags=1 if field!='steps' else 2)
                    if field in ('current','target'):
                        other='target' if field=='current' else 'current'
                        values=list(case[other]);values[axis]=value;case[other]=tuple(values)
                    add(case)
        for flags in range(256):
            case=base_case(mode);case.update(flags=flags,pending=bool(flags&4),alias=bool(flags&8));add(case)
        if mode in ('helper','handler','dispatcher'):
            for gate in range(256):
                case=base_case(mode);case.update(gate=gate,flags=3,variant=gate%2);add(case)
        for current,target,steps in itertools.product((0,1,31,32,63,64,65,126,127),
                                                     (0,1,31,32,63,64,65,126,127),
                                                     ((0,0,0),(1,128,255),(127,127,127),(255,2,0))):
            case=base_case(mode);case.update(current=(current,)*3,target=(target,)*3,steps=steps,
                 magnitude=(0,127,255),remaining=(0,1,255),flags=3,pending=bool(current&1));add(case)
    # All declared seven-bit second/third current pairs, without ramping. This
    # exercises both folded lookup axes and every addressed point of the33x33 grid.
    for b,c in itertools.product(range(128),repeat=2):
        case=base_case('effects');case.update(current=(32,b,c),target=(32,b,c),flags=(b^c),
             variant=(b//16)%2,sr=records.SR_VALUES[c%4],offsets=((0,2,16,36)[b%4],(0,2,16,52)[c%4]));add(case)
    return [selected[k] for k in sorted(selected)]


def original_copy_controls(code,library):
    controls={}
    for name,address,replacement,modes in (
        ('countdown_comparison',0x539E,bytes([code[0x539E]^1]),MODES),
        ('active_state_bit',0x5380,bytes.fromhex('0001'),MODES),
        ('final_coefficient_shift',0x5CDC,((int.from_bytes(code[0x5CDC:0x5CDE],'big')&~0xE00)|0xE00).to_bytes(2,'big'),MODES),
        ('restored_caller_result_mask',0x528C,bytes.fromhex('0001'),('state','helper','handler','dispatcher')),
        ('command_gate',0x41DE,bytes.fromhex('0080'),('helper','handler','dispatcher'))):
        altered=bytearray(code);altered[address:address+len(replacement)]=replacement
        if altered==code:raise ValueError('Ineffective original-copy control')
        rejected=Counter();completed=0
        for mode,variant in itertools.product(modes,(0,1)):
            case=base_case(mode);case.update(flags=3,variant=variant,gate=64,
                current=(10,20,30),target=(10,20,30) if name=='active_state_bit' else (12,25,35),
                steps=(1,1,1),magnitude=(1,1,1),remaining=(2,5,5))
            if name=='restored_caller_result_mask':case['alias']=True
            dev=(0xFFFFFFFF,1) if variant else (0x12345678,0)
            library.configure(dev);model=Contract(code,case,library.snapshot())
            actual=library.run(bytes(altered),entries()[mode],leaf.STOP,FULL_RANGES,model.regions,model.before,budget=512,device=dev)
            if actual['status_code']!=1:raise ValueError('Mutation stopped before terminal semantic comparison: '+name)
            completed+=1
            try:run_case(code,library,case,executed_code=bytes(altered))
            except ValueError as error:
                if str(error).startswith('Native guard:'):raise
                rejected[str(error)]+=1
            else:raise ValueError('Terminal original-copy mutation escaped: '+name+' '+mode)
        controls[name]={'terminal_comparisons':completed,'rejected':sum(rejected.values()),'reasons':dict(rejected)}
    return controls


def execute(code,library):
    selected=cases();digest=hashlib.sha256();counts=Counter();coverage=[set() for _ in TABLES];samples={}
    for case in selected:
        row=run_case(code,library,case);counts[(case['mode'],row['instructions'])]+=1
        digest.update(json.dumps(row,sort_keys=True,separators=(',',':')).encode())
        key=(case['mode'],EFFECT in row['pcs'])
        if key not in samples:samples[key]=row
        for kind,address,size,value in row['events']:
            if kind==1:
                for i,(lo,hi) in enumerate(TABLES):
                    if lo<=address<hi:coverage[i].add(address)
    controls=original_copy_controls(code,library)
    diagnostics={}
    for name,field in [('odd-coefficient-address',6),('odd-address-register',7)]:
        case=base_case('effects');library.configure((0x12345678,0));model=Contract(code,case,library.snapshot())
        regions=list(model.regions);lo,data,writable=regions[1];data=bytearray(data);data[8+field]=1
        regions[1]=(lo,bytes(data),writable)
        actual=library.run(code,EFFECT,leaf.STOP,FULL_RANGES,regions,model.before,budget=512)
        expected_address=0x10075B if field==6 else 0x100783
        if (actual['status_code'],actual['error_address'],actual['error_size'])!=(3,expected_address,2):
            raise ValueError('Unsupported odd-address diagnostic differs')
        diagnostics[name]={'status':actual['status'],'error_address':actual['error_address'],
             'steps':actual['steps'],'completed_original_call':False,'last_pc':actual['pcs'][-1]}
    return dict(cases=len(selected),observations_sha256=digest.hexdigest(),
                instruction_counts=[{'mode':m,'steps':s,'cases':n} for (m,s),n in sorted(counts.items())],
                table_address_coverage=[{'lo':lo,'end':hi,'distinct_read_addresses':len(addresses),
                  'min_read':min(addresses) if addresses else None,'max_read':max(addresses) if addresses else None}
                  for (lo,hi),addresses in zip(TABLES,coverage)],samples=list(samples.values()),
                terminal_original_copy_controls=controls,incomplete_native_diagnostics=diagnostics,
                original_game_bytes_executed=True,natural_field_domains_or_audio_timing_recovered=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True);parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report=dict(schema='neptune.original-nlsnd-state.v1',status='failure',release='usa-mk81070-v1003',
                module='NLSND',cpu='m68000',load_address=0,lifetime='netlink-sound-driver',
                source_path='NETLINK/SNDDRV.BIN',driver_sha256=sound.SOURCES['NLSND'][1],
                native_identity=native.identity(),probe_sha256=pinned.digest(Path(__file__).read_bytes()),
                ramp_contract_sha256=pinned.digest(Path(ramp.__file__).read_bytes()),
                limitations=['Constructed calls in a pinned CPU interpreter with frozen SCSP; no independent hardware proof',
                             'Natural state/command/function domains and sound roles remain unknown',
                             'No Godot campaign/battle, native pixel/audio/timing or full-game/code acceptance'])
    fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:
        phase='identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');library=native.Library(args.prepared)
            report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:report['error']={'phase':phase,'type':type(error).__name__,'reason':str(error)}
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'error':report.get('error')}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
