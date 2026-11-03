#!/usr/bin/env python3
"""ABI7: bounded original-command SCSP slot byte effects, all clocks frozen.

Separate pinned reference component; DSP word effects and ABIs1..6 unchanged.
Only slot byte read0B and writes00/0B/15/17 are admitted, across32 slots.
"""
from __future__ import annotations
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile
import m68k_probe as short
import m68k_scsp_dsp as device
import m68k_scsp_fifo as fifo
import m68k_reset_capacity as capacity
import probe_kernel as pinned

ABI=7
MAX_STEPS,MAX_EVENTS,MAX_REGIONS,MAX_RANGES=8192,4096,16,16
LOCK=Path(__file__).with_name('scsp-slot-source-lock.json')
FIELDS=('StartAddr','KeyBit','WF8Bit','LoopMode','SourceControl','SBXOR','EnvRates[3]',
        'DecayLevel','KRS','AttackLoopLink','EGBypass','ToDSPSelect','ToDSPLevel',
        'DirectVolume[0]','DirectVolume[1]','EffectVolume[0]','EffectVolume[1]')
STRIDE=16+len(FIELDS)
VALUES=32*STRIDE+1
SLOT_STATE_BYTES=3400  # Pinned43-field,72-byte slot;32 slots plus registers/guards/latch.


def between(source,start,end):
    if source.count(start)!=1 or source.count(end)!=1:
        raise ValueError('Ambiguous slot source boundaries')
    return source.split(start,1)[1].split(end,1)[0]


def extract_component(sources):
    blobs={}
    for name,sha in json.loads(LOCK.read_text())['files'].items():
        data=pinned.read_bounded(Path(sources)/name,2*1024*1024)
        if pinned.digest(data)!=sha:raise ValueError('Pinned slot source changed: '+name)
        blobs[name]=data.decode()
    header,source=blobs['mednafen/ss/scsp.h'],blobs['mednafen/ss/scsp.inc']
    declarations=re.findall(r'struct SS_SCSP_Slot\n\{[\s\S]+?\n\};',header)
    enums=re.findall(r'enum\n\{\n ENV_PHASE_ATTACK[\s\S]+?\n\};',header)
    tables=re.findall(r'static const uint16_t SS_SCSP_SB_XOR_Table\[4\] = [^;]+;',header)
    if tuple(map(len,(declarations,enums,tables)))!=(1,1,1):raise ValueError('Ambiguous slot declarations')
    slot=declarations[0]
    reference=source.replace('\nINLINE void ','\nstatic INLINE void ')
    read=fifo.function(reference,'SS_SCSP_RW_u8_W0')
    write=fifo.function(reference,'SS_SCSP_RW_u8_W1')
    read=' if(A < 0x400)'+between(read,' if(A < 0x400)',' if(A < 0x430)')
    block=' if(A < 0x400)'+between(write,' if(A < 0x400)',' if(A < 0x430)')
    selected=block.split('    case 0x00:',1)[0]
    for start,end in (('00','01'),('05','06'),('0A','0B'),('0B','0C')):
        a='    case 0x'+start+':';b='    case 0x'+end+':'
        selected+=a+between(block,a,b)
    selected+='   }\n  }\n  return;\n }\n'
    body=source[:source.index('\n/*\n TODO:')]+'''
/* Generated narrow clock-frozen slot component. Original selected case bodies,
 * declarations, bus macros (from unchanged DSP header), volume helper and table.
 * View contains every accessed field; it is not the complete SCSP or audio core.
 */
typedef struct SS_SCSP_Slot SS_SCSP_Slot;
'''+slot+'\n'+enums[0]+'\n'+tables[0]+'''
typedef struct {
 uint64_t before[4];
 uint16_t SlotRegs[32][16];
 SS_SCSP_Slot Slots[32];
 bool KeyExecute;
 uint64_t after[4];
} NEPTUNE_SLOT_VIEW;
static NEPTUNE_SLOT_VIEW slots;
'''+fifo.function(reference,'SDL_PAN_ToVolume').replace('static INLINE void','static void')
    for name,selected_body in (('read',read),('write',selected)):
        body+='static void neptune_slot_ref_'+name+'(NEPTUNE_SLOT_VIEW* z, uint32_t A, uint8_t* DBV_p)\n{\n A &= 0xFFF;\n'+selected_body+'}\n'
    body+='''
int neptune_slot_configure(uint32_t seed) {
 uint8_t* p=(uint8_t*)&slots;
 for(unsigned i=0;i<sizeof(slots);i++) p[i]=(uint8_t)((seed>>(8*(i%4))) ^ (i*29));
 for(unsigned i=0;i<32;i++) {
'''
    booleans=re.findall(r' bool ([A-Za-z0-9_]+);',slot)
    for name in booleans:body+='  slots.Slots[i].'+name+'=((seed^i)&1)!=0;\n'
    body+='''  for(unsigned j=0;j<16;j++) slots.SlotRegs[i][j]=(uint16_t)(seed^(i*257)^(j*0x1111));
 }
 slots.KeyExecute=(seed&1)!=0;
 return 1;
}
uint32_t neptune_slot_state_size(void) { return sizeof(slots); }
void neptune_slot_snapshot(uint32_t* out, uint8_t* untouched) {
 NEPTUNE_SLOT_VIEW saved;memcpy(&saved,&slots,sizeof(saved));
 for(unsigned i=0;i<32;i++) {
'''
    body+=f'  for(unsigned j=0;j<16;j++) out[i*{STRIDE}+j]=slots.SlotRegs[i][j];\n'
    for n,name in enumerate(FIELDS):
        body+=f'  out[i*{STRIDE}+{16+n}]=(uint32_t)slots.Slots[i].{name};\n  saved.Slots[i].{name}=0;\n'
    body+=''' }
 out[32*'''+str(STRIDE)+''']=slots.KeyExecute;
 memset(saved.SlotRegs,0,sizeof(saved.SlotRegs));saved.KeyExecute=false;
 memcpy(untouched,&saved,sizeof(saved));
}
int neptune_slot_access(uint32_t write, uint32_t address, uint32_t size, uint32_t* value) {
 if(write>1 || size!=1 || address<0x100000 || address>=0x100400) return 0;
 unsigned lane=address&0x1F;
 if((!write && lane!=0x0B) || (write && lane!=0 && lane!=0x0B && lane!=0x15 && lane!=0x17)) return 0;
 uint8_t bus=*value;
 if(write) neptune_slot_ref_write(&slots,address,&bus);
 else neptune_slot_ref_read(&slots,address,&bus);
 *value=bus;return 1;
}
'''
    return body.encode()


