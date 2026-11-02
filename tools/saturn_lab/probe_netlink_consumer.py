#!/usr/bin/env python3
"""Full32-record original NetLink consumer, with bounded nested writer traces."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_consumer_native as extended
import m68k_probe as short
import probe_kernel as pinned
import probe_netlink_command as command
import probe_netlink_pointer as leaf
import probe_netlink_records as records

ENTRY,END,SLOTS,RECORD,PTR=0x4B1C,0x4B6E,0x20000,0x18000,0x450
ALL=0xFFFFFFFF


def cases():
    masks=[0,*[1<<i for i in range(32)],ALL,0x55555555,0xAAAAAAAA]
    shapes=[(mask,ALL) for mask in masks]+[(ALL,m) for m in (0,1,0x80000000,0x55555555,0xAAAAAAAA)]
    return [(active,matching,clear,counter,tag) for active,matching in shapes
            for clear in (0,1,0x100,0xFF) for counter in (0,250,255) for tag in (0,9,255)]


def contract(active,matching,clear,counter,tag):
    sr=0x2700 if tag==0 else 0x271F if tag==9 else 0x200A
    base=0x8000 if tag==0 else 0x10000
    before=records.base_regs(ENTRY,sr);before[13]=SLOTS;before[7]=0x33440000|clear
    expected=list(before)
    entries=bytearray((i*37+19)&255 for i in range(384))
    for i in range(32):
        off=12*i;entries[off]=((0x80 if active>>i&1 else 0)|((i*3+1)&0x7F))
        entries[off+1]=(i*7+0x91)&255
        entries[off+2]=(i*17+0x7F)&255
        entries[off+3]=(i*29+0x80)&255
        pointer=RECORD if matching>>i&1 else RECORD+0x1000
        entries[off+8:off+12]=pointer.to_bytes(4,'big')
    queue=bytes((i*53+71)&255 for i in range(1024))
    regions=[(PTR,base.to_bytes(4,'big'),False),(RECORD+1,bytes([tag]),False),
             (SLOTS,bytes(entries),True),(base+0x1840,bytes([counter]),True),
             (base+0x1A00,queue,True),
             (leaf.SP-26,bytes([0xCD])*26+leaf.STOP.to_bytes(4,'big'),True)]
    buffers=[bytearray(data) for _,data,_ in regions]
    events=[];pcs=[0x4B1C,0x4B20];emitted=[]

    def read(address,size):
        for (lo,data,_),buf in zip(regions,buffers):
            if lo<=address and address+size<=lo+len(data):
                value=int.from_bytes(buf[address-lo:address-lo+size],'big')
                events.append([1,address,size,value]);return value
        raise ValueError('Oracle read outside declared data')

    def write(address,size,value):
        for (lo,data,writable),buf in zip(regions,buffers):
            if writable and lo<=address and address+size<=lo+len(data):
                events.append([2,address,size,value]);buf[address-lo:address-lo+size]=value.to_bytes(size,'big');return
        raise ValueError('Oracle write outside declared data')

    def save_long(address,value):
        write(address+2,2,value&0xFFFF);write(address,2,value>>16)

    save_long(leaf.SP-4,before[13]);save_long(leaf.SP-8,before[6])
    flags=sr&16  # MOVE.W #31,D6 clears N/Z/V/C; X is preserved.
    expected[6]=(before[6]&0xFFFF0000)|31
    for i in range(32):
        address=SLOTS+12*i
        pcs += [0x4B24,0x4B28]
        flag=read(address,1);occupied=bool(flag&128)
        flags=(flags&~4)|(0 if occupied else 4)
        if occupied:
            pcs += [0x4B2C,0x4B30]
            pointer=read(address+8,4)
            is_match=pointer==RECORD
            # All deliberately mismatched pointers are larger positive addresses.
            flags=(flags&16)|(4 if is_match else 9)
            if is_match:
                pcs += [0x4B34,0x4B36]
                low=before[7]&255
                flags=(flags&16)|(8 if low&128 else 4 if low==0 else 0)
                if low:
                    pcs += [0x4B3A]
                    old=read(address,1);write(address,1,old&127);flags &= ~4
                pcs += [0x4B3E,0x4B42,0x4B46,0x4B4A,0x4B4E,0x4B52,0x4B56,0x4B5A]
                status=read(address+1,1)&15
                data=read(address+2,1);payload=read(address+3,1);record_flag=read(address,1)&1
                write(leaf.SP-12,4,0x4B5E)
                pcs += command.PREFIX+command.SUFFIX  # Emitted status80..8F excludes the90 branch.
                call_sp=leaf.SP-12
                for offset,reg in ((4,7),(8,6),(12,5)):save_long(call_sp-offset,expected[reg])
                read(PTR,4);read(RECORD+1,1)
                saved_sr=(sr&~31)|4|(16 if tag&8 else 0)
                write(call_sp-14,2,saved_sr)
                old_counter=read(base+0x1840,1);read(base+0x1840,1)
                write(base+0x1840,1,(old_counter+1)&255)
                destination=base+0x1A00+4*old_counter
                packet=bytes([0,status|(record_flag<<4)|((tag<<5)&255),data,payload])
                for offset,value in enumerate(packet):write(destination+offset,1,value)
                read(call_sp-14,2)
                for offset in (-12,-8,-4):read(call_sp+offset,4)
                read(call_sp,4)
                expected[0]=(before[0]&~255)|0x80
                expected[1]=(before[1]&~255)|data
                expected[2]=(before[2]&~255)|payload
                expected[3]=(before[3]&~255)|(record_flag<<4)
                expected[8:11]=[base,base+0x1840,destination+4]
                flags=saved_sr&31
                emitted.append({'record_index':i,'counter':old_counter,'destination':hex(destination),'packed':packet.hex()})
        pcs += [0x4B5E,0x4B64]
        expected[6]=(expected[6]&0xFFFF0000)|((expected[6]-1)&0xFFFF)
    pcs += [0x4B68,0x4B6C]
    read(leaf.SP-8,4);read(leaf.SP-4,4);read(leaf.SP,4)
    expected[6]=before[6];expected[13]=before[13]
    expected[15:18]=[leaf.SP+4,leaf.STOP,(sr&~31)|flags]
    return before,expected,regions,[bytes(buf) for buf in buffers],events,pcs,emitted


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,emitted=contract(*case)
    actual=library.run(code,ENTRY,leaf.STOP,[(ENTRY,END),(command.ENTRY,command.END)],regions,before,budget=2048)
    records.check(actual,expected,after,events,pcs)
    return {'active_mask':hex(case[0]),'matching_mask':hex(case[1]),'clear_bits':case[2],
            'counter_before':case[3],'tag':case[4],'counter_after':after[3][0],
            'emitted':emitted,'instructions':actual['steps'],'events':len(actual['events']),
            'model_cycles':actual['model_cycles'],'registers_after':actual['registers'],
            'pcs':[hex(pc) for pc in actual['pcs']],'data_events':actual['events'],
            'records_after_sha256':pinned.digest(after[2]),'queue_after_sha256':pinned.digest(after[4]),
            'unaffected_mapped_bytes_equal':True,'all_visible_registers_checked':True}


def short_proof(code,library):
    case=(ALL,ALL,1,250,9)
    before,expected,regions,after,events,pcs,emitted=contract(*case)
    actual=library.run(code,ENTRY,leaf.STOP,[(ENTRY,END),(command.ENTRY,command.END)],regions,before,budget=256)
    if actual['status_code']!=6 or len(actual['events'])!=128:
        raise ValueError('Expected original full-consumer short-profile event rejection was not observed')
    return {'status':'expected-short-profile-rejection','original_game_bytes_executed':True,
            'completed_original_call':False,'guard':actual['status'],'observed_instructions':actual['steps'],
            'observed_events':len(actual['events']),'error_address':hex(actual['error_address']),
            'expected_full_instructions':len(pcs),'expected_full_events':len(events),'expected_emissions':len(emitted),
            'source_unchanged':actual['code_unchanged'],'short_identity':short.identity()}


def execute(code,library):
    selected=cases()
    if len(selected)!=1476 or len(set(selected))!=1476:raise ValueError('Consumer selection changed')
    rows=[run_case(code,library,*case) for case in selected]
    controls_selected=[(active,matching,clear,counter,tag) for active,matching in
        ((ALL,ALL),(ALL,0),(ALL,0xAAAAAAAA),(0x80000000,ALL))
        for clear in (0,1,0x100) for counter in (0,255) for tag in (0,9)]
    controls={}
    for name,offset,replacement in (
        ('wrong_pointer_filter',0x4B30,bytes.fromhex('6700')),
        ('missing_flag_clear',0x4B3A,bytes.fromhex('4e71 4e71')),
        ('scan_only31',0x4B22,(30).to_bytes(2,'big')),
        ('clear_tests_longword',0x4B34,bytes.fromhex('4a87')),
        ('flag_mask_three',0x4B50,(3).to_bytes(2,'big')),
    ):
        altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in controls_selected:
            try:run_case(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original consumer survived')
        controls[name]={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                        'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'original_game_bytes_executed':True,'instruction_controls':controls,
            'max_instructions':max(r['instructions'] for r in rows),'max_events':max(r['events'] for r in rows),
            'max_emissions':max(len(r['emitted']) for r in rows),
            'range_sha256':{f'{lo:x}:{hi:x}':pinned.digest(code[lo:hi]) for lo,hi in
                ((ENTRY,END),(command.ENTRY,command.END))}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--short-proof',action='store_true')
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-consumer.v1','status':'failure','experiment':'EXP-SAT-CODE-009',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1],'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'command_adapter_sha256':pinned.digest(Path(command.__file__).read_bytes()),
            'profile_identity':short.identity() if args.short_proof else extended.identity(),
            'limitations':['Constructed records/RAM/registers; no natural sound-event, hardware or SCSP/DSP validation',
                           'Complete declared32-record call cases, not every possible record/machine state',
                           'Shared interpreter lineage; whole-program/function/dynamic-target denominator unknown']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');phase='prepared_identity'
            library=short.Library(args.prepared) if args.short_proof else extended.Library(args.prepared)
            report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='original_short_rejection' if args.short_proof else 'owned_smoke'
            if args.short_proof:report.update(short_proof(code,library))
            else:
                report['owned_smoke']=extended.smoke(library);phase='original_execution'
                report.update(execute(code,library),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':'Identity, bounded execution or contract failed'}
        output.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0)}))
    return 0 if report['status'] in ('success','expected-short-profile-rejection') else 1


if __name__=='__main__':raise SystemExit(main())
