#!/usr/bin/env python3
"""Compose Japan A208/AE3A with ACE8 context save/restore to captured AB94."""
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
ACE8_END = 0x0600AD60
SAVE, SAVE_END = 0x0600A164, 0x0600A186
RESTORE, RESTORE_END = 0x0600A186, 0x0600A1AA
RESUME_PC, RESTORE_CONTEXT, CONTEXT_BYTES = 0x0600AB94, 0x060BDD7C, 48
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
ALIASES = {0x2600A018: 0x0600A018, 0x2600A01C: 0x0600A01C,
           0x2600A020: 0x0600A020, 0x2600A024: 0x0600A024,
           0x2600A028: 0x0600A028, 0x2600A02C: 0x0600A02C,
           0x2600A044: 0x0600A044}
LITERALS = {0x0600ADA4: (4, 0x2600A020), 0x0600AD9C: (4, 0x2600A044),
            0x0600AD8C: (4, SAVE), 0x0600AD88: (4, RESTORE_CONTEXT),
            0x0600ADA8: (4, RESTORE), 0x0600ADAC: (4, 0x2600A028)}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel, ram, emu, slot, seed, mutate=False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan kernel identity differs")
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("captured frame-1200 WorkRAM-H identity differs")
    ranges = ((CALL, CALL_END), (ENTRY, END), (ACE8, ACE8_END),
              (SAVE, SAVE_END), (RESTORE, RESTORE_END))
    for start, end in ((CALL, CALL_END), (ENTRY, END), (ACE8, ACE8_END),
                       (SAVE, SAVE_END), (RESTORE, RESTORE_END)):
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
    code_ranges = ranges
    saved_context = bytes(work[RESTORE_CONTEXT-WRAM:RESTORE_CONTEXT-WRAM+CONTEXT_BYTES])
    captured_resume = int.from_bytes(saved_context[36:40], "big")

    class Memory(emu.Memory):
        def translate(self, address, width):
            for alias, physical in ALIASES.items():
                if alias <= address and address + width <= alias + 4:
                    return physical + address - alias
            return address

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not any(lo <= address < hi for lo, hi in code_ranges) or address & 1:
                    raise ValueError(f"A208/AE3A PC fence {address:08x}/{width}")
                return super().read(address, width)
            translated = self.translate(address, width)
            if translated != address:
                if width != 4:
                    raise ValueError(f"cache-through alias read width {width}")
                value = super().read(translated, width)
                reads.append(["cache_alias", address, width, value])
                return value
            if address in LITERALS and LITERALS[address][0] == width:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
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
            if row_base <= address and address + width <= row_base + ROW_SIZE and width in (1, 4):
                value = super().read(address, width)
                reads.append(["task_row", address, width, value])
                return value
            if (RESTORE_CONTEXT <= address and address + width <= RESTORE_CONTEXT + CONTEXT_BYTES
                    and width == 4):
                value = super().read(address, width)
                reads.append(["captured_context", address, width, value])
                return value
            if SP - 96 <= address and address + width <= SP and width == 4:
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected A208/AE3A read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= (1 << (width * 8)) - 1
            translated = self.translate(address, width)
            if translated != address:
                if width != 4 or address not in (0x2600A028, 0x2600A02C):
                    raise ValueError(f"unexpected cache-through write {address:08x}/{width}")
                writes.append(["cache_alias", address, width, value])
                return super().write(translated, width, value)
            if width == 4 and SP - 96 <= address and address + width <= SP and address & 3 == 0:
                stack_writes.append([address, width, value])
                writes.append(["stack", address, width, value])
                return super().write(address, width, value)
            if row_base <= address and address + width <= row_base + ROW_SIZE and width in (1, 4):
                writes.append(["task_row", address, width, value])
                return super().write(address, width, value)
            raise ValueError(f"unexpected A208/AE3A write {address:08x}/{width}/{value:08x}")

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
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
    while cpu.pc != RESUME_PC:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A208/AE3A/ACE8/A164/A186 instruction budget exceeded")

    matching = selected_pointer == row_base
    branch_match = matching and not mutate
    expected_task_word = 0 if branch_match else 1
    if captured_resume != RESUME_PC or cpu.pc != captured_resume:
        raise ValueError("A186 did not resume at captured AB94 PR")
    for offset in (0, 4):
        if int.from_bytes(mapped[row_base + offset-WRAM:row_base + offset-WRAM+4], "big") != expected_task_word:
            raise ValueError(f"ACE8 task word at +{offset} differs from AE3A-selected argument")
    if branch_match and mapped[row_base + 81-WRAM] != 4:
        raise ValueError("AE3A matching-row marker store differs")
    restored = [int.from_bytes(saved_context[o:o+4], "big") for o in range(0, CONTEXT_BYTES, 4)]
    restore_regs = {4: restored[0], 8: restored[1], 9: restored[2],
                    10: restored[3], 11: restored[4], 12: restored[5], 13: restored[6],
                    14: restored[7], 15: restored[8]}
    for reg, value in restore_regs.items():
        if cpu.r[reg] != value:
            raise ValueError(f"A186 restored R{reg} differs from captured BDD7C")
    if cpu.r[0] != expected_task_word:
        raise ValueError("A186 RTS delay slot did not copy live R5 into R0")
    if (cpu.pr, cpu.mach, cpu.macl) != (restored[9], restored[10], restored[11]):
        raise ValueError("A186 restored PR/MACH/MACL differ from captured BDD7C")
    return {"slot": slot, "seed": seed, "vbr": hex(cpu.vbr), "task_index": task_index,
            "row": hex(row_base), "selected_pointer": hex(selected_pointer),
            "row_state": row_state, "matching_vbr_row": matching,
            "matching_branch_taken": branch_match, "task_word_after": expected_task_word,
            "pc_stop": hex(cpu.pc), "pr_after_restore": hex(cpu.pr), "sp_after_restore": hex(cpu.r[15]),
            "steps": cpu.steps, "pc_visits": pcs, "reads": reads, "writes": writes,
            "original_bytes_executed": not mutate, "mutation": mutate,
            "captured_resume": hex(captured_resume), "saved_context_sha256": sha(saved_context)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-a208-ae3a-ab94-resume.v1", "status": "failure",
              "release": "Japan T-14302G V1.000", "module": "KRNL", "cpu": "SH-2",
              "entry": hex(CALL), "callee": hex(ENTRY), "stop": hex(RESUME_PC),
              "mapping": hex(BASE), "code_ranges": [[hex(a), hex(b)] for a, b in
                  ((CALL, CALL_END), (ENTRY, END), (ACE8, ACE8_END), (SAVE, SAVE_END), (RESTORE, RESTORE_END))],
              "limits": ["Captured frame-1200 task cursor/table/VBR backing state and BDD7C context; seeded remaining registers",
                         "Executes original A208/AE3A, ACE8, A164 and A186; stops before AB94 body",
                         "No complete natural scheduler cycle, device/timing/gameplay or full-game claim"]}
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
            results = [execute(kernel, ram, emu, 0, seed) for seed in SEEDS]
            mutated = execute(kernel, ram, emu, 0, 0, mutate=True)
            if mutated["pc_visits"] == results[0]["pc_visits"] or mutated["writes"] == results[0]["writes"]:
                raise ValueError("AE6C branch inversion survived original row-match comparison")
            report.update(status="success", cases=len(results), original_game_bytes_executed=True,
                          results=results, mutation_control={"pc": "0x0600AE6C", "original": "0x8B06",
                          "replacement": "0x8906", "matching_row_edge_rejected": True,
                          "mutated_task_word_after": mutated["task_word_after"]},
                          source_kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                          normalized_workram_sha256=RAM_SHA,
                          probe_sha256=sha(Path(__file__).read_bytes()),
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          contract="A208 loads its original AE3A indirect target and passes the captured task cursor through its JSR delay slot. AE3A matches the captured VBR-selected row and stores marker +81=4. ACE8 stores the selected task words, saves the live frame through A164, and calls A186. A186 restores the captured 48-byte BDD7C context and resumes at its PR target AB94; the probe stops before executing AB94.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0),
                      "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