def generated_source():
    if capacity.ABI!=6 or (capacity.MAX_STEPS,capacity.MAX_EVENTS)!=(8192,4096):
        raise ValueError('Accepted capacity layout changed; reconcile ABI7')
    source=capacity.generated_source()
    for old,new in ((b'#include "scsp_dsp_component.h"',b'#include "scsp_dsp_component.h"\n#include "scsp_slot_component.h"'),
        (b'uint32_t neptune_m68k_abi(void) { return 6; }',b'uint32_t neptune_m68k_abi(void) { return 7; }'),
        (b'    if(neptune_dsp_access(0,address,size,&bus))',b'    if(neptune_slot_access(0,address,size,&bus)) { event(1,address,size,bus); return bus; }\n    if(neptune_dsp_access(0,address,size,&bus))'),
        (b'    if(neptune_dsp_access(1,address,size,&bus))',b'    if(neptune_slot_access(1,address,size,&bus)) { event(2,address,size,value&0xFF); return; }\n    if(neptune_dsp_access(1,address,size,&bus))')):
        if source.count(old)!=1:raise ValueError('Ambiguous slot backend substitution')
        source=source.replace(old,new)
    return source


def identity():
    return {'abi':ABI,'capacity_identity':capacity.identity(),'preparation_module_sha256':pinned.digest(Path(__file__).read_bytes()),
            'scsp_slot_source_lock_sha256':pinned.digest(LOCK.read_bytes()),'component_sha256':json.loads(LOCK.read_text())['component_sha256'],
            'derived_backend_sha256':pinned.digest(generated_source()),'max_steps':MAX_STEPS,'max_events':MAX_EVENTS,
            'max_ranges':MAX_RANGES,'max_regions':MAX_REGIONS,'slot_snapshot_values':VALUES,'slot_state_bytes':SLOT_STATE_BYTES,
            'slot_fields':list(FIELDS),'profile':'NLSND-slot-byte00-0B-15-17-clock-frozen-with-unchanged-DSP-words'}


