#!/usr/bin/env python3
"""ABI5: bounded disjoint state-call traces plus unchanged pinned SCSP effects.

This profile exists for the measured NLSND51B2 graph and its outer callers.
Earlier ABIs, source files and preparation generations remain unchanged.
"""
from __future__ import annotations
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import subprocess
import tempfile
import m68k_probe as short
import m68k_consumer_native as capacity
import m68k_scsp_dsp as device
import probe_kernel as pinned

ABI=5
MAX_STEPS,MAX_EVENTS,MAX_REGIONS,MAX_RANGES=2048,1024,16,16


def generated_source():
    if (capacity.MAX_STEPS,capacity.MAX_EVENTS)!=(MAX_STEPS,MAX_EVENTS):
        raise ValueError('Accepted trace layout changed; reconcile ABI5')
    source=device.generated_source()
    for old,new in ((b'#define MAX_STEPS 256',b'#define MAX_STEPS 2048'),
                    (b'#define MAX_EVENTS 128',b'#define MAX_EVENTS 1024'),
                    (b'#define MAX_REGIONS 8',b'#define MAX_REGIONS 16'),
                    (b'#define MAX_RANGES 4',b'#define MAX_RANGES 16'),
                    (b'uint32_t neptune_m68k_abi(void) { return 4; }',
                     b'uint32_t neptune_m68k_abi(void) { return 5; }')):
        if source.count(old)!=1:raise ValueError('Ambiguous ABI5 substitution')
        source=source.replace(old,new)
    return source


def identity():
    return {'abi':ABI,'device_identity':device.identity(),
            'capacity_adapter_sha256':pinned.digest(Path(capacity.__file__).read_bytes()),
            'preparation_module_sha256':pinned.digest(Path(__file__).read_bytes()),
            'derived_backend_sha256':pinned.digest(generated_source()),
            'max_steps':MAX_STEPS,'max_events':MAX_EVENTS,'max_regions':MAX_REGIONS,'max_ranges':MAX_RANGES,
            'profile':'NLSND-state-call-disjoint-code-data-frozen-SCSP-word-effects'}


class Library(device.Library):
    def __init__(self,directory,require_receipt=True):
        directory=Path(directory);self.path=directory/'libneptune_m68k_scsp_state.so'
        expected=json.loads(device.LOCK.read_text())['component_sha256']
        if pinned.digest(pinned.read_bounded(directory/'scsp_dsp_component.h',65536))!=expected:
            raise ValueError('Prepared state reference component differs')
        if pinned.digest(pinned.read_bounded(directory/'bounded_state_backend.c',65536))!=pinned.digest(generated_source()):
            raise ValueError('Prepared state backend differs')
        if require_receipt:
            r=json.loads(pinned.read_bounded(directory/'receipt.json',65536))
            if (r.get('identity')!=identity() or r.get('status')!='ready' or
                    r.get('binary_sha256')!=pinned.digest(pinned.read_bounded(self.path,8*1024*1024)) or
                    r.get('owned_smoke',{}).get('original_game_bytes_executed') is not False):
                raise ValueError('Prepared state profile identity failed')
        self.library=c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype=c.c_uint32
        if self.library.neptune_m68k_abi()!=ABI:raise ValueError('State calls require ABI5')
        self.library.neptune_m68k_run.argtypes=[c.POINTER(short.Request),c.POINTER(capacity.Result)]
        self.library.neptune_m68k_run.restype=c.c_int
        self.library.neptune_dsp_configure.argtypes=[c.c_uint32,c.c_uint32]
        self.library.neptune_dsp_configure.restype=c.c_int
        self.library.neptune_dsp_snapshot.argtypes=[c.POINTER(c.c_uint64),c.POINTER(c.c_uint8)]
        self.library.neptune_dsp_snapshot.restype=None
        self.library.neptune_dsp_state_size.restype=c.c_uint32
        self.state_size=self.library.neptune_dsp_state_size()
        if not 4000<=self.state_size<=16384:raise ValueError('Unexpected reference state size')
        self.library.neptune_dsp_access.argtypes=[c.c_uint32]*3+[c.POINTER(c.c_uint32)]
        self.library.neptune_dsp_access.restype=c.c_int

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
        result=capacity.Result();returned=self.library.neptune_m68k_run(c.byref(request),c.byref(result))
        if returned!=result.status or result.steps>MAX_STEPS or result.event_count>MAX_EVENTS:
            raise ValueError('State native result/count mismatch')
        return {'status':short.STATUS.get(result.status,'unknown-native-status'),'status_code':result.status,
                'error_address':result.error_address,'error_size':result.error_size,'steps':result.steps,
                'pcs':list(result.pcs)[:result.steps],'registers':list(result.after),'model_cycles':result.model_cycles,
                'events':[[e.kind,e.address,e.size,e.value] for e in result.events[:result.event_count]],
                'regions_after':[bytes(buf) for buf in buffers],'code_unchanged':bytes(memory)==code,
                'device_before':before,'device_after':self.snapshot()}


