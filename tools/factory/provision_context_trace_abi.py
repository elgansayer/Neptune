"""Separate master-context ABI. Original source identity belongs to the caller."""
import ctypes as C

CAPACITY, STEP_LIMIT, WITNESS_WORDS = 128, 4096, 339
ROOT, TABLE = 0x060BD020, 0x060BC190
WITNESS_RANGES = ((0x060061C4, 35), (0x06006B9C, 278), (0x06006E00, 26))


class Record(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ("sequence", "kind", "profile", "cpu", "frame", "pc")]
    _fields_ += [("timestamp", C.c_int32), ("dispatch_steps", C.c_uint32),
                 ("opcode", C.c_uint32), ("r", C.c_uint32 * 16)]
    _fields_ += [(name, C.c_uint32) for name in ("sr", "gbr", "vbr", "mach", "macl", "pr",
                                                "context_address", "stack_address")]
    _fields_ += [(name, C.c_uint32 * count) for name, count in
                 (("header", 14), ("root", 12), ("table", 396), ("context", 12), ("stack", 32))]


class Status(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ("abi", "record_bytes", "capacity", "count", "dropped", "errors", "active", "pending",
                 "completed", "requested", "profile", "frame_known", "frame", "step_limit", "steps",
                 "master_dispatches", "outside_inspected", "source_mismatch_candidates", "source_checks",
                 "last_error", "last_pc", "last_address", "fused_nops")]


def serialise(record):
    return {name: list(value) if isinstance(value, C.Array) else value
            for name, _ in record._fields_ for value in (getattr(record, name),)}