def pan_volume(level,pan):
    """Independent integer 1.14 level/pan contract."""
    amplitude=0 if level==0 else 128*(2**level)
    attenuated=amplitude//(2**((pan&15)//2))
    if pan&1:attenuated-=attenuated//4
    if pan&15==15:attenuated=0
    return [amplitude,attenuated] if pan&16 else [attenuated,amplitude]


def transition(before,address,value):
    if type(address) is not int or not 0x100000<=address<0x100400 or address&31 not in (0,11,21,23):
        raise ValueError('Unsupported slot byte destination')
    if type(value) is not int or not 0<=value<=255:raise ValueError('Not a byte')
    actual=before['slot_values'];after={**before,'slot_values':list(actual)};v=after['slot_values']
    slot,lane=divmod(address-0x100000,32);base=slot*STRIDE;index=base+lane//2
    word=(v[index]&0xFF00)|value if lane&1 else (v[index]&255)|(value<<8)
    v[index]=word
    def set_field(name,val):v[base+16+FIELDS.index(name)]=val
    if lane==0:
        v[-1]=int(bool(v[-1]) or bool(word&0x1000));word&=0x0FFF;v[index]=word
        for name,val in (('KeyBit',(word>>11)&1),('SBXOR',(0,0x7FFF,0x8000,0xFFFF)[(word>>9)&3]),
                         ('SourceControl',(word>>7)&3),('LoopMode',(word>>5)&3),('WF8Bit',(word>>4)&1),
                         ('StartAddr',(actual[base+16]&65535)|((word&15)<<16))):set_field(name,val)
    elif lane==11:
        for name,val in (('EnvRates[3]',word&31),('DecayLevel',(word>>5)&31),('KRS',(word>>10)&15),
                         ('AttackLoopLink',(word>>14)&1),('EGBypass',(word>>15)&1)):set_field(name,val)
    elif lane==21:
        v[index]=word&255;set_field('ToDSPLevel',word&7);set_field('ToDSPSelect',(word>>3)&15)
    else:
        for prefix,level,pan in (('DirectVolume',(word>>13)&7,(word>>8)&31),('EffectVolume',(word>>5)&7,word&31)):
            for i,volume in enumerate(pan_volume(level,pan)):set_field(prefix+'['+str(i)+']',volume)
    return after


class Result(c.Structure):
    _fields_=capacity.Result._fields_


owned_case=capacity.owned_case
capacity_smoke=capacity.capacity_smoke


