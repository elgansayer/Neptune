#!/usr/bin/env python3
"""Independent original NLSND5290 ramp preparation, with explicit RAM only.

Parameters have numbered names: their natural sound roles/domains remain unknown.
Constructed byte sweeps are not complete state-updater or command11 acceptance.
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
import m68k_scsp_state as native
import probe_kernel as pinned
import probe_netlink_pointer as leaf
import probe_netlink_records as records

ENTRY,END=0x5290,0x535E
EDGES=(0,1,63,64,126,127,128,129,254,255)
STEPS=(0,1,2,127,128,129,254,255)
BASE=((32,63,64),(64,32,63),(1,130,3))


def cases():
    vectors=set()
    for axis in range(3):
        for current,target,step in itertools.product(EDGES,EDGES,STEPS):
            fields=[list(v) for v in BASE]
            for group,value in enumerate((current,target,step)):fields[group][axis]=value
            vectors.add(tuple(tuple(v) for v in fields))
        for group in range(3):
            for value in range(256):
                fields=[list(v) for v in BASE];fields[group][axis]=value
                vectors.add(tuple(tuple(v) for v in fields))
    return sorted((sr,variant,(current[0]^target[1]^step[2]^variant)&255,current,target,step)
                  for sr,variant in itertools.product(records.SR_VALUES,(0,1))
                  for current,target,step in vectors)


def contract(sr,variant,flags,current,target,step):
    if (sr not in records.SR_VALUES or type(variant) is not int or variant not in (0,1)
            or type(flags) is not int or not 0<=flags<=255
            or any(not isinstance(v,tuple) or len(v)!=3 or
                   any(type(x) is not int or not 0<=x<=255 for x in v)
                   for v in (current,target,step))):
        raise ValueError('Undeclared ramp case')
    before=records.base_regs(ENTRY,sr)
    if variant:before[:15]=[r^0xFFFFFFFF for r in before[:15]]
    base=0x10000 if variant else 0x8000;before[14]=base
    for axis in range(3):before[5+axis]=(before[5+axis]&0xFFFFFF00)|current[axis]
    context=bytearray((i*37+flags+variant)&255 for i in range(80))
    for axis in range(3):
        context[8+0x12+axis*2]=target[axis]
        context[8+0x1A+axis*2]=step[axis]
    context[8+0x2C]=flags
    stack=bytes([0xCD])*16+leaf.STOP.to_bytes(4,'big')
    regions=[(base-8,bytes(context),True),(leaf.SP-16,stack,True)]
    buffers=[bytearray(data) for _,data,_ in regions];events=[]
    def memory(kind,address,size,value=None):
        for (lo,data,writable),buffer in zip(regions,buffers):
            if lo<=address and address+size<=lo+len(data):
                if kind==1:value=int.from_bytes(buffer[address-lo:address-lo+size],'big')
                else:
                    if not writable:raise ValueError('Oracle write outside explicit RAM')
                    buffer[address-lo:address-lo+size]=value.to_bytes(size,'big')
                events.append([kind,address,size,value]);return value
        raise ValueError('Oracle access outside explicit RAM')
    def read(offset):return memory(1,base+offset,1)
    def write(offset,value):memory(2,base+offset,1,value)
    # First parameter uses unsigned distance and a seven-bit step magnitude.
    # The other two preserve the raw signed-byte step and use directional wrap.
    write(0x2C,read(0x2C)|1)
    for offset in (0x12,0x14,0x16):read(offset)
    magnitude=read(0x1A)&127;write(0x26,magnitude)
    write(0x20,abs(target[0]-current[0]))
    write(6,magnitude if target[0]>=current[0] else (-magnitude)&255)
    pcs=[0x5290,0x5296,0x529A,0x529E,0x52A2,0x52A6,0x52AA,0x52AE,0x52B0,0x52B2]
    pcs+=([0x52B6,0x52B8,0x52BA,0x52BE,0x52C2] if target[0]>=current[0]
          else [0x52C6,0x52C8,0x52CA,0x52CE,0x52D0])
    distances=[];magnitudes=[];extend=0
    for axis,start in ((1,0x52D4),(2,0x5312)):
        raw=read(0x1A+axis*2);write(6+axis*2,raw)
        negative=bool(raw&128);mag=(-raw)&255 if negative else raw
        write(0x26+axis*2,mag);magnitudes.append(mag)
        difference=(current[axis]-target[axis]) if negative else (target[axis]-current[axis])
        wrapped=difference<0;distance=difference&255
        extend=16 if wrapped else 0
        if wrapped:
            extend=16 if distance+128>255 else 0
            distance=(distance+128)&255
        write(0x20+axis*2,distance);distances.append(distance)
        if axis==1:
            pcs += [start,0x52D8,0x52DC,0x52E0]
            pcs += ([0x52E4,0x52E6,0x52EA,0x52EC,0x52EE,0x52F0] if negative
                    else [0x52FC,0x5300,0x5302,0x5304,0x5306])
            if wrapped:pcs += [0x52F4,0x52F8] if negative else [0x530A]
            pcs += [0x530E]
        else:
            pcs += [start,0x5316,0x531A,0x531E]
            pcs += ([0x5322,0x5324,0x5328,0x532A,0x532C,0x532E] if negative
                    else [0x533A,0x533E,0x5340,0x5342,0x5344])
            if wrapped:pcs += [0x5332,0x5336] if negative else [0x5348]
            pcs += [0x534C]
    for axis in range(3):write(0xC+axis*2,target[axis])
    pcs += [0x5350,0x5354,0x5358,0x535C]
    memory(1,leaf.SP,4)
    expected=list(before);expected[0]=distances[-1]
    expected[1]=(expected[1]&0xFFFFFF00)|magnitudes[-1]
    for axis in range(3):expected[2+axis]=(expected[2+axis]&0xFFFFFF00)|target[axis]
    flags_out=extend|(8 if target[2]&128 else 4 if target[2]==0 else 0)
    expected[15:18]=[leaf.SP+4,leaf.STOP,(sr&~31)|flags_out]
    return before,expected,regions,[bytes(b) for b in buffers],events,pcs


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs=contract(*case)
    actual=library.run(code,ENTRY,leaf.STOP,[(ENTRY,END)],regions,before,budget=96)
    records.check(actual,expected,after,events,pcs)
    if actual['device_after']!=actual['device_before']:
        raise ValueError('RAM-only ramp helper changed SCSP state')
    return {'case':case,'registers':actual['registers'],'events':actual['events'],
            'pcs':actual['pcs'],'instructions':actual['steps'],'model_cycles':actual['model_cycles'],
            'regions_after':[b.hex() for b in actual['regions_after']],
            'code_unchanged':actual['code_unchanged']}


def execute(code,library):
    selected=cases();digest=hashlib.sha256();counts=Counter();samples=[]
    for case in selected:
        row=run_case(code,library,*case);counts[row['instructions']]+=1
        digest.update(json.dumps(row,sort_keys=True,separators=(',',':')).encode())
        if len(samples)<8:samples.append(row)
    controls={}
    chosen=[(sr,v,0,(127,0,127),(0,127,0),(1,130,1))
            for sr,v in itertools.product((0x2700,0x271F),(0,1))]
    for name,address,value in (('state_bit',0x5292,1),('direction_branch',0x52B2,0x6400),
                                ('wrap_amount',0x534A,127)):
        altered=bytearray(code);altered[address:address+2]=value.to_bytes(2,'big')
        if altered==code:raise ValueError('Ineffective original-copy control')
        reasons=Counter()
        for case in chosen:
            before,_,regions,*_=contract(*case)
            actual=library.run(bytes(altered),ENTRY,leaf.STOP,[(ENTRY,END)],regions,before,budget=96)
            if actual['status_code']!=1:raise ValueError('Mutation did not reach terminal semantics')
            try:run_case(bytes(altered),library,*case)
            except ValueError as error:
                if str(error).startswith('Native guard:'):raise
                reasons[str(error)]+=1
            else:raise ValueError('Terminal original-copy mutation escaped comparison')
        controls[name]={'terminal_comparisons':len(chosen),'rejected':sum(reasons.values()),'reasons':dict(reasons)}
    return {'cases':len(selected),'observations_sha256':digest.hexdigest(),
            'instruction_counts':dict(sorted(counts.items())),'samples':samples,
            'terminal_original_copy_controls':controls,'original_game_bytes_executed':True,
            'original_entry':ENTRY,'original_end_exclusive':END,
            'natural_field_meanings_and_domains_recovered':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True);parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-nlsnd-ramp.v1','status':'failure','release':'usa-mk81070-v1003',
            'module':'NLSND','cpu':'m68000','load_address':0,'lifetime':'netlink-sound-driver',
            'source_path':'NETLINK/SNDDRV.BIN','driver_sha256':sound.SOURCES['NLSND'][1],
            'native_identity':native.identity(),'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'limitations':['Constructed byte/edge/status samples; natural parameter roles and domains remain unknown',
                           'No535E/51B2/command11/caller, native sound timing or production Godot acceptance',
                           'Pinned CPU interpreter and frozen SCSP; no complete game/code recovery claim']}
    fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:
        phase='identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');library=native.Library(args.prepared)
            report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:report['error']={'phase':phase,'type':type(error).__name__,'reason':str(error)}
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'error':report.get('error')}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
