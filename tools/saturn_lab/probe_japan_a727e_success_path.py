#!/usr/bin/env python3
"""Execute Japan A727E's A6142-success branch and original A74E0 copy helper."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source

ENTRY, HANDLER_END = 0x060A727E, 0x060A72AE
STATUS, STATUS_END = 0x060A6142, 0x060A6150
COPY, COPY_END = 0x060A74E0, 0x060A7506
STATUS_WORD = 0xFFFFFF8C
STATUS_VALUES = (0, 1, 2, 3)
LENGTHS = (0, 1, 2, 3)
SOURCE = 0x06009000
DEST = 0x06009100
SOURCE_WORDS = (0x01234567, 0x89ABCDEF)
DEST_WORDS = (0xA5A5A5A5, 0x5A5A5A5A)
STACK = 0x06008000
STACK_BYTES = 16
GLOBAL = 0x060FCD30
GLOBAL_LITERAL = 0x060A7364
STATUS_LITERAL = 0x060A7368
MAX_STEPS = 64


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    # The first row retains the unmodified captured globals (all zero in the
    # frame-1200 state); the rest stage A717C's documented global layout to
    # exercise each low-two-bit copy length and both byte patterns.
    rows = [(value, None, 0, 0) for value in STATUS_VALUES if not (value & 2)]
    rows.extend((status, length, src, dst)
        for status in STATUS_VALUES if status & 2
        for length in LENGTHS for src in SOURCE_WORDS for dst in DEST_WORDS)
    return rows


def expected_pcs(status_value: int, length: int | None):
    pcs = [0x060A727E, 0x060A7280, 0x060A7282, 0x060A7284,
        0x060A7286, 0x060A7288]
    pcs.extend((0x060A6142, 0x060A6144, 0x060A6146, 0x060A6148,
        0x060A614A, 0x060A614C, 0x060A614E, 0x060A728A, 0x060A728C))
    if not (status_value & 2):
        return tuple(pcs + [0x060A728E, 0x060A7290, 0x060A7292, 0x060A7294])
    if length is None:
        raise ValueError("successful A6142 branch requires a staged global block")
    pcs.extend((0x060A7296, 0x060A7298, 0x060A729A, 0x060A729C,
        0x060A729E, 0x060A72A0, 0x060A72A2, 0x060A74E0,
        0x060A74E2, 0x060A74E4))
    if length == 0:
        pcs.extend((0x060A7502, 0x060A7504))
    else:
        pcs.extend((0x060A74E6, 0x060A74E8, 0x060A74EA, 0x060A74EC,
            0x060A74EE, 0x060A74F0, 0x060A74F2))
        for _ in range(length):
            pcs.extend((0x060A74F4, 0x060A74F6, 0x060A74F8, 0x060A74FA,
                0x060A74FC, 0x060A74FE, 0x060A7500))
        pcs.extend((0x060A7502, 0x060A7504))
    pcs.extend((0x060A72A4, 0x060A72A6, 0x060A72A8, 0x060A72AA, 0x060A72AC))
    return tuple(pcs)


def execute(ram: bytes, emu, status_value: int, length: int | None,
        source_word: int, dest_word: int):
    if status_value not in STATUS_VALUES:
        raise ValueError("status word outside the declared two-bit domain")
    if (status_value & 2) and (length not in LENGTHS or source_word not in SOURCE_WORDS
            or dest_word not in DEST_WORDS):
        raise ValueError("success-path input outside the declared domain")
    work = bytearray(ram)
    actual_globals = tuple(int.from_bytes(work[GLOBAL-source.WORKRAM_BASE+off:
        GLOBAL-source.WORKRAM_BASE+off+4], "big") for off in (0, 4, 8))
    if status_value & 2:
        staged_globals = (length, SOURCE, DEST)
        for off, value in zip((0, 4, 8), staged_globals):
            work[GLOBAL-source.WORKRAM_BASE+off:GLOBAL-source.WORKRAM_BASE+off+4] = value.to_bytes(4, "big")
        work[SOURCE-source.WORKRAM_BASE:SOURCE-source.WORKRAM_BASE+4] = source_word.to_bytes(4, "big")
        work[DEST-source.WORKRAM_BASE:DEST-source.WORKRAM_BASE+4] = dest_word.to_bytes(4, "big")
    else:
        staged_globals = actual_globals
    stack_seed = bytes((0x39 + i * 17) & 0xFF for i in range(STACK_BYTES))
    work[STACK-source.WORKRAM_BASE-STACK_BYTES:STACK-source.WORKRAM_BASE] = stack_seed
    before = bytes(work)
    reads, writes, pcs = [], [], []
    allowed = (set(range(ENTRY, HANDLER_END, 2)) |
        set(range(STATUS, STATUS_END, 2)) | set(range(COPY, COPY_END, 2)))
    sentinel = emu.RETURN_SENTINEL

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in allowed:
                    raise ValueError(f"A727E success-path PC fence at {address:08x}/{width}")
                return super().read(address, width)
            if address == STATUS_WORD and width == 4:
                reads.append(["constructed-status-word", address, width, status_value])
                return status_value
            if address in (GLOBAL_LITERAL, STATUS_LITERAL) and width == 4:
                value = super().read(address, width)
                expected = GLOBAL if address == GLOBAL_LITERAL else STATUS
                if value != expected:
                    raise ValueError(f"original pointer literal differs at {address:08x}")
                reads.append(["original-pointer-literal", address, width, value])
                return value
            if address in (GLOBAL, GLOBAL + 4, GLOBAL + 8) and width == 4:
                value = super().read(address, width)
                reads.append(["callback-global", address, width, value])
                return value
            if status_value & 2 and address == SOURCE and width == 4:
                value = super().read(address, width)
                reads.append(["staged-source-word", address, width, value])
                return value
            stack_start = STACK - STACK_BYTES
            if stack_start <= address and address + width <= STACK and width in (1, 4):
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected A727E data read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            stack_start = STACK - STACK_BYTES
            if stack_start <= address and address + width <= STACK and width == 4:
                writes.append(["stack", address, width, value])
                return super().write(address, width, value)
            if status_value & 2 and address >= DEST and address < DEST + 4 and width == 1:
                writes.append(["destination", address, width, value & 0xFF])
                return super().write(address, width, value)
            raise ValueError(f"unexpected A727E write {address:08x}/{width}/{value:08x}")

    memory = Memory()
    work_mem = memory.add(source.WORKRAM_BASE, source.WORKRAM_SIZE, work)
    memory.add(STATUS_WORD, 4, status_value.to_bytes(4, "big"))

    class CPU(emu.CPU):
        def fetch(self, pc):
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= MAX_STEPS or pc not in allowed:
                raise ValueError(f"A727E instruction/budget fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0xC3100000 + i * 0x01020305) & 0xFFFFFFFF for i in range(16)]
    cpu.r[0], cpu.r[4], cpu.r[5], cpu.r[6] = 0xDEADBEEF, 0, 0xDEAD0000, 0xDEAD1000
    cpu.r[15], cpu.pr = STACK, sentinel
    result = cpu.call(ENTRY, max_steps=MAX_STEPS, r4=0)
    expected = expected_pcs(status_value, length)
    if tuple(pcs) != expected:
        raise ValueError(f"A727E exact original PC trace differs: {pcs!r}/{expected!r}")
    success = bool(status_value & 2)
    expected_result = 0 if success else 1
    if result != expected_result or cpu.r[0] != expected_result:
        raise ValueError(f"A727E return differs: {result}/{cpu.r[0]}")
    if cpu.r[15] != STACK or cpu.pr != sentinel:
        raise ValueError("A727E did not restore its incoming SP/PR")

    expected_reads = [["original-pointer-literal", STATUS_LITERAL, 4, STATUS]]
    expected_writes = [["stack", STACK - 4, 4, sentinel], ["stack", STACK - 8, 4, 0]]
    if success:
        expected_reads.extend([
            ["constructed-status-word", STATUS_WORD, 4, status_value],
            ["original-pointer-literal", GLOBAL_LITERAL, 4, GLOBAL],
            ["original-pointer-literal", GLOBAL_LITERAL, 4, GLOBAL],
            ["callback-global", GLOBAL + 4, 4, SOURCE],
            ["callback-global", GLOBAL + 8, 4, DEST],
            ["original-pointer-literal", GLOBAL_LITERAL, 4, GLOBAL],
            ["callback-global", GLOBAL, 4, length]])
        if length:
            expected_reads.append(["staged-source-word", SOURCE, 4, source_word])
            expected_writes.append(["stack", STACK - 12, 4, source_word])
            expected_reads.extend(["stack", STACK - 12 + i, 1,
                (source_word.to_bytes(4, "big")[i])] for i in range(length))
            expected_writes.extend(["destination", DEST + i, 1,
                source_word.to_bytes(4, "big")[i]] for i in range(length))
        expected_reads.append(["stack", STACK - 4, 4, sentinel])
    else:
        expected_reads.append(["constructed-status-word", STATUS_WORD, 4, status_value])
        expected_reads.append(["stack", STACK - 4, 4, sentinel])
    if not success and reads != expected_reads:
        raise ValueError(f"A727E early-route reads differ: {reads!r}/{expected_reads!r}")
    if not success and writes != expected_writes:
        raise ValueError(f"A727E early-route writes differ: {writes!r}/{expected_writes!r}")
    if success:
        # Retain observed event order while checking the exact reads/writes.
        if reads != expected_reads:
            raise ValueError(f"A727E success reads differ: {reads!r}/{expected_reads!r}")
        prefix_writes = [["stack", STACK - 4, 4, sentinel], ["stack", STACK - 8, 4, 0]]
        suffix_writes = ([["stack", STACK - 12, 4, source_word]] if length else [])
        suffix_writes.extend([["destination", DEST + i, 1, source_word.to_bytes(4, "big")[i]]
            for i in range(length)])
        if writes != prefix_writes + suffix_writes:
            raise ValueError(f"A727E success writes differ: {writes!r}/{prefix_writes + suffix_writes!r}")

    after = bytes(work_mem)
    allowed_changed = set(range(STACK - STACK_BYTES, STACK))
    if success:
        allowed_changed.update(range(DEST, DEST + length))
    base = source.WORKRAM_BASE
    for left, right, offset in ((before[:STACK - STACK_BYTES - base], after[:STACK - STACK_BYTES - base], 0),
            (before[STACK - base:], after[STACK - base:], STACK - base)):
        if left != right:
            for i, (a, b) in enumerate(zip(left, right)):
                if a != b and base + offset + i not in allowed_changed:
                    raise ValueError(f"unexpected WorkRAM write at {base + offset + i:08x}")
    expected_stack = bytearray(stack_seed)
    expected_stack[8:12] = (0).to_bytes(4, "big")
    expected_stack[12:16] = sentinel.to_bytes(4, "big")
    if success and length:
        expected_stack[4:8] = source_word.to_bytes(4, "big")
    stack_after = bytes(work_mem[STACK-base-STACK_BYTES:STACK-base])
    if stack_after != bytes(expected_stack):
        raise ValueError("A727E/A74E0 stack image differs outside the explicit saved words")
    expected_dest = dest_word.to_bytes(4, "big")
    if success and length:
        expected_dest = source_word.to_bytes(4, "big")[:length] + expected_dest[length:]
        actual_dest = bytes(work_mem[DEST-base:DEST-base+4])
        if actual_dest != expected_dest:
            raise ValueError(f"A74E0 byte copy differs: {actual_dest.hex()}/{expected_dest.hex()}")
    return {"inputs": {"status_word_at_ffffff8c": status_value,
            "status_result_r0": status_value & 2, "copy_length": length if success else None,
            "source_word": source_word if success else None, "destination_word": dest_word if success else None,
            "route": "A74E0-success-branch" if success else "A727E-early-return",
            "captured_globals_before": list(actual_globals), "staged_globals": list(staged_globals)},
        "result": result, "reads": reads, "writes": writes,
        "pc_trace": [hex(pc) for pc in pcs], "steps": cpu.steps,
        "sp_after": hex(cpu.r[15]), "pr_after": hex(cpu.pr),
        "stack_after_sha256": sha(stack_after), "workram_after_sha256": sha(after),
        "workram_bytes_checked": len(after)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a727e-a6142-a74e0-success.v1",
        "status": "failure", "entry": hex(ENTRY),
        "limits": ["Original A727E/A6142/A74E0 bytes; constructed MMIO status values",
            "Global copy inputs are staged from A717C's field layout; no natural device/caller claim"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                metadata = json.loads(args.checkpoint.read_text())
                if metadata.get("frame") != 1200 or metadata.get("identity", {}).get("core_sha256") != source.CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, source.STATE_MAX)
                if sha(state) != source.STATE_SHA or metadata.get("state_sha256") != source.STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, source.KERNEL_SIZE)
                if len(kernel) != source.KERNEL_SIZE or sha(kernel) != source.KERNEL_SHA:
                    raise ValueError("original Japanese kernel identity differs")
                parsed = sg.parse(state)
                ram = sg.cpu_words(sg.field(parsed, "MAIN", "WorkRAMH", source.WORKRAM_SIZE), "little")
                if sha(ram) != source.RAM_SHA:
                    raise ValueError("frame-1200 WorkRAM-H identity differs")
                for start, end in ((ENTRY, HANDLER_END), (STATUS, STATUS_END), (COPY, COPY_END)):
                    if ram[start-source.WORKRAM_BASE:end-source.WORKRAM_BASE] != kernel[start-source.BASE:end-source.BASE]:
                        raise ValueError(f"captured/source bytes differ in [{start:08x},{end:08x})")
                for address, target in ((GLOBAL_LITERAL, GLOBAL), (STATUS_LITERAL, STATUS)):
                    if int.from_bytes(ram[address-source.WORKRAM_BASE:address-source.WORKRAM_BASE+4], "big") != target:
                        raise ValueError(f"original pointer literal differs at {address:08x}")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for status_value, length, src_word, dst_word in corpus():
                    one = execute(ram, emu, status_value, length, src_word, dst_word)
                    two = execute(ram, emu, status_value, length, src_word, dst_word)
                    if one != two:
                        raise ValueError("repeated A727E success-path execution differs")
                    rows.append(one)
                result_bytes = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                source_bytes = b"".join(kernel[start-source.BASE:end-source.BASE]
                    for start, end in ((ENTRY, HANDLER_END), (STATUS, STATUS_END), (COPY, COPY_END)))
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(result_bytes), probe_sha256=sha(Path(__file__).read_bytes()),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA, source_sha256=sha(source_bytes),
                    original_literals_sha256=sha(kernel[GLOBAL_LITERAL-source.BASE:GLOBAL_LITERAL-source.BASE+8]),
                    interpreter_revision=pinned.INTERPRETER_REVISION, interpreter_sources=pinned.SOURCE_HASHES)
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as error:
        print(f"FAIL: use a fresh report path: {error}")
        return 1
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
