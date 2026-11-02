"""Fixed first-task/library native observation ABI; source witnesses stay private."""
import ctypes as C

CAPACITY, DEPTH, STEP_LIMIT, FRAME_LIMIT = 128, 16, 4194304, 120
WITNESS_RANGES = ((0x0600623A, 3), (0x060089AC, 95), (0x06008BF0, 32),
                  (0x06095B04, 2296), (0x060A6790, 146))
WITNESS_WORDS = sum(count for _, count in WITNESS_RANGES)
CALL_SITES = (0x060089F8, 0x06008A14, 0x06008A1E, 0x06008A34, 0x06008A4A,
              0x06095B5A, 0x06095B66, 0x06095B76, 0x06095B9A, 0x06095BB4)
TAIL_SITES = (0x06095B96, 0x06095BAE)
ROOTS = {1: (0x060089C8, 0x06006240), 2: (0x06095B04, 0x06008A18)}
ROOT_RTS = {1: (0x06008A2C, 0x06008A44, 0x06008A5C, 0x06008A66),
            2: (0x06095BCA, 0x06096CAC)}


class Record(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ('sequence', 'kind', 'profile', 'frame', 'pc', 'opcode', 'pipe_op', 'edge',
                 'call_pc', 'target', 'return_pc', 'depth')]
    _fields_ += [('timestamp', C.c_int32), ('steps', C.c_uint32), ('r', C.c_uint32*16)]
    _fields_ += [(name, C.c_uint32) for name in
                 ('sr', 'gbr', 'vbr', 'mach', 'macl', 'pr', 'stack_address', 'library_address', 'library_valid')]
    _fields_ += [('globals', C.c_uint32*28), ('descriptor', C.c_uint32*3), ('result_handle', C.c_uint32),
                 ('vectors', C.c_uint32*3), ('error_word', C.c_uint32), ('status_word', C.c_uint32),
                 ('library', C.c_uint32*64), ('tables', C.c_uint32*10), ('slots', C.c_uint32*24), ('stack', C.c_uint32*32)]


class Status(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ('abi', 'record_bytes', 'capacity', 'count', 'dropped', 'errors', 'active', 'pending',
                 'completed', 'requested', 'profile', 'frame_known', 'frame', 'step_limit', 'steps',
                 'master_dispatches', 'source_mismatch_candidates', 'source_checks', 'last_error',
                 'last_pc', 'last_address', 'fused_nops', 'depth', 'frame_limit', 'depth_limit',
                 'witness_words', 'exceptional_dispatches')]


def serialise(record):
    value = {name: list(field) if isinstance(field, C.Array) else field
             for name, _ in record._fields_ for field in (getattr(record, name),)}
    if isinstance(record, Record) and not record.library_valid:
        for name in ('library', 'tables', 'slots'): value[name] = None
    return value