class Library(device.Library):
    def __init__(self,directory,require_receipt=True):
        directory=Path(directory);self.path=directory/'libneptune_m68k_scsp_slots.so'
        for file,sha in (('scsp_dsp_component.h',json.loads(device.LOCK.read_text())['component_sha256']),
                         ('scsp_slot_component.h',json.loads(LOCK.read_text())['component_sha256']),
                         ('bounded_slot_backend.c',pinned.digest(generated_source()))):
            if pinned.digest(pinned.read_bounded(directory/file,65536))!=sha:raise ValueError('Prepared slot component/backend differs')
        if require_receipt:
            receipt=json.loads(pinned.read_bounded(directory/'receipt.json',65536))
            if (receipt.get('identity')!=identity() or receipt.get('status')!='ready' or
                receipt.get('binary_sha256')!=pinned.digest(pinned.read_bounded(self.path,8*1024*1024)) or
                receipt.get('owned_smoke',{}).get('original_game_bytes_executed') is not False):
                raise ValueError('Prepared slot identity failed')
        self.library=c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype=c.c_uint32
        if self.library.neptune_m68k_abi()!=ABI:raise ValueError('Slot calls require ABI7')
        self.library.neptune_m68k_run.argtypes=[c.POINTER(short.Request),c.POINTER(Result)]
        self.library.neptune_m68k_run.restype=c.c_int
        self.library.neptune_dsp_configure.argtypes=[c.c_uint32,c.c_uint32];self.library.neptune_dsp_configure.restype=c.c_int
        self.library.neptune_dsp_snapshot.argtypes=[c.POINTER(c.c_uint64),c.POINTER(c.c_uint8)];self.library.neptune_dsp_snapshot.restype=None
        self.library.neptune_dsp_state_size.restype=c.c_uint32;self.state_size=self.library.neptune_dsp_state_size()
        if not 4000<=self.state_size<=16384:raise ValueError('Unexpected DSP state size')
        self.library.neptune_dsp_access.argtypes=[c.c_uint32]*3+[c.POINTER(c.c_uint32)];self.library.neptune_dsp_access.restype=c.c_int
        self.library.neptune_slot_configure.argtypes=[c.c_uint32];self.library.neptune_slot_configure.restype=c.c_int
        self.library.neptune_slot_state_size.restype=c.c_uint32;self.slot_size=self.library.neptune_slot_state_size()
        if self.slot_size!=SLOT_STATE_BYTES:raise ValueError('Unexpected pinned slot state size: '+str(self.slot_size))
        self.library.neptune_slot_snapshot.argtypes=[c.POINTER(c.c_uint32),c.POINTER(c.c_uint8)];self.library.neptune_slot_snapshot.restype=None
        self.library.neptune_slot_access.argtypes=[c.c_uint32]*3+[c.POINTER(c.c_uint32)];self.library.neptune_slot_access.restype=c.c_int

    def configure(self,fixture):
        super().configure(fixture)
        if not self.library.neptune_slot_configure(fixture[0]):raise ValueError('Slot fixture rejected')

    def raw_snapshot(self):
        """Exact full captured values/untouched bytes, avoiding scalar iteration in sweeps."""
        dv=(c.c_uint64*225)();du=(c.c_uint8*self.state_size)()
        sv=(c.c_uint32*VALUES)();su=(c.c_uint8*self.slot_size)()
        self.library.neptune_dsp_snapshot(dv,du);self.library.neptune_slot_snapshot(sv,su)
        return bytes(dv),bytes(du),bytes(sv),bytes(su)

    def snapshot(self):
        v=(c.c_uint32*VALUES)();untouched=(c.c_uint8*self.slot_size)()
        self.library.neptune_slot_snapshot(v,untouched)
        return {**super().snapshot(),'slot_values':list(v),'slot_unrelated_sha256':hashlib.sha256(bytes(untouched)).hexdigest()}

    def run(self,code,entry,stop,ranges,regions,registers,budget=128,device=(0x12345678,0)):
        if (not 0<len(code)<=0x80000 or len(registers)!=18 or not 0<len(regions)<=MAX_REGIONS
                or not 0<len(ranges)<=MAX_RANGES or not 0<budget<=MAX_STEPS
                or any(type(v) is not int or not 0<=v<=0xFFFFFFFF for v in registers)):
            raise ValueError('Invalid bounded state request')
        self.configure(device);before=self.snapshot()
        memory=(c.c_uint8*len(code)).from_buffer_copy(code)
        buffers=[(c.c_uint8*len(data)).from_buffer_copy(data) for _,data,_ in regions]
        mapped=(short.Region*len(regions))(*[short.Region(lo,len(data),int(writable),buf)
            for (lo,data,writable),buf in zip(regions,buffers)])
        allowed=(short.Range*len(ranges))(*[short.Range(lo,end) for lo,end in ranges])
        request=short.Request(memory,len(code),mapped,len(regions),allowed,len(ranges),entry,stop,budget,
                              (c.c_uint32*18)(*registers))
        result=Result();returned=self.library.neptune_m68k_run(c.byref(request),c.byref(result))
        if returned!=result.status or result.steps>MAX_STEPS or result.event_count>MAX_EVENTS:
            raise ValueError('Reset capacity native result/count mismatch')
        return {'status':short.STATUS.get(result.status,'unknown-native-status'),'status_code':result.status,
                'error_address':result.error_address,'error_size':result.error_size,'steps':result.steps,
                'pcs':list(result.pcs)[:result.steps],'registers':list(result.after),'model_cycles':result.model_cycles,
                'events':[[e.kind,e.address,e.size,e.value] for e in result.events[:result.event_count]],
                'regions_after':[bytes(buf) for buf in buffers],'code_unchanged':bytes(memory)==code,
                'device_before':before,'device_after':self.snapshot()}



