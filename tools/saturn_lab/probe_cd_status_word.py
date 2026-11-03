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
STORE_ENTRY=0x06095904
STORE_SITE=0x06095906
STORE_LITERAL=0x06095A08
POLL_ENTRY=0x06095A84
POLL_SITE=0x06095A94

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
    store_off=STORE_ENTRY-probe_kernel.BASE
    store_words=[int.from_bytes(kernel[store_off+i:store_off+i+2],'big') for i in (0,2,4)]
    literal_off=STORE_LITERAL-probe_kernel.BASE
    store_target=int.from_bytes(kernel[literal_off:literal_off+4],'big')
    if store_words!=[0xD340,0x000b,0x2341] or store_target!=DEVICE:
        raise ValueError('Original three-instruction word-store helper/literal changed')
    observed_stores=sorted({r['transfer_value'] for r in rows if r['kind']==3 and r['pc']==STORE_SITE and r['transfer_address']==DEVICE})
    if not observed_stores: raise ValueError('No actual word-store values at selected helper delay slot')
    class LoggedMemory(emu.Memory): pass
    store_outputs=[]
    for value in observed_stores:
        memory=LoggedMemory(); memory.add(probe_kernel.BASE,len(kernel),kernel)
        memory.add(BACKING,2,b'\xa5\x5a'); memory.log=[]; cpu=emu.CPU(memory)
        cpu.call(STORE_ENTRY,max_steps=8,r4=value)
        writes=[item for item in memory.log if item[0]=='w']
        if cpu.steps!=3 or writes!=[('w',DEVICE,2,value)]:
            raise ValueError('Original word-store helper did not issue its one observed transfer')
        store_outputs.append({'observed_store_word':value,'actual_helper_write':writes[0][3],'steps':cpu.steps})
    polls=[r for r in rows if r['kind']==2 and r['pc']==POLL_SITE and r['transfer_address']==DEVICE]
    groups=[]; current=[]
    for row in polls:
        if row['r'][7]==0 and current: groups.append(current); current=[]
        current.append(row)
    if current: groups.append(current)
    poll_words=[0x2FE6,0xEE00,0xD11A,0x67E3,0x2FC6,0xECFD,0x2FB6,0xDB17]
    poll_src=POLL_ENTRY-probe_kernel.BASE
    poll_actual=[int.from_bytes(kernel[poll_src+i:poll_src+i+2],'big') for i in range(0,16,2)]
    poll_base=0x060BFD00
    if (poll_actual!=poll_words or len(groups)!=3 or any(len(g)!=8 for g in groups) or
        any(any(r['r'][4]!=1 or r['r'][7]!=i for i,r in enumerate(g)) for g in groups)):
        raise ValueError('Original natural status-poll groups/source do not satisfy the selected bounded contract')
    poll_results=[]
    for group in groups:
        sequence=[r['transfer_value'] for r in group]
        if any(value&1 for value in sequence[:-1]) or not sequence[-1]&1:
            raise ValueError('Captured original polling values do not show the observed bit transition')
        pointer=group[0]['r'][5]
        if any(r['r'][5]!=pointer for r in group): raise ValueError('Original polling output pointer changed within one call')
        class SequenceMemory(emu.Memory):
            def __init__(self): super().__init__(); self.device_reads=[]
            def read(self,addr,size):
                if addr==DEVICE and size==2:
                    if len(self.device_reads)>=len(sequence): raise ValueError('Original poll read exceeded its retained sequence')
                    value=sequence[len(self.device_reads)]; self.device_reads.append(value); return value
                return super().read(addr,size)
        memory=SequenceMemory(); memory.add(0x060FF000,0x1000,bytes(0x1000))
        memory.add(poll_base,0x200,bytes(0x200)); memory.add(probe_kernel.BASE,len(kernel),kernel); memory.log=[]
        cpu=emu.CPU(memory); cpu.r[15]=0x060FFFE0
        actual=cpu.call(POLL_ENTRY,max_steps=256,r4=1,r5=pointer)
        writes=[item for item in memory.log if item[0]=='w' and item[1]==pointer]
        output=int.from_bytes(memory._find(pointer,4)[0][memory._find(pointer,4)[1]:memory._find(pointer,4)[1]+4],'big')
        if len(memory.device_reads)!=8 or actual!=0 or output!=sequence[-1] or writes!=[('w',pointer,4,sequence[-1])]:
            raise ValueError('Original poll helper did not follow the captured transition to a successful return')
        poll_results.append({'output_pointer':f'0x{pointer:08x}','observed_read_words':[f'0x{x:04x}' for x in sequence],
            'read_count':len(memory.device_reads),'result':actual,'stored_status_word':f'0x{output:04x}','steps':cpu.steps})
    report={'schema':'neptune.original-cd-word-helpers-contract.v3','status':'success',
            'probe_sha256':sha(Path(__file__).read_bytes()),
            'entry':f'0x{ENTRY:08x}','source_instructions':[f'0x{x:04x}' for x in words],
            'source':'read-only USA original kernel bytes; exact kernel hash verified',
            'interpreter_source_hashes':probe_kernel.SOURCE_HASHES,
            'kernel_sha256':sha(kernel),'natural_failure_result_sha256':sha(result_path.read_bytes()),
            'natural_transfer_diagnostic_sha256':sha(records_path.read_bytes()),
            'natural_observation':{'frames':600,'frame':status['frame'],'actual_device_address':f'0x{DEVICE:08x}',
              'actual_read_site':f'0x{ENTRY:08x}','capacity':128,'observed_records':128,'dropped':1,
              'selected_observed_values':[f'0x{x:04x}' for x in sampled]},
            'isolated_cpu_results':outputs,
            'word_store_helper':{'entry':f'0x{STORE_ENTRY:08x}','source_instructions':[f'0x{x:04x}' for x in store_words],
              'original_literal_address':f'0x{STORE_LITERAL:08x}','literal_value':f'0x{store_target:08x}',
              'delay_slot':f'0x{STORE_SITE:08x}','observed_store_values':[f'0x{x:04x}' for x in observed_stores],
              'isolated_cpu_results':store_outputs},
            'status_poll_helper':{'entry':f'0x{POLL_ENTRY:08x}','source_instructions':[f'0x{x:04x}' for x in poll_actual],
              'device_address':f'0x{DEVICE:08x}','mask':1,'observed_original_sequences':poll_results,
              'scope':'three exact eight-read groups captured at the original read site; each transitions from bit0 clear to set'},
            'scope':'one complete three-instruction word-read helper on original SH-2 bytes using only values captured from the natural run; CPU-only isolated memory; no hardware semantics, CD protocol meaning, caller equivalence or complete command root claimed',
            'whole_program_status':'active; incomplete'}
    fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--result',type=Path,required=True);p.add_argument('--records',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();print(json.dumps({'status':run(a.kernel,a.saturn_recomp,a.result,a.records,a.report)['status']}))
if __name__=='__main__':main()
