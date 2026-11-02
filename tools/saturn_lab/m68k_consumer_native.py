#!/usr/bin/env python3
"""Separate ABI2 trace capacity for full bounded consumer calls; preserve ABI1."""
from __future__ import annotations

import argparse
import ctypes as c
import json
import os
from pathlib import Path
import subprocess
import tempfile

import m68k_probe as short
import probe_kernel as pinned

BASE_SHA256 = '1ae72479a22f91955343cb9fe157f261218e9c3a9ee8b8e7a6d519cda766cceb'
MAX_STEPS, MAX_EVENTS, ABI = 2048, 1024, 2


def generated_source():
    source=short.BACKEND.read_bytes()
    if pinned.digest(source)!=BASE_SHA256:
        raise ValueError('Accepted short backend differs; reconcile rather than rewrite its profile')
    for old,new in ((b'#define MAX_STEPS 256',b'#define MAX_STEPS 2048'),
                    (b'#define MAX_EVENTS 128',b'#define MAX_EVENTS 1024'),
                    (b'uint32_t neptune_m68k_abi(void) { return 1; }',
                     b'uint32_t neptune_m68k_abi(void) { return 2; }')):
        if source.count(old)!=1:raise ValueError('Ambiguous profile substitution')
        source=source.replace(old,new)
    return source


def identity():
    return {'base_identity':short.identity(),'base_sha256':BASE_SHA256,
            'derived_backend_sha256':pinned.digest(generated_source()),
            'abi':ABI,'max_steps':MAX_STEPS,'max_events':MAX_EVENTS,
            'profile':'bounded-original32-record-consumer'}


class Result(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('status','error_address','error_size','steps','event_count')]+[
        ('pcs',c.c_uint32*MAX_STEPS),('after',c.c_uint32*18),('model_cycles',c.c_int32),
        ('events',short.Event*MAX_EVENTS)]


class Library:
    def __init__(self,directory,require_receipt=True):
        directory=Path(directory);self.path=directory/'libneptune_m68k_consumer.so'
        if require_receipt:
            receipt=json.loads(pinned.read_bounded(directory/'receipt.json',65536))
            if (receipt.get('identity')!=identity() or receipt.get('status')!='ready'
                    or receipt.get('binary_sha256')!=pinned.digest(pinned.read_bounded(self.path,8*1024*1024))
                    or receipt.get('owned_smoke',{}).get('original_game_bytes_executed') is not False):
                raise ValueError('Long-call prepared identity failed')
        self.library=c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype=c.c_uint32
        if self.library.neptune_m68k_abi()!=ABI:raise ValueError('Consumer requires separate ABI2')
        self.library.neptune_m68k_run.argtypes=[c.POINTER(short.Request),c.POINTER(Result)]
        self.library.neptune_m68k_run.restype=c.c_int

    def run(self,code,entry,stop,ranges,regions,registers,budget=128):
        if (not 0<len(code)<=0x80000 or len(registers)!=18 or not 0<len(regions)<=8
                or not 0<len(ranges)<=4 or not 0<budget<=MAX_STEPS
                or any(type(v) is not int or not 0<=v<=0xFFFFFFFF for v in registers)):
            raise ValueError('Invalid bounded ABI2 request')
        memory=(c.c_uint8*len(code)).from_buffer_copy(code)
        buffers=[(c.c_uint8*len(data)).from_buffer_copy(data) for _,data,_ in regions]
        mapped=(short.Region*len(regions))(*[short.Region(lo,len(data),int(writable),buf)
            for (lo,data,writable),buf in zip(regions,buffers)])
        allowed=(short.Range*len(ranges))(*[short.Range(lo,end) for lo,end in ranges])
        request=short.Request(memory,len(code),mapped,len(regions),allowed,len(ranges),entry,stop,budget,
                              (c.c_uint32*18)(*registers))
        result=Result();returned=self.library.neptune_m68k_run(c.byref(request),c.byref(result))
        if returned!=result.status or result.steps>MAX_STEPS or result.event_count>MAX_EVENTS:
            raise ValueError('ABI2 native result/count mismatch')
        return {'status':short.STATUS.get(result.status,'unknown-native-status'),'status_code':result.status,
                'error_address':result.error_address,'error_size':result.error_size,'steps':result.steps,
                'pcs':list(result.pcs)[:result.steps],'registers':list(result.after),'model_cycles':result.model_cycles,
                'events':[[e.kind,e.address,e.size,e.value] for e in result.events[:result.event_count]],
                'regions_after':[bytes(buf) for buf in buffers],'code_unchanged':bytes(memory)==code}


