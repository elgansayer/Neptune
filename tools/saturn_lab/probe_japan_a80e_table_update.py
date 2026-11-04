#!/usr/bin/env python3
"""Execute original Japan A80E/AACC over constructed 18-row WorkRAM tables."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

BASE, SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
ENTRY, END = 0x0600A80E, 0x0600A8C2
CALLBACK, CALLBACK_END = 0x0600AACC, 0x0600AAEA
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
TABLE, ROW_SIZE, ROWS = 0x060BCEEC, 88, 18
TABLE_SIZE = ROW_SIZE * ROWS
SP = 0x06002000
CODE = tuple(range(ENTRY, END, 2)) + tuple(range(CALLBACK, CALLBACK_END, 2))
LITERALS = {0x0600A8D8: (4, TABLE), 0x0600A8C2: (2, 0x0630),
            0x0600AB2C: (4, TABLE)}
SEEDS = (0, 1)
LIMIT = 4096

CASES = {
    "free_slot_clears_references": {"index": 5, "fields": {
        5: {82: 0xFF, 83: 9}, 0: {80: 1, 82: 5}, 1: {80: 0, 82: 5},
        17: {80: 1, 82: 5, 83: 3}}},
    "active_references_transfer": {"index": 5, "fields": {
        5: {80: 1, 82: 2, 83: 7}, 2: {80: 1, 81: 3, 82: 0xFF, 83: 2},
        0: {80: 1, 82: 5}, 1: {80: 0, 82: 5}, 3: {80: 2, 82: 5}}},
    "last_reference_calls_aacc": {"index": 17, "fields": {
        17: {80: 1, 82: 3, 83: 6}, 3: {80: 1, 81: 4, 82: 0xFF, 83: 1}}},
    "aacc_empty_state_no_store": {"index": 0, "fields": {
        0: {80: 1, 82: 6, 83: 4}, 6: {80: 0, 81: 4, 82: 0xFF, 83: 1}}},
    "reference_count_wrap": {"index": 1, "fields": {
        1: {80: 1, 82: 0, 83: 1}, 0: {80: 1, 81: 0, 82: 0xFF, 83: 0},
        2: {80: 1, 82: 1}}},
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def initial_table(case):
    table = bytearray(TABLE_SIZE)
    for i in range(ROWS):
        table[i * ROW_SIZE + 82] = 0xFF
    for index, fields in case["fields"].items():
        for offset, value in fields.items():
            table[index * ROW_SIZE + offset] = value & 0xFF
    return table


def expected_table(before: bytes, index: int) -> bytes:
    out = bytearray(before)
    field = lambda row, off: out[row * ROW_SIZE + off]
    if field(index, 82) == 0xFF:
        for row in range(ROWS):
            if field(row, 82) == index:
                out[row * ROW_SIZE + 82] = 0xFF
        out[index * ROW_SIZE + 83] = 0
        return bytes(out)

    target = field(index, 82)
    out[target * ROW_SIZE + 83] = (field(target, 83) - 1) & 0xFF
    out[index * ROW_SIZE + 82] = 0xFF
    for row in range(ROWS):
        if field(row, 82) == index and field(row, 80) != 0:
            out[row * ROW_SIZE + 82] = target
            out[target * ROW_SIZE + 83] = (field(target, 83) + 1) & 0xFF
    if field(target, 83) == 0 and field(target, 81) == 4 and field(target, 80) != 0:
        out[target * ROW_SIZE:target * ROW_SIZE + 4] = (1).to_bytes(4, "big")
    out[index * ROW_SIZE + 83] = 0
    return bytes(out)


def execute(kernel: bytes, ram: bytes, emu, case_name: str, seed: int,
            mutate_clear_value: bool = False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("original Japan kernel or captured WorkRAM-H identity differs")
    if case_name not in CASES or seed not in SEEDS:
        raise ValueError("case or seed outside declared corpus")
    for start, end in ((ENTRY, END), (CALLBACK, CALLBACK_END)):
        if ram[start - WRAM:end - WRAM] != kernel[start - BASE:end - BASE]:
            raise ValueError(f"captured code differs from original at {start:08x}")
    before_table = initial_table(CASES[case_name])
    work = bytearray(ram)
    work[TABLE - WRAM:TABLE - WRAM + TABLE_SIZE] = before_table
    if mutate_clear_value:
        work[0x0600A816 - WRAM + 1] = 0xFE  # MOV #-1,R13 becomes MOV #-2,R13.
    reads, writes, pcs = [], [], []
    index = CASES[case_name]["index"]

    class Memory(emu.Memory):
        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in CODE:
                    raise ValueError(f"A80E PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and LITERALS[address][0] == width:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if TABLE <= address and address + width <= TABLE + TABLE_SIZE and width in (1, 4):
                value = super().read(address, width)
                reads.append(["table", address, width, value])
                return value
            if SP - 32 <= address and address + width <= SP and width == 4:
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected A80E read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            if TABLE <= address and address + width <= TABLE + TABLE_SIZE and width in (1, 4):
                writes.append(["table", address, width, value])
            elif SP - 32 <= address and address + width <= SP and width == 4:
                writes.append(["stack", address, width, value])
            else:
                raise ValueError(f"unexpected A80E write {address:08x}/{width}/{value:08x}")
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            if pc not in CODE:
                raise ValueError(f"A80E fetch target {pc:08x} outside caller/callback code")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in CODE:
                raise ValueError(f"A80E instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x73000000 + n * 0x01020305 + seed * 0x11111111) & 0xFFFFFFFF
             for n in range(16)]
    cpu.r[4] = index
    cpu.r[15] = SP
    cpu.sr = 0xF0
    cpu.mach, cpu.macl = 0x12345678 ^ seed, 0x89ABCDEF ^ seed
    initial_registers = cpu.r.copy()
    initial_mach, initial_macl = cpu.mach, cpu.macl
    cpu.pr, cpu.pc = emu.RETURN_SENTINEL, ENTRY
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A80E instruction budget exceeded")
    actual = bytes(mapped[TABLE - WRAM:TABLE - WRAM + TABLE_SIZE])
    expected = expected_table(before_table, index)
    if not mutate_clear_value and actual != expected:
        raise ValueError(f"A80E table differs from independent byte model in {case_name}")
    if cpu.r[15] != SP or cpu.pr != emu.RETURN_SENTINEL:
        raise ValueError("A80E stack/return state differs")
    for reg in (10, 12, 13, 14):
        if cpu.r[reg] != initial_registers[reg]:
            raise ValueError(f"A80E failed to restore R{reg}")
    if (cpu.mach, cpu.macl) != (initial_mach, initial_macl):
        raise ValueError("A80E failed to restore MACH/MACL")
    return {"seed": seed, "case": case_name, "index": index, "steps": cpu.steps,
            "aacc_entries": pcs.count(CALLBACK), "table_sha256_before": sha(before_table),
            "table_sha256_after": sha(actual), "expected_table_sha256": sha(expected),
            "table_matches_independent_model": actual == expected,
            "table_field_writes": sum(1 for row in writes if row[0] == "table"),
            "stack_writes": sum(1 for row in writes if row[0] == "stack"),
            "reads": reads, "writes": writes, "pc_visits": len(pcs),
            "sp_after": hex(cpu.r[15]), "return_pc": hex(cpu.pc),
            "registers_restored": {f"r{n}": cpu.r[n] == initial_registers[n] for n in (10, 12, 13, 14)},
            "mach_macl_restored": [hex(cpu.mach), hex(cpu.macl)],
            "mutation": mutate_clear_value}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a80e-table-update.v1", "status": "failure",
              "entry": hex(ENTRY), "limits": ["Direct constructed 18-row table and incoming index; no natural caller proof",
                         "Captured frame-1200 WorkRAM-H code; table contents are explicit constructed cases",
                         "Only original A80E/AACC code; no device timing, gameplay, or full-game claim"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text())
                state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
                if (meta.get("frame") != 1200 or meta.get("state_sha256") != STATE_SHA
                        or meta.get("identity", {}).get("core_sha256") != CORE_SHA or sha(state) != STATE_SHA):
                    raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel = pinned.read_bounded(args.kernel, SIZE)
                ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
                emu = pinned.interpreter(args.saturn_recomp)
                results = []
                for case_name in CASES:
                    first = execute(kernel, ram, emu, case_name, 0)
                    second = execute(kernel, ram, emu, case_name, 1)
                    first_table_writes = [row for row in first["writes"] if row[0] == "table"]
                    second_table_writes = [row for row in second["writes"] if row[0] == "table"]
                    if (first["table_sha256_after"], first["aacc_entries"], first_table_writes) != (
                            second["table_sha256_after"], second["aacc_entries"], second_table_writes):
                        raise ValueError(f"paired A80E result differs in {case_name}")
                    results.append({"case": case_name, "runs": [first, second],
                                    "paired_table_and_write_contract_identical": True})
                control = execute(kernel, ram, emu, "free_slot_clears_references", 0, mutate_clear_value=True)
                if control["table_matches_independent_model"]:
                    raise ValueError("A80E immediate mutation escaped table comparison")
                report.update(status="success", original_game_bytes_executed=True,
                              captured_snapshot_data_used=True, release="Japan T-14302G V1.000",
                              source_file="0KRNL.BIN", cpu="master SH-2",
                              code_ranges=[[hex(ENTRY), hex(END)], [hex(CALLBACK), hex(CALLBACK_END)]],
                              cases=len(results), executions_per_case=2, results=results,
                              mutation_control={"instruction":"0x0600A816", "original":"0xEDFF",
                                                "replacement":"0xEDFE", "table_model_rejected":True,
                                                "table_sha256":control["table_sha256_after"]},
                              kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                              normalized_workram_sha256=RAM_SHA,
                              probe_sha256=sha(Path(__file__).read_bytes()),
                              interpreter_revision=pinned.INTERPRETER_REVISION,
                              interpreter_sources=pinned.SOURCE_HASHES,
                              contract="A80E treats R4 as a row index in an 18x88-byte table, clears references for a free row or transfers active references from that row to its prior target, adjusts the target reference count, conditionally calls AACC when the count reaches zero and field81 is four, then clears the selected row counter. The five constructed cases are checked against an independent byte-level transition model.")
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
