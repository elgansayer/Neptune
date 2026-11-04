#!/usr/bin/env python3
"""Execute Japan A6D6 until its strict SH7604 register model reaches an unlisted address."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned

BASE, SIZE = 0x0600A000, 786432
ENTRY, END = 0x0600A6D6, 0x0600A714
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
INTERPRETER_REVISION = "f20de940e8013fc84103a5b39c4069ed8071b1f9"
ONCHIP_WORDS = (0xFFFFFF80, 0xFFFFFF84, 0xFFFFFF88, 0xFFFFFF8C,
                0xFFFFFF90, 0xFFFFFF94, 0xFFFFFF98, 0xFFFFFF9C,
                0xFFFFFFB0)
DRCR = (0xFFFFFE71, 0xFFFFFE72)
CODE = tuple(range(ENTRY, END, 2))
LITERALS = {0x0600A746: (2, 0xFE73), 0x0600A748: (2, 0xFE71)}
LIMIT = 128


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class UnlistedRegister(ValueError):
    pass


def execute(kernel: bytes, emu, seed: int):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan 0KRNL.BIN identity differs")
    if seed not in (0, 1):
        raise ValueError("seed outside declared pair")
    registers = {address: 0 for address in ONCHIP_WORDS}
    events, pcs = [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in CODE:
                    raise ValueError(f"A6D6 PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and LITERALS[address][0] == width:
                return super().read(address, width)
            if address in registers and width == 4:
                value = registers[address]
                events.append(["read", f"{address:08x}", width, value])
                return value
            raise ValueError(f"unexpected A6D6 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            widths = {item: 4 for item in ONCHIP_WORDS}
            widths.update({item: 1 for item in DRCR})
            if address == 0xFFFFFFB8:
                raise UnlistedRegister(
                    f"unlisted SH7604 address write {address:08x}/{width}/{value:08x}")
            if address not in widths or widths[address] != width:
                raise ValueError(f"unexpected A6D6 write {address:08x}/{width}/{value:08x}")
            events.append(["write", f"{address:08x}", width, value])
            registers[address] = value

    memory = Memory()
    memory.add(BASE, SIZE, kernel)

    class CPU(emu.CPU):
        def fetch(self, pc):
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in CODE:
                raise ValueError(f"A6D6 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x19000000 + seed * 0x10000 + n * 0x10101) & 0xFFFFFFFF
             for n in range(16)]
    cpu.r[0] = 0
    cpu.r[15] = 0x06002000
    cpu.sr = 0xF0
    cpu.pr = emu.RETURN_SENTINEL
    cpu.pc = ENTRY
    try:
        while cpu.pc != emu.RETURN_SENTINEL:
            cpu.step()
    except UnlistedRegister as error:
        return {"seed": seed, "status": "retained_failure", "error": str(error),
                "steps": cpu.steps, "pc": hex(cpu.pc), "pc_trace": [hex(x) for x in pcs],
                "events": events}
    raise ValueError("A6D6 unexpectedly returned")


def run_pair(kernel: bytes, emu):
    first, second = execute(kernel, emu, 0), execute(kernel, emu, 1)
    strip_seed = lambda row: {k: v for k, v in row.items() if k != "seed"}
    if strip_seed(first) != strip_seed(second):
        raise ValueError("paired A6D6 traces differ")
    return first, second


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a6d6-dmac-boundary.v1",
              "status": "failure", "entry": hex(ENTRY),
              "limits": ["Direct constructed registers/entry; natural A546 reachability unproven",
                         "Listed SH7604 register behavior only; no DMA engine or hardware effects",
                         "Stops at FFFFFFB8, absent from the manual register map; never modeled as RAM"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                kernel = pinned.read_bounded(args.kernel, SIZE)
                emu = pinned.interpreter(args.saturn_recomp)
                rows = run_pair(kernel, emu)
                report.update(original_game_bytes_executed=True, release="Japan T-14302G V1.000",
                              source_file="0KRNL.BIN", cpu="master SH-2", code_range=[hex(ENTRY), hex(END)],
                              executions_per_case=2, runs=rows, paired_execution_traces_identical=True,
                              kernel_sha256=KERNEL_SHA, probe_sha256=sha(Path(__file__).read_bytes()),
                              interpreter_revision=INTERPRETER_REVISION,
                              interpreter_sources=pinned.SOURCE_HASHES,
                              contract="A6D6 executes original SH-2 instructions through documented DMAC register writes, then the RTS delay slot attempts a longword write at FFFFFFB8; the strict model stops because that address is not listed in the SH7604 register map.")
                report["status"] = "bounded_stop"
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "report": str(args.report)}))
        return 0 if report["status"] == "bounded_stop" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
