"""Strict ctypes boundary for the separate, bounded command observer."""
import ctypes as C

CAPACITY, STEP_LIMIT, FRAME_LIMIT = 128, 4194304, 120
WITNESS_RANGES = ((0x06095904,256),(0x060A4FAC,118),(0x060AE676,23),
                  (0x060AE908,23),(0x060AEA30,4))
WITNESS_WORDS = 424
ROOTS = {1:(0x060AE698,0x060A4FAC),2:(0x060AE92E,0x060A4FAC)}

class Record(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('sequence','kind','profile','frame','pc','opcode','pipe_op','steps','transfer_address','transfer_value')]
    _fields_ += [('timestamp',C.c_int32),('r',C.c_uint32*16)]
    _fields_ += [(n,C.c_uint32) for n in ('sr','gbr','vbr','mach','macl','pr','stack_address')]
    _fields_ += [('stack',C.c_uint32*12)]
    _fields_ += [(n,C.c_uint32) for n in ('command_address','response_address','command_valid','response_valid')]
    _fields_ += [('command',C.c_uint32*2),('response',C.c_uint32*2)]

class Status(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('abi','record_bytes','capacity','count','dropped','errors','active','pending','completed','profile','frame_known','frame','step_limit','steps','master_hooks','frame_limit','witness_words','source_checks','last_error','last_pc','last_address','root_rts','root_delay','transfer_count')]

def validate(records,status,witness):
    if (status.abi!=1 or status.record_bytes!=C.sizeof(Record) or status.capacity!=CAPACITY or
        status.step_limit!=STEP_LIMIT or status.frame_limit!=FRAME_LIMIT or status.witness_words!=WITNESS_WORDS or
        status.profile not in ROOTS or len(witness)!=WITNESS_WORDS): raise ValueError('Unsupported command observer ABI/layout/profile/witness')
    if status.active or status.pending or not status.completed or status.errors or status.dropped or not status.frame_known or not records or status.count!=len(records) or status.count>CAPACITY:
        raise ValueError('Empty, unfinished, interrupted, overflowed or failed command trace')
    if status.source_checks < status.count+1 or status.steps>STEP_LIMIT or status.master_hooks<status.steps:
        raise ValueError('Command trace source/hook/budget evidence incomplete')
    for i,row in enumerate(records):
        if row.sequence!=i or row.profile!=status.profile or row.frame>status.frame or row.pc&1 or row.opcode>0xFFFF or row.steps>STEP_LIMIT:
            raise ValueError('Command record order, profile, frame or PC is invalid')
        if i and (row.steps<records[i-1].steps or row.frame<records[i-1].frame): raise ValueError('Command trace clock regressed')
        if row.command_valid not in (0,1) or row.response_valid not in (0,1): raise ValueError('Command/response validity tag is malformed')
        if (not row.command_valid and any(row.command)) or (not row.response_valid and any(row.response)): raise ValueError('Unavailable command/response memory must not appear as observed zeros or data')
        if row.kind in (2,3) and row.transfer_address not in (0x25890008,0x2589000C,0x25890018,0x2589001C,0x25890020,0x25890024): raise ValueError('Unrecognized device transfer address')
    root,entry=ROOTS[status.profile]
    rts=[r for r in records if r.kind==5]; delays=[r for r in records if r.kind==6]
    source_calls=[r for r in records if r.kind==8]; source_delays=[r for r in records if r.kind==9]
    services=[r.pc for r in records if r.kind==4]
    transfers=sum(r.kind in (2,3) for r in records)
    if (len(records)<7 or records[0].kind!=8 or records[1].kind!=9 or records[2].kind!=1 or records[2].pc!=entry or records[-1].kind!=7 or records[-1].pc!=root or
        len(source_calls)!=1 or len(source_delays)!=1 or source_calls[0].pc!=(0x060AE694 if status.profile==1 else 0x060AE92A) or source_calls[0].opcode&0xF0FF!=0x400B or source_calls[0].r[(source_calls[0].opcode>>8)&15]!=entry or source_delays[0].pc!=source_calls[0].pc+2 or len(rts)!=1 or len(delays)!=1 or rts[0].pc!=0x060A4FBA or rts[0].opcode!=0x000B or
        delays[0].pc!=rts[0].pc+2 or delays[0].opcode!=0x0009 or not status.root_rts or
        not status.root_delay or not all(pc in services for pc in (0x06095992,0x060959CA,0x060959AE,0x06095A82,0x060959C8)) or not transfers or status.transfer_count!=transfers or
        records[-1].r[15]!=records[0].r[15] or records[-1].r[14]!=records[0].r[14] or records[-1].pr!=root):
        raise ValueError('Command root entry/RTS/delay/return continuity is incomplete')
    return {'schema':'neptune.original-command-trace.v1','profile':status.profile,
            'scope':'one natural command root with actual observed word transfers; device/game semantics require independent interpretation',
            'records':[{'sequence':r.sequence,'kind':r.kind,'frame':r.frame,'pc':r.pc,'opcode':r.opcode,'steps':r.steps,'address':r.transfer_address,'value':r.transfer_value,'command_address':r.command_address,'response_address':r.response_address,'command_valid':r.command_valid,'response_valid':r.response_valid,'command':list(r.command) if r.command_valid else None,'response':list(r.response) if r.response_valid else None,'r':list(r.r),'sr':r.sr,'pr':r.pr} for r in records],
            'status':{n:getattr(status,n) for n,_ in status._fields_}}

