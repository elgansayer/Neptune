#!/usr/bin/env python3
"""Original NetLink queue parsing, eight transfers and three returning flag paths."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_probe as native
import probe_kernel as pinned
import probe_netlink_pointer as leaf
import probe_netlink_records as records

ENTRY,TABLE_END,FLAG_END=0x241A,0x24D2,0x24EA
TARGETS=(0x3248,0x2BFC,0x24D2,0x24EA,0x1762,0x24DA,0x2B08,0x24E2)
RETURNING={2:(0x24D2,2),5:(0x24DA,3),7:(0x24E2,4)}
SECONDS=(0,255,0x9B,0xE4)
VARIANTS=((0,255,0x2700,0x8000,0),(128,0,0x201F,0x10000,255),
          (255,127,0x2715,0x8000,0x10),(127,128,0x200A,0x10000,4))
PREFIX=(0x241A,0x241C,0x2420,0x2424,0x2426,0x2428,0x242C,0x242E,0x2432,0x2434,0x2438,0x243C,0x243E)
DECODE=(0x2480,0x2482,0x2484,0x2486,0x248A,0x248C,0x2490,0x2494,0x2496,0x2498,
        0x249C,0x24A0,0x24A4,0x24A6,0x24A8,0x24AC,0x24AE)


def cases():
    selected=set()
    for first,variant in itertools.product(range(256),range(4)):
        selected.add((first,SECONDS[variant],(0,255,127,1)[variant],(0,255,254,127)[variant],
                      (0,0x40,0x80,255)[variant],variant))
    for group,second,gate in itertools.product(range(8),range(256),(0,0x40)):
        selected.add((group,second,255 if gate else 0,254 if gate else 255,gate,(group+second)&3))
    for group,index,gate in itertools.product(range(8),range(256),(0,0x40)):
        variant=index&3
        selected.add((group,SECONDS[variant],index,(37*index+255)&255,gate,variant))
    for group,gate in itertools.product((1,4,7),range(256)):
        variant=gate&3
        selected.add((group,SECONDS[variant],(13*gate)&255,(19*gate+255)&255,gate,variant))
    rows=[(*case,False) for case in sorted(selected)]
    rows += [(*case,True) for case in sorted(selected) if case[0]&7 in RETURNING]
    return rows


def contract(first,second,read_index,write_index,gate,variant,complete):
    data2,data3,sr,base,initial_flag=VARIANTS[variant]
    group=first&7
    if complete and group not in RETURNING:raise ValueError('Handler not yet modeled')
    before=records.base_regs(ENTRY,sr);before[14]=base
    expected=list(before)
    scratch=bytearray((i*37+19)&255 for i in range(0x44))
    scratch[0x41],scratch[0x42]=write_index,read_index
    packet=bytes([first,second,data2,data3])
    packet_address=base+0x1A00+4*read_index
    output=bytes((i*53+71)&255 for i in range(256))
    regions=[(base+0x1800,bytes(scratch),True),(packet_address,packet,False),
             (0x4E1,bytes([gate]),False),(base+0x1F00,output,True),
             (0x417,bytes([initial_flag]),True),(leaf.SP,leaf.STOP.to_bytes(4,'big'),False)]
    buffers=[bytearray(data) for _,data,_ in regions];events=[];pcs=list(PREFIX)

    def read(address,size):
        for (lo,data,_),buf in zip(regions,buffers):
            if lo<=address and address+size<=lo+len(data):
                value=int.from_bytes(buf[address-lo:address-lo+size],'big')
                events.append([1,address,size,value]);return value
        raise ValueError('Oracle read outside explicit data')

    def write(address,size,value):
        for (lo,data,writable),buf in zip(regions,buffers):
            if writable and lo<=address and address+size<=lo+len(data):
                events.append([2,address,size,value]);buf[address-lo:address-lo+size]=value.to_bytes(size,'big');return
        raise ValueError('Oracle write outside explicit data')

    read(base+0x1842,1);read(base+0x1842,1);write(base+0x1842,1,(read_index+1)&255)
    read(base+0x1841,1);read(0x4E1,1)
    formatted=[];cursor=write_index
    if gate&0x40:
        status=0x80|((read(packet_address,1)<<4)&255)|(second&15)
        read(packet_address+1,1)
        pcs += [0x2440,0x2442,0x2444,0x2448,0x244C,0x2450,0x2452,0x2456,0x2458,0x245C]
        formatted=[status,data2] if 0xC0<=status<0xE0 else [status,data2,data3]
        write(base+0x1F00+cursor,1,status);cursor=(cursor+1)&255
        if status>=0xC0:
            pcs += [0x245E,0x2462]
        if 0xC0<=status<0xE0:
            pcs += [0x2464,0x246A]
            read(packet_address+2,1);write(base+0x1F00+cursor,1,data2)
        else:
            pcs += [0x246C,0x2472,0x2474]
            read(packet_address+2,1);write(base+0x1F00+cursor,1,data2);cursor=(cursor+1)&255
            read(packet_address+3,1);write(base+0x1F00+cursor,1,data3)
        cursor=(cursor+1)&255
        pcs += [0x247A,0x247C];write(base+0x1841,1,cursor)
    pcs += list(DECODE)
    read(packet_address,1);read(packet_address+1,1)
    bank=(second&0xE0)<<4
    write(base+0x1800,2,bank)
    read(base+0x1800,2)
    offset=second<<4
    write(base+0x180A,2,offset);write(base+0x1802,2,second&31)
    read(packet_address+2,1);read(packet_address+3,1)
    expected[0]=group*4
    expected[1]=(before[1]&0xFFFF0000)|(second&31)
    expected[2]=(before[2]&0xFFFF0000)|(offset&0xFF00)|data2
    expected[3]=(before[3]&~255)|data3
    expected[4]=cursor
    expected[9],expected[10]=packet_address+3,base+0x1F00
    expected[16],expected[17]=TARGETS[group],(sr&~31)|(4 if group==0 else 0)
    pcs += [0x24B2+4*group]
    if complete:
        target,bit=RETURNING[group]
        pcs += [target,target+6]
        old=read(0x417,1);write(0x417,1,old|(1<<bit))
        read(leaf.SP,4)
        expected[15],expected[16]=leaf.SP+4,leaf.STOP
        expected[17]=(sr&~31)|(0 if old&(1<<bit) else 4)
    return before,expected,regions,[bytes(b) for b in buffers],events,pcs,formatted


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,formatted=contract(*case)
    complete=case[-1]
    end=FLAG_END if complete else TABLE_END
    actual=library.run(code,ENTRY,expected[16],[(ENTRY,end)],regions,before,budget=96)
    records.check(actual,expected,after,events,pcs)
    return {'first_byte':case[0],'second_byte':case[1],'read_index':case[2],'write_index':case[3],
            'gate_byte':case[4],'variant':case[5],'complete_flag_return':complete,
            'group':case[0]&7,'dispatch_target':hex(TARGETS[case[0]&7]),'formatted':formatted,
            'registers_after':actual['registers'],'instructions':actual['steps'],'model_cycles':actual['model_cycles'],
            'pcs':actual['pcs'],'data_events':actual['events'],
            'scratch_sha256':pinned.digest(after[0]),'output_sha256':pinned.digest(after[3]),
            'unaffected_mapped_bytes_equal':True,'stopped_before_unmodeled_handler':not complete}


def execute(code,library):
    selected=cases()
    if (len(selected)!=13690 or len(selected)!=len(set(selected))
            or sum(c[-1] for c in selected)!=3711):raise ValueError('Missing/duplicate cases')
    rows=[run_case(code,library,*case) for case in selected]
    controls_selected=[(g,0x9B,255,255,gate,v,g in RETURNING) for g in range(8)
                       for gate in (0,0x40,0x80,255) for v in (0,1)]
    controls={}
    for name,offset,replacement in (
        ('missing_read_index_increment',0x2420,bytes.fromhex('4e71 4e71')),
        ('gate_uses_bit7',0x243C,bytes.fromhex('4e71')),
        ('wrong_two_byte_threshold',0x245A,(0xB0).to_bytes(2,'big')),
        ('group_mask_three',0x24AA,(3).to_bytes(2,'big')),
        ('wrong_flag_bit',0x24D4,(1).to_bytes(2,'big')),
    ):
        altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in controls_selected:
            try:run_case(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Original parser mutation survived')
        controls[name]={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                        'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'dispatch_cases':sum(not c[-1] for c in selected),
            'complete_flag_cases':sum(c[-1] for c in selected),'results':rows,
            'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':pinned.digest(code[ENTRY:FLAG_END]),'targets':[hex(t) for t in TARGETS]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True);parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-parser.v1','status':'failure','experiment':'EXP-SAT-CODE-010',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN','driver_sha256':sound.SOURCES['NLSND'][1],
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),'native_identity':native.identity(),
            'contract_adapter_sha256':pinned.digest(Path(records.__file__).read_bytes()),
            'limitations':['Constructed queues/registers; three returning flag paths only, other handlers stop at transfer',
                           'No natural sound protocol, SCSP/DSP/hardware timing or whole-program completion']}
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
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
