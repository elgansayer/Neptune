#!/usr/bin/env python3
"""Execute the captured Japan BIOS SYS_SETUINT target on pinned SH-2 bytes."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import probe_japan_a80e_table_update as source
import state_graphics as sg

WRAM, WRAM_SIZE = source.WRAM, source.WRAM_SIZE
STATE_SHA, RAM_SHA = source.STATE_SHA, source.RAM_SHA
CORE_SHA = source.CORE_SHA
ENTRY, CODE_END = 0x06000794, 0x060007A2
LITERAL_END = 0x060007B0
VECTOR_BASE, VECTOR_COUNT = 0x06000900, 64
BIOS_TARGET_OFFSET, BIOS_WINDOW = 0xD94, 64
LIMIT = 16

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def execute(ram: bytes, emu, index: int, value: int):
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("normalized frame-1200 Japan WorkRAM differs")
    work = bytearray(ram)
    writes, pcs = [], []
    slot = VECTOR_BASE + index * 4

    class Memory(emu.Memory):
        fetching = False
        def read(self, address, width):
            if self.fetching and (width != 2 or not ENTRY <= address < CODE_END):
                raise ValueError(f"fetch fence {address:08x}/{width}")
            if not self.fetching and not (ENTRY <= address and address + width <= LITERAL_END):
                raise ValueError(f"data read fence {address:08x}/{width}")
            return super().read(address, width)
        def write(self, address, width, written):
            if address != slot or width != 4:
                raise ValueError(f"write fence {address:08x}/{width}")
            writes.append([address, width, written & 0xffffffff])
            return super().write(address, width, written)

    mem = Memory()
    mapped = mem.add(WRAM, WRAM_SIZE, work)
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
    cpu.r[4], cpu.r[5] = index, value
    cpu.pr, cpu.pc = emu.RETURN_SENTINEL, ENTRY
    initial = int.from_bytes(mapped[slot-WRAM:slot-WRAM+4], "big")
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
    final = int.from_bytes(mapped[slot-WRAM:slot-WRAM+4], "big")
    if cpu.steps > LIMIT or len(writes) != 1 or writes[0][2] != final:
        raise ValueError("bounded call did not produce exactly one expected vector write")
    return {"index": index, "input_r5": value, "slot": hex(slot),
            "before": hex(initial), "after": hex(final), "pcs": [hex(pc) for pc in pcs],
            "steps_including_delay": cpu.steps, "writes": writes}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("state", "checkpoint", "saturn-recomp", "bios", "report"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args(argv)
    report = {"schema": "neptune.original-japan-bios-setuint.v1", "status": "failure"}
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
                raise ValueError("captured SYS_SETUINT bytes differ from original Japan BIOS")
            emu = pinned.interpreter(args.saturn_recomp)
            results = []
            for index, value in ((3, 0), (3, 1), (12, 0), (12, 1)):
                results.append(execute(ram, emu, index, value))
            for row in results:
                expected = 0x0600083C if row["input_r5"] == 0 else row["input_r5"]
                if int(row["after"], 16) != expected:
                    raise ValueError(f"vector result mismatch at {row['slot']}")
            report = {"schema": "neptune.original-japan-bios-setuint.v1", "status": "success",
                      "scope": "four bounded executions of byte-identical captured Japan BIOS target",
                      "target": hex(ENTRY), "frame": 1200, "state_sha256": STATE_SHA,
                      "normalized_workram_sha256": RAM_SHA,
                      "original_bios_sha256": sha(bios), "original_window_offset": hex(BIOS_TARGET_OFFSET),
                      "original_window_sha256": sha(original_window), "resident_window_sha256": sha(resident_window),
                      "interpreter_revision": pinned.INTERPRETER_REVISION,
                      "interpreter_sources": pinned.SOURCE_HASHES, "instruction_limit": LIMIT,
                      "results": results,
                      "conclusion": "For indices 3 and 12, R5=0 selects the embedded default address 0x0600083C; nonzero R5 is stored directly. Each case executes the original captured instructions including RTS delay slot.",
                      "limits": ["constructed input registers; no natural caller or startup call proven",
                                 "only target 0x06000794 and two vector slots covered; not BIOS-wide semantics",
                                 "pinned SH-2 interpreter semantics; not independent emulator or hardware parity"]}
        except Exception as e:
            report.update(error={"type": type(e).__name__, "reason": str(e)})
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1

if __name__ == "__main__":
    raise SystemExit(main())
