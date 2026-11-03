#!/usr/bin/env python3
"""ABI8: frozen DSP word/normal longword writes, explicit TEMP and reference bus.

Separate generation; ABIs1..7 unchanged. Long reads, unaligned long stores and
non-MOVE/predecrement CPU long stores remain unsupported. No clocks/audio.
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
import tempfile
import m68k_scsp_slots as slots
import m68k_scsp_dsp as words
import m68k_probe as short
import probe_kernel as pinned

ABI=8
VALUES=353
BUS_LIMIT=8192
LOCK=Path(__file__).with_name('scsp-long-source-lock.json')
MAX_STEPS,MAX_EVENTS,MAX_RANGES,MAX_REGIONS=8192,4096,16,16


def extract_component(sources):
    blobs={}
    for name,sha in json.loads(LOCK.read_text())['files'].items():
        data=pinned.read_bounded(Path(sources)/name,2*1024*1024)
        if pinned.digest(data)!=sha:raise ValueError('Pinned longword source changed: '+name)
        blobs[name]=data.decode()
    component=words.extract_component(sources).decode()
    for suffix in ('W0','W1'):
        name='SS_SCSP_RW_u16_'+suffix
        full=slots.fifo.function(blobs['mednafen/ss/scsp.inc'].replace('\nINLINE void ','\nstatic INLINE void '),name)
        tail=full[full.index(' if(A >= 0x700 && A <= 0x77F)'):]
        tail=tail[:tail.index(' //\n // z->DSP memory read stack')]
        old=slots.fifo.function(component,name)
        new='static void '+name+'(SS_SCSP* z, uint32_t A, uint16_t* DBV_p)\n{\n'+tail+'}\n'
        if component.count(old)!=1:raise ValueError('Ambiguous extended reference function')
        component=component.replace(old,new)
    signs=re.findall(r'^#define sign_x_to_s32[^\n]+',blobs['mednafen/math_ops.h'],re.M)
    if len(signs)!=1:raise ValueError('Ambiguous pinned sign extension')
    notice=blobs['mednafen/math_ops.h'].split('#ifndef',1)[0]
    component=notice+'\n'+signs[0]+'\n'+component
    for old,new in (
        ('    dsp.DSP.WritePending=(seed&1)!=0;', '    for(unsigned i=0;i<128;i++) dsp.DSP.TEMP[i]=sign_x_to_s32(24,dsp.DSP.TEMP[i]);\n    dsp.DSP.WritePending=(seed&1)!=0;'),
        ('    out[224]=dsp.DSP.MPROG_Dirty;','    out[224]=dsp.DSP.MPROG_Dirty;\n    for(unsigned i=0;i<128;i++) out[225+i]=(uint32_t)dsp.DSP.TEMP[i];'),
        ('    saved.DSP.MPROG_Dirty=false;','    saved.DSP.MPROG_Dirty=false;\n    memset(saved.DSP.TEMP,0,sizeof(saved.DSP.TEMP));')):
        if component.count(old)!=1:raise ValueError('Ambiguous TEMP snapshot/fixture substitution')
        component=component.replace(old,new)
    component=component[:component.index('int neptune_dsp_access(')]
    bus=slots.fifo.function(blobs['mednafen/hw_cpu/m68k/m68k_private.h'].replace('\nINLINE void ','\nstatic INLINE void '),'Write_u32').replace('static INLINE void','static void')
    # These pinned dispatchers establish normal versus predecrement ordering.
    ham=blobs['mednafen/hw_cpu/m68k/m68k_ham_body.inc.h']
    if 'else if (HAM_AM == ADDR_REG_INDIR_PRE)' not in ham or 'Write_u32_longdec(h->zptr, h->ea, val);' not in ham or 'Write_u32(h->zptr, h->ea, val);' not in ham:
        raise ValueError('Pinned operand dispatch changed')
    return (component+BUS_WRAPPER_PREFIX+bus+BUS_WRAPPER_SUFFIX).encode()


BUS_WRAPPER_PREFIX="""
/* Owned adapter around the pinned Write_u32 body. The minimal bus view is not
 * the full reference CPU. Recorded16-bit transactions are frozen reference bus
 * dispatch, not measured physical Saturn cycles. */
