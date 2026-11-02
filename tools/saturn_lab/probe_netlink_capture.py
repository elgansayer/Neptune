#!/usr/bin/env python3
"""Original130E handshake/empty returns and1326 capture prefix before139A."""
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

ENTRY, DISPATCH, END = 0x130E, 0x139A, 0x13B2
VARIANTS = ((0x8000,0x271F,0xA17E), (0x10000,0x2000,0x5E81))


def cases():
    selected=set()
    for gate,ack,v in itertools.product(range(256),(0,0x7F,0x80,0xFF),range(2)):
        selected.add((gate,ack,-1,0,0x7FF,255,v))
    for slot,cmd,gate,ack,v in itertools.product(range(8),(1,0x7F,0x80,0xFF),
                        (0,0x20,0x40,0x60,0x80,0xA0,0xFF),(0,0x80),range(2)):
        selected.add((gate,ack,slot,cmd,0 if v==0 else 0x7FF,0 if v==0 else 255,v))
    for cmd,slot,gate in itertools.product(range(1,256),(0,7),(0,0x20,0xA0)):
        selected.add((gate,0x80,slot,cmd,0,0,0))
    for index,noise,gate,writer in itertools.product(range(128),(0,0xF00F),(0,0x20),(0,255)):
        selected.add((gate,0x80,3,0x5A,index*16|noise,writer,0))
    for writer,gate,slot,v in itertools.product(range(256),(0x20,0xA0),(0,7),range(2)):
        selected.add((gate,0x80,slot,0x5A,0x7FF,writer,v))
    return sorted(selected)


def logic_flags(byte,x):
    return x | (8 if byte&128 else 0) | (4 if byte==0 else 0)


def doubled_flags(byte):
    result=(byte+byte)&255
    return logic_flags(result,16 if byte&128 else 0) | (1 if byte&128 else 0) | (2 if (byte^result)&128 else 0)


