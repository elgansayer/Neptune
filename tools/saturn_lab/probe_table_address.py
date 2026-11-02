#!/usr/bin/env python3
"""Compare a table-address hypothesis with one pinned original SH-2 function.

No game bytes are bundled. A successful run is isolated original-byte evidence,
not natural caller validation, whole-game recovery or hardware/timing parity.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import probe_kernel as pinned

ENTRY = 0x0600B934
MAX_STEPS = 256
MASK = 0xFFFFFFFF
EXPERIMENT = "EXP-SAT-CODE-002"
SOURCE_REVISION = "c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3"
SOURCE_BLOB = "6aba3320e95f988d4424ce5a10c77ee29ed46ab1"
REGISTERS = tuple(f"r{i}" for i in range(16)) + ("sr", "gbr", "vbr", "mach", "macl", "pr")


def candidate(n: int, m: int) -> int:
    """Pinned upstream C hypothesis, expressed with explicit 32-bit arithmetic."""
    return ((10 * n + m) * 152 + 0x00207F74) & MASK


def inputs() -> list[tuple[str, int, int]]:
    ordinary = (0, 1, 2, 9, 10, 63, 100, 255, 999, 1000)
    boundary = (0, 1, 0x7FFF, 0x8000, 0xFFFF, 0x10000,
                0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF)
    result = [("upstream-sample-domain", n, m) for n in ordinary for m in ordinary]
    seen = {(n, m) for _, n, m in result}
    result.extend(("constructed-32-bit-boundary", n, m)
                  for n in boundary for m in boundary if (n, m) not in seen)
    return result


def exercise(call) -> dict:
    cases = inputs()
    if (len(cases) != 196 or len({(n, m) for _, n, m in cases}) != 196
            or sum(kind == "upstream-sample-domain" for kind, _, _ in cases) != 100
            or sum(kind == "constructed-32-bit-boundary" for kind, _, _ in cases) != 96):
        raise ValueError("Probe requires its complete nonempty 100+96-case selection")
    rows, visited, changed = [], set(), set()
    mutations = {"changed_stride": 0, "changed_base": 0, "swapped_arguments": 0}
    for kind, n, m in cases:
        if any(type(value) is not int or not 0 <= value <= MASK for value in (n, m)):
            raise ValueError("Arguments must be unsigned 32-bit register values")
        observed = call(n, m)
        result, steps = observed["result"], observed["instructions"]
        pcs, registers = observed["pcs"], observed["changed_registers"]
        if type(result) is not int or result != candidate(n, m):
            raise ValueError(f"Result mismatch for n=0x{n:08x}, m=0x{m:08x}")
        if type(steps) is not int or not 0 < steps <= MAX_STEPS:
            raise ValueError("Missing or invalid bounded instruction count")
        if (not isinstance(pcs, list) or len(pcs) != steps
                or any(type(pc) is not int or pc % 2 or not pinned.BASE <= pc < pinned.BASE + pinned.SIZE for pc in pcs)):
            raise ValueError("Missing, out-of-module or inconsistent executed-PC evidence")
        if (not isinstance(registers, list) or len(set(registers)) != len(registers)
                or any(name not in REGISTERS for name in registers)
                or observed.get("return_sentinel_reached") is not True):
            raise ValueError("Invalid register/termination evidence")
        visited.update(pcs)
        changed.update(registers)
        rows.append({"kind": kind, "n": n, "m": m, "result": result,
                     "instructions": steps, "changed_registers": sorted(registers)})
        mutations["changed_stride"] += (((10 * n + m) * 151 + 0x00207F74) & MASK) != result
        mutations["changed_base"] += ((candidate(n, m) + 4) & MASK) != result
        mutations["swapped_arguments"] += candidate(m, n) != result
    if not all(mutations.values()):
        raise ValueError("Case selection did not distinguish all deliberately wrong hypotheses")
    return {"cases": len(rows), "case_domains": {"upstream_sample_domain": 100,
             "constructed_32_bit_boundaries": 96}, "results": rows,
            "results_sha256": pinned.digest(json.dumps(rows, sort_keys=True).encode()),
            "max_instructions": max(row["instructions"] for row in rows),
            "executed_pcs": [f"0x{pc:08x}" for pc in sorted(visited)],
            "observed_changed_registers": sorted(changed),
            "writes": 0, "mutation_rejections": mutations}


def execute(data: bytes, sh2emu) -> dict:
    if len(data) != pinned.SIZE:
        raise ValueError("Execution requires the complete kernel-sized input")

    class ReadOnlyMemory(sh2emu.Memory):
        def write(self, addr, size, value):
            raise ValueError(f"Unexpected write at 0x{addr:08x}; pure-function hypothesis failed")

    class ObservedCPU(sh2emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.visited = []

        def exec(self, instruction, pc, in_slot=False):
            # The pinned CPU invokes exec for both normal instructions and delay
            # slots. Wrapping step alone would omit the latter from the evidence.
            if len(self.visited) >= MAX_STEPS:
                raise RuntimeError("Original function exceeded the instruction bound")
            if pc % 2 or not pinned.BASE <= pc < pinned.BASE + len(data):
                raise ValueError("Execution left the mapped original kernel")
            self.visited.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    memory = ReadOnlyMemory()
    memory.add(pinned.BASE, len(data), data)

    def registers(cpu):
        return {**{f"r{i}": value for i, value in enumerate(cpu.r)},
                **{name: getattr(cpu, name) for name in REGISTERS[16:]}}

    def call(n, m):
        cpu = ObservedCPU(memory)
        cpu.r = [0xA5A5A5A5] * 16
        cpu.r[15] = 0x060FFFF0  # deliberately unmapped: stack writes must fail
        cpu.r[4], cpu.r[5] = n, m
        cpu.pr = sh2emu.RETURN_SENTINEL
        before = registers(cpu)
        result = cpu.call(ENTRY, max_steps=MAX_STEPS, r4=n, r5=m)
        after = registers(cpu)
        return {"result": result, "instructions": cpu.steps, "pcs": cpu.visited,
                "changed_registers": [name for name in REGISTERS if before[name] != after[name]],
                "return_sentinel_reached": cpu.pc == sh2emu.RETURN_SENTINEL}

    return exercise(call)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True, help="Fresh private report, never overwritten")
    args = parser.parse_args(argv)
    report = {"schema": "neptune.table-address-probe.v1", "status": "failure",
              "experiment": EXPERIMENT, "entry": f"0x{ENTRY:08x}",
              "game": "USA MK-81070 V1.003", "kernel_sha256": pinned.KERNEL_SHA256,
              "interpreter_revision": pinned.INTERPRETER_REVISION,
              "interpreter_sources": pinned.SOURCE_HASHES,
              "hypothesis_source": {"repository": "callumjenkins/pc-saturnbomberman",
                                    "revision": SOURCE_REVISION, "path": "decomp/krnl.c", "blob": SOURCE_BLOB},
              "probe_sha256": pinned.digest(Path(__file__).read_bytes()),
              "input_adapter_sha256": pinned.digest(Path(pinned.__file__).read_bytes()),
              "scope": "isolated original-byte function samples in a CPU interpreter",
              "limitations": ["Upstream arithmetic is a hypothesis until this original-byte run succeeds.",
                              "Constructed arguments are not natural gameplay observations.",
                              "No recovered function boundaries, natural caller or full ABI contract.",
                              "Instruction counts are not SH-2 cycles, game ticks or timing parity.",
                              "Same pinned interpreter lineage is not an independent oracle.",
                              "No whole-program or whole-game completion established."]}
    try:
        descriptor = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            phase = "kernel_identity"
            try:
                data = pinned.kernel_bytes(args.kernel)
                phase = "interpreter_identity"
                module = pinned.interpreter(args.saturn_recomp)
                phase = "original_execution"
                result = execute(data, module)
                report.update(status="success", **result)
            except Exception as error:
                # Avoid embedding private paths, raw instructions or memory in a
                # derived report. The private operator can inspect the exception.
                report["error"] = {"type": type(error).__name__, "phase": phase,
                                   "reason": "Input identity, execution or hypothesis validation failed"}
            output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except OSError:
        print("FAIL: cannot create a fresh private report", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "experiment": EXPERIMENT,
                      "cases": report.get("cases", 0)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
