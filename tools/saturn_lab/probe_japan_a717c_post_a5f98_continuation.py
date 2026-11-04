#!/usr/bin/env python3
"""Execute the original A717C post-A5F98 register/global publication tail."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source

ENTRY, CODE_END, STOP = 0x060A7244, 0x060A727E, 0x060A71A8
STACK, FINAL_SP = 0x06007FA4, 0x06008000
GLOBAL = 0x060FCD30
R8_VALUES = (0, 1, 0x10102020, 0xFFFFFFFF)
BASES = (0x06009000, 0x06009004)
STACK_WORDS = (0, 1, 0x11223344, 0xFFFFFFFF)
SAVED_R7 = (0x11223344, 0xA55A5AA5)
PR_VALUE = 0x060A71A8
PCS = tuple(range(ENTRY, CODE_END, 2))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(ram: bytes, emu, r8: int, base: int, stack_word: int, r7: int):
    work = bytearray(ram)
    # The continuation is entered at the exact post-A5F98 boundary. These
    # stack words model the already established A717C frame; they are not
    # claimed as a naturally observed task context.
    words = {STACK: r7, STACK + 60: PR_VALUE, STACK + 64: 0x8899AABB,
        STACK + 68: 0x99AABBCC, STACK + 72: 0xAABBCCDD,
        STACK + 76: 0xBBCCDDEE, STACK + 80: base,
        STACK + 84: 1, STACK + 88: 0xCCDDEEFF,
        STACK + 92: stack_word}
    for address, value in words.items():
        offset = address - source.WORKRAM_BASE
        work[offset:offset + 4] = value.to_bytes(4, "big")
    before = bytes(work)
    reads, writes, pcs = [], [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in PCS:
                    raise ValueError(f"continuation PC fence at {address:08x}/{width}")
                return super().read(address, width)
            if address == source.GLOBAL_LITERAL and width == 4:
                value = super().read(address, width)
                if value != GLOBAL:
                    raise ValueError("captured global literal differs")
                reads.append(["global-literal", address, width, value])
                return value
            if STACK <= address <= FINAL_SP and width == 4:
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected continuation read {address:08x}/{width}")

        def write(self, address, width, value):
            if width != 4 or address not in (GLOBAL, GLOBAL + 4, GLOBAL + 8):
                raise ValueError(f"unexpected continuation write {address:08x}/{width}")
            value &= 0xFFFFFFFF
            writes.append([address, width, value])
            return super().write(address, width, value)

    mem = Memory()
    work_mem = mem.add(source.WORKRAM_BASE, source.WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 40 or pc not in PCS:
                raise ValueError(f"continuation instruction fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x13570000 + i * 0x00010203) & 0xFFFFFFFF for i in range(16)]
    cpu.r[8], cpu.r[10], cpu.r[12], cpu.r[13] = r8, base, 4, 1
    cpu.r[15], cpu.pr, cpu.pc = STACK, 0x060A7244, ENTRY
    saved = cpu.r.copy()
    saved[7] = r7
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > 40:
            raise ValueError("continuation instruction budget exceeded")
    if tuple(pcs) != PCS:
        raise ValueError(f"continuation PC sequence differs: {pcs!r}")
    expected_words = (0, (r7 + 4 * stack_word) & 0xFFFFFFFF,
        (base + 4 * r8) & 0xFFFFFFFF)
    actual_words = tuple(int.from_bytes(work_mem[GLOBAL - source.WORKRAM_BASE + off:
        GLOBAL - source.WORKRAM_BASE + off + 4], "big") for off in (0, 4, 8))
    if actual_words != expected_words:
        raise ValueError(f"global values differ: {actual_words!r}/{expected_words!r}")
    if writes != [[GLOBAL, 4, 0], [GLOBAL + 8, 4, expected_words[2]],
            [GLOBAL + 4, 4, expected_words[1]]]:
        raise ValueError(f"global write trace differs: {writes!r}")
    if cpu.r[15] != FINAL_SP or cpu.r[14] != 0xCCDDEEFF or cpu.pc != STOP:
        raise ValueError("continuation SP, R14 delay-slot restore, or return boundary differs")
    for reg, address in zip(range(8, 14), range(STACK + 64, STACK + 88, 4)):
        if cpu.r[reg] != words[address]:
            raise ValueError(f"saved register R{reg} restore differs")
    if cpu.pr != PR_VALUE:
        raise ValueError("saved PR restore differs")
    after = bytes(work_mem)
    global_offset = GLOBAL - source.WORKRAM_BASE
    if (before[:global_offset] != after[:global_offset] or
            before[global_offset + 12:] != after[global_offset + 12:]):
        raise ValueError("unexpected WorkRAM mutation outside the 12-byte global block")
    return {"inputs": {"r8": r8, "r10_base": base, "stack_plus_92": stack_word,
            "saved_r7_at_entry_sp": r7}, "global_words": list(actual_words),
        "reads": reads, "writes": writes, "pc_trace": [hex(pc) for pc in pcs],
        "steps": cpu.steps, "pr_after": hex(cpu.pr), "sp_after": hex(cpu.r[15]),
        "r14_after_rts_delay": hex(cpu.r[14]), "unaffected_workram_bytes_checked": len(after) - 12}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-post-a5f98-continuation.v1",
        "status": "failure", "entry": hex(ENTRY), "stop": hex(STOP),
        "limits": ["Original bytes from the staged post-A5F98 boundary only",
            "Stack/register context is constructed; no natural caller reachability claim"]}
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
                if ram[ENTRY-source.WORKRAM_BASE:STOP-source.WORKRAM_BASE] != kernel[ENTRY-source.BASE:STOP-source.BASE]:
                    raise ValueError("captured continuation differs from original kernel")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for r8 in R8_VALUES:
                    for base in BASES:
                        for stack_word in STACK_WORDS:
                            for r7 in SAVED_R7:
                                first = execute(ram, emu, r8, base, stack_word, r7)
                                second = execute(ram, emu, r8, base, stack_word, r7)
                                if first != second:
                                    raise ValueError("paired continuation execution differs")
                                rows.append(first)
                results = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(results), probe_sha256=sha(Path(__file__).read_bytes()),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA,
                    source_sha256=sha(kernel[ENTRY-source.BASE:CODE_END-source.BASE]),
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
