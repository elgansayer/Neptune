#!/usr/bin/env python3
"""Continue A208/AE3A/ACE8/A164/A186 in the same CPU through captured AB94."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned
import probe_japan_a80e_table_update as a80e
import state_graphics as sg

BASE, SIZE = a80e.BASE, a80e.SIZE
WRAM, WRAM_SIZE = a80e.WRAM, a80e.WRAM_SIZE
KERNEL_SHA, STATE_SHA, RAM_SHA, CORE_SHA = (
    a80e.KERNEL_SHA, a80e.STATE_SHA, a80e.RAM_SHA, a80e.CORE_SHA)
CALL, CALL_END = 0x0600A208, 0x0600A20E
LOOP, LOOP_END = 0x0600AE3A, 0x0600AE96
ACE8, ACE8_END = 0x0600ACE8, 0x0600AD60
SAVE, SAVE_END = 0x0600A164, 0x0600A186
RESTORE, RESTORE_END = 0x0600A186, 0x0600A1AA
AB94, AB94_END = 0x0600AB94, 0x0600AD60
AB30, AB30_END = 0x0600AB30, 0x0600AB78
RETURN_CURSOR = 0x060BCC80
CONTEXT, CONTEXT_SIZE = 0x060BDD7C, 48
TABLE, ROW_SIZE, ROWS = a80e.TABLE, a80e.ROW_SIZE, a80e.ROWS
TABLE_END = TABLE + ROW_SIZE * ROWS
CALL_LITERAL, TABLE_LITERAL, SELECTOR_LITERAL = 0x0600A2CC, 0x0600AF04, 0x0600AF08
SP, LIMIT = 0x06002000, 8192
SLOTS, SEEDS = (0,), (0, 1)
CODE_RANGES = ((CALL, CALL_END), (LOOP, LOOP_END), (ACE8, ACE8_END),
               (SAVE, SAVE_END), (RESTORE, RESTORE_END),
               (AB94, AB94_END), (AB30, AB30_END))
ALIASES = {a: a - 0x20000000 for a in (
    0x2600A018, 0x2600A01C, 0x2600A020, 0x2600A024, 0x2600A028,
    0x2600A02C, 0x2600A030, 0x2600A038, 0x2600A040, 0x2600A044)}
LITERALS = {a: 4 for a in range(0x0600AD7C, 0x0600ADB0, 4)}
STACK_WINDOWS = ((SP - 96, SP), (0x060BD8F4 - 256, 0x060BD8F4 + 64),
                 (0x060BCC6C - 256, 0x060BCC6C + 64),
                 (0x060BE18C - 256, 0x060BE18C + 64))

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def execute(kernel, ram, emu, slot, seed, mutate=False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan kernel identity differs")
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("captured frame-1200 WorkRAM-H identity differs")
    for lo, hi in CODE_RANGES:
        if ram[lo-WRAM:hi-WRAM] != kernel[lo-BASE:hi-BASE]:
            raise ValueError(f"captured code differs from original at {lo:08x}..{hi:08x}")
    if slot not in SLOTS or seed not in SEEDS:
        raise ValueError("VBR slot or register seed outside declared set")

    work = bytearray(ram)
    if mutate:
        work[0x0600AE6C-WRAM:0x0600AE6E-WRAM] = (0x8906).to_bytes(2, "big")
    task_index = int.from_bytes(work[RETURN_CURSOR-WRAM:RETURN_CURSOR-WRAM+4], "big")
    if task_index >= ROWS:
        raise ValueError("captured task cursor is outside the 18-row table")
    row_base = TABLE + task_index * ROW_SIZE
    selected_alias = 0x2600A020 + slot * 4
    selected_physical = selected_alias - 0x20000000
    selected_pointer = int.from_bytes(work[selected_physical-WRAM:selected_physical-WRAM+4], "big")
    if work[row_base + 83-WRAM] == 0:
        raise ValueError("captured task row does not enter the AE3A eligibility path")

    reads, writes, pcs = [], [], []
    stack_writes = []
    saved_context = bytes(work[CONTEXT-WRAM:CONTEXT-WRAM+CONTEXT_SIZE])
    captured_resume = int.from_bytes(saved_context[36:40], "big")

    class Memory(emu.Memory):
        fetching = False
        current_pc = None
        def translate(self, address, width):
            for alias, physical in ALIASES.items():
                if alias <= address and address + width <= alias + 4:
                    return physical + address - alias
            return address
        def read(self, address, width):
            if self.fetching:
                if width != 2 or not any(lo <= address < hi for lo, hi in CODE_RANGES) or address & 1:
                    raise ValueError(f"PC fetch fence {address:08x}/{width}")
                return super().read(address, width)
            physical = self.translate(address, width)
            if physical != address:
                if width != 4:
                    raise ValueError(f"cache alias read width {width}")
                value = super().read(physical, width)
                reads.append(["cache_alias", address, width, value])
                return value
            if address in LITERALS and width == LITERALS[address]:
                value = super().read(address, width); reads.append(["literal", address, width, value]); return value
            if (address, width) in ((CALL_LITERAL, 4), (TABLE_LITERAL, 4), (SELECTOR_LITERAL, 4)):
                value = super().read(address, width); reads.append(["literal", address, width, value]); return value
            if address == RETURN_CURSOR and width == 4:
                value = super().read(address, width); reads.append(["task_cursor", address, width, value]); return value
            if address == selected_alias and width == 4:
                value = super().read(selected_physical, width); reads.append(["selected_vbr_pointer", address, width, value]); return value
            if TABLE <= address and address + width <= TABLE_END and width in (1, 4):
                value = super().read(address, width); reads.append(["task_table", address, width, value]); return value
            if CONTEXT <= address and address + width <= CONTEXT + CONTEXT_SIZE and width == 4:
                value = super().read(address, width); reads.append(["captured_context", address, width, value]); return value
            if address == 0x060BDDAC and width == 4:
                value = super().read(address, width); reads.append(["previous_counter", address, width, value]); return value
            if 0x060B3D4C <= address and address + width <= 0x060B3D54 and width == 4:
                value = super().read(address, width); reads.append(["scheduler_pointer", address, width, value]); return value
            if 0x060B3D54 <= address and address + width <= 0x060B3D5C and width == 4:
                value = super().read(address, width); reads.append(["scheduler_cursor", address, width, value]); return value
            if any(lo <= address and address + width <= hi for lo, hi in STACK_WINDOWS) and width == 4:
                value = super().read(address, width); reads.append(["stack", address, width, value]); return value
            raise ValueError(f"unexpected read at {self.current_pc!s}: {address:08x}/{width}")
        def write(self, address, width, value):
            value &= (1 << (8 * width)) - 1
            physical = self.translate(address, width)
            if physical != address:
                if width != 4:
                    raise ValueError(f"cache alias write width {width}")
                writes.append(["cache_alias", address, width, value])
                return super().write(physical, width, value)
            if TABLE <= address and address + width <= TABLE_END and width in (1, 4):
                writes.append(["task_table", address, width, value]); return super().write(address, width, value)
            if address == 0x060BDDAC and width == 4:
                writes.append(["previous_counter", address, width, value]); return super().write(address, width, value)
            if 0x060B3D54 <= address and address + width <= 0x060B3D5C and width == 4:
                writes.append(["scheduler_cursor", address, width, value]); return super().write(address, width, value)
            if any(lo <= address and address + width <= hi for lo, hi in STACK_WINDOWS) and width == 4:
                stack_writes.append([address, width, value]); writes.append(["stack", address, width, value])
                return super().write(address, width, value)
            regs = getattr(self, "current_registers", [])
            summary = {f"r{i}": hex(regs[i]) for i in (0, 2, 13, 14) if len(regs) > i}
            raise ValueError(f"unexpected write at {self.current_pc!s} after {getattr(self, 'current_steps', '?')} steps: {address:08x}/{width}/{value:08x}; registers={summary!r}")

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)
    class CPU(emu.CPU):
        def fetch(self, pc):
            if not any(lo <= pc < hi for lo, hi in CODE_RANGES) or pc & 1:
                raise ValueError(f"fetch escaped bounded original code {pc:08x}")
            memory.fetching = True
            try: return super().fetch(pc)
            finally: memory.fetching = False
        def exec(self, instruction, pc, in_slot=False):
            if self.steps > LIMIT or not any(lo <= pc < hi for lo, hi in CODE_RANGES):
                raise ValueError(f"instruction fence {pc:08x}")
            memory.current_pc = hex(pc)
            memory.current_registers = self.r.copy()
            memory.current_steps = self.steps
            pcs.append(pc)
            if pc == AB94 and not hasattr(self, "ab94_entry"):
                self.ab94_entry = {"r": self.r.copy(), "pr": self.pr, "mach": self.mach,
                                   "macl": self.macl, "sr": self.sr, "sp": self.r[15]}
                self.ab94_task_words = [int.from_bytes(mapped[row_base-WRAM+i:row_base-WRAM+i+4], "big")
                                        for i in (0, 4)]
                self.ab94_row_marker = mapped[row_base + 81-WRAM]
            if pc == RESTORE and not hasattr(self, "a186_entry"):
                self.a186_entry = {"r": self.r.copy(), "pr": self.pr, "mach": self.mach, "macl": self.macl}
            if pc == 0x0600AD38:
                self.ad38_entry = {"r": self.r.copy(), "pr": self.pr, "mach": self.mach,
                                   "macl": self.macl, "sr": self.sr}
            return super().exec(instruction, pc, in_slot=in_slot)
        def step(self):
            instruction = self.fetch(self.pc)
            needed = 2 if instruction.delay else 1
            if self.steps + needed > LIMIT:
                self.budget_stop = self.pc
                self.pc = emu.RETURN_SENTINEL
                return
            return super().step()

    cpu = CPU(memory)
    cpu.r = [(0x61000000 + i * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF for i in range(16)]
    cpu.r[11], cpu.r[15] = RETURN_CURSOR, SP
    cpu.vbr, cpu.sr = 0x06000000 + slot * 0x400, 0xF0
    cpu.mach, cpu.macl, cpu.pr, cpu.pc = 0x10203040 ^ seed, 0xA1B2C3D4 ^ seed, emu.RETURN_SENTINEL, CALL
    task_word_before = bytes(mapped[row_base-WRAM:row_base-WRAM+8])
    while cpu.pc != emu.RETURN_SENTINEL:
        if cpu.pc == emu.RETURN_SENTINEL:
            break
        if cpu.pc == RETURN_CURSOR:
            cpu.dynamic_stop = cpu.pc
            break
        if not any(lo <= cpu.pc < hi for lo, hi in CODE_RANGES):
            cpu.dynamic_stop = cpu.pc
            break
        cpu.step()

    if not hasattr(cpu, "ab94_entry"):
        raise ValueError("same-instance path did not execute original AB94")
    matching = selected_pointer == row_base
    expected_task_word = 0 if matching and not mutate else 1
    if cpu.ab94_task_words != [expected_task_word, expected_task_word]:
        raise ValueError(f"ACE8 task words at AB94 differ: {cpu.ab94_task_words!r}")
    if matching and not mutate and cpu.ab94_row_marker != 4:
        raise ValueError("AE3A row marker differs")
    if captured_resume != AB94:
        raise ValueError(f"captured saved PR is not AB94: {captured_resume:08x}")
    result = {"slot": slot, "seed": seed, "vbr": hex(cpu.vbr), "task_index": task_index,
              "row": hex(row_base), "selected_pointer": hex(selected_pointer),
              "matching_vbr_row": matching, "task_words_before": task_word_before.hex(),
              "task_words_at_ab94": [hex(x) for x in cpu.ab94_task_words],
              "row_marker_at_ab94": cpu.ab94_row_marker,
              "registers_at_ab94": [hex(x) for x in cpu.ab94_entry["r"]],
              "special_at_ab94": {k: hex(v) for k, v in cpu.ab94_entry.items() if k != "r"},
              "stop_pc": hex(getattr(cpu, "dynamic_stop", getattr(cpu, "budget_stop", cpu.pc))),
              "stop_reason": "nonresident_or_unapproved_dynamic_target" if hasattr(cpu, "dynamic_stop") else
                             "instruction_budget" if hasattr(cpu, "budget_stop") else "return_sentinel",
              "steps": cpu.steps, "pcs": pcs, "reads": reads, "writes": writes,
              "stack_writes": stack_writes, "a186_reached": hasattr(cpu, "a186_entry"),
              "ad38_reached": hasattr(cpu, "ad38_entry"),
              "registers_at_ad38": [hex(x) for x in cpu.ad38_entry["r"]] if hasattr(cpu, "ad38_entry") else None,
              "pr_at_ad38": hex(cpu.ad38_entry["pr"]) if hasattr(cpu, "ad38_entry") else None,
              "probe_mutation": mutate}
    return result

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args(argv)
    report = {"schema": "neptune.original-japan-a208-ab94-same-instance.v1", "status": "failure"}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        print(f"FAIL: exclusive private report path required: {e}"); return 1
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        try:
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            meta = json.loads(args.checkpoint.read_text())
            if (meta.get("frame") != 1200 or meta.get("state_sha256") != STATE_SHA or
                meta.get("identity", {}).get("core_sha256") != CORE_SHA or sha(state) != STATE_SHA):
                raise ValueError("frame-1200 state/checkpoint/core identity differs")
            kernel = pinned.read_bounded(args.kernel, SIZE)
            if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
                raise ValueError("original Japan kernel identity differs")
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
            emu = pinned.interpreter(args.saturn_recomp)
            results = [execute(kernel, ram, emu, slot, seed) for slot in SLOTS for seed in SEEDS]
            # The scheduler may branch on constructed R6/R7 seeds. Retain both traces;
            # do not assert seed-independent paths or side effects.
            pair = results
            pair_comparison = {
                "pc_trace_identical": pair[0]["pcs"] == pair[1]["pcs"],
                "read_events_identical": pair[0]["reads"] == pair[1]["reads"],
                "write_address_width_shape_identical": [(x[0], x[1], x[2]) for x in pair[0]["writes"]] ==
                                                       [(x[0], x[1], x[2]) for x in pair[1]["writes"]],
                "write_values_identical": pair[0]["writes"] == pair[1]["writes"]}
            report = {"schema": "neptune.original-japan-a208-ab94-same-instance.v1", "status": "success",
                      "release": "Japan T-14302G V1.000", "module": "KRNL", "cpu": "SH-2",
                      "source_mapping": hex(BASE), "source_kernel_sha256": KERNEL_SHA,
                      "code_ranges": [[hex(a), hex(b)] for a, b in CODE_RANGES],
                      "frame": 1200, "state_sha256": STATE_SHA, "normalized_workram_sha256": RAM_SHA,
                      "interpreter_revision": pinned.INTERPRETER_REVISION,
                      "interpreter_sources": pinned.SOURCE_HASHES, "instruction_limit": LIMIT,
                      "probe_sha256": sha(Path(__file__).read_bytes()),
                      "case_count": len(results), "seed_pair_comparison": pair_comparison, "results": results,
                      "contract": "Each case executes A208→AE3A→ACE8→A164→A186 and continues in the same CPU and memory instance at captured PR AB94. It runs until return, an unapproved/nonresident dynamic target, or the declared instruction bound.",
                      "limits": ["frame-1200 WorkRAM-H/task context and table words are captured; initial GPRs/stack and VBR slot selection are constructed",
                                 "a stop at BCC80 or another nonresident target is recorded before fetching it; no kernel-file bytes substitute for missing resident bytes",
                                 "no natural hardware task ownership, device timing, gameplay, other module, or whole-program claim"]}
        except Exception as e:
            report.update(error={"type": type(e).__name__, "reason": str(e)})
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("case_count", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1

if __name__ == "__main__":
    raise SystemExit(main())
