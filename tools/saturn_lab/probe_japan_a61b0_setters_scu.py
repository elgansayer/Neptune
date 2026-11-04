#!/usr/bin/env python3
"""Execute the original Japan A61B0 tail, BIOS setters and SCU write intent."""
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
ENTRY, END = 0x060A6236, 0x060A6280
BASE, SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
BIOS_MAP = 0x20000000
VBR = 0x06000000
SP, RETURN = 0x06002000, 0xFFFFFE00
STACK_BASE, STACK_SIZE = SP - 40, 40
SCU_BASE = 0x25FE0010
SCU_VALUE = 0x0101
SR_VALUES, SEEDS, INDICES = (0x030, 0x130), (0, 1), (0, 1, 2)
SERVICES = (75, 74, 73)
STUBS = (0x06000784, 0x06000786, 0x06000788, 0x0600078A,
         0x0600078C, 0x0600078E, 0x06000790, 0x06000792,
         0x06000794, 0x06000796, 0x06000798, 0x0600079A,
         0x0600079C, 0x0600079E, 0x060007A0)
LITERALS = {
    0x060A62C8: (4, 0x060FCD2C), 0x060A62CC: (4, 0x06000300),
    0x060A62D0: (4, 0x06000310), 0x060A62B4: (2, 0x0101),
    0x060A62D4: (4, SCU_BASE), 0x060A62B6: (2, 0xFF0F),
}
MASK = 0xFFFFFFFF


class Fence(ValueError):
    pass


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def corpus():
    return [(i, sr, seed) for i in INDICES for sr in SR_VALUES for seed in SEEDS]


def kernel_word(kernel: bytes, address: int, width: int) -> int:
    off = address - BASE
    value = int.from_bytes(kernel[off:off + width], "big")
    if len(kernel[off:off + width]) != width:
        raise ValueError("literal outside original kernel")
    return value