def owned_case(nranges=16,nregions=16):
    """Independent owned nested-call and all-region read fixture, without game bytes."""
    code=bytearray(0x500);sp=0x70000;stop=0xFFF000
    registers=[0xA5A50000+i*0x101 for i in range(18)];registers[15:18]=[sp,0x100,0x2715]
    regions=[(sp-128,bytes([0xCD])*128+stop.to_bytes(4,'big'),True)]
    regions += [(0x50000+i*16,(i*37+7).to_bytes(2,'big'),False) for i in range(1,nregions)]
    addresses=[0x100+i*0x20 for i in range(nranges)];ranges=[]
    after=[bytearray(data) for _,data,_ in regions];events=[];pcs=[];last=0
    for i,address in enumerate(addresses):
        lo,data,_=regions[min(i,nregions-1)];last=int.from_bytes(data[:2],'big')
        words=bytes.fromhex('3039')+lo.to_bytes(4,'big')
        pcs.append(address);events.append([1,lo,2,last])
        if i+1<nranges:
            words+=bytes.fromhex('4eb9')+addresses[i+1].to_bytes(4,'big')
            sp-=4;value=address+12;offset=sp-regions[0][0]
            after[0][offset:offset+4]=value.to_bytes(4,'big');events.append([2,sp,4,value])
        words+=bytes.fromhex('4e75');pcs.append(address+6)
        code[address:address+len(words)]=words;ranges.append((address,address+len(words)))
    for i in reversed(range(nranges)):
        value=addresses[i-1]+12 if i else stop;events.append([1,sp,4,value]);sp+=4
        if i:pcs.append(value)
    expected=list(registers);expected[0]=(expected[0]&0xFFFF0000)|last
    expected[15:18]=[sp,stop,0x2710|(8 if last&0x8000 else 4 if last==0 else 0)]
    return bytes(code),registers,regions,ranges,expected,[bytes(b) for b in after],events,pcs


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
    result=capacity.Result();before=library.snapshot()
    returned=library.library.neptune_m68k_run(c.byref(request),c.byref(result))
    if (returned!=8 or result.status!=8 or result.steps or result.event_count or
            bytes(memory)!=code or [bytes(b) for b in buffers]!=[data for _,data,_ in regions]
            or library.snapshot()!=before):
        raise ValueError('Native over-capacity request did not reject before execution')
    return True


def smoke(library):
    initial=short.smoke(library)
    actual_device=device.smoke(library)
    actual_capacity=capacity.smoke(library)
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
    return {**actual_device,'capacity':actual_capacity,'max_ranges_executed':16,'max_regions_read':16,
            'disjoint_call_steps':len(pcs),'missing_range_guarded':True,'native_excess_rejections':excess}


def prepare(sources,scsp_sources,cache):
    sources,cache=Path(sources),Path(cache)
    cpu_lock=json.loads(short.SOURCE_LOCK.read_text())
    for name,sha in cpu_lock['files'].items():
        if pinned.digest(pinned.read_bounded(sources/name,2*1024*1024))!=sha:
            raise ValueError('Pinned CPU source changed')
    component=device.extract_component(scsp_sources)
    if pinned.digest(component)!=json.loads(device.LOCK.read_text())['component_sha256']:
        raise ValueError('Pinned SCSP extraction changed')
    if cache.exists():
        library=Library(cache);smoke(library)
        return json.loads((cache/'receipt.json').read_text())
    cache.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.m68k-state-prepare-',dir=cache.parent))
    (stage/'scsp_dsp_component.h').write_bytes(component)
    (stage/'COPYING.SCSP').write_bytes((Path(scsp_sources)/'COPYING').read_bytes())
    backend=stage/'bounded_state_backend.c';backend.write_bytes(generated_source())
    vendor=sources/'runtime/third_party/musashi'
    command=['/usr/bin/cc',*short.FLAGS,'-I',str(vendor),'-o',str(stage/'libneptune_m68k_scsp_state.so'),
             str(backend),str(vendor/'m68kcpu.c'),str(vendor/'m68kops.c'),str(vendor/'softfloat/softfloat.c'),'-lm']
    completed=subprocess.run(command,capture_output=True,timeout=60)
    (stage/'build.stdout').write_bytes(completed.stdout);(stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode:raise ValueError('ABI5 compile failed; stage diagnostics retained')
    library=Library(stage,require_receipt=False);owned=smoke(library)
    receipt={'schema':'neptune.prepared-m68k-scsp-state.v1','status':'ready','identity':identity(),
             'source_revision':cpu_lock['revision'],'source_files':cpu_lock['files'],
             'scsp_source_lock':json.loads(device.LOCK.read_text()),'owned_smoke':owned,
             'binary_sha256':pinned.digest(library.path.read_bytes()),
             'compiler':subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],
             'compile_timeout_seconds':60,'compile_exit':completed.returncode,'preparation_has_original_inputs':False,
             'limitations':['Frozen SCSP register effects only; no DSP execution, clocks, audio or hardware timing',
                            'Explicit disjoint code/data; unsupported MMIO and odd accesses stay guarded',
                            '2048steps/1024events/16ranges/16regions maximum; callers should use smaller budgets',
                            'Existing ABIs1/2/3/4 and reference cores unchanged; shared interpreter lineage']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');os.rename(stage,cache)
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True);parser.add_argument('--scsp-sources',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True);args=parser.parse_args(argv)
    r=prepare(args.sources,args.scsp_sources,args.cache)
    print(json.dumps({'status':r['status'],'abi':ABI,'binary_sha256':r['binary_sha256'],'original_game_bytes_executed':False}))


if __name__=='__main__':main()
