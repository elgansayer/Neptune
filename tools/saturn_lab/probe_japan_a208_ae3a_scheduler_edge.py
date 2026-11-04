#!/usr/bin/env python3
"""Run Japan's original A208 callsite through AE3A to its first ACE8 handoff."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a80e_table_update as a80e

BASE, SIZE = a80e.BASE, a80e.SIZE
WRAM, WRAM_SIZE = a80e.WRAM, a80e.WRAM_SIZE
CALL, CALL_END = 0x0600A208, 0x0600A20E
ENTRY, END = 0x0600AE3A, 0x0600AE96
ACE8 = 0x0600ACE8
TABLE, ROW_SIZE = a80e.TABLE, a80e.ROW_SIZE
TASK_CURSOR = 0x060BCC80
SELECTOR_ALIAS = 0x2600A020
SELECTOR_LITERAL = 0x0600AF08
TABLE_LITERAL = 0x0600AF04
CALL_LITERAL = 0x0600A2CC
SP, LIMIT = 0x06002000, 160
KERNEL_SHA, STATE_SHA, RAM_SHA, CORE_SHA = (
    a80e.KERNEL_SHA, a80e.STATE_SHA, a80e.RAM_SHA, a80e.CORE_SHA)
SLOTS, SEEDS = (0, 1), (0, 1)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel, ram, emu, slot, seed, mutate=False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan kernel identity differs")
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("captured frame-1200 WorkRAM-H identity differs")
    for start, end in ((CALL, CALL_END), (ENTRY, END)):
        if ram[start-WRAM:end-WRAM] != kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured code differs from original at {start:08x}")
    if slot not in SLOTS or seed not in SEEDS:
        raise ValueError("VBR slot or seed outside declared corpus")

    work = bytearray(ram)
    if mutate:
        work[0x0600AE6C-WRAM:0x0600AE6E-WRAM] = (0x8906).to_bytes(2, "big")
    task_index = int.from_bytes(work[TASK_CURSOR-WRAM:TASK_CURSOR-WRAM+4], "big")
    if task_index >= 18:
        raise ValueError("captured A208 task cursor outside the 18-row table")
    row_base = TABLE + task_index * ROW_SIZE
    selector = SELECTOR_ALIAS + slot * 4
    physical_selector = selector - 0x20000000
    selected_pointer = int.from_bytes(work[physical_selector-WRAM:physical_selector-WRAM+4], "big")
    row_state = work[row_base + 83-WRAM]
    if row_state == 0:
        raise ValueError("captured first row does not enter the task-loop handoff")
    reads, writes, pcs = [], [], []
    stack_writes = []
    code_ranges = ((CALL, CALL_END), (ENTRY, END))

    class Memory(emu.Memory):
        def read(self, address, width):
            if self.fetching:
                if width != 2 or not any(lo <= address < hi for lo, hi in code_ranges) or address & 1:
                    raise ValueError(f"A208/AE3A PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address == TASK_CURSOR and width == 4:
                value = super().read(address, width)
                reads.append(["task_cursor", address, width, value])
                return value
            if (address, width) in ((CALL_LITERAL, 4), (TABLE_LITERAL, 4),
                                    (SELECTOR_LITERAL, 4)):
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if address == selector and width == 4:
                value = super().read(physical_selector, width)
                reads.append(["selected_cache_alias", address, width, value])
                return value
            if address == row_base + 83 and width == 1:
                value = super().read(address, width)
                reads.append(["row_state", address, width, value])
                return value
            raise ValueError(f"unexpected A208/AE3A read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= (1 << (width * 8)) - 1
            if width == 4 and SP - 28 <= address and address + width <= SP and address & 3 == 0:
                stack_writes.append([address, width, value])
                writes.append(["stack", address, width, value])
                return super().write(address, width, value)
            if address == row_base + 81 and width == 1 and not mutate:
                writes.append(["row_marker", address, width, value])
                return super().write(address, width, value)
            raise ValueError(f"unexpected A208/AE3A write {address:08x}/{width}/{value:08x}")

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            if pc == ACE8:
                raise ValueError("attempted to execute ACE8 before recording its handoff edge")
            if not any(lo <= pc < hi for lo, hi in code_ranges):
                raise ValueError(f"A208/AE3A fetch escaped bounded code {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= LIMIT or not any(lo <= pc < hi for lo, hi in code_ranges):
                raise ValueError(f"A208/AE3A instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x61000000 + i * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF
             for i in range(16)]
    cpu.r[11] = TASK_CURSOR
    cpu.r[15] = SP
    cpu.vbr, cpu.sr = 0x06000000 + slot * 0x400, 0xF0
    cpu.mach, cpu.macl, cpu.pr, cpu.pc = 0x10203040 ^ seed, 0xA1B2C3D4 ^ seed, emu.RETURN_SENTINEL, CALL
    before = cpu.r.copy()
    while cpu.pc != ACE8:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A208/AE3A instruction budget exceeded")

    matching = selected_pointer == row_base
    branch_match = matching and not mutate
    expected_r4 = 0 if branch_match else 1
    if cpu.r[4] != expected_r4:
        raise ValueError(f"AE3A ACE8 argument differs slot={slot} pointer={selected_pointer:08x} row={row_base:08x} actual={cpu.r[4]} expected={expected_r4}")
    expected_pr = 0x0600AE76 if branch_match else 0x0600AE80
    if cpu.pr != expected_pr or cpu.r[15] != SP - 28:
        raise ValueError("AE3A ACE8 edge PR or saved-register stack differs")
    if len(stack_writes) != 7:
        raise ValueError(f"AE3A prologue stored {len(stack_writes)} words, expected seven")
    if branch_match:
        if mapped[row_base + 81-WRAM] != 4 or len([w for w in writes if w[0] == "row_marker"]) != 1:
            raise ValueError("AE3A matching-row marker store differs")
    elif mapped[row_base + 81-WRAM] != ram[row_base + 81-WRAM]:
        raise ValueError("AE3A nonmatching-row path changed the marker")
    if mutate and (cpu.r[4] != 1 or mapped[row_base + 81-WRAM] != ram[row_base + 81-WRAM]):
        raise ValueError("mutated AE6C branch did not change the matching-row edge")
    if any(cpu.r[i] != before[i] for i in (5, 6, 7, 8, 9)):
        raise ValueError("AE3A changed an undeclared saved register before ACE8")
    return {"slot": slot, "seed": seed, "vbr": hex(cpu.vbr), "task_index": task_index,
            "row": hex(row_base), "selected_pointer": hex(selected_pointer),
            "row_state": row_state, "matching_vbr_row": matching,
            "matching_branch_taken": branch_match, "r4_at_ace8": cpu.r[4],
            "pc_stop": hex(cpu.pc), "pr_at_edge": hex(cpu.pr), "sp_at_edge": hex(cpu.r[15]),
            "steps": cpu.steps, "pc_visits": pcs, "reads": reads, "writes": writes,
            "original_bytes_executed": not mutate, "mutation": mutate}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-a208-ae3a-ace8-edge.v1", "status": "failure",
              "release": "Japan T-14302G V1.000", "module": "KRNL", "cpu": "SH-2",
              "entry": hex(CALL), "callee": hex(ENTRY), "stop": hex(ACE8),
              "mapping": hex(BASE), "code_ranges": [[hex(a), hex(b)] for a, b in ((CALL, CALL_END), (ENTRY, END))],
              "limits": ["Captured frame-1200 task cursor/table/VBR backing state; seeded remaining registers",
                         "Executes original A208 callsite and AE3A through first ACE8 transfer; ACE8 body not run here",
                         "No complete natural task cycle, device/timing/gameplay or full-game claim"]}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print("FAIL: fresh private report path required")
        return 1
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        try:
            meta = json.loads(args.checkpoint.read_text())
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            if (meta.get("frame") != 1200 or meta.get("state_sha256") != STATE_SHA or
                    meta.get("identity", {}).get("core_sha256") != CORE_SHA or sha(state) != STATE_SHA):
                raise ValueError("frame-1200 state/checkpoint/core identity differs")
            kernel = pinned.read_bounded(args.kernel, SIZE)
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
            emu = pinned.interpreter(args.saturn_recomp)
            results = [execute(kernel, ram, emu, slot, seed)
                       for slot in SLOTS for seed in SEEDS]
            mutated = execute(kernel, ram, emu, 0, 0, mutate=True)
            if mutated["pc_visits"] == results[0]["pc_visits"] or mutated["writes"] == results[0]["writes"]:
                raise ValueError("AE6C branch inversion survived original row-match comparison")
            report.update(status="success", cases=len(results), original_game_bytes_executed=True,
                          results=results, mutation_control={"pc": "0x0600AE6C", "original": "0x8B06",
                          "replacement": "0x8906", "matching_row_edge_rejected": True,
                          "mutated_r4_at_ace8": mutated["r4_at_ace8"]},
                          source_kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                          normalized_workram_sha256=RAM_SHA,
                          probe_sha256=sha(Path(__file__).read_bytes()),
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          contract="A208 loads its original AE3A indirect target and passes the captured task cursor through its JSR delay slot. AE3A scans the selected 88-byte row, compares its pointer against the VBR-selected cache-through pointer, marks a matching row +81=4 and reaches ACE8 with R4=0; the nonmatching slot path reaches ACE8 with R4=1. Execution stops before ACE8 body fetch.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0),
                      "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
