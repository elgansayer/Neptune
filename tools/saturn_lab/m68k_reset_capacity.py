#!/usr/bin/env python3
"""ABI6: command10 record/reset trace capacity; unchanged frozen SCSP word effects.

The original active record scan exceeds ABI5 at1024events. This generation
extends trace storage only. Slot/byte/longword device accesses remain guarded.
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
import m68k_scsp_state as state
import m68k_scsp_dsp as device
import probe_kernel as pinned

ABI=6
MAX_STEPS,MAX_EVENTS,MAX_REGIONS,MAX_RANGES=8192,4096,16,16


def generated_source():
    if (state.ABI,state.MAX_STEPS,state.MAX_EVENTS,state.MAX_REGIONS,state.MAX_RANGES)!=(5,2048,1024,16,16):
        raise ValueError('Accepted ABI5 layout changed; reconcile the separate ABI6')
    source=state.generated_source()
    for old,new in ((b'#define MAX_STEPS 2048',b'#define MAX_STEPS 8192'),
                    (b'#define MAX_EVENTS 1024',b'#define MAX_EVENTS 4096'),
                    (b'uint32_t neptune_m68k_abi(void) { return 5; }',
                     b'uint32_t neptune_m68k_abi(void) { return 6; }')):
        if source.count(old)!=1:raise ValueError('Ambiguous ABI6 source substitution')
        source=source.replace(old,new)
    return source


def identity():
    return {'abi':ABI,'accepted_state_identity':state.identity(),
            'preparation_module_sha256':pinned.digest(Path(__file__).read_bytes()),
            'derived_backend_sha256':pinned.digest(generated_source()),
            'max_steps':MAX_STEPS,'max_events':MAX_EVENTS,'max_regions':MAX_REGIONS,'max_ranges':MAX_RANGES,
            'profile':'NLSND-command10-reset-trace-capacity-unchanged-frozen-SCSP-word-effects'}


class Result(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('status','error_address','error_size','steps','event_count')]+[
        ('pcs',c.c_uint32*MAX_STEPS),('after',c.c_uint32*18),('model_cycles',c.c_int32),
        ('events',short.Event*MAX_EVENTS)]


owned_case=state.owned_case


class Library(device.Library):
    def __init__(self,directory,require_receipt=True):
        directory=Path(directory);self.path=directory/'libneptune_m68k_reset_capacity.so'
        expected=json.loads(device.LOCK.read_text())['component_sha256']
        if pinned.digest(pinned.read_bounded(directory/'scsp_dsp_component.h',65536))!=expected:
            raise ValueError('Prepared reset capacity reference component differs')
        if pinned.digest(pinned.read_bounded(directory/'bounded_reset_capacity_backend.c',65536))!=pinned.digest(generated_source()):
            raise ValueError('Prepared reset capacity backend differs')
        if require_receipt:
            r=json.loads(pinned.read_bounded(directory/'receipt.json',65536))
            if (r.get('identity')!=identity() or r.get('status')!='ready' or
                    r.get('binary_sha256')!=pinned.digest(pinned.read_bounded(self.path,8*1024*1024)) or
                    r.get('owned_smoke',{}).get('original_game_bytes_executed') is not False):
                raise ValueError('Prepared reset capacity profile identity failed')
        self.library=c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype=c.c_uint32
        if self.library.neptune_m68k_abi()!=ABI:raise ValueError('State calls require ABI6')
        self.library.neptune_m68k_run.argtypes=[c.POINTER(short.Request),c.POINTER(Result)]
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



def capacity_smoke(library):
    initial=short.smoke(library)
    code=bytearray(0x200);code[0x100:0x102]=bytes.fromhex('60fe')
    regs=[0xA5A5A5A5]*18;regs[8]=0x60000;regs[15:18]=[0x70000,0x100,0x2715]
    regions=[(0x70000,(0xFFF000).to_bytes(4,'big'),False)]
    loop=library.run(code,0x100,0xFFF000,[(0x100,0x104)],regions,regs,budget=MAX_STEPS)
    if loop['status_code']!=2 or loop['steps']!=MAX_STEPS:
        raise ValueError('ABI6 full instruction fence did not reject')
    code[0x100:0x104]=bytes.fromhex('5210 60fc')
    events=library.run(code,0x100,0xFFF000,[(0x100,0x104)],regions+[(0x60000,b'\0',True)],regs,budget=MAX_STEPS)
    if (events['status_code']!=6 or len(events['events'])!=MAX_EVENTS or
            events['regions_after'][-1]!=b'\0' or not events['code_unchanged']):
        raise ValueError('ABI6 full event fence or bounded memory differs')
    if short.smoke(library)!=initial:raise ValueError('ABI6 post-fence recovery differs')
    return {**initial,'full_instruction_limit_rejected':loop['steps'],
            'full_event_limit_rejected':len(events['events']),'fresh_after_full_overflow':True}


def smoke(library):
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
    stage=Path(tempfile.mkdtemp(prefix='.m68k-reset-capacity-prepare-',dir=cache.parent))
    (stage/'scsp_dsp_component.h').write_bytes(component)
    (stage/'COPYING.SCSP').write_bytes((Path(scsp_sources)/'COPYING').read_bytes())
    backend=stage/'bounded_reset_capacity_backend.c';backend.write_bytes(generated_source())
    vendor=sources/'runtime/third_party/musashi'
    command=['/usr/bin/cc',*short.FLAGS,'-I',str(vendor),'-o',str(stage/'libneptune_m68k_reset_capacity.so'),
             str(backend),str(vendor/'m68kcpu.c'),str(vendor/'m68kops.c'),str(vendor/'softfloat/softfloat.c'),'-lm']
    completed=subprocess.run(command,capture_output=True,timeout=60)
    (stage/'build.stdout').write_bytes(completed.stdout);(stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode:raise ValueError('ABI6 compile failed; stage diagnostics retained')
    library=Library(stage,require_receipt=False);owned=smoke(library)
    receipt={'schema':'neptune.prepared-m68k-reset-capacity.v1','status':'ready','identity':identity(),
             'source_revision':cpu_lock['revision'],'source_files':cpu_lock['files'],
             'scsp_source_lock':json.loads(device.LOCK.read_text()),'owned_smoke':owned,
             'binary_sha256':pinned.digest(library.path.read_bytes()),
             'compiler':subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],
             'compile_timeout_seconds':60,'compile_exit':completed.returncode,'preparation_has_original_inputs':False,
             'limitations':['Frozen SCSP register effects only; no DSP execution, clocks, audio or hardware timing',
                            'Explicit disjoint code/data; unsupported MMIO and odd accesses stay guarded',
                            '8192steps/4096events/16ranges/16regions maximum; callers should use smaller budgets',
                            'Existing ABIs1/2/3/4/5 and reference cores unchanged; shared interpreter lineage']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');os.rename(stage,cache)
    return receipt



def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True);parser.add_argument('--scsp-sources',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True);args=parser.parse_args(argv)
    r=prepare(args.sources,args.scsp_sources,args.cache)
    print(json.dumps({'status':r['status'],'abi':ABI,'binary_sha256':r['binary_sha256'],'original_game_bytes_executed':False}))


if __name__=='__main__':main()