typedef struct { void (*BusWrite16)(uint32_t, uint16_t); } M68K;
static uint32_t bus_events[8192][4],bus_count;
static void neptune_reference_word_write(uint32_t address,uint16_t value) {
 uint16_t bus=value;
 SS_SCSP_RW_u16_W1(&dsp,address&0xFFF,&bus);
 bus_events[bus_count][0]=2;bus_events[bus_count][1]=address;
 bus_events[bus_count][2]=2;bus_events[bus_count++][3]=value;
}
"""
BUS_WRAPPER_SUFFIX="""
void neptune_dsp_bus_reset(void) { bus_count=0; }
uint32_t neptune_dsp_bus_count(void) { return bus_count; }
void neptune_dsp_bus_snapshot(uint32_t* out) { memcpy(out,bus_events,bus_count*4*sizeof(uint32_t)); }
int neptune_dsp_access(uint32_t write,uint32_t address,uint32_t size,uint32_t* value) {
 if(write>1 || address<0x100700 || address>0x100DFE || (address&1)) return 0;
 if(size==4) {
  if(!write || (address&3) || address>0x100DFC || bus_count>8190) return 0;
  M68K view={neptune_reference_word_write};Write_u32(&view,address,*value);return 1;
 }
 if(size!=2 || bus_count>=8192 || (!write && address>=0x1007C0 && address<0x100800)) return 0;
 uint16_t bus=*value;
 if(write) neptune_reference_word_write(address,bus);
 else {
  SS_SCSP_RW_u16_W0(&dsp,address&0xFFF,&bus);
  bus_events[bus_count][0]=1;bus_events[bus_count][1]=address;
  bus_events[bus_count][2]=2;bus_events[bus_count++][3]=bus;
 }
 *value=bus;return 1;
}
"""


def generated_source():
    source=slots.generated_source()
    for old,new in (
        (b'uint32_t neptune_m68k_abi(void) { return 7; }',b'uint32_t neptune_m68k_abi(void) { return 8; }'),
        (b'    if(neptune_dsp_access(1,address,size,&bus))',b"""    if(size==4 && address>=0x100700 && address<=0x100DFF) {
        uint32_t pc=result->pcs[result->steps-1];
        uint16_t opcode=((uint16_t)request->code[pc]<<8)|request->code[pc+1];
        if((opcode&0xF000)!=0x2000 || ((opcode>>6)&7)==4) fail(5,address,size);
    }
    if(neptune_dsp_access(1,address,size,&bus))""")):
        if source.count(old)!=1:raise ValueError('Ambiguous ABI8 substitution')
        source=source.replace(old,new)
    return source


def identity():
    return {'abi':ABI,'accepted_slot_identity':slots.identity(),'preparation_module_sha256':pinned.digest(Path(__file__).read_bytes()),
            'source_lock_sha256':pinned.digest(LOCK.read_bytes()),'component_sha256':json.loads(LOCK.read_text())['component_sha256'],
            'derived_backend_sha256':pinned.digest(generated_source()),'dsp_snapshot_values':VALUES,'bus_word_capacity':BUS_LIMIT,
            'profile':'NLSND-frozen-DSP-word-and-aligned-normal-MOVE-long-writes-TEMP-explicit'}


def word_transition(before,address,value):
    if type(address) is not int or address&1 or not 0x100700<=address<=0x100DFE:raise ValueError('Unsupported word address')
    if type(value) is not int or not 0<=value<=65535:raise ValueError('Not a word')
    if address<0x100C00:return words.transition(before,address,value)
    after={**before,'temp':list(before['temp'])};index=(address-0x100C00)//4;old=after['temp'][index]&0xFFFFFF
    if address&2:new=(old&255)|(value<<8)
    else:new=(old&0xFFFF00)|(value&255)
    after['temp'][index]=new if new<0x800000 else new|0xFF000000
    return after


def transition(before,address,value,size):
    if type(size) is not int or size not in (2,4):raise ValueError('Unsupported width')
    if size==2:return word_transition(before,address,value)
    if type(address) is not int or address&3 or not 0x100700<=address<=0x100DFC:raise ValueError('Unsupported longword address')
    if type(value) is not int or not 0<=value<=0xFFFFFFFF:raise ValueError('Not a longword')
    return word_transition(word_transition(before,address,value>>16),address+2,value&65535)


class Result(c.Structure):
    _fields_=slots.Result._fields_


class Library(slots.Library):
    def __init__(self,directory,require_receipt=True):
        directory=Path(directory);self.path=directory/'libneptune_m68k_scsp_long.so'
        for file,sha in (('scsp_dsp_component.h',json.loads(LOCK.read_text())['component_sha256']),
                         ('scsp_slot_component.h',json.loads(slots.LOCK.read_text())['component_sha256']),
                         ('bounded_long_backend.c',pinned.digest(generated_source()))):
            if pinned.digest(pinned.read_bounded(directory/file,65536))!=sha:raise ValueError('Prepared slot component/backend differs')
        if require_receipt:
            receipt=json.loads(pinned.read_bounded(directory/'receipt.json',65536))
            if (receipt.get('identity')!=identity() or receipt.get('status')!='ready' or
                receipt.get('binary_sha256')!=pinned.digest(pinned.read_bounded(self.path,8*1024*1024)) or
                receipt.get('owned_smoke',{}).get('original_game_bytes_executed') is not False):
                raise ValueError('Prepared slot identity failed')
        self.library=c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype=c.c_uint32
        if self.library.neptune_m68k_abi()!=ABI:raise ValueError('Long calls require ABI8')
        self.library.neptune_m68k_run.argtypes=[c.POINTER(short.Request),c.POINTER(Result)]
        self.library.neptune_m68k_run.restype=c.c_int
        self.library.neptune_dsp_configure.argtypes=[c.c_uint32,c.c_uint32];self.library.neptune_dsp_configure.restype=c.c_int
        self.library.neptune_dsp_snapshot.argtypes=[c.POINTER(c.c_uint64),c.POINTER(c.c_uint8)];self.library.neptune_dsp_snapshot.restype=None
        self.library.neptune_dsp_state_size.restype=c.c_uint32;self.state_size=self.library.neptune_dsp_state_size()
        if not 4000<=self.state_size<=16384:raise ValueError('Unexpected DSP state size')
        self.library.neptune_dsp_access.argtypes=[c.c_uint32]*3+[c.POINTER(c.c_uint32)];self.library.neptune_dsp_access.restype=c.c_int
        self.library.neptune_slot_configure.argtypes=[c.c_uint32];self.library.neptune_slot_configure.restype=c.c_int
        self.library.neptune_slot_state_size.restype=c.c_uint32;self.slot_size=self.library.neptune_slot_state_size()
        if self.slot_size!=slots.SLOT_STATE_BYTES:raise ValueError('Unexpected pinned slot state size: '+str(self.slot_size))
        self.library.neptune_slot_snapshot.argtypes=[c.POINTER(c.c_uint32),c.POINTER(c.c_uint8)];self.library.neptune_slot_snapshot.restype=None
        self.library.neptune_slot_access.argtypes=[c.c_uint32]*3+[c.POINTER(c.c_uint32)];self.library.neptune_slot_access.restype=c.c_int

        self.library.neptune_dsp_bus_reset.argtypes=[];self.library.neptune_dsp_bus_reset.restype=None
        self.library.neptune_dsp_bus_count.restype=c.c_uint32
        self.library.neptune_dsp_bus_snapshot.argtypes=[c.POINTER(c.c_uint32)]
        self.library.neptune_dsp_bus_snapshot.restype=None

    def configure(self,fixture):
        super().configure(fixture)
        self.library.neptune_dsp_bus_reset()

    def raw_snapshot(self):
        dv=(c.c_uint64*VALUES)();du=(c.c_uint8*self.state_size)()
        sv=(c.c_uint32*slots.VALUES)();su=(c.c_uint8*self.slot_size)()
        self.library.neptune_dsp_snapshot(dv,du);self.library.neptune_slot_snapshot(sv,su)
        return bytes(dv),bytes(du),bytes(sv),bytes(su)

    def snapshot(self):
        raw=self.raw_snapshot();v=(c.c_uint64*VALUES).from_buffer_copy(raw[0]);s=(c.c_uint32*slots.VALUES).from_buffer_copy(raw[2])
        return {'coef':list(v[:64]),'madrs':list(v[64:96]),'mprog':list(v[96:224]),'dirty':v[224],'temp':list(v[225:]),
                'unrelated_sha256':hashlib.sha256(raw[1]).hexdigest(),'slot_values':list(s),'slot_unrelated_sha256':hashlib.sha256(raw[3]).hexdigest()}

    def bus_trace(self):
        count=self.library.neptune_dsp_bus_count()
        if count>BUS_LIMIT:raise ValueError('Untrusted bus trace count')
        data=(c.c_uint32*(BUS_LIMIT*4))();self.library.neptune_dsp_bus_snapshot(data)
        return [list(data[i*4:i*4+4]) for i in range(count)]

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
                'device_before':before,'device_after':self.snapshot(),'reference_bus_events':self.bus_trace()}


def read_word(before,address):
    if address<0x100780:return before['coef'][(address-0x100700)//2]<<3
    if address<0x1007C0:return before['madrs'][(address-0x100780)//2]
    if address<0x100800:raise ValueError('Undefined gap read')
    if address<0x100C00:return (before['mprog'][(address-0x100800)//8]>>(16*(3-((address-0x100800)%8)//2)))&65535
    value=before['temp'][(address-0x100C00)//4]
    return (value>>8)&65535 if address&2 else value&255


def smoke(library):
    raw_cases=cpu_cases=identical=guards=0
    for seed,dirty in ((0,0),(0x12345678,0),(0xFFFFFFFF,1)):
        for size in (2,4):
            for address in range(0x100700,0x100E00,size):
                for value in ((0,1,7,8,0x7FFF,0x8000,0xFFFF) if size==2 else (0,1,0x12345678,0x7FFFFFFF,0x80000000,0xFFFFFFFF)):
                    library.configure((seed,dirty));before=library.snapshot();bus=c.c_uint32(value)
                    if library.library.neptune_dsp_access(1,address,size,c.byref(bus))!=1:raise ValueError('Qualified raw DSP store rejected')
                    expected=transition(before,address,value,size)
                    if library.snapshot()!=expected:raise ValueError('Reference DSP write differs from independent full-state contract')
                    expected_bus=[[2,address+i,2,(value>>(8*(size-i-2)))&65535] for i in range(0,size,2)]
                    if library.bus_trace()!=expected_bus:raise ValueError('Pinned word-bus order/value differs')
                    if size==2 and not 0x1007C0<=address<0x100800:
                        if library.library.neptune_dsp_access(0,address,2,c.byref(bus))!=1 or bus.value!=read_word(expected,address):raise ValueError('Reference word read differs')
                        if library.snapshot()!=expected:raise ValueError('Reference read changed state')
                    raw_cases+=1
        for address in range(0x100800,0x100C00,2):
            library.configure((seed,0));before=library.snapshot();bus=c.c_uint32(read_word(before,address))
            if library.library.neptune_dsp_access(1,address,2,c.byref(bus))!=1 or library.snapshot()!=word_transition(before,address,bus.value):raise ValueError('Identical program word write failed invalidation')
            identical+=1
    code=bytearray(0x200);regions=[(0x70000,(0xFFF000).to_bytes(4,'big'),False)]
    for address in range(0x100700,0x100E00,4):
        for value in (0,0x12345678,0xFFFFFFFF):
            for mode in ('absolute','postincrement'):
                instruction=(bytes.fromhex('23c1')+address.to_bytes(4,'big')) if mode=='absolute' else bytes.fromhex('20c1')
                body=instruction+bytes.fromhex('4e75');code[0x100:0x100+len(body)]=body
                regs=[0xA5A5A5A5]*18;regs[1]=value;regs[8]=address;regs[15:18]=[0x70000,0x100,0x271F]
                actual=library.run(code,0x100,0xFFF000,[(0x100,0x100+len(body))],regions,regs)
                expected=list(regs);expected[15:18]=[0x70004,0xFFF000,0x2710|(8 if value&0x80000000 else 4 if value==0 else 0)]
                if mode=='postincrement':expected[8]+=4
                if (actual['status_code']!=1 or actual['registers']!=expected or actual['events']!=[[2,address,4,value],[1,0x70000,4,0xFFF000]]
                        or actual['pcs']!=[0x100,0x100+len(instruction)] or actual['steps']!=2 or not actual['code_unchanged']
                        or actual['regions_after']!=[v for _,v,_ in regions]
                        or actual['device_after']!=transition(actual['device_before'],address,value,4)
                        or actual['reference_bus_events']!=[[2,address,2,value>>16],[2,address+2,2,value&65535]]):
                    raise ValueError('Native normal MOVE longword/CPU operand/reference bus contract differs')
                cpu_cases+=1
    # Raw invalid requests must not partially affect a register or trace.
    for write in (0,1,2):
        for address,size in ((0x1006FC,4),(0x100DFE,4),(0x100E00,2),(0x100700,1),(0x100701,2),(0x100702,4),(0x1007C0,4)):
            if write==1 and address==0x1007C0:continue # Declared no-op gap write, not a read.
            library.configure((0x12345678,0));before=library.raw_snapshot();bus=c.c_uint32(0x12345678)
            if library.library.neptune_dsp_access(write,address,size,c.byref(bus))!=0 or library.raw_snapshot()!=before or library.bus_trace() or bus.value!=0x12345678:
                raise ValueError('Unsupported raw DSP access affected state')
            guards+=1
    for opcode,address,status in (('23c1',0x100702,5),('23c1',0x100DFE,5),('2039',0x100700,4),('13c1',0x100C00,5),('23c1',0x100701,3),('42b9',0x100700,5)):
        body=bytes.fromhex(opcode)+address.to_bytes(4,'big')+bytes.fromhex('4e75');code[0x100:0x100+len(body)]=body
        regs=[0xA5A5A5A5]*18;regs[15:18]=[0x70000,0x100,0x271F]
        actual=library.run(code,0x100,0xFFF000,[(0x100,0x100+len(body))],regions,regs)
        if actual['status_code']!=status or actual['device_before']!=actual['device_after'] or actual['reference_bus_events']:raise ValueError('Unsupported CPU DSP request did not guard before effects')
        guards+=1
    # Explicit predecrement guard: normal-order helper must never be substituted.
    code[0x100:0x104]=bytes.fromhex('2101 4e75');regs[8]=0x100704
    actual=library.run(code,0x100,0xFFF000,[(0x100,0x104)],regions,regs)
    if actual['status_code']!=5 or actual['device_before']!=actual['device_after'] or actual['reference_bus_events']:raise ValueError('Predecrement CPU write was not fenced')
    library.configure((0,0));bus=c.c_uint32(0x12345678)
    for _ in range(BUS_LIMIT//2):
        if library.library.neptune_dsp_access(1,0x100C00,4,c.byref(bus))!=1:raise ValueError('Full bus trace did not fit')
    before=library.raw_snapshot()
    if library.library.neptune_dsp_access(1,0x100C00,4,c.byref(bus))!=0 or library.raw_snapshot()!=before or len(library.bus_trace())!=BUS_LIMIT:
        raise ValueError('Reference bus trace overflow was not atomic')
    library.configure((0,0))
    if library.bus_trace() or library.library.neptune_dsp_access(1,0x100C00,4,c.byref(bus))!=1:raise ValueError('Reference bus recovery failed')
    inherited_slots=slots.slot_smoke(library)
    inherited_capacity=slots.capacity_smoke(library)
    # Actual native16 range/region calls and17th-count rejection stay qualified.
    owned=slots.owned_case();owned_code,regs,regions,ranges,expected,after,events,pcs=owned
    actual=library.run(owned_code,0x100,0xFFF000,ranges,regions,regs,budget=64)
    if (actual['status_code']!=1 or actual['registers']!=expected or actual['regions_after']!=after or actual['events']!=events
            or actual['pcs']!=pcs or not actual['code_unchanged'] or actual['device_before']!=actual['device_after']):raise ValueError('Disjoint native capacity contract changed')
    missing=library.run(owned_code,0x100,0xFFF000,ranges[:-1],regions,regs,budget=64)
    if missing['status_code']!=3:raise ValueError('Missing code range did not guard')
    excess={'17_ranges':slots.reject_native_counts(library,17,16),'17_regions':slots.reject_native_counts(library,16,17)}
    return {'original_game_bytes_executed':False,'reference_write_cases':raw_cases,'identical_program_word_cases':identical,
            'normal_longword_cpu_cases':cpu_cases,'dsp_invalid_access_guards':guards,'predecrement_guarded':True,
            'reference_word_bus_capacity_rejected':BUS_LIMIT,'reference_bus_recovered':True,'native_excess_rejections':excess,
            'max_ranges_executed':16,'max_regions_read':16,'missing_range_guarded':True,
            'capacity':inherited_capacity,**inherited_slots}


def prepare(sources,scsp_sources,cache):
    sources,cache=Path(sources),Path(cache)
    cpu_lock=json.loads(short.SOURCE_LOCK.read_text())
    for name,sha in cpu_lock['files'].items():
        if pinned.digest(pinned.read_bounded(sources/name,2*1024*1024))!=sha:raise ValueError('Pinned CPU source changed')
    component=extract_component(scsp_sources);slot=slots.extract_component(scsp_sources)
    if pinned.digest(component)!=json.loads(LOCK.read_text())['component_sha256']:raise ValueError('Long reference extraction changed')
    if pinned.digest(slot)!=json.loads(slots.LOCK.read_text())['component_sha256']:raise ValueError('Slot reference extraction changed')
    if cache.exists():
        library=Library(cache);smoke(library);return json.loads((cache/'receipt.json').read_text())
    cache.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.m68k-long-prepare-',dir=cache.parent))
    (stage/'scsp_dsp_component.h').write_bytes(component);(stage/'scsp_slot_component.h').write_bytes(slot)
    (stage/'COPYING.SCSP').write_bytes((Path(scsp_sources)/'COPYING').read_bytes());backend=stage/'bounded_long_backend.c';backend.write_bytes(generated_source())
    vendor=sources/'runtime/third_party/musashi'
    command=['/usr/bin/cc',*short.FLAGS,'-I',str(vendor),'-o',str(stage/'libneptune_m68k_scsp_long.so'),str(backend),str(vendor/'m68kcpu.c'),str(vendor/'m68kops.c'),str(vendor/'softfloat/softfloat.c'),'-lm']
    completed=subprocess.run(command,capture_output=True,timeout=60);(stage/'build.stdout').write_bytes(completed.stdout);(stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode:raise ValueError('ABI8 compile failed; diagnostics retained')
    library=Library(stage,require_receipt=False);owned=smoke(library)
    receipt={'schema':'neptune.prepared-m68k-scsp-long.v1','status':'ready','identity':identity(),'source_revision':cpu_lock['revision'],'source_files':cpu_lock['files'],
             'scsp_source_lock':json.loads(LOCK.read_text()),'slot_source_lock':json.loads(slots.LOCK.read_text()),'owned_smoke':owned,'binary_sha256':pinned.digest(library.path.read_bytes()),
             'compiler':subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],'compile_timeout_seconds':60,'compile_exit':0,'preparation_has_original_inputs':False,
             'limitations':['Pinned CPU operand observations and extracted reference16-bit bus dispatch, not physical bus/hardware timing','Frozen register view; no DSP/envelope/key clocks, PCM or natural gameplay','ABIs1..7 caches untouched; new explicit TEMP initialisation normalises24-bit signed values','Only aligned normal MOVE long stores; predecrement/other CPU modes and long reads remain unsupported']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');os.rename(stage,cache);return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sources',type=Path,required=True);p.add_argument('--scsp-sources',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    a=p.parse_args(argv);r=prepare(a.sources,a.scsp_sources,a.cache)
    print(json.dumps({'status':r['status'],'abi':ABI,'binary_sha256':r['binary_sha256'],'original_game_bytes_executed':False}))


if __name__=='__main__':main()
