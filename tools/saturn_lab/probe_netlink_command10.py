#!/usr/bin/env python3
"""Independent complete constructed command10 contracts, not natural traffic.

The specification models descriptor/channel/reset operations and their ordered
observations. It never interprets candidate/original instructions as its oracle.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import itertools
import json
import os
from pathlib import Path
import analyze_sound_driver as sound
import m68k_scsp_long as native
import probe_command_dispatch as dispatch
import probe_netlink_pointer as leaf
import probe_netlink_records as records
import probe_netlink_slot_effects as effects
import probe_netlink_dsp_reset as reset

RAM,POOL=0x7000,0x20000
RANGES=[(0x1640,0x167A),(0x1DEA,0x1E2E),(0x1E68,0x1EEE),(0x3530,0x35BC),
        (0x4412,0x4442),(0x4B00,0x4B6E),(0x4BB6,0x4BE0),(0x4C2A,0x4C9A),(0x17F2,0x18F2)]
# gate, sign, redirect byte, queue counter, slot shape, caller slot base, register variant
PROFILES=((0,0,0,0,0,0,0),(1,0x80,1,250,1,1,1),(0,0x80,1,255,2,14,0),
          (255,0,255,0,3,14,1),(0,0,255,250,4,1,1),(1,0xFF,0,255,2,0,0))
INPUTS=(0x40000,RAM+0x187E,RAM+0x188B,RAM+0x188E,POOL+0x2100,0x780)


def selection():
    rows=set()
    for mode,profile,mask,sr in itertools.product(('handler','dispatcher'),range(6),range(32),records.SR_VALUES):
        rows.add((mode,tuple((mask>>i)&1 for i in range(5)),profile,sr,0,0))
    for mode,profile,mask,location in itertools.product(('handler','dispatcher'),(0,2),range(32),range(1,6)):
        rows.add((mode,tuple((mask>>i)&1 for i in range(5)),profile,0x271F,location,0xFFFF))
    for mode,index,value,surround in itertools.product(('handler','dispatcher'),range(5),range(256),(0,1)):
        controls=[surround]*5;controls[index]=value;profile=(index+value+surround)%6
        rows.add((mode,tuple(controls),profile,records.SR_VALUES[(index+value)%4],0,0x8000 if value&128 else 0))
    for mode,location,index,value,surround in itertools.product(('handler','dispatcher'),range(1,6),range(5),(0,1,2,127,128,129,255),(0,1)):
        controls=[surround]*5;controls[index]=value
        rows.add((mode,tuple(controls),(index+location)%6,0x2015,location,0xFFFF))
    for mode,value,last in itertools.product(('handler','dispatcher'),range(256),(0,1)):
        # Custom redirect values use profile identifiers6..261, preserving profile0's other fields.
        rows.add((mode,(0,0,0,1,last),6+value,0x271F,0,0))
    for mode,profile,word,mask in itertools.product(('handler','dispatcher'),range(6),dispatch.WORDS,(0,1,8,16,31)):
        rows.add((mode,tuple((mask>>i)&1 for i in range(5)),profile,0x200A,0,word))
    for mode,mask in itertools.product(('handler','dispatcher'),range(8)):
        rows.add((mode,tuple((mask>>i)&1 for i in range(3))+(1,),0,0x271F,0,0))
    return sorted(rows)


def profile_values(index):
    if type(index) is not int or not 0<=index<262:raise ValueError('Undeclared profile')
    return PROFILES[index] if index<6 else (*PROFILES[0][:2],index-6,*PROFILES[0][3:])


class Contract:
    def __init__(self,case,device):
        mode,controls,profile,sr,location,word=case
        gate,sign,redirect,counter,shape,slot_base,variant=profile_values(profile)
        if (mode not in ('handler','dispatcher') or len(controls) not in (4,5)
                or any(type(v) is not int or not 0<=v<=255 for v in controls)
                or sr not in records.SR_VALUES or type(location) is not int or not 0<=location<len(INPUTS)
                or type(word) is not int or not 0<=word<=65535
                or (len(controls)==4 and (location!=0 or controls[3]!=1 or gate!=0))):raise ValueError('Undeclared command10 case')
        self.case=case;entry=0x1E68 if mode=='handler' else dispatch.ENTRY
        self.regs=records.base_regs(entry,sr)
        if variant:self.regs[:15]=[v^0xFFFFFFFF for v in self.regs[:15]]
        self.regs[0]=(self.regs[0]&0xFFFF0000)|word
        if mode=='dispatcher':self.regs[7]=(self.regs[7]&0xFFFFFF00)|0x10
        self.regs[8]=INPUTS[location];self.regs[13]=0x100000+slot_base*32;self.regs[14]=0x50000 if variant else 0x24000
        self.before=list(self.regs);self.device=deepcopy(device);self.events=[];self.bus=[];self.pcs=[];self.emitted=0
        ram=bytearray((i*37+profile)&255 for i in range(0x2000))
        ram[0x1831]=sign;ram[0x1832]=gate;ram[0x188E]=redirect
        ram[0x1890:0x18A0]=bytes((0 if shape==0 else 0x80|((i*3)&31) if shape in (1,2) else 0x7F if i&1 else 0xFF) for i in range(16))
        pool=bytearray((i*53+71+profile)&255 for i in range(0x2800));pool[0x1840]=counter
        tags=(0,9,255,7,8,127,128,31) if variant else tuple(range(8))
        for i in range(8):pool[0x2100+96*i+1]=tags[i]
        for i in range(32):
            at=0x2400+12*i;active=shape in (1,2) or (shape==3 and i%2==0) or shape==4
            pool[at]=int(active)*128|(i&1);pool[at+1:at+4]=bytes(((i*7+0x91)&255,(i*17+0x7F)&255,(i*29+0x80)&255))
            target=POOL+0x2100+96*(0 if shape==1 else i%8) if shape in (1,2) else POOL+0x3000
            pool[at+8:at+12]=target.to_bytes(4,'big')
        low=bytes((i*37+profile)&255 for i in range(48))
        stack=bytes([0xCD])*512+leaf.STOP.to_bytes(4,'big')+bytes([0xAD])*32
        self.regions=[(0x450,POOL.to_bytes(4,'big'),False),(RAM,bytes(ram),True),(POOL,bytes(pool),True),
                      (0x770,low,True),(leaf.SP-512,stack,True)]
        if location==0:self.regions.append((INPUTS[location],bytes(controls),False))
        self.buffers=[bytearray(b) for _,b,_ in self.regions]
        if location:
            address=INPUTS[location]
            for (lo,data,_),buf in zip(self.regions,self.buffers):
                if lo<=address and address+len(controls)<=lo+len(data):buf[address-lo:address-lo+len(controls)]=bytes(controls);break
            else:raise ValueError('Unmapped input alias')
            self.regions=[(lo,bytes(buf),w) for (lo,_,w),buf in zip(self.regions,self.buffers)]

    def regbyte(self,index,value):self.regs[index]=(self.regs[index]&0xFFFFFF00)|(value&255)
    def regword(self,index,value):self.regs[index]=(self.regs[index]&0xFFFF0000)|(value&65535)
    def logic(self,value,bits=8):self.regs[17]=(self.regs[17]&~15)|(8 if value&(1<<(bits-1)) else 4 if value==0 else 0)
    def extend(self,value):self.regs[17]=(self.regs[17]&~16)|(16 if value else 0)
    def peek(self,address,size):
        for (lo,data,_),buf in zip(self.regions,self.buffers):
            if lo<=address and address+size<=lo+len(data):return int.from_bytes(buf[address-lo:address-lo+size],'big')
        raise ValueError('Oracle unmapped read: '+hex(address))
    def access(self,kind,address,size,value=None):
        if address>=0x100000:
            if size==1:
                if kind==1:
                    if address&31!=11:raise ValueError('Oracle unsupported slot read')
                    value=self.device['slot_values'][((address-0x100000)//32)*native.slots.STRIDE+5]&255
                else:self.device=native.slots.transition(self.device,address,value)
            elif kind==2:
                self.device=native.transition(self.device,address,value,size)
                self.bus.extend([2,address+i,2,(value>>(8*(size-i-2)))&65535] for i in range(0,size,2))
            else:raise ValueError('Oracle unsupported DSP read')
        elif kind==1:value=self.peek(address,size)
        else:
            for (lo,data,w),buf in zip(self.regions,self.buffers):
                if lo<=address and address+size<=lo+len(data):
                    if not w:raise ValueError('Oracle read-only write')
                    buf[address-lo:address-lo+size]=value.to_bytes(size,'big');break
            else:raise ValueError('Oracle unmapped write: '+hex(address))
        self.events.append([kind,address,size,value]);return value
    def push(self,value,size=4):self.regs[15]-=size;self.access(2,self.regs[15],size,value)
    def pop(self,size=4):
        value=self.access(1,self.regs[15],size);self.regs[15]+=size;return value
    def save(self,indexes):
        for index in reversed(indexes):
            self.regs[15]-=4;self.access(2,self.regs[15]+2,2,self.regs[index]&65535);self.access(2,self.regs[15],2,self.regs[index]>>16)
    def restore(self,indexes):
        for index in indexes:self.regs[index]=self.pop()
    def ret(self):self.regs[16]=self.pop()
    def call(self,return_pc,function,*args):self.push(return_pc);function(*args)

    def emit(self):
        self.pcs += [0x4C2A,0x4C2E,0x4C32,0x4C36,0x4C3A,0x4C3C,0x4C3E,0x4C42,0x4C46]
        self.save((5,6,7));base=self.access(1,0x450,4);self.regs[8:11]=[base,base+0x1840,base+0x1A00]
        status=self.regs[0]&255
        if status&0xF0!=0x80:raise ValueError('Consumer contract only emits status80..8F')
        self.regbyte(5,status);self.regbyte(6,status);self.regbyte(0,status&0xF0)
        self.pcs += [0x4C62,0x4C64,0x4C68,0x4C6C,0x4C6E,0x4C70,0x4C74,0x4C76,0x4C78,0x4C7A,0x4C7C,
                     0x4C80,0x4C82,0x4C84,0x4C86,0x4C88,0x4C8A,0x4C8C,0x4C8E,0x4C90,0x4C92,0x4C94,0x4C98]
        self.regbyte(5,(status>>4)&7);self.regbyte(6,status&15);self.regbyte(3,(self.regs[3]<<4)&255)
        self.regbyte(6,(self.regs[6]|self.regs[3])&255)
        tag=self.access(1,self.regs[14]+1,1);self.regbyte(7,tag);self.regbyte(7,tag<<5);self.regbyte(6,self.regs[6]|self.regs[7])
        saved_sr=(self.regs[17]&~31)|4|(16 if tag&8 else 0);self.regs[7]=0;self.push(saved_sr,2);self.regs[17]=0x2700
        counter=self.access(1,self.regs[9],1);self.regbyte(7,counter)
        old=self.access(1,self.regs[9],1);self.access(2,self.regs[9],1,(old+1)&255)
        self.regword(7,counter*4);self.regs[10]+=self.regs[7]
        for value in (self.regs[5]&255,self.regs[6]&255,self.regs[1]&255,self.regs[2]&255):
            self.access(2,self.regs[10],1,value);self.regs[10]+=1
        self.regs[17]=self.pop(2);self.restore((5,6,7));self.ret();self.emitted+=1

    def consume(self):
        self.pcs += [0x4B1C,0x4B20];self.save((6,13));self.regword(6,31);self.logic(31,16)
        for i in range(32):
            address=self.regs[13];self.pcs += [0x4B24,0x4B28];flags=self.access(1,address,1)
            if flags&128:
                self.pcs += [0x4B2C,0x4B30];pointer=self.access(1,address+8,4)
                if pointer==self.regs[14]:
                    self.pcs += [0x4B34,0x4B36]
                    if self.regs[7]&255:
                        self.pcs.append(0x4B3A);old=self.access(1,address,1);self.access(2,address,1,old&127)
                    self.pcs += [0x4B3E,0x4B42,0x4B46,0x4B4A,0x4B4E,0x4B52,0x4B56,0x4B5A]
                    for index,offset in ((0,1),(1,2),(2,3),(3,0)):self.regbyte(index,self.access(1,address+offset,1))
                    self.regbyte(3,self.regs[3]&1);self.regbyte(0,(self.regs[0]&15)|128)
                    self.call(0x4B5E,self.emit)
            self.pcs += [0x4B5E,0x4B64];self.regs[13]+=12;self.regword(6,self.regs[6]-1)
        self.pcs += [0x4B68,0x4B6C];self.restore((6,13));self.ret()

    def setup_pool(self):
        self.pcs += [0x4B00,0x4B04,0x4B0A,0x4B0C,0x4B0E,0x4B14,0x4B1A]
        base=self.access(1,0x450,4);self.regs[12:15]=[base+0x2000,base+0x2400,base+0x2100];self.ret()

    def copy_record(self):
        self.pcs += records.COPY_PCS;self.save((0,1,2,8));base=self.access(1,0x450,4);self.regs[8]=base+0x80
        first=self.access(1,self.regs[14]+2,1);second=self.access(1,self.regs[14]+3,1);tag=self.access(1,self.regs[14]+1,1)
        self.regbyte(0,first);self.regbyte(1,second);self.regs[2]=2*tag;self.extend(False)
        self.access(2,self.regs[8]+self.regs[2],1,first);self.access(2,self.regs[8]+self.regs[2]+1,1,second);self.logic(second)
        self.restore((0,1,2,8));self.ret()

    def clear_descriptors(self):
        self.pcs += [0x4412];self.call(0x4416,self.setup_pool);self.pcs.append(0x4416);self.regword(6,7);self.logic(7,16)
        for _ in range(8):
            self.pcs += [0x441A,0x441E,0x4422];self.access(2,self.regs[14],1,0);self.regbyte(7,1);self.logic(1)
            self.call(0x4426,self.consume);self.pcs += [0x4426,0x442C,0x4432]
            self.access(2,self.regs[14]+2,1,0);self.access(2,self.regs[14]+3,1,0);self.logic(0)
            self.call(0x4436,self.copy_record);self.pcs += [0x4436,0x443C];self.regs[14]+=96;self.regword(6,self.regs[6]-1)
        self.pcs.append(0x4440);self.ret()

    def slot_helper(self,mode):
        if mode=='release':
            self.pcs += [0x3540,0x3546,0x354A];self.regs[13]=0x100000;self.regs[9]=self.regs[13]+11;self.regs[7]=31
            for _ in range(32):
                self.pcs += [0x354C,0x3550,0x3554];value=self.access(1,self.regs[9],1)|31;self.access(2,self.regs[9],1,value)
                self.logic(value);self.regs[9]+=32;self.regword(7,self.regs[7]-1)
            self.pcs.append(0x3558)
        else:
            prefix=(0x355A,0x355E,0x3560) if mode=='send' else (0x356E,0x3572,0x3574)
            loop=(0x3562,0x3564,0x3568) if mode=='send' else (0x3576,0x3578,0x357C)
            self.pcs+=list(prefix);self.regs[9]=self.regs[13]+(21 if mode=='send' else 23);self.regs[7]=15;self.regs[0]=0;self.logic(0)
            for _ in range(16):
                self.pcs+=list(loop);self.access(2,self.regs[9],1,0);self.regs[9]+=32;self.regword(7,self.regs[7]-1)
            if mode=='send':self.pcs.append(0x356C)
            else:
                self.pcs += [0x3580,0x3584,0x3588,0x358C,0x3590]
                for offset in (0x187E,0x1882,0x1886,0x188A):self.access(2,self.regs[14]+offset,4,0)
        self.ret()

    def clear_low(self):
        self.pcs += [0x3530,0x3532,0x3536,0x3538,0x353A,0x353C,0x353E];self.regs[0]=0;self.regs[8]=0x780;self.logic(0)
        for _ in range(4):self.access(2,self.regs[8],4,0);self.regs[8]+=4
        self.ret()

    def clear_pair_channel(self):
        self.pcs += [0x1DEA,0x1DF0,0x1DF4,0x1DF8,0x1DFC,0x1E00]
        self.regs[13:15]=[0x100000,RAM];self.regs[11]=RAM+0x1890;self.regs[10]=RAM+0x1000
        self.regbyte(4,self.access(1,self.regs[11]+(self.regs[7]&65535),1))
        if self.regs[4]&128:
            self.pcs += [0x1E02,0x1E08];address=self.regs[11]+(self.regs[7]&65535);old=self.access(1,address,1);self.access(2,address,1,old&127)
            self.call(0x1E0C,self.clear_channel)
        self.pcs += [0x1E0C,0x1E10];self.regbyte(4,self.access(1,self.regs[11]+(self.regs[7]&65535)+1,1))
        if self.regs[4]&128:
            self.pcs.append(0x1E12);address=self.regs[11]+(self.regs[7]&65535)+1;old=self.access(1,address,1);self.access(2,address,1,old&127)
            self.clear_channel();return # The shared tail returns directly to1E68's caller.
        self.pcs.append(0x1E2C);self.ret()

    def clear_channel(self):
        self.pcs += [0x1E18,0x1E1C,0x1E1E,0x1E24,0x1E26,0x1E2C]
        self.regword(4,(self.regs[4]&31)<<6);self.access(2,self.regs[10]+(self.regs[4]&65535)+0x34,1,0)
        self.regword(4,(self.regs[4]&65535)>>1);self.access(2,self.regs[13]+(self.regs[4]&65535),1,16);self.extend(False);self.logic(16);self.ret()

    def dsp_helper(self,mode):
        entry,offset,count,prefix,*_=reset.MODES[mode];self.pcs+=prefix;self.regs[9]=self.regs[13]+offset
        self.regs[7]=((self.regs[7]&0xFFFF0000) if mode=='program' else 0)|65535
        self.regs[0]=0;self.logic(0)
        for _ in range(count):
            self.pcs += [0x35B4,0x35B6];address=self.regs[9];self.events.append([2,address,4,0]);self.bus.extend(([2,address,2,0],[2,address+2,2,0]));self.regs[9]+=4
        field='mprog' if mode=='program' else mode;self.device[field]=[0]*(128 if mode in ('program','temp') else 64 if mode=='coef' else 32)
        if mode=='program':self.device['dirty']=1
        self.pcs.append(0x35BA);self.ret()

    def restore_volumes(self):
        self.pcs += [0x1640,0x1644];gate=self.access(1,RAM+0x1832,1);self.regbyte(0,gate);self.logic(gate)
        if gate:self.pcs.append(0x1660);self.ret();return
        self.pcs += [0x1646,0x164A,0x164C,0x1650];self.regs[8]=RAM+0x187E;self.regs[7]=15
        sign=self.access(1,RAM+0x1831,1);self.regbyte(4,sign);self.regword(4,0);negative=bool(sign&128)
        self.pcs.append(0x1662 if negative else 0x1652)
        for _ in range(16):
            value=self.access(1,self.regs[8],1);self.regs[8]+=1
            if negative:self.regbyte(0,value&0xE0);value&=0xE0;self.pcs += [0x1664,0x1666,0x166A,0x166E,0x1672]
            else:self.pcs += [0x1654,0x1658,0x165C]
            self.access(2,self.regs[13]+(self.regs[4]&65535)+23,1,value);self.regword(4,self.regs[4]+32);self.regword(7,self.regs[7]-1);self.extend(False)
        if negative:self.pcs += [0x1676,0x1678];self.logic(self.regs[0]&65535,16)
        else:self.pcs.append(0x1660)
        self.ret()

    def control(self,pcs):
        self.pcs+=pcs;value=self.access(1,self.regs[8],1);self.regs[8]+=1;result=(value-1)&255;self.regbyte(0,result)
        self.regs[17]=(self.regs[17]&~31)|(16 if value<1 else 0)|(8 if result&128 else 4 if result==0 else 0)|(2 if value==128 else 0)|(1 if value<1 else 0)
        return value==1

    def handler(self):
        self.pcs += [0x1E68,0x1E6A];self.push(self.regs[17],2);self.regs[17]=0x2700
        if self.control([0x1E6E,0x1E70,0x1E72]):
            self.pcs += [0x1E74,0x1E78,0x1E7C];self.save((8,));self.save((13,));self.call(0x1E80,self.clear_descriptors)
            self.pcs += [0x1E80,0x1E84];self.restore((13,));self.call(0x1E88,self.slot_helper,'release')
            self.pcs.append(0x1E88);self.call(0x1E8C,self.clear_low);self.pcs.append(0x1E8C);self.restore((8,))
        if self.control([0x1E90,0x1E92,0x1E94]):
            self.pcs += [0x1E96,0x1E98];self.regs[1]=7;self.regs[7]=0
            for _ in range(8):
                self.pcs.append(0x1E9A);self.call(0x1E9E,self.clear_pair_channel);self.pcs += [0x1E9E,0x1EA0];self.regword(7,self.regs[7]+2);self.regword(1,self.regs[1]-1)
        if self.control([0x1EA4,0x1EA6,0x1EA8]):
            self.pcs += [0x1EAA,0x1EAC,0x1EB0];self.regs[0]=0
            self.access(2,self.regs[13]+0x217,1,0);self.access(2,self.regs[13]+0x237,1,0)
        self.pcs += [0x1EB4,0x1EB8];self.regs[14]=RAM;self.regs[13]=0x100000
        if self.control([0x1EBE,0x1EC0,0x1EC2]):
            for at,mode in ((0x1EC4,'send'),(0x1EC8,'volume')):
                self.pcs.append(at);self.call(at+4,self.slot_helper,mode)
            for at,mode in ((0x1ECC,'program'),(0x1ED0,'madrs'),(0x1ED4,'coef'),(0x1ED8,'temp')):
                self.pcs.append(at);self.call(at+4,self.dsp_helper,mode)
            self.pcs.append(0x1EDC);self.call(0x1EE0,self.restore_volumes)
        if self.control([0x1EE0,0x1EE2,0x1EE4]):self.pcs.append(0x1EE6);self.call(0x1EEA,self.slot_helper,'volume')
        self.pcs += [0x1EEA,0x1EEC];self.regs[17]=self.pop(2);self.ret()

    def run(self):
        if self.case[0]=='dispatcher':
            self.pcs += dispatch.contract(0x10,self.before[0]&65535,self.before[7]&0xFFFFFF00,self.before[17],self.before[14])[5]
            self.save((13,14));self.push(0x1868);self.regs[7]=(self.regs[7]&0xFFFF0000)|0x40;self.regs[12]=self.regs[14];self.regs[17]&=~31
            self.handler();self.pcs += [0x1868,0x186C];self.restore((13,14));self.ret()
        else:self.handler()
        return {'registers':self.regs,'regions_after':[bytes(b) for b in self.buffers],'device_after':self.device,'events':self.events,'pcs':self.pcs,'steps':len(self.pcs),'reference_bus_events':self.bus}


def compare(actual,expected):
    effects.compare(actual,expected)


def run_case(code,library,case):
    *_,profile,sr,location,word=case;values=profile_values(profile);fixture=(0xFFFFFFFF,1) if values[-1] else (0x12345678,0)
    library.configure(fixture);contract=Contract(case,library.snapshot());expected=contract.run()
    actual=library.run(code,contract.before[16],leaf.STOP,RANGES,contract.regions,contract.before,budget=8192,device=fixture)
    try:compare(actual,expected)
    except ValueError as error:
        fields=[key for key in expected if actual.get(key)!=expected[key]]
        first={}
        for key in fields:
            a,b=actual.get(key),expected[key]
            if isinstance(a,list) and isinstance(b,list):
                i=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
                first[key]={'index':i,'actual':[hashlib.sha256(x).hexdigest() if isinstance(x,bytes) else x for x in a[i:i+3]],'expected':[hashlib.sha256(x).hexdigest() if isinstance(x,bytes) else x for x in b[i:i+3]],'lengths':[len(a),len(b)]}
            elif key=='device_after':first[key]=[name for name in b if a.get(name)!=b[name]]
            else:first[key]={'actual':a,'expected':b}
        raise ValueError(str(error)+' '+json.dumps({'case':case,'status':actual['status'],'error_address':hex(actual['error_address']),'differences':first})) from error
    return actual,contract.emitted


def fixture_for(case):
    return (0xFFFFFFFF,1) if profile_values(case[2])[-1] else (0x12345678,0)


def mutations():
    """Declared semantic alterations; every selected execution must return."""
    out=[]
    for index,at in enumerate((0x1E70,0x1E92,0x1EA6,0x1EC0,0x1EE2)):
        selected=[]
        for mode,profile,surround in itertools.product(('handler','dispatcher'),(0,2),(0,1)):
            values=[surround]*5;values[index]=1
            selected.append((mode,tuple(values),profile,0x200A,0,0x8000))
        out.append(('control'+str(index)+'_equals2',at,b'\x55',selected))
    for name,at,data,mask,profiles in (
            ('missing_volume_restore',0x1EDC,bytes.fromhex('4e71 4e71'),8,(0,2)),
            ('missing_last_pointer_increment',0x1EE0,bytes.fromhex('1010'),0,(0,2)),
            ('descriptor_count_seven',0x4419,b'\x06',1,(0,2)),
            ('missing_queue_increment',0x4C82,bytes.fromhex('4e71'),1,(2,)),
            ('duplicate_clear_lane',0x1EAF,b'\x37',4,(0,2)),
            ('missing_tag_double',0x4BD0,bytes.fromhex('4e71'),1,(2,)),
            ('restore_ccr_only',0x1EEA,bytes.fromhex('44df'),0,(0,2))):
        selected=[(mode,tuple((mask>>i)&1 for i in range(5)),profile,0x200A,0,0)
                  for mode,profile in itertools.product(('handler','dispatcher'),profiles)]
        out.append((name,at,data,selected))
    return out


def controls(code,library):
    results={}
    for name,at,replacement,selected in mutations():
        changed=bytearray(code);changed[at:at+len(replacement)]=replacement;reasons=set()
        for case in selected:
            fixture=fixture_for(case);library.configure(fixture)
            contract=Contract(case,library.snapshot());expected=contract.run()
            actual=library.run(changed,contract.before[16],leaf.STOP,RANGES,contract.regions,contract.before,budget=8192,device=fixture)
            if actual['status_code']!=1:raise ValueError('Mutation did not reach terminal command10 semantics: '+name)
            try:compare(actual,expected)
            except ValueError as error:reasons.add(str(error))
            else:raise ValueError('Terminal mutation escaped independent comparison: '+name)
        results[name]={'offset':hex(at),'replacement_hex':replacement.hex(),'terminal_tested':len(selected),'rejected':len(selected),'reasons':sorted(reasons),'changed_source_sha256':hashlib.sha256(changed).hexdigest()}
    return results


def execute(code,library):
    selected=selection();digest=hashlib.sha256();counts=Counter();bounds={};examples=[]
    for case in selected:
        actual,emitted=run_case(code,library,case);mode=case[0];counts[mode]+=1
        bounds.setdefault(mode,{'steps':[8192,0],'model_cycles':[2**63,0],'records':[32,0],'events':[4096,0]})
        for name,value in (('steps',actual['steps']),('model_cycles',actual['model_cycles']),('records',emitted),('events',len(actual['events']))):
            bounds[mode][name]=[min(bounds[mode][name][0],value),max(bounds[mode][name][1],value)]
        row={'case':case,'registers':actual['registers'],'events':actual['events'],'pcs':actual['pcs'],
             'reference_bus_events':actual['reference_bus_events'],'model_cycles':actual['model_cycles'],
             'regions_after_sha256':[hashlib.sha256(b).hexdigest() for b in actual['regions_after']],
             'device_after_sha256':hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest()}
        digest.update(json.dumps(row,sort_keys=True).encode()+b'\n')
        if case[2]==0 and case[3]==0x271F and case[4]==0 and case[5]==0 and case[1] in ((0,0,0,0,0),(0,0,0,1,0),(0,0,0,0,1),(1,1,1,1,1),(0,0,0,1)):
            examples.append({'case':case,'registers':actual['registers'],'steps':actual['steps'],'records':emitted,
                             'events':len(actual['events']),'reference_bus_events':len(actual['reference_bus_events'])})
    return {'cases':len(selected),'cases_by_mode':dict(counts),'bounds':bounds,'observations_sha256':digest.hexdigest(),
            'sample_results':examples,'terminal_mutations':controls(code,library),'all_registers_sr_pcs_operands_reference_bus_ram_device_compared':True,
            'code_ranges_sha256':{hex(lo)+'-'+hex(hi):hashlib.sha256(code[lo:hi]).hexdigest() for lo,hi in RANGES},
            'natural_execution':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-file',type=Path,required=True);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-command10-contract.v1','status':'failure','original_game_bytes_executed':False,
            'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'native_identity':native.identity(),
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,'lifetime':'netlink-sound-driver',
            'scope':'Complete declared constructed1E68 and17F2 command10 calls; not natural traffic/meaning, hardware clocks, DSP execution/audio, Godot or whole-game fidelity'}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a new private path');return 1
    with os.fdopen(fd,'w') as out:
        phase='source_identity'
        try:
            code=sound.source_bytes(a.source_file,'NLSND');phase='native_load';library=native.Library(a.prepared)
            report.update(driver_sha256=hashlib.sha256(code).hexdigest(),native_binary_sha256=hashlib.sha256(library.path.read_bytes()).hexdigest())
            phase='original_contracts';report['original_game_bytes_executed']=True;report['contracts']=execute(code,library);report['status']='success'
        except Exception as error:report['error']={'phase':phase,'type':type(error).__name__,'message':str(error)}
        finally:out.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('contracts',{}).get('cases')}));return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