def smoke(library):
    inherited=short.smoke(library)
    code=bytearray(0x200);code[0x100:0x102]=bytes.fromhex('60fe')
    regs=[0xA5A5A5A5]*18;regs[8]=0x60000;regs[15:18]=[0x70000,0x100,0x2715]
    regions=[(0x70000,(0xFFF000).to_bytes(4,'big'),False)]
    loop=library.run(code,0x100,0xFFF000,[(0x100,0x104)],regions,regs,budget=MAX_STEPS)
    if loop['status_code']!=2 or loop['steps']!=MAX_STEPS:
        raise ValueError('ABI2 full instruction-bound rejection failed')
    # Owned ADDQ.B #1,(A0); BRA back: two data events per two instructions.
    code[0x100:0x104]=bytes.fromhex('5210 60fc')
    events=library.run(code,0x100,0xFFF000,[(0x100,0x104)],regions+[(0x60000,b'\0',True)],regs,budget=MAX_STEPS)
    if events['status_code']!=6 or len(events['events'])!=MAX_EVENTS:
        raise ValueError('ABI2 full event-bound rejection failed')
    if short.smoke(library)!=inherited:raise ValueError('ABI2 CPU recovery after overflow failed')
    return {**inherited,'full_instruction_limit_rejected':loop['steps'],
            'full_event_limit_rejected':len(events['events']),'fresh_after_full_overflow':True}


def prepare(sources,cache):
    sources,cache=Path(sources),Path(cache)
    lock=json.loads(short.SOURCE_LOCK.read_text())
    for relative,sha in lock['files'].items():
        if pinned.digest(pinned.read_bounded(sources/relative,2*1024*1024))!=sha:
            raise ValueError('Pinned CPU source changed')
    if cache.exists():
        library=Library(cache);smoke(library)
        return json.loads((cache/'receipt.json').read_text())
    cache.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.m68k-consumer-prepare-',dir=cache.parent))
    backend=stage/'bounded_consumer_backend.c';backend.write_bytes(generated_source())
    vendor=sources/'runtime/third_party/musashi'
    command=['/usr/bin/cc',*short.FLAGS,'-I',str(vendor),'-o',str(stage/'libneptune_m68k_consumer.so'),
             str(backend),str(vendor/'m68kcpu.c'),str(vendor/'m68kops.c'),str(vendor/'softfloat/softfloat.c'),'-lm']
    completed=subprocess.run(command,capture_output=True,timeout=60)
    (stage/'build.stdout').write_bytes(completed.stdout);(stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode:raise ValueError('ABI2 compile failed; stage diagnostics retained')
    library=Library(stage,require_receipt=False);owned=smoke(library)
    receipt={'schema':'neptune.prepared-m68k-consumer.v1','status':'ready','identity':identity(),
             'source_revision':lock['revision'],'source_files':lock['files'],'owned_smoke':owned,
             'binary_sha256':pinned.digest((stage/'libneptune_m68k_consumer.so').read_bytes()),
             'compiler':subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],
             'compile_timeout_seconds':60,'compile_exit':completed.returncode,'preparation_has_original_inputs':False,
             'limitations':['Same CPU-only Musashi lineage; no original game, device or natural timing proof',
                            'Only trace capacities and ABI tag differ from accepted hash-pinned owned shim',
                            'Existing short ABI1 source/cache remain unchanged; host/provider limits unchanged']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    os.rename(stage,cache);return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True);parser.add_argument('--cache',type=Path,required=True)
    args=parser.parse_args(argv);r=prepare(args.sources,args.cache)
    print(json.dumps({'status':r['status'],'binary_sha256':r['binary_sha256'],'abi':ABI,'original_game_bytes_executed':False}))


if __name__=='__main__':main()