def execute(kernel: bytes, ram: bytes, bios: bytes, emu, index: int, sr: int, seed: int,
            mutate_scu: bool = False):
    if index not in INDICES or sr not in SR_VALUES or seed not in SEEDS:
        raise ValueError("A61B0 tail input outside declared corpus")
    if len(kernel) != SIZE or len(ram) != WRAM_SIZE or sha(kernel) != KERNEL_SHA or sha(bios) != BIOS_SHA:
        raise ValueError("original kernel, complete captured WorkRAM-H, or BIOS identity differs")
    if ram[ENTRY - WRAM:END - WRAM] != kernel[ENTRY - BASE:END - BASE]:
        raise ValueError("captured A61B0 tail differs from original kernel")
    service = SERVICES[index]
    selected = (0x060A62D8, 0x060A6348, 0x060A63B8)[index]
    flag_addr = 0x060FCD2C + index
    scu_addr = SCU_BASE + index * 32
    vbr_entry = VBR + service * 4
    setuint_slot, setsint_slot = 0x06000300, 0x06000310
    expected_getsint = int.from_bytes(ram[vbr_entry - WRAM:vbr_entry - WRAM + 4], "big")
    expected_bios = int.from_bytes(bios[0x600 + service * 4:0x604 + service * 4], "big")
    if expected_getsint == 0 or expected_bios == 0:
        raise ValueError("captured VBR or original BIOS default service entry is empty")
    for addr, width, expected in [(0x060A62C8, 4, 0x060FCD2C), (0x060A62CC, 4, setuint_slot),
                                  (0x060A62D0, 4, setsint_slot), (0x060A62B4, 2, SCU_VALUE),
                                  (0x060A62D4, 4, SCU_BASE), (0x060A62B6, 2, 0xFF0F)]:
        if mutate_scu and addr == 0x060A62D4:
            continue
        if kernel_word(kernel, addr, width) != expected:
            raise ValueError(f"A61B0 literal changed at {addr:08x}")
    for addr, expected in [(setuint_slot, 0x06000794), (setsint_slot, 0x06000784)]:
        if int.from_bytes(ram[addr - WRAM:addr - WRAM + 4], "big") != expected:
            raise ValueError(f"captured BIOS vector differs at {addr:08x}")

    work = bytearray(ram)
    if mutate_scu:
        work[0x060A62D4 - WRAM:0x060A62D8 - WRAM] = (SCU_BASE + 0x80).to_bytes(4, "big")
    stack = bytearray((0x37 + seed * 43 + n * 19) & 0xFF for n in range(STACK_SIZE))
    saved = {
        SP - 28: (sr >> 4) & 15,
        SP - 24: index * 4,
        SP - 20: RETURN,
        SP - 16: 0x7A000001 + seed,
        SP - 12: 0x7B000002 + seed,
        SP - 8: 0x7C000003 + seed,
        SP - 4: 0x7D000004 + seed,
    }
    for addr, value in saved.items():
        off = addr - STACK_BASE
        stack[off:off + 4] = value.to_bytes(4, "big")
    work[STACK_BASE - WRAM:SP - WRAM] = stack
    reads, writes, mmio, pcs = [], [], [], []
    code_pc = lambda pc: ENTRY <= pc < END or pc in STUBS

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not code_pc(address):
                    raise Fence(f"A61B0 tail PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and LITERALS[address][0] == width:
                value = (super().read(address, width) if mutate_scu and address == 0x060A62D4
                         else LITERALS[address][1])
                reads.append(["kernel-literal", address, width, value]); return value
            if address in (setuint_slot, setsint_slot) and width == 4:
                value = super().read(address, width); reads.append(["captured-vector", address, width, value]); return value
            if address == BIOS_MAP + 0x600 + service * 4 and width == 4:
                value = super().read(address, width); reads.append(["original-bios-default", address, width, value]); return value
            if address in (0x060007A4, 0x060007A8) and width == 4:
                value = super().read(address, width); reads.append(["captured-stub-literal", address, width, value]); return value
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                value = super().read(address, width); reads.append(["constructed-frame", address, width, value]); return value
            raise ValueError(f"unexpected A61B0 tail read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= MASK
            if address == scu_addr and width == 4 and value == SCU_VALUE:
                mmio.append([address, width, value]); return
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                writes.append(["constructed-frame", address, width, value]); return super().write(address, width, value)
            if address == 0x060FCD20 + index * 4 and width == 4 and value == expected_getsint:
                writes.append(["getsint-result", address, width, value]); return super().write(address, width, value)
            if address == flag_addr and width == 1 and value == 1:
                writes.append(["request-flag", address, width, value]); return super().write(address, width, value)
            if address == 0x06000900 + service * 4 and width == 4 and value == selected:
                writes.append(["sys-setuint-table", address, width, value]); return super().write(address, width, value)
            if address == vbr_entry and width == 4 and value == expected_bios:
                writes.append(["sys-setsint-vbr", address, width, value]); return super().write(address, width, value)
            raise ValueError(f"unexpected A61B0 tail write {address:08x}/{width}/{value:08x}")

    mem = Memory()
    work_mem = mem.add(WRAM, WRAM_SIZE, work)
    # The pinned SH-2 Memory folds the 0x2 cache-through alias onto physical ROM.
    mem.add(0, len(bios), bytearray(bios))

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try: return super().fetch(pc)
            finally: mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 64 or not code_pc(pc): raise Fence(f"A61B0 tail instruction fence {pc:08x}")
            pcs.append(pc); return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x43000000 + j * 0x01010107 + seed * 0x101) & MASK for j in range(16)]
    cpu.r[0], cpu.r[1], cpu.r[2] = expected_getsint, 0x06000774, 0
    cpu.r[4], cpu.r[5], cpu.r[8] = service, 0, 0x060FCD20 + index * 4
    cpu.r[12], cpu.r[13], cpu.r[14] = selected, index, service
    cpu.r[15], cpu.sr, cpu.vbr, cpu.pr, cpu.pc = SP - 28, 0xF0, VBR, ENTRY, ENTRY
    before = bytes(work_mem)
    while cpu.pc != RETURN:
        cpu.step()
        if cpu.steps > 64: raise ValueError("A61B0 tail instruction budget exceeded")

    expected_final = bytearray(before)
    for label, address, width, value in writes:
        off = address - WRAM
        expected_final[off:off + width] = value.to_bytes(width, "big")
    if bytes(work_mem) != bytes(expected_final): raise ValueError("unlisted WorkRAM-H mutation")
    if cpu.r[15] != SP or cpu.pr != RETURN or (cpu.sr & 0xF0) != (sr & 0xF0):
        raise ValueError("A61B0 tail return SP/PR/SR differs")
    expected_writes = [
        ["getsint-result", 0x060FCD20 + index * 4, 4, expected_getsint],
        ["request-flag", flag_addr, 1, 1],
        ["sys-setuint-table", 0x06000900 + service * 4, 4, selected],
        ["sys-setsint-vbr", vbr_entry, 4, expected_bios],
    ]
    if writes != expected_writes or mmio != [[scu_addr, 4, SCU_VALUE]]:
        raise ValueError(f"A61B0 stores/MMIO differ: writes={writes!r} mmio={mmio!r}")
    return {"index": index, "sr_input": sr, "seed": seed, "service": service,
            "steps": cpu.steps, "pc_trace": [hex(pc) for pc in pcs], "reads": reads,
                              "writes": writes, "mmio_write_intents": mmio, "bios_default": hex(expected_bios),
            "getsint_value": hex(expected_getsint), "selected_table_pointer": hex(selected),
            "vbr_after_set": hex(expected_bios), "sp_after_return": hex(cpu.r[15]),
            "pr_after_return": hex(cpu.pr), "sr_after_return": hex(cpu.sr),
            "workram_bytes_unchanged_outside_declared_stores": WRAM_SIZE - 4 - 1 - 4 - 4}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "bios", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-a61b0-setters-scu.v1", "status": "failure",
              "entry": hex(ENTRY), "stop": hex(END), "limits": [
                  "Continuation starts at original A61B0 PC 0x060A6236 with a constructed frame/register state consistent with the preceding actual SYS_GETSINT return",
                  "Uses actual captured SYS_SETUINT/SYS_SETSINT vectors and frame-1200 WorkRAM-H plus the supplied original BIOS image",
                  "SCU D0EN write is retained as an MMIO write intent; no SCU hardware effects or completion are emulated",
                  "Captured runtime stubs are not claimed as BIOS-ROM copies; natural A70B8 reachability remains unproven"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text())
                state = pinned.read_bounded(args.state, source.STATE_MAX)
                if meta.get("frame") != 1200 or sha(state) != source.STATE_SHA or meta.get("state_sha256") != source.STATE_SHA:
                    raise ValueError("frame-1200 checkpoint/state identity differs")
                kernel = pinned.read_bounded(args.kernel, SIZE); bios = pinned.read_bounded(args.bios, 524288)
                if sha(kernel) != KERNEL_SHA or sha(bios) != BIOS_SHA: raise ValueError("original kernel or BIOS SHA-256 differs")
                raw = sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE); ram = sg.cpu_words(raw, "little")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for index, sr, seed in corpus():
                    a = execute(kernel, ram, bios, emu, index, sr, seed)
                    b = execute(kernel, ram, bios, emu, index, sr, seed)
                    if a != b: raise ValueError("paired A61B0 tail executions differ")
                    rows.append(a)
                try:
                    execute(kernel, ram, bios, emu, 0, SR_VALUES[0], SEEDS[0], mutate_scu=True)
                except ValueError as error:
                    if not str(error).lower().startswith("unexpected a61b0 tail write 25fe0090/4/"):
                        raise ValueError("wrong-SCU-address mutation failed outside MMIO contract") from error
                    mutation = {"rejected": True, "changed_literal": "0x060A62D4",
                                "replacement": "0x25FE0090", "reason": str(error)}
                else:
                    raise ValueError("wrong SCU address passed the MMIO contract")
                report.update(status="success", cases=len(rows), executions_per_case=2, results=rows,
                              results_sha256=sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
                              kernel_sha256=KERNEL_SHA, bios_sha256=BIOS_SHA, state_sha256=source.STATE_SHA,
                              normalized_workram_sha256=sha(ram), probe_sha256=sha(Path(__file__).read_bytes()),
                              tail_sha256=sha(kernel[ENTRY - BASE:END - BASE]),
                              setuint_stub_sha256=sha(ram[0x06000794 - WRAM:0x060007A4 - WRAM]),
                              setsint_stub_sha256=sha(ram[0x06000784 - WRAM:0x06000794 - WRAM]),
                              interpreter_revision="f20de940e8013fc84103a5b39c4069ed8071b1f9",
                              index_service_pairs=[[i, SERVICES[i]] for i in INDICES],
                              mutation_control=mutation)
            except Exception as e:
                report["error"] = {"type": type(e).__name__, "reason": str(e)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
