#!/usr/bin/env python3
"""Execute original Japan AE98's VBR-selected two-longword record store."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a80e_table_update as a80e

BASE, SIZE = a80e.BASE, a80e.SIZE
WRAM, WRAM_SIZE = a80e.WRAM, a80e.WRAM_SIZE
ENTRY, END = 0x0600AE98, 0x0600AEAE
LITERAL, ALIAS = 0x0600AF08, 0x2600A020
TABLE, ROW_SIZE = a80e.TABLE, a80e.ROW_SIZE
SP, LIMIT = 0x06002000, 32
KERNEL_SHA, STATE_SHA, RAM_SHA, CORE_SHA = (
    a80e.KERNEL_SHA, a80e.STATE_SHA, a80e.RAM_SHA, a80e.CORE_SHA)
SLOTS, SEEDS = (0, 1), (0, 1)
SELECTED_ROWS = {0: 3, 1: 12}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel, ram, emu, slot, seed, mutate=False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan kernel identity differs")
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("captured frame-1200 WorkRAM-H identity differs")
    if ram[ENTRY-WRAM:END-WRAM] != kernel[ENTRY-BASE:END-BASE]:
        raise ValueError("captured AE98 bytes differ from original source")
    if slot not in SLOTS or seed not in SEEDS:
        raise ValueError("VBR slot or seed outside declared corpus")

    selected_alias = ALIAS + slot * 4
    selected_phys = selected_alias - 0x20000000
    row_base = TABLE + SELECTED_ROWS[slot] * ROW_SIZE
    work = bytearray(ram)
    work[0x0600A020-WRAM:0x0600A024-WRAM] = (TABLE + 3 * ROW_SIZE).to_bytes(4, "big")
    work[0x0600A024-WRAM:0x0600A028-WRAM] = (TABLE + 12 * ROW_SIZE).to_bytes(4, "big")
    before_words = (0x11223344 ^ seed, 0x55667788 ^ (seed << 8))
    work[row_base + 12-WRAM:row_base + 16-WRAM] = before_words[0].to_bytes(4, "big")
    work[row_base + 16-WRAM:row_base + 20-WRAM] = before_words[1].to_bytes(4, "big")
    if mutate:
        work[0x0600AEAC-WRAM:0x0600AEAE-WRAM] = (0x1644).to_bytes(2, "big")
    reads, writes, pcs = [], [], []

    class Memory(emu.Memory):
        def read(self, address, width):
            if self.fetching:
                if width != 2 or not ENTRY <= address < END or address & 1:
                    raise ValueError(f"AE98 PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address == LITERAL and width == 4:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if address == selected_alias and width == 4:
                value = super().read(selected_phys, width)
                reads.append(["selected_cache_alias", address, width, value])
                return value
            raise ValueError(f"unexpected AE98 read {address:08x}/{width}")

        def write(self, address, width, value):
            if (address, width) not in ((row_base + 12, 4), (row_base + 16, 4)):
                raise ValueError(f"unexpected AE98 write {address:08x}/{width}; reads={reads}")
            writes.append([address, width, value & 0xFFFFFFFF])
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= LIMIT or not ENTRY <= pc < END:
                raise ValueError(f"AE98 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x51000000 + i * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF
             for i in range(16)]
    cpu.r[4] = 0xA4000000 | (slot << 12) | seed
    cpu.r[5] = 0xB5000000 | (slot << 12) | (seed << 4) | 3
    cpu.r[15] = SP
    cpu.vbr, cpu.sr = 0x06000000 + slot * 0x400, 0xF0
    cpu.mach, cpu.macl, cpu.pr = 0x10203040 ^ seed, 0xA1B2C3D4 ^ seed, emu.RETURN_SENTINEL
    before_r, before_pr = cpu.r.copy(), cpu.pr
    cpu.call(ENTRY, max_steps=LIMIT)
    expected_words = (cpu.r[4], cpu.r[4] if mutate else cpu.r[5])
    actual_words = tuple(int.from_bytes(mapped[row_base + off-WRAM:row_base + off-WRAM+4], "big")
                          for off in (12, 16))
    if actual_words != expected_words:
        raise ValueError("AE98 selected-row stores differ from source/delay-slot values")
    if len(writes) != 2 or [w[0] for w in writes] != [row_base + 12, row_base + 16]:
        raise ValueError("AE98 write order or selected row differs")
    if cpu.r[15] != SP or cpu.pr != before_pr or cpu.mach != (0x10203040 ^ seed) or cpu.macl != (0xA1B2C3D4 ^ seed):
        raise ValueError("AE98 changed stack, PR, MACH, or MACL")
    if any(cpu.r[i] != before_r[i] for i in set(range(16)) - {0, 6}):
        raise ValueError("AE98 changed an undeclared general register")
    if any((a, n) not in ((row_base + 12, 4), (row_base + 16, 4)) for a, n, _ in writes):
        raise ValueError("AE98 write escaped selected record")
    return {"slot": slot, "seed": seed, "vbr": hex(cpu.vbr), "row": hex(row_base),
            "steps": cpu.steps, "pc_visits": pcs, "reads": reads, "writes": writes,
            "before_words": [hex(v) for v in before_words],
            "after_words": [hex(v) for v in actual_words],
            "original_bytes_executed": not mutate, "mutation": mutate}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-ae98-vbr-record-store.v1", "status": "failure",
              "release": "Japan T-14302G V1.000", "module": "KRNL", "cpu": "SH-2",
              "mapping": hex(BASE), "entry": hex(ENTRY), "code_range": [hex(ENTRY), hex(END)],
              "literal": {"address": hex(LITERAL), "value": hex(ALIAS)},
              "limits": ["Constructed VBR-selected task-row pointers, destination words and registers",
                         "Exact cache-through read alias; only selected row offsets +12/+16 writable",
                         "No natural caller, context lifetime, device, timing, gameplay or full-game claim"]}
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
            if results[0]["after_words"] == mutated["after_words"]:
                raise ValueError("AEAC source-register mutation survived the delay-slot control")
            report.update(status="success", original_game_bytes_executed=True,
                          original_executions=len(results), results=results,
                          mutation_control={"pc": "0x0600AEAC", "original": "0x1654",
                                            "replacement": "0x1644", "r5_delay_value_rejected": True,
                                            "mutated_writes": mutated["writes"]},
                          kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                          normalized_workram_sha256=RAM_SHA,
                          probe_sha256=sha(Path(__file__).read_bytes()),
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          contract="AE98 uses VBR bit 2 to select one cache-through pointer from 0x2600A020/24, stores R4 at selected row +12, then stores R5 at +16 in the RTS delay slot. It clobbers R0/R6; stack, PR, MACH/MACL and other GPRs are preserved.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("original_executions", 0),
                      "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