def source_word(witness, address):
    index = 0
    for start, count in WITNESS_RANGES:
        if start <= address < start+2*count and not (address-start) & 1:
            return witness[index+(address-start)//2]
        index += count
    return None


def target(record):
    code, pc = record.opcode, record.pc
    if code >> 12 == 0xB:
        disp = code & 0xFFF
        if disp & 0x800: disp -= 0x1000
        return (pc+4+disp*2) & 0xFFFFFFFF
    if code & 0xF0FF in (0x400B, 0x402B):
        return record.r[(code >> 8) & 15]
    raise ValueError('Unsupported named call/tail opcode')


def validate(records, status, witness):
    if (status.abi != 1 or status.record_bytes != C.sizeof(Record) or status.capacity != CAPACITY or
            status.step_limit != STEP_LIMIT or status.frame_limit != FRAME_LIMIT or status.depth_limit != DEPTH or
            status.witness_words != WITNESS_WORDS or status.profile not in ROOTS or len(witness) != WITNESS_WORDS):
        raise ValueError('Unsupported initialization observer ABI/layout/profile/witness')
    if (status.active or status.pending or status.errors or status.dropped or status.depth or
            not status.frame_known or status.completed != 1 or status.requested != 1 or
            not 4 <= status.count == len(records) <= CAPACITY or status.source_checks < status.count+1 or
            not 1 <= status.steps <= STEP_LIMIT or status.master_dispatches < status.steps):
        raise ValueError('Empty, interrupted, partial, overflowed or failed initialization trace')
    root, returned = ROOTS[status.profile]
    first, last = records[0], records[-1]
    if (first.kind != 1 or first.pc != root or first.opcode != 0x2FE6 or first.pr != returned or
            first.steps != 1 or first.depth or last.kind != 10 or last.pc != returned or last.pr != returned or
            last.r[15] != first.r[15] or last.r[14] != first.r[14] or last.steps != status.steps or
            last.frame-first.frame >= FRAME_LIMIT):
        raise ValueError('Original initialization root entry/return/stack linkage differs')
    calls, branch, edges, root_rts, root_delay = [], None, 0, None, None
    for index, row in enumerate(records):
        sp = row.r[15]; stack = min(max(sp-64, 0x06000000), 0x060FFF80)
        valid = not row.library_address & 3 and 0x06000000 <= row.library_address <= 0x06100000-0x1B7C
        delay = row.kind in (3, 9)
        if (row.sequence != index or row.profile != status.profile or not 1 <= row.kind <= 10 or
                not 1 <= row.steps <= STEP_LIMIT or row.frame > status.frame or row.pc & 1 or
                row.opcode > 0xFFFF or row.pipe_op == 0xFF or bool(row.pipe_op & 0x80) != delay or
                sp & 3 or not 0x06000000 <= sp <= 0x06100000 or row.stack_address != stack or
                row.library_valid != int(valid)):
            raise ValueError('Initialization record order/pipeline/snapshot address differs')
        if not valid and any(any(getattr(row, name)) for name in ('library', 'tables', 'slots')):
            raise ValueError('Unavailable library memory must not be represented as observed values')
        if index and (row.frame < records[index-1].frame or row.steps < records[index-1].steps or
                      row.frame == records[index-1].frame and row.timestamp < records[index-1].timestamp):
            raise ValueError('Nonmonotonic initialization observation clock')
        expected_word = source_word(witness, row.pc)
        if expected_word is not None and expected_word != row.opcode:
            raise ValueError('Executed named opcode differs from the private source witness')
        if row.kind == 1:
            if index: raise ValueError('Repeated initialization root entry')
        elif row.kind in (2, 6):
            tail = row.kind == 6
            if branch or root_rts or row.pc not in (TAIL_SITES if tail else CALL_SITES):
                raise ValueError('Unexpected/reordered named initialization call')
            edges += 1
            if (row.edge != edges or row.call_pc != row.pc or row.target != target(row) or row.target & 1 or
                    row.return_pc != (row.pr if tail else row.pc+4) or
                    row.depth != len(calls)+(not tail) or row.depth > DEPTH):
                raise ValueError('Named call target/link/depth differs')
            if tail and row.opcode & 0xF0FF != 0x402B:
                raise ValueError('Tail must be an actual JMP instruction')
            if not tail:
                if not (row.opcode >> 12 == 0xB or row.opcode & 0xF0FF == 0x400B):
                    raise ValueError('Call must be an actual BSR/JSR instruction')
                calls.append([row, False])
            branch = [row, False]
        elif row.kind == 3:
            if not branch or branch[1]: raise ValueError('Missing/duplicate call delay')
            caller = branch[0]
            if (row.edge != caller.edge or row.call_pc != caller.pc or row.pc != caller.pc+2 or
                    row.target != caller.target or row.return_pc != caller.return_pc or
                    row.depth != caller.depth or row.steps <= caller.steps or row.pr != caller.return_pc):
                raise ValueError('Actual call delay/link differs')
            branch[1] = True
        elif row.kind in (4, 7):
            if not branch or not branch[1]: raise ValueError('Callee entry lacks actual source call/delay')
            caller = branch[0]; tail = caller.kind == 6
            if (row.kind != (7 if tail else 4) or row.edge != caller.edge or row.pc != caller.target or
                    row.call_pc != caller.pc or row.target != caller.target or row.return_pc != caller.return_pc or
                    row.depth != caller.depth or row.pr != caller.return_pc or
                    row.r[15] != caller.r[15]+(4 if tail else 0)):
                raise ValueError('Actual callee entry/target/SP/PR differs')
            if not tail: calls[-1][1] = True
            branch = None
        elif row.kind == 5:
            if not calls or branch or not calls[-1][1]: raise ValueError('Call return lacks actual entry')
            caller = calls.pop()[0]
            if (row.edge != caller.edge or row.call_pc != caller.pc or row.pc != caller.return_pc or
                    row.target != caller.target or row.return_pc != caller.return_pc or row.depth != caller.depth or
                    row.r[15] != caller.r[15] or row.pr != caller.return_pc):
                raise ValueError('Actual named call return/stack/link differs')
        elif row.kind == 8:
            if (calls or branch or root_rts or row.depth or row.pc not in ROOT_RTS[status.profile] or
                    row.opcode != 0x000B or row.pr != returned or row.r[15] != first.r[15]-4):
                raise ValueError('Root RTS boundary is missing or inconsistent')
            root_rts = row
        elif row.kind == 9:
            if (root_rts is None or root_delay or row.pc != root_rts.pc+2 or row.opcode != 0x6EF6 or
                    row.pr != returned or row.r[15] != first.r[15]-4 or row.depth):
                raise ValueError('Root return lacks its actual restore delay')
            root_delay = row
            saved_r14 = row.stack[(row.r[15]-row.stack_address)//4]
            if saved_r14 != first.r[14]: raise ValueError('Root restore delay stack word differs')
        elif row.kind == 10:
            if index != len(records)-1 or calls or branch or root_rts is None or root_delay is None or row.depth:
                raise ValueError('Root return lacks complete calls/RTS/delay continuity')
    return {'schema': 'neptune.original-first-task-init-trace.v1', 'profile': status.profile,
            'cpu': 'master SH-2 interpreter', 'completed_roots': 1,
            'dispatch_steps': 'master observer hooks including fused NOP delays; not hardware cycles/instruction counts',
            'scope': 'named direct call and complete root boundaries; internal device/callback semantics remain unresolved',
            'records': [serialise(row) for row in records], 'status': serialise(status)}


class Trace:
    def __init__(self, dll):
        self.dll, self.started, self.expected = dll, False, None
        functions = {'begin': ([C.c_uint32, C.c_uint32, C.POINTER(C.c_uint16), C.c_uint32], C.c_uint32),
                     'frame': ([C.c_uint32], C.c_uint32), 'stop': ([], None),
                     'status': ([C.POINTER(Status), C.c_uint32], C.c_uint32),
                     'records': ([C.POINTER(Record), C.c_uint32], C.c_uint32),
                     'witness': ([C.POINTER(C.c_uint16), C.c_uint32, C.c_uint32], C.c_uint32)}
        try:
            for name, (arguments, result) in functions.items():
                function = getattr(dll, 'neptune_init_'+name)
                function.argtypes, function.restype = arguments, result
        except AttributeError as error:
            raise ValueError('Core has no separate initialization observer') from error
        status = self.status()
        if status.abi != 1 or status.record_bytes != C.sizeof(Record) or status.capacity != CAPACITY:
            raise ValueError('Unsupported initialization observer layout')

    def status(self):
        value = Status()
        if self.dll.neptune_init_status(C.byref(value), C.sizeof(value)) != 1:
            raise ValueError('Core rejected exact-sized initialization status')
        return value

    def start(self, profile, roots, witness):
        if (self.started or type(profile) is not int or profile not in ROOTS or type(roots) is not int or roots != 1 or
                len(witness) != WITNESS_WORDS or any(type(word) is not int or not 0 <= word <= 0xFFFF for word in witness)):
            raise ValueError('Require one fixed initialization profile/root and exact private source witness')
        words = (C.c_uint16*WITNESS_WORDS)(*witness)
        if self.dll.neptune_init_begin(profile, roots, words, WITNESS_WORDS) != 1:
            raise ValueError('Core rejected active/JIT/unsupported initialization trace')
        self.expected = tuple(witness); self.started = True

    def frame(self, frame):
        if not self.started or type(frame) is not int or not 0 <= frame <= 0xFFFFFFFF:
            raise ValueError('Missing start or invalid initialization frame')
        if self.dll.neptune_init_frame(frame) != 1:
            raise ValueError('Core rejected skipped/overflowing/over-budget initialization frame')

    def snapshot(self):
        status = self.status(); records = (Record*CAPACITY)()
        count = self.dll.neptune_init_records(records, CAPACITY)
        if count > CAPACITY or count != status.count: raise ValueError('Incomplete/oversized initialization records')
        return list(records)[:count], status

    def witness(self, mismatch=False):
        words = (C.c_uint16*WITNESS_WORDS)()
        if self.dll.neptune_init_witness(words, WITNESS_WORDS, int(mismatch)) != WITNESS_WORDS: return None
        return list(words)

    def finish(self):
        if not self.started: raise ValueError('Initialization observer never started')
        self.dll.neptune_init_stop()
        return validate(*self.snapshot(), self.expected)


def probe_library(path):
    observer = Trace(C.CDLL(str(path))); zeros = (C.c_uint16*WITNESS_WORDS)()
    for profile, roots, count in ((0, 1, WITNESS_WORDS), (3, 1, WITNESS_WORDS),
                                  (1, 0, WITNESS_WORDS), (1, 2, WITNESS_WORDS), (1, 1, WITNESS_WORDS-1)):
        if observer.dll.neptune_init_begin(profile, roots, zeros, count) != 0:
            raise ValueError('Initialization observer accepted invalid profile/root/witness bounds')
    observer.start(1, 1, list(zeros)); observer.frame(10)
    try: observer.frame(12)
    except ValueError: pass
    else: raise ValueError('Initialization observer accepted a frame gap')
    status = observer.status()
    if status.errors != 1 or status.active or status.pending or status.count:
        raise ValueError('Initialization observer lost bad-frame evidence')
    try: observer.finish()
    except ValueError: pass
    else: raise ValueError('Initialization observer accepted empty execution')
    return {'scope': 'initialization ABI/profile/witness/frame fences only; no media execution',
            'abi': status.abi, 'record_bytes': status.record_bytes, 'capacity': status.capacity,
            'step_limit': status.step_limit, 'frame_limit': status.frame_limit,
            'rejected_invalid_profile_budget_witness_and_frame': True}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Probe separate initialization observer ABI without media')
    parser.add_argument('--probe-core', required=True)
    args = parser.parse_args()
    print(json.dumps(probe_library(args.probe_core), sort_keys=True))
