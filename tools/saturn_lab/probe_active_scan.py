#!/usr/bin/env python3
"""Complete original130E scans with actual returning17F2 paths, no handler stubs."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_consumer_native as native
import probe_command_dispatch as dispatch
import probe_kernel as pinned
import probe_netlink_capture as capture
import probe_netlink_pointer as leaf
import probe_netlink_records as records

ENTRY, END = 0x130E,0x13B2
RETURNING=tuple(c for c in range(1,256) if dispatch.contract(c,0,0,0x2700,0x8000)[-1]=='complete-return')
MIXED=(0x1F,0x8D,0x20,0x8B,0x91,0x8E,0x14,0xFF)


def cases():
    rows=set()
    def add(mask,command,gate,ack,ring,writer,v):
        rows.add((mask,command if mask else 0x100,gate,ack,ring,writer,v))
    for command,mask,gate,v in itertools.product(RETURNING,(1,128),(0,0xA0),range(2)):
        add(mask,command,gate,0xFF if v==0 else 0x80,0x7FF if v==0 else 0xFFFF,255,v)
    for command,gate in itertools.product(RETURNING,(0,0xA0)):
        add(255,command,gate,0xFF,0x7FF,255,0)
    for mask,gate in itertools.product(range(256),(0,0xA0)):
        add(mask,0x100,gate,0xFF,0x7FF,255,0)
    for writer in range(256):add(255,0x100,0xA0,0x80,0xFFFF,writer,1)
    for ring in range(128):add(255,0x100,0x20,0x80,ring*16|0xF00F,255,1)
    for gate,mask,ack,v in itertools.product((0x20,0x40,0x60,0x80,0xA0,0xFF),(0,255),(0,0x80,0xFF),range(2)):
        add(mask,0x100,gate,ack,0x7FF,255,v)
    return sorted(rows)


def contract(mask,command,gate,ack,ring,writer,variant):
    if command!=0x100 and command not in RETURNING:raise ValueError('Unresolved active handler is not a returning fixture')
    base,sr,timestamp=capture.VARIANTS[variant]
    before=records.base_regs(ENTRY,sr);before[14]=base
    source=bytearray((i*37+19+variant*83)&255 for i in range(128))
    for i in range(8):source[16*i]=(MIXED[i] if command==0x100 else command) if mask>>i&1 else 0
    regions=[(0x4E0,bytes([ack,gate]),True),(0x700,bytes(source),True),
             (base+0x1834,bytes.fromhex('deadcafe')+timestamp.to_bytes(2,'big')+ring.to_bytes(2,'big'),True),
             (0x800,bytes((i*19+7)&255 for i in range(2048)),True),(0x41A,bytes.fromhex('c35a'),True),
             (base+0x1841,bytes([writer]),True),(base+0x1F00,bytes((i*13+5)&255 for i in range(256)),True),
             (leaf.SP-24,bytes([0xCD])*24+leaf.STOP.to_bytes(4,'big'),True)]
    buffers=[bytearray(data) for _,data,_ in regions]
    regs=list(before);events=[];pcs=[];processed=[]
    def memory(kind,address,size,value=None):
        for (lo,data,writable),buffer in zip(regions,buffers):
            if lo<=address and address+size<=lo+len(data):
                if kind==1:value=int.from_bytes(buffer[address-lo:address-lo+size],'big')
                else:
                    if not writable:raise ValueError('Oracle attempted readonly write')
                    value &= (1<<(size*8))-1
                    buffer[address-lo:address-lo+size]=value.to_bytes(size,'big')
                events.append([kind,address,size,value]);return value
        raise ValueError('Oracle left declared RAM')
    def read(address,size):return memory(1,address,size)
    def write(address,size,value):memory(2,address,size,value)
    def push(value):
        regs[15]-=4;write(regs[15],4,value)
    def pop():
        value=read(regs[15],4);regs[15]+=4;return value
    def save(registers):
        for reg in reversed(registers):
            regs[15]-=4;write(regs[15]+2,2,regs[reg]&0xFFFF);write(regs[15],2,regs[reg]>>16)
    def restore(registers):
        for reg in registers:regs[reg]=pop()
    def real_dispatch():
        c=regs[7]&255
        pcs.extend([0x17F2,0x17F6,0x17F8]);regs[7]=(regs[7]&0xFFFF0000)|c
        if c<0x80:
            pcs.extend([0x1854,0x1858])
            if c<0x20:
                pcs.extend([0x185A,0x185C,0x185E,0x1860,0x1864])
                regs[7]=(regs[7]&0xFFFF0000)|c*4;regs[12]=regs[14]
                save((13,14));push(0x1868)
                pcs.append(0x1872+4*c)
                if c:pcs.extend([0x186E,0x1870])
                if pop()!=0x1868:raise ValueError('Oracle low nested return differs')
                pcs.extend([0x1868,0x186C]);restore((13,14))
            else:pcs.extend([0x186E,0x1870])
        else:
            pcs.extend([0x17FA,0x17FE])
            if c<0x91:
                index=c&15
                pcs.extend([0x1800,0x1804,0x1806,0x1808,0x180E+4*index])
                regs[7]=(regs[7]&0xFFFF0000)|index*4;push(0x180C)
                if index==13:regs[0]|=0x6E;pcs.append(0x1846)
                pcs.extend([0x186E,0x1870])
                if pop()!=0x180C:raise ValueError('Oracle high nested return differs')
                pcs.extend([0x180C,0x186E,0x1870])
            else:pcs.extend([0x186E,0x1870])
        if pop()!=0x139E:raise ValueError('Oracle dispatcher return differs')
    pcs.extend([0x130E,0x1312]);read(0x4E1,1);regs[0]=(regs[0]&~255)|gate
    nested=False
    active_scan=not(gate&128) or bool(ack&128)
    if gate&128:
        pcs.extend([0x1314,0x1318]);read(0x4E0,1);regs[0]=(regs[0]&~255)|ack
        if ack&128:
            nested=True;pcs.append(0x131A);push(0x131E)
    if active_scan:
        pcs.append(0x1326);regs[0]=(regs[0]&0xFFFF0000)|0x700
        for i in range(8):
            address=0x700+16*i;regs[8]=address
            pcs.extend([0x132A,0x132C,0x132E])
            c=read(address,1);regs[7]=(regs[7]&~255)|c
            if c:
                processed.append(i);regs[8]+=2
                pcs.extend([0x1330,0x1332,0x1336]);write(base+0x1834,2,regs[0]&0xFFFF)
                save((0,9))
                pcs.extend([0x133A,0x133E,0x1342,0x1346,0x1348,0x134C,0x1350,0x1354])
                offset=read(base+0x183A,2)&0x7F0;regs[9]=0x800+offset
                for relative,width in ((0,2),(2,4),(6,4),(10,4)):
                    write(0x800+offset+relative,width,read(address+relative,width))
                pcs.extend([0x1358,0x135C,0x1360,0x1364,0x1368,0x136E,0x1372,0x1374,0x1376])
                write(base+0x183A,2,offset+16);write(0x41A,2,offset+16)
                write(0x800+offset+14,2,read(base+0x1838,2));write(base+0x1838,2,0)
                read(0x4E1,1)
                if gate&0x20:
                    pcs.extend([0x1378,0x137A,0x137E,0x1382,0x1386])
                    cursor=read(base+0x1841,1);regs[10]=base+0x1F00;regs[11]=address
                    for j in range(16):
                        pcs.extend([0x1388,0x138C,0x138E])
                        write(base+0x1F00+((cursor+j)&255),1,read(address+j,1))
                    regs[1]=0xFFFF;regs[11]=address+16
                    pcs.append(0x1392);write(base+0x1841,1,(cursor+16)&255)
                pcs.extend([0x1396,0x139A]);restore((0,9));push(0x139E)
                real_dispatch()
                pcs.extend([0x139E,0x13A2,0x13A4])
                regs[0]=(regs[0]&0xFFFF0000)|read(base+0x1834,2)
                regs[8]=regs[0]&0xFFFF;write(regs[8],2,0)
            pcs.extend([0x13A8,0x13AC]);regs[0]=(regs[0]&~255)|((regs[0]+16)&255)
        pcs.append(0x13B0)
        if pop()!=(0x131E if nested else leaf.STOP):raise ValueError('Oracle scan return differs')
        if nested:
            pcs.append(0x131E);write(0x4E0,1,read(0x4E0,1)&127)
            regs[17]=(sr&~31)|(4 if ack&127==0 else 0)
        else:regs[17]=(sr&~31)|0xA
    else:regs[17]=(sr&~31)|capture.logic_flags(ack,sr&16)
    if gate&128:
        pcs.append(0x1324)
        if pop()!=leaf.STOP:raise ValueError('Oracle outer return differs')
    regs[16]=leaf.STOP
    return before,regs,regions,[bytes(b) for b in buffers],events,pcs,processed


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,processed=contract(*case)
    actual=library.run(code,ENTRY,leaf.STOP,[(ENTRY,END),(dispatch.ENTRY,dispatch.END)],regions,before,budget=1024)
    records.check(actual,expected,after,events,pcs)
    return {'case':list(case),'processed_slots':processed,'completed_original_call':True,'after_registers':expected,
            'data_events':events,'pcs':pcs,'instructions':actual['steps'],'model_cycles':actual['model_cycles'],
            'log_cursor_after':int.from_bytes(after[2][6:8],'big'),'forward_cursor_after':after[5][0],
            'all_visible_registers_checked':True,'unaffected_mapped_bytes_equal':True}


def execute(code,library):
    selected=cases()
    if len(selected)!=3196:raise ValueError('Constructed selection changed')
    rows=[run_case(code,library,*case) for case in selected]
    controls_selected=list(itertools.product((1,128,255),(0x1F,0x8D),(0,0xA0),(0xFF,),(0x7FF,),(255,),(0,)))
    controls={}
    for name,offset,replacement in (
            ('missing_slot_word_clear',0x13A4,bytes.fromhex('4e71 4e71')),
            ('scan_stride_32',0x13AA,bytes.fromhex('0020')),
            ('missing_ack_clear',0x131E,bytes.fromhex('4e71 4e71 4e71')),
            ('missing_dispatch_call',0x139A,bytes.fromhex('4e71 4e71')),
            ('forward_fifteen_bytes',0x1386,bytes.fromhex('720e'))):
        altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in controls_selected:
            try:run_case(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original survived all selected cases')
        controls[name]={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                        'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,'returning_command_bytes':list(RETURNING),
            'ranges_sha256':{f'{lo:x}:{end:x}':pinned.digest(code[lo:end]) for lo,end in ((ENTRY,END),(dispatch.ENTRY,dispatch.END))},
            'max_processed_slots':max(len(r['processed_slots']) for r in rows)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-active-scan.v1','status':'failure','experiment':'EXP-SAT-CODE-015',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1],'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'accepted_prefix_sha256':pinned.digest(Path(capture.__file__).read_bytes()),
            'accepted_dispatch_sha256':pinned.digest(Path(dispatch.__file__).read_bytes()),
            'limitations':['Complete scans only for returning skip/no-op commands; no substitute handlers',
                           'Nontrivial handlers and illegal command contexts remain unresolved, not whole1326 recovery',
                           'Constructed inputs/stack; no natural boot/commands/SCSP/DSP/audio/hardware proof',
                           'Existing ABI2 bounds unchanged; whole-program/function/dynamic-target denominators unknown']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');phase='prepared_identity'
            library=native.Library(args.prepared);report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='owned_smoke';report['owned_smoke']=native.smoke(library)
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':'Identity, bounded execution or contract failed'}
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
