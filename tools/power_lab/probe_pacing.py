#!/usr/bin/env python3
"""Reproduce Power 0.7.8c server pacing logic from its actual private CIL bodies.

Single-thread, bounded interpretation of four original methods. Monitor,
Interlocked and Enumerable.Max are modelled; this is not CLR/network validation.
"""
from __future__ import annotations
import argparse
import copy
from collections import deque
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import sys

ASSEMBLY = "9e435a445cef37cf4d3f8911099caeb074feb24a455cc3656d95d75d88a199e1"
METHODS = {
    0x51: ("Reset", 0x3424, "7068ce85e22aa2ccc0c8ac847ce8fcd856b62d7d71ee783f1cb2fdb158bc60ad"),
    0x52: ("IncreaseCount", 0x3488, "d5ae830811da2915f941f06b92e39623946d5cafef7dc6563352dad2270de824"),
    0x53: ("GetMax", 0x3498, "d28c2bca5028e84e62ac721369d4919e7d2ebf4e41da8963c6ff251719c9b3a1"),
    0x54: ("EndPhase", 0x34DC, "97f890aaa4e191248e09b10ac1ee056e1395c6c7fe1e3f2cacff626e7471f185"),
}
DEPS = {"dnfile": "0.17.0", "dncil": "1.0.2", "pefile": "2024.8.26"}
CALLS = {0x0A000063: ("System.Threading.Monitor", "Enter"),
         0x0A00006B: ("System.Threading.Monitor", "Exit"),
         0x0A000083: ("System.Threading.Interlocked", "Increment"),
         0x0A000084: ("System.Linq.Enumerable", "Max")}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    if path.stat().st_size != 129536 or digest(path.read_bytes()) != ASSEMBLY:
        raise ValueError("Not the pinned developer-linked Power 0.7.8c server assembly")
    for name, version in DEPS.items():
        if importlib.metadata.version(name) != version:
            raise ValueError("Dependency version mismatch: " + name)
    import dnfile
    from dncil.cil.body.reader import read_method_body_from_bytes
    pe = dnfile.dnPE(str(path))
    owner = pe.net.mdtables.TypeDef.rows[10]
    if str(owner.TypeNamespace) + "." + str(owner.TypeName) != "PBServer2.Utilities.PacingTracker":
        raise ValueError("Wrong original type")
    for token, (kind, name) in CALLS.items():
        row = pe.net.mdtables.MemberRef.rows[(token & 0xFFFFFF) - 1]
        typ = row.Class.row
        if (str(typ.TypeNamespace) + "." + str(typ.TypeName), str(row.Name)) != (kind, name):
            raise ValueError("External call target mismatch")
    bodies, identities, disassembly = {}, {}, []
    for rid, (name, rva, expected) in METHODS.items():
        row = pe.net.mdtables.MethodDef.rows[rid - 1]
        body = read_method_body_from_bytes(pe.get_data(row.Rva, 4096))
        if str(row.Name) != name or row.Rva != rva or digest(body.raw_bytes) != expected:
            raise ValueError("Original method identity changed: " + name)
        bodies[rid] = body
        identities[name] = {"token": hex(0x06000000 | rid), "rva": hex(rva),
                            "code_rva": hex(rva + body.header_size),
                            "file_offset": pe.get_offset_from_rva(rva),
                            "body_bytes": len(body.raw_bytes), "code_bytes": body.code_size,
                            "body_sha256": expected}
        disassembly.append(name + " " + hex(rva) + "\n" + "\n".join(map(str, body.instructions)))
    return bodies, identities, "\n\n".join(disassembly) + "\n"


def signed32(value):
    return ((value + 2**31) % 2**32) - 2**31


