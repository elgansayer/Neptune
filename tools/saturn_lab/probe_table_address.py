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
STACK_TOP = 0x060FFFF0
STACK_BASE = STACK_TOP - 64
STACK_SIZE = 80


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


def execute(data: bytes, sh2emu, *, bounded_stack: bool = False) -> dict:
    if len(data) != pinned.SIZE:
        raise ValueError("Execution requires the complete kernel-sized input")

    class ObservedMemory(sh2emu.Memory):
        def read(self, addr, size):
            physical = addr & MASK
            if physical >> 28 == 0x2:
                physical &= 0x1FFFFFFF
            if bounded_stack and STACK_BASE <= physical < STACK_BASE + STACK_SIZE:
                if addr != STACK_TOP - 4 or size != 4 or self.writes != 1 or self.reads:
                    raise ValueError("Unexpected stack read; spill/restore contract failed")
                self.reads += 1
            return super().read(addr, size)

        def write(self, addr, size, value):
            if not bounded_stack:
                raise ValueError(f"Unexpected write at 0x{addr:08x}; pure-function hypothesis failed")
            if addr != STACK_TOP - 4 or size != 4 or self.writes or value != self.expected_macl:
                raise ValueError("Unexpected write; only the observed MACL spill is allowed")
            self.writes += 1
            return super().write(addr, size, value)

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

    memory = ObservedMemory()
    kernel = memory.add(pinned.BASE, len(data), data)
    stack = memory.add(STACK_BASE, STACK_SIZE, bytes(STACK_SIZE)) if bounded_stack else None
    witnesses = []

    def registers(cpu):
        return {**{f"r{i}": value for i, value in enumerate(cpu.r)},
                **{name: getattr(cpu, name) for name in REGISTERS[16:]}}

    def call(n, m):
        cpu = ObservedCPU(memory)
        cpu.r = [0xA5A5A5A5] * 16
        cpu.r[15] = STACK_TOP  # unmapped unless the observed stack contract is explicit
        cpu.r[4], cpu.r[5] = n, m
        cpu.pr = sh2emu.RETURN_SENTINEL
        if bounded_stack:
            cpu.macl = (0x13579BDF ^ n ^ (m << 1)) & MASK
            cpu.sr = 0x3F0
            pattern = bytes((index + (n & 255) + (m & 255)) % 256 for index in range(STACK_SIZE))
            stack[:] = pattern
            memory.reads = memory.writes = 0
            memory.expected_macl = cpu.macl
        before = registers(cpu)
        result = cpu.call(ENTRY, max_steps=MAX_STEPS, r4=n, r5=m)
        after = registers(cpu)
        if bounded_stack:
            expected = bytearray(pattern)
            expected[60:64] = before["macl"].to_bytes(4, "big")
            if (memory.writes != 1 or memory.reads != 1 or stack != expected or kernel != data):
                raise ValueError("Stack footprint or unchanged original-memory contract failed")
            preserved = set(REGISTERS) - {"r0", "r2", "r3", "r6", "sr"}
            if any(before[name] != after[name] for name in preserved):
                raise ValueError("Preserved register, MACL or stack pointer changed")
            expected_sr = (before["sr"] & ~1) | (((5 * n) & MASK) >> 31)
            if after["sr"] != expected_sr:
                raise ValueError("SHLL condition-bit contract failed")
            witnesses.append({"n": n, "m": m, "macl": before["macl"],
                              "writes": memory.writes, "reads": memory.reads,
                              "stack_sha256": pinned.digest(stack)})
        return {"result": result, "instructions": cpu.steps, "pcs": cpu.visited,
                "changed_registers": [name for name in REGISTERS if before[name] != after[name]],
                "return_sentinel_reached": cpu.pc == sh2emu.RETURN_SENTINEL}

    result = exercise(call)
    if bounded_stack:
        result.update(writes=len(witnesses), memory_contract={
            "mode": "observed-macl-spill", "kernel": "read-only and unchanged",
            "constructed_stack_base": f"0x{STACK_BASE:08x}", "constructed_stack_bytes": STACK_SIZE,
            "only_stack_access": {"address": f"0x{STACK_TOP - 4:08x}", "bytes": 4,
                                 "writes_per_case": 1, "reads_per_case": 1},
            "other_stack_bytes_unchanged": True, "sp_and_macl_preserved": True,
            "validated_cases": len(witnesses),
            "witnesses_sha256": pinned.digest(json.dumps(witnesses, sort_keys=True).encode())})
    return result


def instruction_controls(data: bytes, sh2emu) -> list[dict]:
    """Execute four explicitly altered private copies; never modify the original.

    The CLI validates original identity before calling this experiment. A normal
    result or a timeout is not a passing semantic/footprint negative control.
    """
    changes = (("stride150", 0x0600B96C, 2, 150),
               ("base_plus4", 0x0600B984, 4, 0x00207F78),
               ("remove_macl_restore_delay_slot", 0x0600B94E, 2, 0x0009),
               ("remove_macl_spill", 0x0600B934, 2, 0x0009))
    results = []
    for name, address, size, value in changes:
        altered = bytearray(data)
        offset = address - pinned.BASE
        altered[offset:offset + size] = value.to_bytes(size, "big")
        if len(altered) != pinned.SIZE or altered == data:
            raise ValueError("Invalid or ineffective original-copy mutation")
        try:
            execute(bytes(altered), sh2emu, bounded_stack=True)
        except ValueError as error:
            results.append({"name": name, "address": f"0x{address:08x}",
                            "altered_sha256": pinned.digest(altered), "rejected": True,
                            "error_class": type(error).__name__, "reason": str(error),
                            "source": "explicitly altered private copy; never reference"})
        else:
            raise ValueError("Original-copy mutation was not detected: " + name)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True, help="Fresh private report, never overwritten")
    parser.add_argument("--bounded-stack", action="store_true",
                        help="Explicit observed one-word MACL spill/restore; default rejects all writes")
    parser.add_argument("--instruction-controls", action="store_true",
                        help="Also reject four fixed private original-copy mutations; requires bounded stack")
    args = parser.parse_args(argv)
    if args.instruction_controls and not args.bounded_stack:
        parser.error("--instruction-controls requires --bounded-stack")
    report = {"schema": "neptune.table-address-probe.v1", "status": "failure",
              "experiment": EXPERIMENT, "entry": f"0x{ENTRY:08x}",
              "game": "USA MK-81070 V1.003", "kernel_sha256": pinned.KERNEL_SHA256,
              "interpreter_revision": pinned.INTERPRETER_REVISION,
              "interpreter_sources": pinned.SOURCE_HASHES,
              "hypothesis_source": {"repository": "callumjenkins/pc-saturnbomberman",
                                    "revision": SOURCE_REVISION, "path": "decomp/krnl.c", "blob": SOURCE_BLOB},
              "probe_sha256": pinned.digest(Path(__file__).read_bytes()),
              "input_adapter_sha256": pinned.digest(Path(pinned.__file__).read_bytes()),
              "memory_mode": "observed-macl-spill" if args.bounded_stack else "strict-no-writes",
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
                result = execute(data, module, bounded_stack=args.bounded_stack)
                if args.instruction_controls:
                    result["instruction_controls"] = instruction_controls(data, module)
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
