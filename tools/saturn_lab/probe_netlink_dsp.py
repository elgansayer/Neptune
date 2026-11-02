#!/usr/bin/env python3
"""Original NLSND4188, command12 and17F2 caller with bounded SCSP word effects.

Constructed inputs with frozen device clocks. Odd destinations remain explicit
native guard diagnostics, never completed68000 exception paths.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import analyze_sound_driver as sound
import m68k_scsp_dsp as native
import probe_command_dispatch as dispatch
import probe_kernel as pinned
import probe_netlink_pointer as leaf
import probe_netlink_records as records

ENTRY, END, HANDLER, POINTER, TABLE = 0x4188,0x41D4,0x1E4C,0x412,0x4210
MODES=('helper','handler','dispatcher')


def cases():
    selected=set(itertools.product(MODES,records.SR_VALUES,range(2),(0,0x10,0x20,0x30),
                                   (0,1,3,4,7,255),(0,1,15,16,31,32,255),(0,0x7E,0x80,0xBE,0xC0,0xFE)))
    for mode in MODES:
        for byte in range(256):
            selected.update(((mode,0x271F,0,byte,7,31,0),
                             (mode,0x2700,1,0x20,byte,16,0),
                             (mode,0x200A,0,0x10,4,byte,0x80),
                             (mode,0x2015,1,0x30,7,31,byte)))
    return sorted(selected)


def contract(code,mode,sr,variant,flags,selector,index,offset):
    if (mode not in MODES or sr not in records.SR_VALUES or variant not in (0,1)
            or any(type(v) is not int or not 0<=v<=255 for v in (flags,selector,index,offset))):
        raise ValueError('Undeclared DSP case')
    entry=ENTRY if mode=='helper' else HANDLER if mode=='handler' else dispatch.ENTRY
    before=records.base_regs(entry,sr)
    if variant:before[:15]=[r^0xFFFFFFFF for r in before[:15]]
    before[0]=(0xE1FFFF00 if variant else 0x11220000)|selector
    before[1]=(0xDEADFF00 if variant else 0x33440000)|index
    before[7]=(0xA5A5FF00 if variant else 0x11220000)|0x12
    before[8]=0x18000;before[14]=0x28000 if variant else 0x20000
    base=0x10000 if variant else 0x8000
    context=bytearray((i*37+selector+index)&255 for i in range(48))
    context[12:14]=bytes((flags,offset))
    stack=bytes((i*29+offset)&255 for i in range(64))+leaf.STOP.to_bytes(4,'big')
    regions=[(POINTER,base.to_bytes(4,'big'),False),(base-8,bytes(context),True),
             (0x18000,bytes((selector,index)),False),(TABLE,bytes(code[TABLE:TABLE+256]),False),
             (leaf.SP-64,stack,True)]
    buffers=[bytearray(data) for _,data,_ in regions]
    expected=list(before);events=[];pcs=[];sp=leaf.SP
    def memory(kind,address,size,value=None):
        for (lo,data,writable),buffer in zip(regions,buffers):
            if lo<=address and address+size<=lo+len(data):
                if kind==1:value=int.from_bytes(buffer[address-lo:address-lo+size],'big')
                else:
                    if not writable:raise ValueError('Oracle write outside writable RAM')
                    buffer[address-lo:address-lo+size]=value.to_bytes(size,'big')
                events.append([kind,address,size,value]);return value
        raise ValueError('Oracle access outside explicit RAM')
    def push(value):
        nonlocal sp
        sp-=4;memory(2,sp,4,value)
    def pop():
        nonlocal sp
        value=memory(1,sp,4);sp+=4;return value
    if mode=='dispatcher':
        pcs+=dispatch.contract(0x12,before[0]&0xFFFF,before[7]&0xFFFFFF00,sr,before[14])[5]
        for reg in (14,13):
            sp-=4;memory(2,sp+2,2,before[reg]&0xFFFF);memory(2,sp,2,before[reg]>>16)
        push(0x1868);expected[7]=(before[7]&0xFFFF0000)|0x48;expected[12]=before[14]
    if mode!='helper':
        pcs += [HANDLER,HANDLER+2,HANDLER+4]
        memory(1,0x18000,1);memory(1,0x18001,1);push(0x1E54)
    memory(1,POINTER,4);memory(1,base+4,1)
    expected[8]=base;expected[2]=(expected[2]&0xFFFFFF00)|(flags&0x30)
    pcs += [0x4188,0x418C,0x4190,0x4194]
    active=bool(flags&0x30);writes=[]
    if active:
        mask=3 if flags&0x10 else 7
        scaled_selector=(before[0]&mask)*8;scaled_index=(before[1]&31)*8
        destination=0x100700+offset+scaled_selector
        expected[0],expected[1],expected[3],expected[7]=scaled_selector,scaled_index,mask,offset
        expected[9],expected[10]=destination+8,TABLE+scaled_index+8
        pcs += [0x4198,0x419E,0x41A4,0x41A6,0x41AA]
        if mask==3:pcs.append(0x41AC)
        pcs += [0x41B0,0x41B2,0x41B4,0x41BA,0x41BC,0x41BE,0x41C2,0x41C4,0x41C6]
        memory(1,base+5,1)
        for i in range(4):
            pcs.append(0x41C8+i*2)
            value=memory(1,TABLE+scaled_index+i*2,2)
            writes.append((destination+i*2,value));events.append([2,destination+i*2,2,value])
        pcs.append(0x41D0)
    else:destination=None
    pcs += [0x40FA,0x40FC]
    if pop()!=(leaf.STOP if mode=='helper' else 0x1E54):raise ValueError('Helper return contract')
    if mode!='helper':
        pcs.append(0x1E54)
        if pop()!=(leaf.STOP if mode=='handler' else 0x1868):raise ValueError('Handler return contract')
    if mode=='dispatcher':
        pcs += [0x1868,0x186C]
        if [pop(),pop(),pop()]!=[before[13],before[14],leaf.STOP]:raise ValueError('Caller restore contract')
    expected[15:18]=[sp,leaf.STOP,(sr&~31)|dispatch.word_flags(expected[0]&0xFFFF,0 if active or mode=='dispatcher' else sr&16)]
    return before,expected,regions,[bytes(b) for b in buffers],events,pcs,writes,destination


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,writes,destination=contract(code,*case)
    entry=ENTRY if case[0]=='helper' else HANDLER if case[0]=='handler' else dispatch.ENTRY
    actual=library.run(code,entry,leaf.STOP,[(ENTRY,END),(HANDLER,HANDLER+10),
                       (dispatch.ENTRY,dispatch.END),(0x40FA,0x4104)],regions,before,budget=80,
                       device=(0xFFFFFFFF if case[2] else 0x12345678,case[2]))
    if destination is not None and destination&1:
        if ((actual['status_code'],actual['error_address'],actual['error_size'])!=(3,destination,2)
                or actual['pcs'][-1]!=0x41C8 or actual['device_after']!=actual['device_before']
                or any(e[0]==2 and e[1]>=0x100000 for e in actual['events']) or not actual['code_unchanged']):
            raise ValueError('Odd destination did not retain native alignment diagnostic')
        outcome='native-alignment-guard'
    else:
        records.check(actual,expected,after,events,pcs)
        device=actual['device_before']
        for address,value in writes:device=native.transition(device,address,value)
        if actual['device_after']!=device:raise ValueError('Terminal device register effects differ')
        outcome='complete-active' if writes else 'complete-inactive'
    return {'case':list(case),'outcome':outcome,'completed_original_call':outcome.startswith('complete-'),
            'registers':actual['registers'],'events':actual['events'],'pcs':actual['pcs'],'instructions':actual['steps'],
            'model_cycles':actual['model_cycles'],'device_before':actual['device_before'],'device_after':actual['device_after'],
            'regions_after':[b.hex() for b in actual['regions_after']],'code_unchanged':actual['code_unchanged']}


def execute(code,library):
    selected=cases()
    if len(selected)!=27195 or len(set(selected))!=27195:raise ValueError('Declared DSP selection changed')
    digest=hashlib.sha256();outcomes=Counter();samples=[];counts=Counter()
    for case in selected:
        row=run_case(code,library,*case);outcomes[row['outcome']]+=1;counts[(case[0],row['instructions'])]+=1
        digest.update(json.dumps(row,sort_keys=True,separators=(',',':')).encode())
        if case[1:3]==(0x2700,0) and case[3:6] in ((0,0,0),(0x10,4,16),(0x20,7,31)) and case[6] in (0,0x7E,0xC0,0xFE):samples.append(row)
    controls={}
    chosen=list(itertools.product(MODES,(0x2700,0x271F),(0,1),(0x10,),(4,7),(16,31),(0,)))
    for name,address,replacement in (('selector_mask',0x41AE,7),('table_mask',0x41B8,15),('device_base',0x419C,0x702)):
        altered=bytearray(code);altered[address:address+2]=replacement.to_bytes(2,'big')
        if bytes(altered)==bytes(code):raise ValueError('Ineffective original-copy control')
        reasons=Counter()
        for case in chosen:
            try:run_case(altered,library,*case)
            except ValueError as error:
                if str(error).startswith('Native guard:'):raise ValueError('Mutation failed before terminal semantics') from error
                reasons[str(error)]+=1
            else:raise ValueError('Original-copy control survived')
        controls[name]={'address':hex(address),'tested':len(chosen),'terminal_semantic_rejections':sum(reasons.values()),
                        'reasons':dict(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(selected),'outcomes':dict(outcomes),'observations_sha256':digest.hexdigest(),
            'instruction_counts':{mode+':'+str(n):v for (mode,n),v in sorted(counts.items())},
            'samples':samples,'instruction_controls':controls,'original_game_bytes_executed':True,
            'table_data_sha256':pinned.digest(code[TABLE:TABLE+256])}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True);parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-nlsnd-dsp.v1','status':'failure','release':'usa-mk81070-v1003',
            'module':'NLSND','cpu':'m68000','load_address':0,'lifetime':'netlink-sound-driver',
            'source_path':'NETLINK/SNDDRV.BIN','driver_sha256':sound.SOURCES['NLSND'][1],
            'native_identity':native.identity(),'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'limitations':['Constructed cases; device clocks frozen; no natural command domain or hardware proof',
                           'Odd addresses retain native alignment guard, not full68000 exception semantics',
                           'No complete SCSP/DSP/audio/gameplay/timing or whole-code recovery claim']}
    fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:
        phase='identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');library=native.Library(args.prepared)
            report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':str(error)}
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'error':report.get('error')}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