def reject_native_counts(library,nranges,nregions):
    # Exercise the native boundary directly; Python's own count checks are not proof.
    code,regs,regions,ranges,*_=owned_case(nranges,nregions)
    memory=(c.c_uint8*len(code)).from_buffer_copy(code)
    buffers=[(c.c_uint8*len(data)).from_buffer_copy(data) for _,data,_ in regions]
    mapped=(short.Region*len(regions))(*[short.Region(lo,len(data),int(w),buf)
        for (lo,data,w),buf in zip(regions,buffers)])
    allowed=(short.Range*len(ranges))(*[short.Range(lo,end) for lo,end in ranges])
    request=short.Request(memory,len(code),mapped,len(regions),allowed,len(ranges),0x100,0xFFF000,128,
                          (c.c_uint32*18)(*regs))
    result=Result();before=library.snapshot()
    returned=library.library.neptune_m68k_run(c.byref(request),c.byref(result))
    if (returned!=8 or result.status!=8 or result.steps or result.event_count or
            bytes(memory)!=code or [bytes(b) for b in buffers]!=[data for _,data,_ in regions]
            or library.snapshot()!=before):
        raise ValueError('Native over-capacity request did not reject before execution')
    return True

def slot_smoke(library):
    reference_cases=0
    for seed,dirty in ((0,0),(0x12345678,0),(0xFFFFFFFF,1)):
        library.configure((seed,dirty));baseline=library.snapshot();baseline_raw=library.raw_snapshot()
        for slot in range(32):
            base=slot*STRIDE
            if baseline['slot_values'][base:base+16]!=[(seed^(slot*257)^(j*0x1111))&65535 for j in range(16)]:
                raise ValueError('Slot fixture words differ')
            for lane in (0,11,21,23):
                address=0x100000+slot*32+lane
                for value in range(256):
                    library.configure((seed,dirty));bus=c.c_uint32(value)
                    if library.library.neptune_slot_access(1,address,1,c.byref(bus))!=1:
                        raise ValueError('Qualified slot write rejected')
                    expected=transition(baseline,address,value)
                    expected_raw=(*baseline_raw[:2],struct.pack('='+str(VALUES)+'I',*expected['slot_values']),baseline_raw[3])
                    if library.raw_snapshot()!=expected_raw:raise ValueError('Slot effect differs from independent full-byte contract')
                    if lane==11:
                        if library.library.neptune_slot_access(0,address,1,c.byref(bus))!=1 or bus.value!=value:
                            raise ValueError('Slot read lane differs')
                        if library.raw_snapshot()!=expected_raw:raise ValueError('Slot read modified state')
                    reference_cases+=1
    code=bytearray(0x200);regions=[(0x70000,(0xFFF000).to_bytes(4,'big'),False)]
    cpu=0
    for slot in range(32):
        for lane in (0,11,21,23):
            address=0x100000+slot*32+lane
            words=bytes.fromhex('13c1')+address.to_bytes(4,'big')
            if lane==11:words+=bytes.fromhex('1039')+address.to_bytes(4,'big')
            words+=bytes.fromhex('4e75');code[0x100:0x100+len(words)]=words
            for value in (0,1,8,16,31,127,128,255):
                regs=[0xA5A5A5A5]*18;regs[1]=0x87654300|value;regs[15:18]=[0x70000,0x100,0x271F]
                actual=library.run(code,0x100,0xFFF000,[(0x100,0x100+len(words))],regions,regs)
                expected_regs=list(regs);expected_regs[15:18]=[0x70004,0xFFF000,(regs[17]&~15)|(8 if value&128 else 4 if value==0 else 0)]
                events=[[2,address,1,value]];pcs=[0x100,0x106]
                if lane==11:
                    expected_regs[0]=(regs[0]&0xFFFFFF00)|value;events.append([1,address,1,value]);pcs.append(0x10C)
                events.append([1,0x70000,4,0xFFF000])
                if (actual['status_code']!=1 or actual['registers']!=expected_regs or actual['pcs']!=pcs or actual['events']!=events
                        or actual['regions_after']!=[v for _,v,_ in regions] or not actual['code_unchanged']
                        or actual['device_after']!=transition(actual['device_before'],address,value)):
                    raise ValueError('Owned slot CPU write/read/return differs')
                cpu+=1
    rmw=0
    for seed in (0,0x12345678,0xFFFFFFFF):
        for slot in range(32):
            address=0x100000+slot*32+11
            words=bytes.fromhex('0039 001f')+address.to_bytes(4,'big')+bytes.fromhex('4e75')
            code[0x100:0x100+len(words)]=words
            regs=[0xA5A5A5A5]*18;regs[15:18]=[0x70000,0x100,0x271F]
            actual=library.run(code,0x100,0xFFF000,[(0x100,0x10A)],regions,regs,device=(seed,0))
            old=actual['device_before']['slot_values'][slot*STRIDE+5]&255;value=old|31
            expected=list(regs);expected[15:18]=[0x70004,0xFFF000,(regs[17]&~15)|(8 if value&128 else 0)]
            if (actual['status_code']!=1 or actual['registers']!=expected or actual['pcs']!=[0x100,0x108]
                    or actual['events']!=[[1,address,1,old],[2,address,1,value],[1,0x70000,4,0xFFF000]]
                    or actual['device_after']!=transition(actual['device_before'],address,value)
                    or actual['regions_after']!=[v for _,v,_ in regions] or not actual['code_unchanged']):
                raise ValueError('Owned ORI.B read-modify-write/SR contract differs')
            rmw+=1
    library.configure((0x12345678,0));expected=library.snapshot()
    for value in (0x18,0,0x10,8,0):
        bus=c.c_uint32(value);assert library.library.neptune_slot_access(1,0x100000,1,c.byref(bus))==1
        expected=transition(expected,0x100000,value)
        if library.snapshot()!=expected:raise ValueError('Key execution latch was cleared or not latched')
    rejections=0
    for write in (0,1,2):
        for address,size in ((0xFFFFF,1),(0x100400,1),(0x100001,1),(0x1003FF,1),(0x100000,2),(0x10000B,4)):
            before=library.snapshot();bus=c.c_uint32(0xA5)
            if library.library.neptune_slot_access(write,address,size,c.byref(bus))!=0 or library.snapshot()!=before or bus.value!=0xA5:
                raise ValueError('Unsupported raw slot access changed state')
            rejections+=1
    for opcode,address,status in (('13c1',0x100001,5),('33c1',0x100000,5),('23c1',0x100000,5),
                                  ('1039',0x100000,4),('3039',0x10000A,4),('2039',0x100000,4)):
        words=bytes.fromhex(opcode)+address.to_bytes(4,'big')+bytes.fromhex('4e75');code[0x100:0x100+len(words)]=words
        regs=[0xA5A5A5A5]*18;regs[15:18]=[0x70000,0x100,0x271F]
        result=library.run(code,0x100,0xFFF000,[(0x100,0x100+len(words))],regions,regs)
        if result['status_code']!=status or result['device_before']!=result['device_after']:
            raise ValueError('Unsupported CPU slot width/address did not guard')
    for destination in (0x100000,0x100700):
        code[0x100:0x102]=bytes.fromhex('4e75')
        regs=[0xA5A5A5A5]*18;regs[15:18]=[0x70000,0x100,0x271F]
        mapped=regions+[(destination,b'\0',True)]
        rejected=library.run(code,0x100,0xFFF000,[(0x100,0x102)],mapped,regs)
        if (rejected['status_code']!=8 or rejected['steps'] or rejected['events'] or
                rejected['regions_after']!=[v for _,v,_ in mapped] or not rejected['code_unchanged'] or
                rejected['device_before']!=rejected['device_after']):
            raise ValueError('Native request accepted fake device RAM')
    return {'slot_reference_byte_cases':reference_cases,'slot_cpu_cases':cpu,'slot_rmw_cases':rmw,
            'slot_raw_rejections':rejections,'slot_key_latch_sequence':5,'slot_width_cpu_guards':6,'native_fake_device_ram_rejections':2}


