#!/usr/bin/env python3
"""Original96C60 status/error handling and9696C setter with real89C2 callback.

Closed callback contract: null or the unchanged original RTS/NOP at89C2.
Other callback targets, BIOS/device behavior and whole-library semantics remain open.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_task_init as task

pinned, records, guard = task.pinned, task.records, task.short
STATUS, SETTER, CALLBACK = 0x06096C60, 0x0609696C, 0x060089C2
CELL, STATUS_WORD, BLOCK = 0x060FA8BC, 0x060FC080, 0x060D0000
MASK = 0xFFFFFFFF
MAPPINGS = {(-16)&MASK: (-25)&MASK, (-14)&MASK: (-2)&MASK, (-13)&MASK: (-23)&MASK}
LITERALS = {0x06096CF0: STATUS_WORD, 0x06096CE8: CELL, 0x060969D0: CELL}
HALFWORDS = {0x06096CE4: 0xB8, 0x060969B4: 0xB8}
FAMILIES = ('status', 'setter')


def effective(status, argument):
    return MAPPINGS.get(status & MASK, argument & MASK)


class Model(records.Model):
    def read(self, address, size):
        source = LITERALS if size == 4 else HALFWORDS if size == 2 else {}
        if address in source:
            value = source[address]; self.events.append([1,address,size,value]); return value
        return super().read(address, size)

    def setter(self):
        r = self.reg
        self.step(SETTER); r['r6'] = self.read(0x060969D0,4)
        self.step(SETTER+2); r['r3'] = self.read(r['r6'],4)
        self.step(SETTER+4); r['r0'] = self.read(0x060969B4,2)
        self.step(SETTER+6); self.write(r['r3']+r['r0'],4,r['r4'])
        self.step(SETTER+8); r['r3'] = self.read(r['r6'],4)
        self.step(SETTER+10); r['r0'] += 4
        self.step(SETTER+12); self.write(r['r3']+r['r0'],4,r['r5'])
        self.step(SETTER+14)
        self.step(SETTER+16,True); r['r4'] = 0
        self.status()

    def status(self):
        r = self.reg
        for pc,name in ((STATUS,'r14'),(STATUS+2,'r13'),(STATUS+4,'pr')):
            self.step(pc); self.push(r[name])
        self.step(STATUS+6); r['r3'] = self.read(0x06096CF0,4)
        self.step(STATUS+8); r['r0'] = self.read(r['r3'],4)
        self.step(STATUS+10); self.t(r['r0'] == ((-16)&MASK))
        self.step(STATUS+12)
        self.step(STATUS+14,True); r['r14'] = r['r4']
        if r['sr']&1:
            self.step(0x06096C88); r['r14'] = (-25)&MASK
        else:
            self.step(0x06096C70); self.t(r['r0'] == ((-14)&MASK))
            self.step(0x06096C72)
            if r['sr']&1:
                self.step(0x06096C84)
                self.step(0x06096C86,True); r['r14'] = (-2)&MASK
            else:
                self.step(0x06096C74); self.t(r['r0'] == ((-13)&MASK))
                self.step(0x06096C76)
                if r['sr']&1:
                    self.step(0x06096C80)
                    self.step(0x06096C82,True); r['r14'] = (-23)&MASK
                else:
                    self.step(0x06096C78); self.t(r['r0'] == 0)
                    self.step(0x06096C7A)
                    if not r['sr']&1:
                        self.step(0x06096C7C); self.step(0x06096C7E,True)
        self.step(0x06096C8A); self.t(r['r14'] == 0)
        self.step(0x06096C8C); r['r3'] = self.read(0x06096CE8,4)
        self.step(0x06096C8E); r['r13'] = self.read(r['r3'],4)
        self.step(0x06096C90); r['r2'] = self.read(0x06096CE4,2)
        self.step(0x06096C92); r['r13'] += r['r2']
        self.step(0x06096C94)
        self.step(0x06096C96,True); self.write(r['r13']+8,4,r['r14'])
        if not r['sr']&1:
            self.step(0x06096C98); r['r1'] = self.read(r['r13'],4)
            self.step(0x06096C9A); self.t(r['r1'] == 0)
            self.step(0x06096C9C)
            if not r['sr']&1:
                if r['r1'] != CALLBACK: raise ValueError('Outside closed original89C2 callback contract')
                self.step(0x06096C9E); r['r5'] = r['r14']
                self.step(0x06096CA0); r['r3'] = self.read(r['r13'],4)
                self.step(0x06096CA2); r['pr'] = 0x06096CA6
                self.step(0x06096CA4,True); r['r4'] = self.read(r['r13']+4,4)
                self.step(CALLBACK); self.step(CALLBACK+2,True)
        self.step(0x06096CA6); r['r0'] = r['r14']
        self.step(0x06096CA8); r['pr'] = self.pop()
        self.step(0x06096CAA); r['r13'] = self.pop()
        self.step(0x06096CAC)
        self.step(0x06096CAE,True); r['r14'] = self.pop()
        r['pc'] = r['pr']


def cases(family):
    if family not in FAMILIES: raise ValueError('Unknown status/setter family')
    statuses = tuple(i&MASK for i in range(-128,128))+(256,0xFFFFFF00,0x80000000,0x7FFFFFFF)
    if family == 'status':
        rows = [(family,v,s,status,cb,arg,0x12345678^s) for v,s,status,cb,arg in
                itertools.product(range(2),(0,255),statuses,(0,CALLBACK),(0,(-5)&MASK))]
        rows += [(family,v,37,status,cb,arg,0xFEDCBA98) for v,status,cb,arg in itertools.product(
            range(2),(0,1,MASK,(-16)&MASK), (0,CALLBACK),(1,0x80000000,0x7FFFFFFF,0xFFFF0000,0xA5A5A5A5,0x12345678))]
        return rows
    return [(family,v,s,status,cb,0,user) for v,s,status,cb,user in itertools.product(
        range(2),(0,255),(0,1,MASK,(-16)&MASK,(-14)&MASK,(-13)&MASK,0x80000000,0x7FFFFFFF),
        (0,CALLBACK),(0,1,MASK,0x12345678))]


def contract(data, case):
    family,variant,seed,status,callback,argument,userdata = case
    if family not in FAMILIES or callback not in (0,CALLBACK): raise ValueError('Outside closed callback contract')
    if any(type(n) is not int or not 0 <= n <= MASK for n in (status,argument,userdata)):
        raise ValueError('Require unsigned32-bit status/argument/userdata')
    entry = STATUS if family == 'status' else SETTER
    before = records.initial(entry,argument if family == 'status' else callback,variant)
    before['r15'] -= 0x100+variant*0x1000; before['r5'] = userdata
    block,sp = BLOCK+variant*0x2000,before['r15']
    canary = lambda n: bytes((seed+37*i)&255 for i in range(n))
    word = lambda n: n.to_bytes(4,'big')
    regions = [(STATUS_WORD-16,canary(16),False),(STATUS_WORD,word(status),False),(STATUS_WORD+4,canary(16),False),
               (CELL-16,canary(16),False),(CELL,word(block),False),(CELL+4,canary(16),False),
               (block+0xA8,canary(16),False),(block+0xB8,word(callback if family=='status' else 0xDEADBEEF),family=='setter'),
               (block+0xBC,word(userdata if family=='status' else 0xCAFEBABE),family=='setter'),
               (block+0xC0,word(0x55AA55AA),True),(block+0xC4,canary(16),False),
               (sp-64,canary(52),False),(sp-12,canary(12),True),(sp,canary(64),False)]
    for address,value in HALFWORDS.items():
        raw = data[address-pinned.BASE:address-pinned.BASE+2]
        if raw != value.to_bytes(2,'big'): raise ValueError('Original offset literal differs')
        regions.append((address,raw,False))
    model = Model(before,[(lo,buf) for lo,buf,_ in regions]); getattr(model,family)()
    expected = [buf for _,buf,_ in regions]
    result = effective(status,argument if family=='status' else 0)
    expected[9] = word(result)
    if family=='setter': expected[7:9] = [word(callback),word(userdata)]
    expected[12] = b''.join(word(before[name]) for name in ('pr','r13','r14'))
    if [bytes(buf) for buf in model.buffers] != expected or model.reg['r0'] != result:
        raise ValueError('Independent scalar status/setter contract differs')
    return entry,model,regions


def observe(data, emu, family, before, regions):
    ranges = ((STATUS,0x06096CB0),(CALLBACK,CALLBACK+4))
    if family=='setter': ranges += ((SETTER,SETTER+18),)
    return guard.observe(data,emu,before['pc'],regions,before,ranges=ranges,
                         literals=tuple(LITERALS),aliases=(),terminals={before['pr']:'returned'},budget=128)


def run_case(data, emu, case):
    entry,model,regions = contract(data,case)
    actual = observe(data,emu,case[0],model.before,regions)
    reason = None
    if actual['status'] != 'returned': reason = 'Original status/setter did not return: '+str(actual['error'])
    elif actual['registers'] != model.reg: reason = 'Status/setter register/PC/SR/PR/MAC differs'
    elif actual['trace'] != model.trace or actual['steps'] != len(model.trace): reason = 'Status/setter PC/delay trace differs'
    elif actual['events'] != model.events: reason = 'Status/setter data transactions differ'
    elif actual['regions_after'] != [bytes(buf) for buf in model.buffers] or not actual['original_unaffected_bytes_equal']:
        reason = 'Status/setter output/canaries/other original bytes differ'
    if reason: raise task.CaseFailure(reason,case,actual)
    return {'case':list(case),'entry':entry,'status':'returned','instructions':actual['steps'],
            'after_registers':actual['registers'],'trace':actual['trace'],'data_events':actual['events'],
            'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']], 'all_visible_state_checked':True}


def execute(data, emu, family):
    selected = cases(family); rows = [run_case(data,emu,case) for case in selected]
    mutations = [('mapping-25',0x06096C88,0xEEE8),('mapping-2',0x06096C86,0xEEFF),
                 ('mapping-23',0x06096C82,0xEEEA),('lost-input-delay',0x06096C6E,9),
                 ('lost-error-store-delay',0x06096C96,9),('lost-callback-userdata-delay',0x06096CA4,9),
                 ('lost-root-R14-restore',0x06096CAE,9),('changed-original-callback-delay',CALLBACK+2,0xE400)]
    if family=='setter':
        mutations += [('lost-callback-store',SETTER+6,9),('lost-userdata-store',SETTER+12,9),
                      ('changed-tail-zero-delay',SETTER+16,0xE401)]
    chosen = selected[::max(1,len(selected)//32)]+[case for case in selected if case[3] in MAPPINGS][:64]
    controls = {}
    for name,pc,word in mutations:
        changed = bytearray(data); changed[pc-pinned.BASE:pc-pinned.BASE+2] = word.to_bytes(2,'big')
        count,first = 0,None
        for case in chosen:
            try: run_case(changed,emu,case)
            except task.CaseFailure as error:
                fault = error.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']: continue
                count += 1
                if first is None: first = error.evidence
        if not count: raise ValueError('No non-budget semantic rejection: '+name)
        controls[name] = {'pc':pc,'tested':len(chosen),'nonbudget_rejections':count,'first_rejection':first,
                          'mutated_kernel_sha256':pinned.digest(changed)}
    return {'cases':len(rows),'complete_returns':len(rows),'results':rows,
            'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True); parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,required=True); parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args(argv)
    report = {'schema':'neptune.original-library-status-contracts.v1','status':'failure','selection':args.family,
              'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,
              'lifetime':'resident-kernel','kernel_sha256':pinned.KERNEL_SHA256,
              'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,
              'original_game_bytes_executed':False,'programme_status':'active; incomplete',
              'source_sha256':{p.name:pinned.digest(p.read_bytes()) for p in map(Path,(__file__,
                    records.__file__,task.__file__,pinned.__file__,guard.__file__))},
              'limitations':['Constructed high-RAM block/stack; only null or unchanged original89C2 callback',
                    'Other callback targets/device behavior and complete95B04/89C8 semantics unresolved',
                    'No stubs/MMIO/injected ticks; original128 guard unchanged; gameplay/hardware parity unknown']}
    try: fd = os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError: print('FAIL: require fresh report path'); return 1
    with os.fdopen(fd,'w') as output:
        try:
            data = pinned.kernel_bytes(args.kernel); emu = pinned.interpreter(args.saturn_recomp)
            report['original_game_bytes_executed'] = None
            report.update(execute(data,emu,args.family),status='success')
            if pinned.digest(args.kernel.read_bytes()) != pinned.digest(data): raise ValueError('Original file changed')
            report['original_file_unchanged'] = True
        except Exception as error:
            report['status'] = 'failure'; report['error'] = {'type':type(error).__name__,'reason':str(error)}
            if isinstance(error,task.CaseFailure):
                report['failure_evidence'] = error.evidence; report['original_game_bytes_executed'] = True
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'family':args.family,'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__': raise SystemExit(main())
