#!/usr/bin/env python3
"""Bounded CPU-only semantics for one kernel word-read helper.

Values come from retained natural command-observer transfer records. The helper
is executed against original SH-2 source bytes, while the sampled device word is
provided by a separate read-only CPU memory region. This does not emulate CD
hardware or claim a completed command-service root.
"""
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel

ENTRY=0x060958EC
DEVICE=0x25890008
BACKING=0x05890008 # pinned SH-2 test memory folds the cache-through 0x2 alias

def sha(data): return hashlib.sha256(data).hexdigest()
def read_json(path):
    return json.loads(probe_kernel.read_bounded(path,2*1024**2))
def run(kernel_path,source_root,result_path,records_path,out):
    kernel=probe_kernel.kernel_bytes(kernel_path); result=read_json(result_path); capture=read_json(records_path)
    status=capture.get('status'); rows=capture.get('records')
    if (result.get('schema')!='neptune.explicit-command-trace-experiment.v1' or
        result.get('status')!='failure' or result.get('original_game_bytes_executed') is not True or
        result.get('selected_core_sha256')!='3a95acef8cc6e20297d907a9658f6ae6c067f8ae1a72dbb84a594b742938184a' or
        result.get('frames')!=600 or result.get('port_zero_start_frames')!=8 or
        capture.get('schema')!='neptune.failed-command-trace-diagnostic.v1' or capture.get('accepted') is not False or
        not isinstance(status,dict) or status.get('capacity')!=128 or status.get('count')!=128 or
        status.get('dropped')!=1 or status.get('last_error')!=5 or status.get('transfer_count')!=129 or
        not isinstance(rows,list) or len(rows)!=128):
        raise ValueError('Require the exact bounded natural overflow capture and its original-run provenance')
    sampled=sorted({r['transfer_value'] for r in rows if r['kind']==2 and r['pc']==ENTRY and r['transfer_address']==DEVICE})
    if not sampled or any(type(v)is not int or not 0<=v<=0xffff for v in sampled):
        raise ValueError('No original transferred word values at the selected helper')
    emu=probe_kernel.interpreter(source_root)
    off=ENTRY-probe_kernel.BASE
    words=[int.from_bytes(kernel[off+i:off+i+2],'big') for i in (0,2,4)]
    if words!=[0x6031,0x000b,0x600d]: raise ValueError('Original helper source instructions differ')
    class ReadOnlyMemory(emu.Memory):
        def write(self,addr,size,value): raise ValueError(f'Unexpected source helper write at {addr:08x}')
    outputs=[]
    for value in sampled:
        memory=ReadOnlyMemory(); memory.add(probe_kernel.BASE,len(kernel),kernel)
        memory.add(BACKING,2,value.to_bytes(2,'big')); cpu=emu.CPU(memory)
        actual=cpu.call(ENTRY,max_steps=8,r3=DEVICE)
        if actual!=value or cpu.steps!=3: raise ValueError('Original helper did not return its observed word exactly')
        outputs.append({'observed_device_word':value,'helper_result':actual,'steps':cpu.steps})
    report={'schema':'neptune.original-cd-word-helper-contract.v1','status':'success',
            'entry':f'0x{ENTRY:08x}','source_instructions':[f'0x{x:04x}' for x in words],
            'source':'read-only USA original kernel bytes; exact kernel hash verified',
            'interpreter_source_hashes':probe_kernel.SOURCE_HASHES,
            'kernel_sha256':sha(kernel),'natural_failure_result_sha256':sha(result_path.read_bytes()),
            'natural_transfer_diagnostic_sha256':sha(records_path.read_bytes()),
            'natural_observation':{'frames':600,'frame':status['frame'],'actual_device_address':f'0x{DEVICE:08x}',
              'actual_read_site':f'0x{ENTRY:08x}','capacity':128,'observed_records':128,'dropped':1,
              'selected_observed_values':[f'0x{x:04x}' for x in sampled]},
            'isolated_cpu_results':outputs,
            'scope':'one complete three-instruction word-read helper on original SH-2 bytes using only values captured from the natural run; CPU-only isolated memory; no hardware semantics, CD protocol meaning, caller equivalence or complete command root claimed',
            'whole_program_status':'active; incomplete'}
    fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--result',type=Path,required=True);p.add_argument('--records',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();print(json.dumps({'status':run(a.kernel,a.saturn_recomp,a.result,a.records,a.report)['status']}))
if __name__=='__main__':main()
