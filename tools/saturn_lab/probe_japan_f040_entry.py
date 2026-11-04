#!/usr/bin/env python3
"""Run a bounded, guarded Japan KRNL F040 entry diagnostic on captured RAM."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg

BASE = 0x06000000
KERNEL_BASE = 0x0600A000
RAM_SIZE = 0x100000
ENTRY = 0x0600F040
TASK_CURSOR = 0x060BCC80
STACK = 0x06002000
DEFAULT_INSTRUCTION_LIMIT = 1024
ALLOWED_INSTRUCTION_LIMITS = (1024, 2048, 4096, 8192)
SNAPSHOT_PCS = {0x06095C24, 0x06095C3A, 0x06095C60, 0x06095C78,
                0x06095C88, 0x0609DC10, 0x0609DC2E, 0x0609DC7C}
KERNEL_SHA256 = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA256 = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
WORKRAM_SHA256 = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA256 = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel: bytes, ram: bytes, emu, seed: int, instruction_limit: int) -> dict:
    work = bytearray(ram)
    reads: list[list[int]] = []
    writes: list[list[int]] = []
    pcs: list[int] = []
    snapshots: list[dict] = []

    class Memory(emu.Memory):
        fetching = False

        def read(self, address, width):
            if self.fetching:
                offset = address - KERNEL_BASE
                if width != 2 or not 0 <= offset <= len(kernel) - width:
                    raise ValueError(f"original code fetch fence {address:08x}/{width}")
                if work[address - BASE:address - BASE + width] != kernel[offset:offset + width]:
                    raise ValueError(f"captured code differs from original at {address:08x}")
            value = super().read(address, width)
            reads.append([address, width, value])
            return value

        def write(self, address, width, value):
            if width not in (1, 2, 4) or address < BASE or address + width > BASE + RAM_SIZE:
                raise ValueError(f"WorkRAM write fence {address:08x}/{width}")
            value &= (1 << (width * 8)) - 1
            writes.append([address, width, value])
            return super().write(address, width, value)

    memory = Memory()
    memory.add(BASE, len(work), work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= instruction_limit:
                raise ValueError("instruction budget")
            pcs.append(pc)
            if pc in SNAPSHOT_PCS:
                snapshots.append({"pc": hex(pc), "steps": self.steps,
                    "registers": [hex(value) for value in self.r],
                    "pr": hex(self.pr), "mach": hex(self.mach), "macl": hex(self.macl)})
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x61000000 + i * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF
             for i in range(16)]
    cpu.r[11] = TASK_CURSOR
    cpu.r[15] = STACK
    cpu.r[4] = int.from_bytes(work[TASK_CURSOR - BASE:TASK_CURSOR - BASE + 4], "big")
    cpu.vbr, cpu.sr = 0x06000000, 0xF0
    cpu.pr, cpu.pc = emu.RETURN_SENTINEL, ENTRY

    try:
        while cpu.pc != emu.RETURN_SENTINEL:
            cpu.step()
        stop = {"kind": "return_sentinel", "pc": hex(cpu.pc)}
    except Exception as error:
        stop = {"kind": "guard_or_budget", "type": type(error).__name__,
                "detail": str(error), "pc": hex(cpu.pc), "steps": cpu.steps}

    return {"seed": seed, "stop": stop, "steps": cpu.steps,
            "pcs": [hex(pc) for pc in pcs], "snapshots": snapshots,
            "reads": reads, "writes": writes,
            "final_registers": [hex(value) for value in cpu.r],
            "pr": hex(cpu.pr), "sr": hex(cpu.sr), "vbr": hex(cpu.vbr)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--instruction-limit", type=int, choices=ALLOWED_INSTRUCTION_LIMITS,
                        default=DEFAULT_INSTRUCTION_LIMIT)
    args = parser.parse_args(argv)

    report = {"schema": "neptune.japan-f040-entry-diagnostic.v1", "status": "failure"}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        print(f"FAIL: fresh private report path required: {error}")
        return 1

    with os.fdopen(fd, "w", encoding="utf-8") as output:
        try:
            kernel = pinned.read_bounded(args.kernel, 786432)
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            metadata = json.loads(args.checkpoint.read_text())
            if sha(kernel) != KERNEL_SHA256:
                raise ValueError("Japan original kernel identity differs")
            if (sha(state) != STATE_SHA256 or metadata.get("frame") != 1200 or
                    metadata.get("state_sha256") != STATE_SHA256 or
                    metadata.get("identity", {}).get("core_sha256") != CORE_SHA256):
                raise ValueError("frame-1200 state/checkpoint/core identity differs")
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", RAM_SIZE), "little")
            if sha(ram) != WORKRAM_SHA256:
                raise ValueError("normalized captured WorkRAM-H identity differs")
            emu = pinned.interpreter(args.saturn_recomp)
            results = [execute(kernel, ram, emu, seed, args.instruction_limit) for seed in (0, 1)]
            report.update(
                status="diagnostic_complete", release="Japan T-14302G V1.000", module="KRNL",
                cpu="SH-2", entry=hex(ENTRY), kernel_sha256=KERNEL_SHA256,
                state_sha256=STATE_SHA256, normalized_workram_sha256=WORKRAM_SHA256,
                interpreter_revision=pinned.INTERPRETER_REVISION,
                interpreter_sources=pinned.SOURCE_HASHES,
                instruction_limit=args.instruction_limit,
                probe_sha256=sha(Path(__file__).read_bytes()),
                initial_conditions=("Captured frame-1200 WorkRAM-H; constructed GPR seeds, "
                    "SP=0x06002000 and VBR=0x06000000; R4 seeded from captured task cursor word; "
                    "direct F040 entry, not a natural A20E return."),
                contract=("Executes original resident instructions from direct F040 entry while "
                    "allowing only captured WorkRAM reads/writes and source-matching kernel fetches. "
                    "A return, guard failure, or declared instruction bound is recorded."),
                limitations=["Constructed entry registers and stack; natural A20E caller is unresolved",
                    "No independent emulator, hardware timing, BIOS contract, gameplay, or full-program claim",
                    "Bounded diagnostic does not establish complete F040/F134/A946 behavior"],
                results=results,
                pair_comparison={
                    "pc_traces_identical": results[0]["pcs"] == results[1]["pcs"],
                    "reads_identical": results[0]["reads"] == results[1]["reads"],
                    "write_address_width_shapes_identical":
                        [(x[0], x[1]) for x in results[0]["writes"]] ==
                        [(x[0], x[1]) for x in results[1]["writes"]],
                    "write_values_identical": results[0]["writes"] == results[1]["writes"]})
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report),
                      "steps": [item.get("steps") for item in report.get("results", [])]}))
    return 0 if report["status"] == "diagnostic_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