class Original:
    def __init__(self, bodies, size):
        self.bodies = bodies
        self.fields = {0x29: 0, 0x2A: [0] * size, 0x2B: 0, 0x2C: 1, 0x2D: object()}
        self.exits = 0
        self.run(0x51)

    def run(self, rid):
        body = self.bodies[rid]
        instructions = {i.offset: i for i in body.instructions}
        pc, stack, local, pending, entered = body.instructions[0].offset, [], {}, None, False
        for _ in range(10000):
            if pc not in instructions:
                raise ValueError("Branch outside original instruction boundaries")
            i = instructions[pc]
            op, arg = i.opcode.name, i.operand
            pc += i.size
            if op == "ldarg.0": stack.append(self.fields)
            elif op.startswith("ldc.i4."):
                stack.append(-1 if op.endswith("m1") else int(op.rsplit(".", 1)[1]))
            elif op.startswith("ldloc."): stack.append(local[int(op.rsplit(".", 1)[1])])
            elif op.startswith("stloc."): local[int(op.rsplit(".", 1)[1])] = stack.pop()
            elif op == "ldloca.s": stack.append(("local", arg.index))
            elif op in ("ldfld", "ldflda"):
                obj, field = stack.pop(), arg.value & 0xFFFFFF
                stack.append(obj[field] if op == "ldfld" else ("field", obj, field))
            elif op == "stfld":
                value, obj = stack.pop(), stack.pop()
                obj[arg.value & 0xFFFFFF] = value
            elif op == "stelem.i4":
                value, index, array = stack.pop(), stack.pop(), stack.pop()
                if not 0 <= index < len(array): raise ValueError("Original array bound failure")
                array[index] = value
            elif op == "ldlen": stack.append(len(stack.pop()))
            elif op == "conv.i4": stack.append(signed32(stack.pop()))
            elif op in ("add", "rem"):
                right, left = stack.pop(), stack.pop()
                if op == "rem" and (left < 0 or right <= 0):
                    raise ValueError("Probe only models non-negative remainder operands")
                stack.append(signed32(left + right) if op == "add" else left % right)
            elif op == "pop": stack.pop()
            elif op == "br.s": pc = arg
            elif op == "blt.s":
                right, left = stack.pop(), stack.pop()
                if left < right: pc = arg
            elif op == "ble.s":
                right, left = stack.pop(), stack.pop()
                if left <= right: pc = arg
            elif op == "brfalse.s":
                if not stack.pop(): pc = arg
            elif op == "call":
                if arg.value == 0x0A000063:
                    reference, lock = stack.pop(), stack.pop()
                    if entered or lock is not self.fields[0x2D] or reference[0] != "local":
                        raise ValueError("Invalid monitor acquisition")
                    local[reference[1]], entered = True, True
                elif arg.value == 0x0A00006B:
                    if not entered or stack.pop() is not self.fields[0x2D]:
                        raise ValueError("Unbalanced monitor release")
                    entered = False
                    self.exits += 1
                elif arg.value == 0x0A000083:
                    reference = stack.pop()
                    _, obj, field = reference
                    obj[field] = signed32(obj[field] + 1)
                    stack.append(obj[field])
                elif arg.value == 0x0A000084: stack.append(max(stack.pop()))
                else: raise ValueError("Unmodelled external call")
            elif op == "leave.s":
                eligible = [h for h in body.exception_handlers if h.exception_type == 2
                            and h.try_start + body.header_size <= i.offset < h.try_end + body.header_size]
                if len(eligible) != 1 or pending is not None or stack:
                    raise ValueError("Unmodelled exception flow")
                pending, pc = arg, eligible[0].handler_start + body.header_size
            elif op == "endfinally":
                if pending is None: raise ValueError("No leave continuation")
                pc, pending = pending, None
            elif op == "ret":
                if entered or pending is not None or len(stack) > 1:
                    raise ValueError("Invalid terminal interpreter state")
                return stack.pop() if stack else None
            else: raise ValueError("Unsupported original opcode: " + op)
        raise ValueError("Instruction limit")


def experiment(bodies):
    rng = random.Random(20261030)
    trace, transitions = [], 0
    for size in (1, 2, 3, 32):
        original = Original(bodies, size)
        history, expected_max = deque([1] * size, maxlen=size), 1
        counts = [9, 0, 0, 2] + [1] * (size + 1)
        counts += [rng.randrange(0, 17) for _ in range(1000)]
        for phase, count in enumerate(counts):
            if phase == 500:
                original.run(0x51)
                history = deque([1] * size, maxlen=size)
                # Real Reset leaves cached maxValue unchanged.
                if original.run(0x53) != expected_max: raise ValueError("Reset cached-max mismatch")
            for _ in range(count): original.run(0x52)
            original.run(0x54)
            if count:
                history.append(count)
                expected_max = max(history)
            actual = original.run(0x53)
            if actual != expected_max or original.fields[0x29] != 0:
                raise ValueError("Recovered model disagrees with original CIL")
            trace.append([size, phase, count, actual])
            transitions += 1
    # Semantic controls: idle phases do not age the rolling window; Reset does
    # not refresh the cached maximum. These would fail common alternative models.
    o = Original(bodies, 2)
    for _ in range(9): o.run(0x52)
    o.run(0x54)
    for _ in range(5): o.run(0x54)
    idle = o.run(0x53)
    o.run(0x51)
    reset = o.run(0x53)
    if idle != 9 or reset != 9:
        raise ValueError("Semantic controls failed")
    from dncil.cil.opcode import OpCodes
    changed = dict(bodies)
    changed[0x54] = copy.copy(bodies[0x54])
    changed[0x54].instructions = [copy.copy(i) for i in bodies[0x54].instructions]
    branch = [i for i in changed[0x54].instructions if i.opcode.name == "ble.s"]
    if len(branch) != 1: raise ValueError("Original control branch is ambiguous")
    branch[0].opcode = OpCodes.Blt_S
    altered = Original(changed, 1)
    for _ in range(9): altered.run(0x52)
    altered.run(0x54)
    altered.run(0x54)
    if altered.run(0x53) == 9:
        raise ValueError("Changed original-CIL branch escaped the control")
    return {"transitions": transitions, "trace_sha256": digest(json.dumps(trace).encode()),
            "controls": {"age_on_idle_alternative_rejected": idle != 1,
                         "reset_cached_max_alternative_rejected": reset != 1,
                         "original_cil_ble_to_blt_mutation_rejected": True},
            "control_observations": {"after_five_empty_phases": idle, "after_reset": reset},
            "sample": trace[:8]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assembly", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args(argv)
    bodies, identities, disassembly = load(args.assembly)
    result = experiment(bodies)
    report = {"schema": "neptune.power-pacing.v1", "status": "original-cil-analysis-pass",
              "game": "Power Bomberman", "build": "0.7.8c optional server; developer Drive mirror",
              "assembly_sha256": ASSEMBLY, "probe_sha256": digest(Path(__file__).read_bytes()),
              "dependencies": DEPS, "methods": identities, "result": result,
              "limitations": ["Original server CIL interpreted, not CLR or client execution",
                              "External synchronization/LINQ calls modelled; single-thread cases only",
                              "No network latency, gameplay timing, Saturn code or spritesheet claimed",
                              "Readme/build label plus exact archive/assembly identity; hotfix uniqueness unknown"]}
    with args.report.open("x") as f: f.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "transitions": result["transitions"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