def contract(gate,ack,slot,command,ring,writer,variant):
    base,sr,timestamp=VARIANTS[variant]
    before=records.base_regs(ENTRY,sr);before[14]=base
    source=bytearray((i*37+19+variant*83)&255 for i in range(128))
    for i in range(8):source[16*i]=command if i==slot else 0
    state=bytes.fromhex('deadcafe')+timestamp.to_bytes(2,'big')+ring.to_bytes(2,'big')
    log=bytes((i*19+7)&255 for i in range(2048))
    forwarding=bytes((i*13+5)&255 for i in range(256))
    stack=bytes([0xCD])*12+leaf.STOP.to_bytes(4,'big')
    regions=[(0x4E0,bytes([ack,gate]),True),(0x700,bytes(source),False),
             (base+0x1834,state,True),(0x800,log,True),(0x41A,bytes.fromhex('c35a'),True),
             (base+0x1841,bytes([writer]),True),(base+0x1F00,forwarding,True),
             (leaf.SP-12,stack,True)]
    after=[r[1] for r in regions]
    expected=list(before)
    pcs=[0x130E,0x1312];events=[[1,0x4E1,1,gate]]
    flags=logic_flags(gate,sr&16)
    expected[0]=(before[0]&~255)|gate
    nested=False
    sp=leaf.SP
    if gate&128:
        pcs += [0x1314,0x1318]
        events += [[1,0x4E0,1,ack]]
        expected[0]=(before[0]&~255)|ack
        flags=logic_flags(ack,sr&16)
        if ack&128:
            nested=True;sp-=4
            pcs += [0x131A]
            events += [[2,sp,4,0x131E]]
            saved=bytearray(after[7]);saved[8:12]=(0x131E).to_bytes(4,'big');after[7]=bytes(saved)
    run_scan=not(gate&128) or bool(ack&128)
    stop=leaf.STOP
    if run_scan:
        pcs += [0x1326]
        limit=slot+1 if slot>=0 else 8
        for i in range(limit):
            pcs += [0x132A,0x132C,0x132E]
            events += [[1,0x700+16*i,1,source[16*i]]]
            if i!=slot:pcs += [0x13A8,0x13AC]
        expected[0]=(before[0]&0xFFFF0000)|(0x700+16*(slot if slot>=0 else 8))
        expected[7]=(before[7]&~255)|(command if slot>=0 else 0)
        expected[8]=0x700+16*(slot if slot>=0 else 7)
        if slot<0:
            flags=0xA  # final70+10=80: N,V; X,C,Z clear
            pcs += [0x13B0]
            events += [[1,sp,4,0x131E if nested else leaf.STOP]]
        else:
            stop=DISPATCH
            address=0x700+slot*16;offset=ring&0x7F0
            expected[8]=address+2
            pcs += [0x1330,0x1332,0x1336,0x133A,0x133E,0x1342,0x1346,0x1348,
                    0x134C,0x1350,0x1354,0x1358,0x135C,0x1360,0x1364,0x1368,0x136E,
                    0x1372,0x1374,0x1376]
            events += [[2,base+0x1834,2,address]]
            # Actual predecrement MOVEM saves A1 thenD0, each low word first.
            saved_d0=expected[0]
            for depth,value in ((4,before[9]),(8,saved_d0)):
                events += [[2,sp-depth+2,2,value&0xFFFF],[2,sp-depth,2,value>>16]]
            saved=bytearray(after[7]);start=sp-8-(leaf.SP-12)
            saved[start:start+8]=saved_d0.to_bytes(4,'big')+before[9].to_bytes(4,'big');after[7]=bytes(saved)
            events += [[1,base+0x183A,2,ring]]
            for source_offset,width in ((0,2),(2,4),(6,4),(10,4)):
                value=int.from_bytes(source[slot*16+source_offset:slot*16+source_offset+width],'big')
                events += [[1,address+source_offset,width,value],[2,0x800+offset+source_offset,width,value]]
            events += [[2,base+0x183A,2,offset+16],[2,0x41A,2,offset+16],
                       [1,base+0x1838,2,timestamp],[2,0x800+offset+14,2,timestamp],
                       [2,base+0x1838,2,0],[1,0x4E1,1,gate]]
            changed=bytearray(state);changed[:2]=address.to_bytes(2,'big');changed[4:6]=b'\0\0';changed[6:8]=(offset+16).to_bytes(2,'big');after[2]=bytes(changed)
            changed=bytearray(log);changed[offset:offset+16]=source[slot*16:slot*16+14]+timestamp.to_bytes(2,'big');after[3]=bytes(changed)
            after[4]=(offset+16).to_bytes(2,'big')
            flags=doubled_flags((gate*2)&255)
            if gate&0x20:
                pcs += [0x1378,0x137A,0x137E,0x1382,0x1386]
                events += [[1,base+0x1841,1,writer]]
                changed=bytearray(forwarding)
                for i in range(16):
                    value=source[slot*16+i];destination=base+0x1F00+((writer+i)&255)
                    events += [[1,address+i,1,value],[2,destination,1,value]]
                    changed[(writer+i)&255]=value
                    pcs += [0x1388,0x138C,0x138E]
                pcs += [0x1392]
                cursor=(writer+16)&255
                events += [[2,base+0x1841,1,cursor]]
                after[5]=bytes([cursor]);after[6]=bytes(changed)
                expected[1]=0xFFFF
                expected[10],expected[11]=base+0x1F00,address+16
                flags=logic_flags(cursor,16 if writer==240 else 0)
            pcs += [0x1396]
            events += [[1,sp-8,4,saved_d0],[1,sp-4,4,before[9]]]
            expected[15]=sp
    if stop==leaf.STOP:
        if nested and run_scan:
            pcs += [0x131E]
            events += [[1,0x4E0,1,ack],[2,0x4E0,1,ack&127]]
            after[0]=bytes([ack&127,gate])
            flags=logic_flags(ack&127,0)
        if gate&128:pcs += [0x1324]
        if gate&128:events += [[1,leaf.SP,4,leaf.STOP]]
        expected[15]=leaf.SP+4
    expected[16]=stop;expected[17]=(sr&~31)|flags
    outcome='capture-prefix' if slot>=0 and run_scan else 'empty-return' if run_scan else 'unready-return'
    return before,expected,regions,after,events,pcs,stop,outcome


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,stop,outcome=contract(*case)
    actual=library.run(code,ENTRY,stop,[(ENTRY,END)],regions,before,budget=128)
    records.check(actual,expected,after,events,pcs)
    return {'case':list(case),'outcome':outcome,'after_registers':expected,'pcs':pcs,'data_events':events,
            'instructions':actual['steps'],'model_cycles':actual['model_cycles'],
            'all_visible_registers_checked':True,'unaffected_mapped_bytes_equal':True}


def execute(code,library):
    rows=[run_case(code,library,*case) for case in cases()]
    controls_selected=list(itertools.product((0,0x20,0x80,0xA0),(0,0x80),(0,7),(1,),
                                             (0x7FF,),(255,),(0,1)))
    controls={}
    for name,offset,replacement in (
            ('handshake_bpl_to_beq',0x1312,bytes.fromhex('6712')),
            ('ring_mask_3F0',0x1340,bytes.fromhex('03f0')),
            ('ring_increment_eight',0x135A,bytes.fromhex('0008')),
            ('missing_timestamp_clear',0x1368,bytes.fromhex('4e71 4e71 4e71')),
            ('forward_fifteen_bytes',0x1386,bytes.fromhex('720e'))):
        altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in controls_selected:
            try:run_case(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original survived every selected case')
        controls[name]={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                        'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'outcomes':{name:sum(r['outcome']==name for r in rows) for name in sorted({r['outcome'] for r in rows})},
            'range_sha256':pinned.digest(code[ENTRY:END]),'variants':list(VARIANTS)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-capture.v1','status':'failure','experiment':'EXP-SAT-CODE-012',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1],'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'contract_adapter_sha256':pinned.digest(Path(records.__file__).read_bytes()),
            'limitations':['Complete empty/unready returns; active capture stops before JSR17F2 at139A',
                           'Constructed RAM/registers, no natural command, boot, audio or hardware validation',
                           'CPU-only fixed RAM; no SCSP/DSP/device timing, shared interpreter lineage',
                           'Whole-program/function/dynamic-target denominators unknown']}
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
