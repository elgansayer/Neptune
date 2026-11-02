"""Versioned bounded master-call observations, never a substitute for core identity."""
import ctypes as C

ENTRY = 0x0600B934
CAPACITY = 128
STEP_LIMIT = 4096


class Record(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ("sequence", "kind", "cpu", "frame", "pc")]
    _fields_ += [("timestamp", C.c_int32), ("dispatch_steps", C.c_uint32),
                 ("opcode", C.c_uint32), ("r", C.c_uint32 * 16)]
    _fields_ += [(name, C.c_uint32) for name in ("sr", "gbr", "vbr", "mach", "macl", "pr")]


class Status(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ("abi", "record_bytes", "capacity", "count", "dropped", "errors",
                 "pending", "completed", "active", "frame_known", "frame", "step_limit")]


def serialise(record):
    return {name: list(value) if name == "r" else value
            for name, _ in record._fields_ for value in (getattr(record, name),)}


def validate(records, status):
    if (status.abi != 1 or status.record_bytes != C.sizeof(Record) or
            status.capacity != CAPACITY or status.step_limit != STEP_LIMIT):
        raise ValueError("Unsupported trace ABI/layout")
    if (status.active or status.dropped or status.errors or status.pending or
            not status.frame_known or not 1 <= status.completed <= CAPACITY // 2 or
            status.count != 2 * status.completed or len(records) != status.count):
        raise ValueError("Empty, incomplete, ambiguous or overflowed call trace")
    for index in range(0, len(records), 2):
        before, after = records[index:index + 2]
        if (before.sequence != index or after.sequence != index + 1 or
                before.kind != 1 or after.kind != 2 or before.cpu or after.cpu or
                before.pc != ENTRY or before.opcode != 0x4F12 or
                after.pc != before.pr or after.pr != before.pr or
                after.frame < before.frame or after.frame > status.frame or
                (after.frame == before.frame and after.timestamp < before.timestamp) or
                before.dispatch_steps != 1 or not 14 <= after.dispatch_steps <= STEP_LIMIT):
            raise ValueError("Call/return boundary, order, CPU or clock mismatch")
        n, m = before.r[4], before.r[5]
        expected = ((10 * n + m) * 152 + 0x00207F74) & 0xFFFFFFFF
        if after.r[0] != expected or after.r[2] != 152 or after.r[3] != n or after.r[6] != 0x00207F74:
            raise ValueError("Natural call result/scratch-register mismatch")
        expected_sr = (before.sr & ~1) | (((5 * n) & 0xFFFFFFFF) >> 31)
        if (any(before.r[i] != after.r[i] for i in range(16) if i not in (0, 2, 3, 6)) or
                any(getattr(before, name) != getattr(after, name) for name in ("gbr", "vbr", "mach", "macl")) or
                after.sr != expected_sr):
            raise ValueError("Natural call SP/MACL/register/condition preservation mismatch")
    return {"schema": "neptune.original-master-call-trace.v1", "entry": f"0x{ENTRY:08x}",
            "cpu": "master SH-2 interpreter", "pairs": status.completed,
            "timestamp_unit": "signed core SH-2 scheduler timestamps, rebased each emulated frame",
            "dispatch_steps": "master hook dispatches, not hardware cycles; may include interruption",
            "records": [serialise(record) for record in records],
            "status": {name: getattr(status, name) for name, _ in status._fields_}}


class Trace:
    def __init__(self, dll):
        self.dll = dll
        self.started = False
        try:
            signatures = {
                "neptune_call_begin": ([C.c_uint32, C.c_uint32], C.c_uint32),
                "neptune_call_frame": ([C.c_uint32], C.c_uint32),
                "neptune_call_stop": ([], None),
                "neptune_call_status": ([C.POINTER(Status), C.c_uint32], C.c_uint32),
                "neptune_call_records": ([C.POINTER(Record), C.c_uint32], C.c_uint32),
            }
            for name, (arguments, result) in signatures.items():
                function = getattr(dll, name)
                function.argtypes, function.restype = arguments, result
        except AttributeError as error:
            raise ValueError("Core has no supported bounded-call observer") from error
        status = self.status()
        if status.abi != 1 or status.record_bytes != C.sizeof(Record) or status.capacity != CAPACITY:
            raise ValueError("Unsupported bounded-call observer ABI")

    def status(self):
        status = Status()
        if self.dll.neptune_call_status(C.byref(status), C.sizeof(status)) != 1:
            raise ValueError("Core refused exact-sized status observation")
        return status

    def start(self, pairs=64):
        if self.started or type(pairs) is not int or not 1 <= pairs <= CAPACITY // 2:
            raise ValueError("One bounded trace with 1..64 pairs per core instance")
        if self.dll.neptune_call_begin(ENTRY, pairs) != 1:
            raise ValueError("Core rejected trace; active/JIT/unsupported mode")
        self.started = True

    def frame(self, frame):
        if not self.started or type(frame) is not int or not 0 <= frame <= 0xFFFFFFFF:
            raise ValueError("Missing start or invalid emulated frame")
        if self.dll.neptune_call_frame(frame) != 1:
            raise ValueError("Core rejected nonconsecutive frame boundary")

    def finish(self):
        if not self.started:
            raise ValueError("Trace was never started")
        self.dll.neptune_call_stop()
        status = self.status()
        records = (Record * CAPACITY)()
        count = self.dll.neptune_call_records(records, CAPACITY)
        if count > CAPACITY or count != status.count:
            raise ValueError("Core returned a partial or oversized trace")
        return validate(list(records)[:count], status)


def probe_library(path):
    """Real exported ABI/argument/clock fences; no CPU or original media is run."""
    observer = Trace(C.CDLL(str(path)))
    if (observer.dll.neptune_call_begin(ENTRY, 0) != 0 or
            observer.dll.neptune_call_begin(ENTRY + 2, 1) != 0 or
            observer.dll.neptune_call_begin(ENTRY, 65) != 0):
        raise ValueError("Observer accepted unsupported entry/budget")
    observer.start(1)
    observer.frame(10)
    try:
        observer.frame(12)
    except ValueError:
        pass
    else:
        raise ValueError("Observer accepted a skipped frame")
    status = observer.status()
    if status.errors != 1 or status.active or status.count or status.pending:
        raise ValueError("Observer did not retain its failed boundary")
    return {"scope": "libretro observer ABI and argument/frame fences only; no media execution",
            "abi": status.abi, "record_bytes": status.record_bytes,
            "capacity": status.capacity, "step_limit": status.step_limit,
            "rejected_invalid_entry_budget_and_frame": True}


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Probe a separately pinned core observer ABI; no media")
    parser.add_argument("--probe-core", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe_library(args.probe_core), sort_keys=True))