def smoke(library):
    slot_checks=slot_smoke(library)
    initial=short.smoke(library)
    actual_device=device.smoke(library)
    actual_capacity=capacity_smoke(library)
    code,regs,regions,ranges,expected,after,events,pcs=owned_case()
    result=library.run(code,0x100,0xFFF000,ranges,regions,regs,budget=64)
    if (result['status_code']!=1 or result['registers']!=expected or result['regions_after']!=after or
            result['events']!=events or result['pcs']!=pcs or not result['code_unchanged'] or
            result['device_before']!=result['device_after']):
        raise ValueError('Maximum disjoint-call/region owned contract failed')
    missing=library.run(code,0x100,0xFFF000,ranges[:-1],regions,regs,budget=64)
    if missing['status_code']!=3 or missing['error_address']!=ranges[-1][0]:
        raise ValueError('Missing disjoint executable range did not guard')
    excess={'17_ranges':reject_native_counts(library,17,16),
            '17_regions':reject_native_counts(library,16,17)}
    if short.smoke(library)!=initial:raise ValueError('Post-boundary recovery differs')
    return {**actual_device,**slot_checks,'capacity':actual_capacity,'max_ranges_executed':16,'max_regions_read':16,
            'disjoint_call_steps':len(pcs),'missing_range_guarded':True,'native_excess_rejections':excess}

