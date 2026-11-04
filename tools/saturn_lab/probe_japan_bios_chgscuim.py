#!/usr/bin/env python3
"""Execute the captured Japan BIOS SYS_CHGSCUIM target on pinned SH-2 bytes."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import probe_japan_a80e_table_update as source
import state_graphics as sg

WRAM, WRAM_SIZE = source.WRAM, source.WRAM_SIZE
STATE_SHA, RAM_SHA, CORE_SHA = source.STATE_SHA, source.RAM_SHA, source.CORE_SHA
ENTRY, CODE_END = 0x060007C0, 0x060007E6
VECTOR_SLOT, SCU_IMS = 0x06000348, 0x25FE00A0
BIOS_TARGET_OFFSET, BIOS_WINDOW = 0xDC0, 64
LIMIT = 32
CASES = ((0x0000FFFF, 0), (0x00007FFF, 1), (0, 0x00008000), (0x00000FFF, 0x00001000))

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def execute(ram: bytes, emu, r4: int, r5: int, initial_sr: int):
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("normalized frame-1200 Japan WorkRAM differs")
    work = bytearray(ram)
    writes, pcs = [], []
    allowed_mmio = {SCU_IMS, SCU_IMS + 4, SCU_IMS + 8}

    class Memory(emu.Memory):
        fetching = False
        def read(self, address, width):
            if self.fetching:
                if width != 2 or not ENTRY <= address < CODE_END:
                    raise ValueError(f"fetch fence {address:08x}/{width}")
            elif (address, width) not in {
                (0x06000828, 2), (0x060007EC, 4), (0x060007E8, 4),
                (VECTOR_SLOT, 4)}:
                raise ValueError(f"data read fence {address:08x}/{width}")
            return super().read(address, width)
        def write(self, address, width, value):
            if width != 4 or (address != VECTOR_SLOT and address not in allowed_mmio):
                raise ValueError(f"write fence {address:08x}/{width}")
            writes.append([hex(address), width, value & 0xffffffff])
            return super().write(address, width, value)

    mem = Memory()
    mapped = mem.add(WRAM, WRAM_SIZE, work)
    scu = mem.add(0x05FE00A0, 12, bytes.fromhex("a5a5a5a55a5a5a5ac3c3c3c3"))
    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False
        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or not ENTRY <= pc < CODE_END:
                raise ValueError(f"instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r[4], cpu.r[5], cpu.sr = r4, r5, initial_sr
    cpu.pr, cpu.pc = emu.RETURN_SENTINEL, ENTRY
    slot_before = int.from_bytes(mapped[VECTOR_SLOT-WRAM:VECTOR_SLOT-WRAM+4], "big")
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
    slot_after = int.from_bytes(mapped[VECTOR_SLOT-WRAM:VECTOR_SLOT-WRAM+4], "big")
    signed_control = ((r4 | r5) & 0xffff)
    signed_control = signed_control - 0x10000 if signed_control & 0x8000 else signed_control
    expected_slot = ((slot_before & r4) | r5) & 0xffffffff
    expected = [[hex(VECTOR_SLOT), 4, expected_slot],
                [hex(SCU_IMS), 4, expected_slot],
                [hex(SCU_IMS+4), 4, signed_control & 0xffffffff]]
    if signed_control >= 0:
        expected.append([hex(SCU_IMS+8), 4, 1])
    if (cpu.steps > LIMIT or writes != expected or slot_after != expected_slot or cpu.sr != initial_sr):
        raise ValueError(f"SYS_CHGSCUIM state mismatch: writes={writes!r}, expected={expected!r}, SR={cpu.sr:04x}")
    return {"r4_in": hex(r4), "r5_in": hex(r5), "sr_in": hex(initial_sr),
            "sr_out": hex(cpu.sr), "vector_before": hex(slot_before),
            "vector_after": hex(slot_after), "pcs": [hex(pc) for pc in pcs],
            "steps_including_delay": cpu.steps, "writes": writes,
            "scu_mmio_after": [scu[i:i+4].hex() for i in (0, 4, 8)]}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("state", "checkpoint", "saturn-recomp", "bios", "report"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args(argv)
    report = {"schema": "neptune.original-japan-bios-chgscuim.v1", "status": "failure"}
    with args.report.open("x", encoding="utf-8") as out:
        try:
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            meta = json.loads(args.checkpoint.read_text())
            if (sha(state) != STATE_SHA or meta.get("state_sha256") != STATE_SHA or
                    meta.get("frame") != 1200 or meta.get("identity", {}).get("core_sha256") != CORE_SHA):
                raise ValueError("captured frame-1200 checkpoint identity mismatch")
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
            bios = pinned.read_bounded(args.bios, 512 * 1024)
            original_window = bios[BIOS_TARGET_OFFSET:BIOS_TARGET_OFFSET+BIOS_WINDOW]
            resident_window = ram[ENTRY-WRAM:ENTRY-WRAM+BIOS_WINDOW]
            if sha(original_window) != sha(resident_window):
                raise ValueError("captured SYS_CHGSCUIM bytes differ from original Japan BIOS")
            emu = pinned.interpreter(args.saturn_recomp)
            results = [execute(ram, emu, a, b, 0xA1) for a, b in CASES]
            report = {"schema": "neptune.original-japan-bios-chgscuim.v1", "status": "success",
                      "scope": "four bounded executions of byte-identical captured Japan BIOS target",
                      "target": hex(ENTRY), "frame": 1200, "state_sha256": STATE_SHA,
                      "normalized_workram_sha256": RAM_SHA,
                      "original_bios_sha256": sha(bios), "original_window_offset": hex(BIOS_TARGET_OFFSET),
                      "original_window_sha256": sha(original_window), "resident_window_sha256": sha(resident_window),
                      "interpreter_revision": pinned.INTERPRETER_REVISION,
                      "interpreter_sources": pinned.SOURCE_HASHES, "instruction_limit": LIMIT,
                      "constructed_scu_mmio_seed": "a5a5a5a55a5a5a5ac3c3c3c3", "results": results,
                      "conclusion": "The bounded target applies (old vector word & R4) | R5 to vector slot 0x06000348 and SCU.IMS; writes sign-extended low-word (R4 | R5) to IMS+4; and writes 1 to IMS+8 only when that low word is nonnegative. The input SR is restored.",
                      "limits": ["constructed registers and MMIO backing; no natural caller or device timing proof",
                                 "only target 0x060007C0 covered; not BIOS-wide semantics",
                                 "pinned SH-2 interpreter only; no independent emulator or hardware parity"]}
        except Exception as e:
            report.update(error={"type": type(e).__name__, "reason": str(e)})
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1

if __name__ == "__main__":
    raise SystemExit(main())
