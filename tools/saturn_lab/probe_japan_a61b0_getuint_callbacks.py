#!/usr/bin/env python3
"""Execute the three original per-service callbacks installed by Japan A61B0."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import probe_japan_a717c_zero_divisor as source
import state_graphics as sg

KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
BIOS_SHA = "dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac"
WRAM, WRAM_SIZE = 0x06000000, 0x100000
KERNEL_BASE, KERNEL_SIZE = 0x0600A000, 786432
BIOS_ALIAS = 0x20000000
VBR, SP = 0x06000000, 0x06002000
STACK_BASE, STACK_SIZE = SP - 16, 16
RETURN = 0xFFFFFE00
FUNCTIONS = ((0x060A62D8, 0x060A6332), (0x060A6348, 0x060A63A2), (0x060A63B8, 0x060A6412))
SERVICES = (75, 74, 73)
SETUINT_SLOT, SETSINT_SLOT = 0x06000300, 0x06000310
GETUINT_GLOBAL, GETSINT_GLOBAL, FLAG_GLOBAL = 0x060FCD14, 0x060FCD20, 0x060FCD2C
SETUINT_STUB = 0x06000794
SETSINT_STUBS = (0x06000784, 0x06000786, 0x06000788, 0x0600078A,
                 0x0600078C, 0x0600078E, 0x06000790, 0x06000792)
SETUINT_STUBS = (0x06000794, 0x06000796, 0x06000798, 0x0600079A,
                 0x0600079C, 0x0600079E, 0x060007A0)
STUB_PCS = SETSINT_STUBS + SETUINT_STUBS
SR_VALUES, SEEDS = (0x030, 0x130, 0x230, 0x3F0), (0, 1)
MASK = 0xFFFFFFFF


class Fence(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def literal_layout(index):
    start, end = FUNCTIONS[index]
    service = SERVICES[index]
    return {
        start + 0x5A: (2, 0xFF0F),
        start + 0x5C: (4, FLAG_GLOBAL + index),
        start + 0x60: (4, SETUINT_SLOT),
        start + 0x64: (4, GETUINT_GLOBAL + index * 4),
        start + 0x68: (4, SETSINT_SLOT),
        start + 0x6C: (4, GETSINT_GLOBAL + index * 4),
    }


def corpus():
    # First family is the identity-checked captured WorkRAM-H; remaining families
    # exercise the original zero and nonzero service-setter branches.
    values = (("captured-frame1200", None, None),
              ("constructed-zero-defaults", 0, 0),
              ("constructed-nonzero-values", 0x0600083C, 0x0600087C))
    return [(i, sr, seed, name, getuint, getsint)
            for i in range(3) for sr in SR_VALUES for seed in SEEDS
            for name, getuint, getsint in values]


def execute(kernel, ram, bios, emu, index, sr, seed, input_name, getuint_value, getsint_value,
            mutate_vector=False):
    if index not in range(3) or sr not in SR_VALUES or seed not in SEEDS:
        raise ValueError("callback case outside declared corpus")
    if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA or sha(bios) != BIOS_SHA:
        raise ValueError("original Japan kernel or BIOS identity differs")
    if len(ram) != WRAM_SIZE:
        raise ValueError("complete frame-1200 WorkRAM-H is required")
    start, end = FUNCTIONS[index]
    if ram[start - WRAM:end - WRAM] != kernel[start - KERNEL_BASE:end - KERNEL_BASE]:
        raise ValueError("captured callback bytes differ from original Japan kernel")
    service = SERVICES[index]
    literals = literal_layout(index)
    for address, (width, expected) in literals.items():
        off = address - KERNEL_BASE
        if int.from_bytes(kernel[off:off + width], "big") != expected:
            raise ValueError(f"callback literal differs at {address:08x}")
    for slot, expected in ((SETUINT_SLOT, SETUINT_STUB), (SETSINT_SLOT, 0x06000784)):
        if int.from_bytes(ram[slot - WRAM:slot - WRAM + 4], "big") != expected:
            raise ValueError(f"captured setter vector differs at {slot:08x}")

    work = bytearray(ram)
    getuint_addr = GETUINT_GLOBAL + index * 4
    getsint_addr = GETSINT_GLOBAL + index * 4
    if input_name != "captured-frame1200":
        work[getuint_addr - WRAM:getuint_addr - WRAM + 4] = getuint_value.to_bytes(4, "big")
        work[getsint_addr - WRAM:getsint_addr - WRAM + 4] = getsint_value.to_bytes(4, "big")
    if mutate_vector:
        work[SETUINT_SLOT - WRAM:SETUINT_SLOT - WRAM + 4] = (0x06000702).to_bytes(4, "big")
    flag_addr = FLAG_GLOBAL + index
    selected_table = 0x06000900 + service * 4
    vbr_entry = VBR + service * 4
    getuint_value = int.from_bytes(work[getuint_addr - WRAM:getuint_addr - WRAM + 4], "big")
    getsint_value = int.from_bytes(work[getsint_addr - WRAM:getsint_addr - WRAM + 4], "big")
    default_service = int.from_bytes(bios[0x600 + service * 4:0x604 + service * 4], "big")
    if default_service == 0:
        raise ValueError("original BIOS default service word is zero")
    fallback_getuint = int.from_bytes(ram[0x060007AC - WRAM:0x060007B0 - WRAM], "big")
    if fallback_getuint == 0:
        raise ValueError("captured SYS_SETUINT fallback literal is zero")
    expected_table = getuint_value if getuint_value else fallback_getuint
    expected_vbr = getsint_value if getsint_value else default_service
    read_events, write_events, pcs = [], [], []
    function_start, function_end = FUNCTIONS[index]
    executable = lambda pc: function_start <= pc < function_end or pc in STUB_PCS

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not executable(address):
                    raise Fence(f"callback PC fence at {address:08x}/{width}")
                return super().read(address, width)
            if address in literals and literals[address][0] == width:
                value = literals[address][1]
                read_events.append(["original-kernel-literal", address, width, value]); return value
            if address in (SETUINT_SLOT, SETSINT_SLOT) and width == 4:
                value = super().read(address, width); read_events.append(["captured-setter-vector", address, width, value]); return value
            if address in (getuint_addr, getsint_addr) and width == 4:
                value = super().read(address, width)
                label = "getuint-global" if address == getuint_addr else "getsint-global"
                read_events.append([label, address, width, value]); return value
            if address in (0x060007A4, 0x060007A8, 0x060007AC) and width == 4:
                value = super().read(address, width); read_events.append(["captured-stub-literal", address, width, value]); return value
            if address == BIOS_ALIAS + 0x600 + service * 4 and width == 4:
                value = super().read(address, width); read_events.append(["original-bios-default", address, width, value]); return value
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                value = super().read(address, width); read_events.append(["constructed-caller-stack", address, width, value]); return value
            raise ValueError(f"unexpected callback read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= MASK
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                write_events.append(["stack", address, width, value]); return super().write(address, width, value)
            if address == selected_table and width == 4 and value == expected_table:
                write_events.append(["service-table", address, width, value]); return super().write(address, width, value)
            if address == vbr_entry and width == 4 and value == expected_vbr:
                write_events.append(["vbr", address, width, value]); return super().write(address, width, value)
            if address == flag_addr and width == 1 and value == 0:
                write_events.append(["status-clear", address, width, value]); return super().write(address, width, value)
            raise ValueError(f"unexpected callback write {address:08x}/{width}/{value:08x}")

    mem = Memory(); work_mem = mem.add(WRAM, WRAM_SIZE, work); mem.add(0, len(bios), bytearray(bios))

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try: return super().fetch(pc)
            finally: mem.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= 96 or not executable(pc): raise Fence(f"callback instruction fence at {pc:08x}")
            pcs.append(pc); return super().exec(instruction, pc, in_slot=in_slot)

    stack = bytearray((0xB1 + seed * 13 + n * 7) & 0xFF for n in range(STACK_SIZE))
    work[STACK_BASE - WRAM:SP - WRAM] = stack
    cpu = CPU(mem)
    cpu.r = [(0x34000000 + j * 0x01010307 + seed * 0x103) & MASK for j in range(16)]
    cpu.r[0], cpu.r[4], cpu.r[5] = 0xDEADBEEF, 0xF00D0000 + index, 0xBAD00000 + seed
    cpu.r[15], cpu.sr, cpu.vbr, cpu.pr, cpu.pc = SP, sr, VBR, RETURN, function_start
    before = bytes(work_mem)
    while cpu.pc != RETURN:
        cpu.step()
        if cpu.steps > 96: raise ValueError("callback instruction budget exceeded")
    if cpu.r[15] != SP or cpu.pr != RETURN or (cpu.sr & 0xF0) != (sr & 0xF0):
        raise ValueError("callback return SP/PR/SR contract differs")
    expected_writes = [["service-table", selected_table, 4, expected_table],
                       ["vbr", vbr_entry, 4, expected_vbr], ["status-clear", flag_addr, 1, 0]]
    expected_stack = [["stack", SP - 4, 4, RETURN], ["stack", SP - 12, 4, (sr >> 4) & 15],
                      ["stack", SP - 8, 4, flag_addr]]
    if (write_events[:3] != expected_stack or
            write_events[-4:] != [["status-clear", flag_addr, 1, 0], *expected_writes] or
            len(write_events) != 7):
        raise ValueError(f"callback write contract differs: {write_events!r}")
    expected_memory = bytearray(before)
    for label, address, width, value in write_events:
        off = address - WRAM; expected_memory[off:off + width] = value.to_bytes(width, "big")
    if bytes(work_mem) != bytes(expected_memory): raise ValueError("unlisted callback WorkRAM mutation")
    return {"index": index, "service": service, "entry": hex(function_start),
            "input_kind": input_name, "getuint_global": hex(getuint_value), "getsint_global": hex(getsint_value),
            "expected_table_value": hex(expected_table), "expected_vbr_value": hex(expected_vbr),
            "steps": cpu.steps, "pc_trace": [hex(x) for x in pcs], "reads": read_events,
            "writes": write_events, "sp_after_return": hex(cpu.r[15]), "pr_after_return": hex(cpu.pr),
            "sr_after_return": hex(cpu.sr), "workram_bytes_unchanged_outside_frame_and_three_original_stores": WRAM_SIZE - STACK_SIZE - 9}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "bios", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-a61b0-getuint-callbacks.v1", "status": "failure",
              "limits": ["Original callback bytes and captured SETUINT/SETSINT runtime stubs execute with constructed caller registers/stack",
                         "Capture-derived global inputs are labeled separately from synthetic branch controls",
                         "Runtime stubs are not proven BIOS-ROM copies; natural caller and device timing remain open"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text())
                state = pinned.read_bounded(args.state, source.STATE_MAX)
                if meta.get("frame") != 1200 or sha(state) != source.STATE_SHA or meta.get("state_sha256") != source.STATE_SHA:
                    raise ValueError("frame-1200 checkpoint/state identity differs")
                kernel = pinned.read_bounded(args.kernel, KERNEL_SIZE); bios = pinned.read_bounded(args.bios, 524288)
                if sha(kernel) != KERNEL_SHA or sha(bios) != BIOS_SHA:
                    raise ValueError("original Japan kernel or BIOS identity differs")
                parsed = sg.parse(state); raw = sg.field(parsed, "MAIN", "WorkRAMH", WRAM_SIZE); ram = sg.cpu_words(raw, "little")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for case in corpus():
                    index, sr, seed, name, getuint, getsint = case
                    if name == "captured-frame1200":
                        getuint = int.from_bytes(ram[GETUINT_GLOBAL + index * 4 - WRAM:GETUINT_GLOBAL + index * 4 - WRAM + 4], "big")
                        getsint = int.from_bytes(ram[GETSINT_GLOBAL + index * 4 - WRAM:GETSINT_GLOBAL + index * 4 - WRAM + 4], "big")
                    first = execute(kernel, ram, bios, emu, index, sr, seed, name, getuint, getsint)
                    second = execute(kernel, ram, bios, emu, index, sr, seed, name, getuint, getsint)
                    if first != second: raise ValueError("paired callback executions differ")
                    rows.append(first)
                try:
                    execute(kernel, ram, bios, emu, 0, SR_VALUES[0], SEEDS[0], "captured-frame1200", 0, 0, mutate_vector=True)
                except Fence as error:
                    if "pc fence" not in str(error).lower(): raise
                    mutation = {"rejected": True, "slot": hex(SETUINT_SLOT), "target": "0x06000702", "reason": str(error)}
                else: raise ValueError("mutated setter vector escaped callback PC fence")
                report.update(status="success", cases=len(rows), executions_per_case=2, results=rows,
                              results_sha256=sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
                              kernel_sha256=KERNEL_SHA, bios_sha256=BIOS_SHA, state_sha256=source.STATE_SHA,
                              normalized_workram_sha256=sha(ram), probe_sha256=sha(Path(__file__).read_bytes()),
                              callback_sha256={str(i): sha(kernel[a - KERNEL_BASE:b - KERNEL_BASE]) for i,(a,b) in enumerate(FUNCTIONS)},
                              setter_stub_sha256={"setuint": sha(ram[0x06000794 - WRAM:0x060007A4 - WRAM]),
                                                  "setsint": sha(ram[0x06000784 - WRAM:0x06000794 - WRAM])},
                              interpreter_revision="f20de940e8013fc84103a5b39c4069ed8071b1f9",
                              mutation_control=mutation)
            except Exception as e: report["error"] = {"type": type(e).__name__, "reason": str(e)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"})); return 2


if __name__ == "__main__":
    raise SystemExit(main())
