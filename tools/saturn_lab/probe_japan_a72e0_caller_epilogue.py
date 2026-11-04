#!/usr/bin/env python3
"""Execute the original A72E0 epilogue after its A717C call returns."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source

ENTRY, CODE_END, STOP = 0x060A72FE, 0x060A7306, 0x060A73B8
STACK, FINAL_SP = 0x06007F84, 0x06007FA0
SAVED_PR = 0x060A73B8
PCS = (0x060A72FE, 0x060A7300, 0x060A7302, 0x060A7304)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(ram: bytes, emu):
    work = bytearray(ram)
    work[STACK + 24 - source.WORKRAM_BASE:STACK + 28 - source.WORKRAM_BASE] = SAVED_PR.to_bytes(4, "big")
    before = bytes(work)
    reads, pcs = [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in PCS:
                    raise ValueError(f"A72E0 epilogue PC fence at {address:08x}/{width}")
                return super().read(address, width)
            if address == STACK + 24 and width == 4:
                value = super().read(address, width)
                reads.append(["saved-outer-pr", address, width, value])
                return value
            raise ValueError(f"unexpected A72E0 epilogue data read {address:08x}/{width}")

        def write(self, address, width, value):
            raise ValueError(f"unexpected A72E0 epilogue write {address:08x}/{width}")

    mem = Memory()
    work_mem = mem.add(source.WORKRAM_BASE, source.WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 8 or pc not in PCS:
                raise ValueError(f"A72E0 epilogue instruction fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x24680000 + i * 0x00010203) & 0xFFFFFFFF for i in range(16)]
    cpu.r[15], cpu.pr, cpu.pc = STACK, 0x060A72FE, ENTRY
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > 8:
            raise ValueError("A72E0 epilogue instruction budget exceeded")
    if tuple(pcs) != PCS or reads != [["saved-outer-pr", STACK + 24, 4, SAVED_PR]]:
        raise ValueError("A72E0 epilogue trace or saved-PR read differs")
    if cpu.r[15] != FINAL_SP or cpu.pr != SAVED_PR or cpu.pc != STOP:
        raise ValueError("A72E0 epilogue restored PR/SP/return target differs")
    after = bytes(work_mem)
    if after != before:
        raise ValueError("A72E0 epilogue modified WorkRAM")
    return {"entry_sp": hex(STACK), "saved_outer_pr": hex(SAVED_PR),
        "reads": reads, "pc_trace": [hex(pc) for pc in pcs], "steps": cpu.steps,
        "pr_after": hex(cpu.pr), "sp_after": hex(cpu.r[15]),
        "return_pc": hex(cpu.pc), "workram_unchanged_bytes": len(after)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a72e0-caller-epilogue.v1",
        "status": "failure", "entry": hex(ENTRY), "code_end_exclusive": hex(CODE_END),
        "stop": hex(STOP), "limits": ["Original four-instruction epilogue only",
            "Stack word and outer PR are staged from the bounded caller contract"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                metadata = json.loads(args.checkpoint.read_text())
                if metadata.get("frame") != 1200 or metadata.get("identity", {}).get("core_sha256") != source.CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, source.STATE_MAX)
                if sha(state) != source.STATE_SHA or metadata.get("state_sha256") != source.STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, source.KERNEL_SIZE)
                if len(kernel) != source.KERNEL_SIZE or sha(kernel) != source.KERNEL_SHA:
                    raise ValueError("original Japanese kernel identity differs")
                parsed = sg.parse(state)
                ram = sg.cpu_words(sg.field(parsed, "MAIN", "WorkRAMH", source.WORKRAM_SIZE), "little")
                if sha(ram) != source.RAM_SHA:
                    raise ValueError("frame-1200 WorkRAM-H identity differs")
                if ram[ENTRY-source.WORKRAM_BASE:CODE_END-source.WORKRAM_BASE] != kernel[ENTRY-source.BASE:CODE_END-source.BASE]:
                    raise ValueError("captured epilogue differs from original kernel")
                emu = pinned.interpreter(args.saturn_recomp)
                first, second = execute(ram, emu), execute(ram, emu)
                if first != second:
                    raise ValueError("paired A72E0 epilogue executions differ")
                results = json.dumps(first, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=1, executions_per_case=2,
                    results=first, results_sha256=sha(results), probe_sha256=sha(Path(__file__).read_bytes()),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA,
                    source_sha256=sha(kernel[ENTRY-source.BASE:CODE_END-source.BASE]),
                    interpreter_revision=pinned.INTERPRETER_REVISION, interpreter_sources=pinned.SOURCE_HASHES)
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as error:
        print(f"FAIL: use a fresh report path: {error}")
        return 1
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
