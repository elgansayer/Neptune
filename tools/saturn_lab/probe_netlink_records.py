#!/usr/bin/env python3
"""Original NetLink state-copy and record-scan samples with explicit RAM only."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_probe as native
import probe_netlink_pointer as leaf
import probe_kernel as pinned

COPY, COPY_END, SCAN, SCAN_END = 0x4BB6, 0x4BE0, 0x4BE0, 0x4C2A
RECORD, SLOTS, PTR = 0x18000, 0x20000, 0x404
SR_VALUES = (0x2700,0x271F,0x200A,0x2015)
COPY_PCS = [0x4BB6,0x4BBA,0x4BBE,0x4BC2,0x4BC6,0x4BCA,0x4BCC,0x4BD0,0x4BD2,0x4BD6,0x4BDA,0x4BDE]


def copy_cases():
    return list(itertools.product(range(256), ((0,0),(1,255),(128,127),(255,128)),
                                  SR_VALUES, (0x30000,0x40000)))


def scan_cases():
    return list(itertools.product(range(-1,32), SR_VALUES, (0,1)))


def base_regs(entry,sr):
    regs=[0xA5A5A5A5]*18
    regs[14],regs[15],regs[16],regs[17]=RECORD,leaf.SP,entry,sr
    return regs


def copy_contract(index,payload,sr,base):
    before=base_regs(COPY,sr)
    expected=list(before)
    expected[15],expected[16]=leaf.SP+4,leaf.STOP
    expected[17]=(sr & ~31) | (8 if payload[1]&128 else 4 if payload[1]==0 else 0)
    destination=base+0x80+2*index
    saved=b''.join(before[i].to_bytes(4,'big') for i in (0,1,2,8))
    stack=bytes([0xCD])*16+leaf.STOP.to_bytes(4,'big')
    regions=[(PTR,base.to_bytes(4,'big'),False),(RECORD+1,bytes([index,*payload]),False),
             (destination,bytes.fromhex('e36c'),True),(leaf.SP-16,stack,True)]
    events=[[2,leaf.SP-offset,4,before[reg]] for offset,reg in ((4,8),(8,2),(12,1),(16,0))]
    events += [[1,PTR,4,base],[1,RECORD+2,1,payload[0]],[1,RECORD+3,1,payload[1]],
               [1,RECORD+1,1,index],[2,destination,1,payload[0]],[2,destination+1,1,payload[1]]]
    events += [[1,leaf.SP+offset,4,before[reg]] for offset,reg in ((-16,0),(-12,1),(-8,2),(-4,8))]
    events += [[1,leaf.SP,4,leaf.STOP]]
    after=[regions[0][1],regions[1][1],bytes(payload),saved+stack[16:]]
    return before,expected,regions,after,events,destination


def scan_contract(free,sr,variant):
    before=base_regs(SCAN,sr)
    before[13]=SLOTS
    before[:5]=([0x11223300,0x4455667F,0x77889980,0xABCDEF01,0xDEADBEEF] if variant==0 else
                [0xFFFFFFFF,0x80000000,0x123456FF,0x87654380,0])
    records=bytearray((i*37+19)&255 for i in range(32*12))
    for i in range(32): records[i*12]=0xFF if variant else 0x80|i
    if free>=0:
        records[free*12]=0x7F if variant else 1
        if free+1<32:records[(free+1)*12]=0  # A second free slot must not be chosen.
    expected_records=bytearray(records)
    expected=list(before)
    expected[15],expected[16],expected[17]=leaf.SP+4,leaf.STOP,0x2700
    stack=bytes([0xCD])*10+leaf.STOP.to_bytes(4,'big')
    regions=[(SLOTS,bytes(records),True),(leaf.SP-10,stack,True)]
    events=[[2,leaf.SP-4,4,before[13]],[2,leaf.SP-8,4,before[7]],[2,leaf.SP-10,2,0x2700]]
    limit=free+1 if free>=0 else 32
    events += [[1,SLOTS+12*i,1,records[12*i]] for i in range(limit)]
    if free>=0:
        offset=free*12
        for field,reg in ((1,0),(2,1),(3,2),(0,3)):
            expected_records[offset+field]=before[reg]&255
            events.append([2,SLOTS+offset+field,1,before[reg]&255])
        for field,reg in ((4,4),(8,14)):
            expected_records[offset+field:offset+field+4]=before[reg].to_bytes(4,'big')
            events.append([2,SLOTS+offset+field,4,before[reg]])
        events.append([1,SLOTS+offset,1,before[3]&255])
        expected_records[offset] |= 128
        events.append([2,SLOTS+offset,1,expected_records[offset]])
    events += [[1,leaf.SP-10,2,0x2700],[1,leaf.SP-8,4,before[7]],
               [1,leaf.SP-4,4,before[13]],[1,leaf.SP,4,leaf.STOP]]
    expected_stack=(0x2700).to_bytes(2,'big')+before[7].to_bytes(4,'big')+before[13].to_bytes(4,'big')+stack[10:]
    pcs=[0x4BE0,0x4BE4,0x4BE6,0x4BEA]
    if free>=0:
        pcs += [pc for _ in range(free) for pc in (0x4BEC,0x4BF0,0x4BF4,0x4BFA,0x4BFC)]
        pcs += [0x4BEC,0x4BF0,0x4C0A,0x4C0E,0x4C12,0x4C16,0x4C1A,0x4C1E,0x4C22,0x4C26,0x4C28]
    else:
        pcs += [pc for _ in range(32) for pc in (0x4BEC,0x4BF0,0x4BF4,0x4BFA,0x4BFC)]
        pcs += [0x4BFE]
    pcs += [0x4C02,0x4C04,0x4C08]
    return before,expected,regions,[bytes(expected_records),expected_stack],events,pcs


def check(actual,expected,regions_after,events,pcs):
    if actual['status_code']!=1:raise ValueError('Native guard: '+actual['status'])
    if actual['registers']!=expected:raise ValueError('Register/SR result differs from independent contract')
    if actual['regions_after']!=regions_after or not actual['code_unchanged']:
        raise ValueError('Output or unaffected mapped byte differs')
    if actual['events']!=events:raise ValueError('Read/write sequence or widths differ')
    if actual['pcs']!=pcs or actual['steps']!=len(pcs):raise ValueError('Original executed-PC path differs')


def run_copy(code,library,index,payload,sr,base):
    before,expected,regions,after,events,destination=copy_contract(index,payload,sr,base)
    actual=library.run(code,COPY,leaf.STOP,[(COPY,COPY_END)],regions,before,budget=32)
    check(actual,expected,after,events,COPY_PCS)
    return {'entry':hex(COPY),'index':index,'payload':list(payload),'initial_SR':sr,'base':base,
            'destination':hex(destination),'after_SR':expected[17],'instructions':actual['steps'],
            'model_cycles':actual['model_cycles'],'data_events':events,'pcs':[hex(p) for p in actual['pcs']],
            'other_visible_registers_preserved':True,'unaffected_mapped_bytes_equal':True}


def run_scan(code,library,free,sr,variant):
    before,expected,regions,after,events,pcs=scan_contract(free,sr,variant)
    actual=library.run(code,SCAN,leaf.STOP,[(SCAN,SCAN_END)],regions,before,budget=256)
    check(actual,expected,after,events,pcs)
    return {'entry':hex(SCAN),'first_free_index':free,'variant':variant,'initial_SR':sr,
            'after_SR':expected[17],'instructions':actual['steps'],'model_cycles':actual['model_cycles'],
            'data_events':events,'pcs':[hex(p) for p in actual['pcs']],
            'general_registers_preserved':True,'unaffected_mapped_bytes_equal':True,
            'result_record_sha256':pinned.digest(after[0])}


def execute(code,library):
    copies,scans=copy_cases(),scan_cases()
    if len(copies)!=8192 or len(scans)!=264:raise ValueError('Constructed selections changed')
    rows=[run_copy(code,library,*case) for case in copies]+[run_scan(code,library,*case) for case in scans]
    controls={}
    for name,address,replacement,call,selected in (
        ('copy_missing_index_clear',0x4BCA,bytes.fromhex('4e71'),run_copy,copies[::32]),
        ('copy_missing_second_store',0x4BD6,bytes.fromhex('4e71 4e71'),run_copy,copies[::32]),
        ('scan_limit31',0x4BE4,bytes.fromhex('7e1f'),run_scan,scans),
        ('scan_no_allocation_flag',0x4C22,bytes.fromhex('4e71 4e71'),run_scan,scans),
    ):
        altered=bytearray(code);altered[address:address+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in selected:
            try:call(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original survived all selected cases')
        controls[name]={'address':hex(address),'tested':len(selected),'rejected':rejected,'reasons':sorted(reasons),
                        'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'copy_cases':len(copies),'scan_cases':len(scans),'results':rows,
            'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':{f'{lo:x}:{hi:x}':pinned.digest(code[lo:hi]) for lo,hi in ((COPY,COPY_END),(SCAN,SCAN_END))}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-records.v1','status':'failure','experiment':'EXP-SAT-CODE-007',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1],'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'bridge_sha256':pinned.digest(Path(native.__file__).read_bytes()),
            'limitations':['Initialized RAM/registers, not natural sound events or a proven queue role',
                           'No SCSP/device/DSP model, independent hardware oracle, timing or whole-program completion']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');phase='prepared_identity'
            library=native.Library(args.prepared);report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='owned_smoke';report['owned_smoke']=native.smoke(library)
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':'Identity, execution or contract failed'}
        output.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