def prepare(sources,scsp_sources,cache):
    sources,cache=Path(sources),Path(cache)
    cpu_lock=json.loads(short.SOURCE_LOCK.read_text())
    for name,sha in cpu_lock['files'].items():
        if pinned.digest(pinned.read_bounded(sources/name,2*1024*1024))!=sha:
            raise ValueError('Pinned CPU source changed')
    component=device.extract_component(scsp_sources)
    slot_component=extract_component(scsp_sources)
    if pinned.digest(slot_component)!=json.loads(LOCK.read_text())['component_sha256']:raise ValueError('Pinned slot extraction changed')
    if pinned.digest(component)!=json.loads(device.LOCK.read_text())['component_sha256']:
        raise ValueError('Pinned SCSP extraction changed')
    if cache.exists():
        library=Library(cache);smoke(library)
        return json.loads((cache/'receipt.json').read_text())
    cache.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.m68k-slot-prepare-',dir=cache.parent))
    (stage/'scsp_dsp_component.h').write_bytes(component)
    (stage/'scsp_slot_component.h').write_bytes(slot_component)
    (stage/'COPYING.SCSP').write_bytes((Path(scsp_sources)/'COPYING').read_bytes())
    backend=stage/'bounded_slot_backend.c';backend.write_bytes(generated_source())
    vendor=sources/'runtime/third_party/musashi'
    command=['/usr/bin/cc',*short.FLAGS,'-I',str(vendor),'-o',str(stage/'libneptune_m68k_scsp_slots.so'),
             str(backend),str(vendor/'m68kcpu.c'),str(vendor/'m68kops.c'),str(vendor/'softfloat/softfloat.c'),'-lm']
    completed=subprocess.run(command,capture_output=True,timeout=60)
    (stage/'build.stdout').write_bytes(completed.stdout);(stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode:raise ValueError('ABI7 compile failed; stage diagnostics retained')
    library=Library(stage,require_receipt=False);owned=smoke(library)
    receipt={'schema':'neptune.prepared-m68k-scsp-slots.v1','status':'ready','identity':identity(),
             'source_revision':cpu_lock['revision'],'source_files':cpu_lock['files'],
             'scsp_source_lock':json.loads(device.LOCK.read_text()),'slot_source_lock':json.loads(LOCK.read_text()),'owned_smoke':owned,
             'binary_sha256':pinned.digest(library.path.read_bytes()),
             'compiler':subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],
             'compile_timeout_seconds':60,'compile_exit':completed.returncode,'preparation_has_original_inputs':False,
             'limitations':['Frozen SCSP register effects only; no DSP execution, clocks, audio or hardware timing',
                            'Explicit disjoint code/data; unsupported MMIO/widths and odd word/long accesses stay guarded',
                            '8192steps/4096events/16ranges/16regions maximum; callers should use smaller budgets',
                            'Existing ABIs1..6 and reference cores unchanged; shared interpreter lineage']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');os.rename(stage,cache)
    return receipt



def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True);parser.add_argument('--scsp-sources',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True);args=parser.parse_args(argv)
    r=prepare(args.sources,args.scsp_sources,args.cache)
    print(json.dumps({'status':r['status'],'abi':ABI,'binary_sha256':r['binary_sha256'],'original_game_bytes_executed':False}))


if __name__=='__main__':main()