class Trace:
    def __init__(self,dll):
        self.dll=dll; self.started=False; self.expected=None
        signatures={'begin':([C.c_uint32,C.POINTER(C.c_uint16),C.c_uint32],C.c_uint32),
                    'frame':([C.c_uint32],C.c_uint32),'stop':([],None),
                    'status':([C.POINTER(Status),C.c_uint32],C.c_uint32),
                    'records':([C.POINTER(Record),C.c_uint32],C.c_uint32),
                    'witness':([C.POINTER(C.c_uint16),C.c_uint32,C.c_uint32],C.c_uint32)}
        try:
            for name,(args,result) in signatures.items():
                fn=getattr(dll,'neptune_command_'+name);fn.argtypes=args;fn.restype=result
        except AttributeError as e: raise ValueError('Core has no separate command observer') from e
        s=self.status()
        if s.abi!=1 or s.record_bytes!=C.sizeof(Record) or s.capacity!=CAPACITY: raise ValueError('Unsupported command observer layout')
    def status(self):
        out=Status()
        if self.dll.neptune_command_status(C.byref(out),C.sizeof(out))!=1: raise ValueError('Core rejected exact-sized command status')
        return out
    def start(self,profile,witness):
        if self.started or type(profile)is not int or profile not in ROOTS or len(witness)!=WITNESS_WORDS or any(type(x)is not int or not 0<=x<=65535 for x in witness): raise ValueError('Require fixed profile and exact 424-word source witness')
        words=(C.c_uint16*WITNESS_WORDS)(*witness)
        if self.dll.neptune_command_begin(profile,words,WITNESS_WORDS)!=1: raise ValueError('Core rejected active/JIT/unsupported command trace')
        self.started=True;self.expected=tuple(witness)
    def frame(self,frame):
        if not self.started or type(frame)is not int or not 0<=frame<=0xffffffff: raise ValueError('Missing start or invalid command frame')
        if self.dll.neptune_command_frame(frame)!=1: raise ValueError('Core rejected skipped/overflowing command frame')
    def snapshot(self):
        s=self.status(); rows=(Record*CAPACITY)(); n=self.dll.neptune_command_records(rows,CAPACITY)
        if n>CAPACITY or n!=s.count: raise ValueError('Incomplete/oversized command records')
        return list(rows)[:n],s
    def witness(self,mismatch=False):
        mode=2 if mismatch=='current' else int(bool(mismatch))
        rows=(C.c_uint16*WITNESS_WORDS)()
        if self.dll.neptune_command_witness(rows,WITNESS_WORDS,mode)!=WITNESS_WORDS:return None
        return list(rows)
    def finish(self):
        if not self.started: raise ValueError('Command observer never started')
        actual=self.witness('current')
        self.dll.neptune_command_stop()
        if actual!=list(self.expected): raise ValueError('Final command source witness differs from the original')
        rows,status=self.snapshot();return validate(rows,status,self.expected)