def context_at(record, address):
    if address == ROOT:
        return list(record.root)
    offset = address - TABLE - 32
    if offset < 0 or offset % 88 or offset // 88 >= 18:
        raise ValueError("Unknown context address")
    return list(record.table)[offset // 4 + 8:offset // 4 + 20]


def save_pair(before, after):
    expected = [before.r[8], *list(before.r)[8:16], before.pr, before.mach, before.macl]
    if (after.dispatch_steps - before.dispatch_steps != 17 or before.pc != 0x060061C4 or
            before.opcode != 0x1480 or after.pc != before.pr or after.pr != before.pr or
            after.context_address != before.context_address or list(after.context) != expected or
            list(after.r) != [0, *list(before.r)[1:]] or
            any(getattr(before, name) != getattr(after, name) for name in ("sr", "gbr", "vbr", "mach", "macl"))):
        raise ValueError("Original context save boundary/layout/register mismatch")


def restore_pair(before, after):
    context = list(before.context)
    registers = list(before.r)
    registers[0], registers[4] = before.r[5], context[0]
    registers[8:16] = context[1:9]
    if (after.dispatch_steps - before.dispatch_steps != 18 or before.pc != 0x060061E6 or
            before.opcode != 0x5841 or after.pc != context[9] or after.pr != context[9] or
            after.mach != context[10] or after.macl != context[11] or list(after.r) != registers or
            after.context_address != before.context_address or list(after.context) != context or
            any(getattr(before, name) != getattr(after, name) for name in ("sr", "gbr", "vbr"))):
        raise ValueError("Original context restore boundary/layout/register mismatch")


def validate(records, status):
    if (status.abi != 2 or status.record_bytes != C.sizeof(Record) or status.capacity != CAPACITY or
            status.step_limit != STEP_LIMIT or status.profile not in (1, 2, 3)):
        raise ValueError("Unsupported context observer ABI/layout/profile")
    width = 3 if status.profile == 2 else 5
    if (status.active or status.dropped or status.errors or status.pending or status.outside_inspected or
            not status.frame_known or not 1 <= status.completed == status.requested <= 16 or
            status.count != width * status.completed or len(records) != status.count or
            status.source_checks < status.count or status.master_dispatches < status.count):
        raise ValueError("Empty, incomplete, interrupted, failed or overflowed context trace")
    for i, record in enumerate(records):
        stack = min(max(record.r[15] - 64, 0x06000000), 0x060FFF80)
        if (record.sequence != i or record.profile != status.profile or record.cpu or
                record.frame > status.frame or not 1 <= record.dispatch_steps <= STEP_LIMIT or
                record.r[15] & 3 or not 0x06000000 <= record.r[15] <= 0x06100000 or
                record.stack_address != stack or list(record.context) != context_at(record, record.context_address)):
            raise ValueError("Record order/CPU/clock/address/snapshot mismatch")
        if i and (record.frame < records[i-1].frame or
                  record.frame == records[i-1].frame and record.timestamp < records[i-1].timestamp):
            raise ValueError("Nonmonotonic context observation clock")
    for index in range(0, len(records), width):
        cycle = records[index:index + width]
        entry, restore, transfer = cycle[0], cycle[-2], cycle[-1]
        kinds = [1, 4, 5] if status.profile == 2 else [1, 2, 3, 4, 5]
        entry_pc, entry_op = {1: (0x06006BE4, 0x2FE6), 2: (0x06006C00, 0xD084),
                              3: (0x06006D36, 0x0022)}[status.profile]
        if ([r.kind for r in cycle] != kinds or entry.pc != entry_pc or entry.opcode != entry_op or
                entry.dispatch_steps != 1 or any(a.dispatch_steps >= b.dispatch_steps for a, b in zip(cycle, cycle[1:]))):
            raise ValueError("Context entry/stage/dispatch order mismatch")
        if status.profile != 2:
            before, saved = cycle[1:3]
            save_pair(before, saved)
            if (before.context_address != entry.context_address or
                    before.pr != (0x06006C00 if status.profile == 1 else 0x06006D86) or
                    before.r[15] != entry.r[15] - (44 if status.profile == 1 else 16)):
                raise ValueError("Caller save context/stack/linkage mismatch")
            if status.profile == 1 and (entry.context_address != ROOT or list(saved.root) != list(restore.root)):
                raise ValueError("Fresh selection root context continuity mismatch")
            if status.profile == 3 and (entry.context_address != entry.header[2 + ((entry.vbr >> 10) & 1)] + 32 or
                                       list(entry.root) != list(restore.root) or
                                       list(saved.context) != context_at(restore, saved.context_address)):
                raise ValueError("Yield current-record/root context continuity mismatch")
        if (status.profile == 3 and restore.context_address != ROOT or
                status.profile != 3 and restore.context_address == ROOT):
            raise ValueError("Wrong selected/root restore role")
        restore_pair(restore, transfer)
    return {"schema": "neptune.original-master-context-trace.v1", "cpu": "master SH-2 interpreter",
            "profile": status.profile, "completed_cycles": status.completed,
            "dispatch_steps": "master observer hooks including actual fused NOP delays; not hardware cycles",
            "scope": "original save/restore and caller boundaries; no task-body or whole-game parity claim",
            "records": [serialise(record) for record in records], "status": serialise(status)}


class Trace:
    def __init__(self, dll):
        self.dll, self.started = dll, False
        signatures = {"begin": ([C.c_uint32, C.c_uint32, C.POINTER(C.c_uint16), C.c_uint32], C.c_uint32),
                      "frame": ([C.c_uint32], C.c_uint32), "stop": ([], None),
                      "status": ([C.POINTER(Status), C.c_uint32], C.c_uint32),
                      "records": ([C.POINTER(Record), C.c_uint32], C.c_uint32),
                      "witness": ([C.POINTER(C.c_uint16), C.c_uint32, C.c_uint32], C.c_uint32)}
        try:
            for name, (arguments, result) in signatures.items():
                function = getattr(dll, "neptune_context_" + name)
                function.argtypes, function.restype = arguments, result
        except AttributeError as error:
            raise ValueError("Core has no supported context observer") from error
        status = self.status()
        if status.abi != 2 or status.record_bytes != C.sizeof(Record) or status.capacity != CAPACITY:
            raise ValueError("Unsupported context observer layout")

    def status(self):
        status = Status()
        if self.dll.neptune_context_status(C.byref(status), C.sizeof(status)) != 1:
            raise ValueError("Core refused exact-sized context status")
        return status

    def start(self, profile, pairs, witness):
        if (self.started or type(profile) is not int or profile not in (1, 2, 3) or
                type(pairs) is not int or not 1 <= pairs <= 16 or len(witness) != WITNESS_WORDS or
                any(type(word) is not int or not 0 <= word <= 0xFFFF for word in witness)):
            raise ValueError("One context trace, profiles 1..3, cycles 1..16 and exact source witness required")
        expected = (C.c_uint16 * WITNESS_WORDS)(*witness)
        if self.dll.neptune_context_begin(profile, pairs, expected, WITNESS_WORDS) != 1:
            raise ValueError("Core rejected active/JIT/unsupported context trace")
        self.started = True

    def frame(self, frame):
        if not self.started or type(frame) is not int or not 0 <= frame <= 0xFFFFFFFF:
            raise ValueError("Missing start or invalid emulated frame")
        if self.dll.neptune_context_frame(frame) != 1:
            raise ValueError("Core rejected nonconsecutive context frame")

    def snapshot(self):
        status = self.status()
        records = (Record * CAPACITY)()
        count = self.dll.neptune_context_records(records, CAPACITY)
        if count > CAPACITY or count != status.count:
            raise ValueError("Core returned incomplete/oversized context data")
        return list(records)[:count], status

    def witness(self, mismatch=False):
        words = (C.c_uint16 * WITNESS_WORDS)()
        if self.dll.neptune_context_witness(words, WITNESS_WORDS, int(mismatch)) != WITNESS_WORDS:
            return None
        return list(words)

    def finish(self):
        if not self.started:
            raise ValueError("Context observer was never started")
        self.dll.neptune_context_stop()
        return validate(*self.snapshot())


def probe_library(path):
    """Native no-media ABI only, with an owned zero witness and no CPU dispatch."""
    observer = Trace(C.CDLL(str(path)))
    words = (C.c_uint16 * WITNESS_WORDS)()
    for profile, pairs, count in ((0, 1, 339), (4, 1, 339), (1, 0, 339), (1, 17, 339), (1, 1, 338)):
        if observer.dll.neptune_context_begin(profile, pairs, words, count) != 0:
            raise ValueError("Observer accepted invalid profile/cycle/witness budget")
    observer.start(1, 1, list(words))
    observer.frame(10)
    try:
        observer.frame(12)
    except ValueError:
        pass
    else:
        raise ValueError("Observer accepted a skipped frame")
    status = observer.status()
    if status.errors != 1 or status.active or status.count or status.pending:
        raise ValueError("Observer failed to retain bad frame evidence")
    try:
        observer.finish()
    except ValueError:
        pass
    else:
        raise ValueError("Observer accepted empty/failed execution as evidence")
    return {"scope": "observer ABI/profile/witness/frame fences only; no media execution",
            "abi": status.abi, "record_bytes": status.record_bytes,
            "capacity": status.capacity, "step_limit": status.step_limit,
            "rejected_invalid_profile_budget_witness_and_frame": True}


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Probe separate context ABI, no original media")
    parser.add_argument("--probe-core", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe_library(args.probe_core), sort_keys=True))
