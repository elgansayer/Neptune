#!/usr/bin/env python3
"""Execute two original USA split-halfword add helpers with controlled RAM."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned
from probe_position_bounds import OBJECTS, SP, LIMIT

INDEX = 0x060C1AA8
FUNCTIONS = {0x0600A25E: (12, 16, 0x0600A28C),
             0x0600A2D8: (14, 18, 0x0600A306)}
EXPERIMENT = "EXP-SAT-CODE-004"


def cases():
    return list(itertools.product(
        (0, 1, 127, 255, 780, 781, 0x7FFF, 0x8000, 0xFFFE, 0xFFFF),
        (0, 1, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0xFFFF0000, 0xFFFFFFFF),
        (0, 1, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)))


def expected_halfwords(value, delta):
    # A scalar oracle, separate from the original loads, shifts and additions.
    result = (value + delta) % (1 << 32)
    return result & 0xFFFF, result >> 16


def map_inputs(memory, data, overlays):
    """Map disjoint original file segments and explicitly initialized RAM."""
    if len(data) != pinned.SIZE:
        raise ValueError("Incomplete original file mapping")
    overlays = sorted(overlays)
    for (start, buf), (next_start, _) in zip(overlays, overlays[1:]):
        if start + len(buf) > next_start:
            raise ValueError("Overlapping controlled data regions")
    cursor, end = pinned.BASE, pinned.BASE + len(data)
    for start, buf in overlays:
        if pinned.BASE <= start < end:
            if cursor < start:
                memory.add(cursor, start - cursor, data[cursor-pinned.BASE:start-pinned.BASE])
            cursor = min(end, start + len(buf))
        memory.add(start, len(buf), buf)
    if cursor < end:
        memory.add(cursor, end - cursor, data[cursor-pinned.BASE:])


def run_case(data, emu, entry, index, value, delta):
    if entry not in FUNCTIONS or not 0 <= index <= 0xFFFF:
        raise ValueError("Unknown function or invalid halfword index")
    low, high, end = FUNCTIONS[entry]
    address = OBJECTS + ((84 * index) & 0xFFFF)
    record = bytearray((i * 37 + 19) & 255 for i in range(84))
    record[low:low + 2] = (value & 0xFFFF).to_bytes(2, 'big')
    record[high:high + 2] = (value >> 16).to_bytes(2, 'big')
    expected = bytearray(record)
    expected_low, expected_high = expected_halfwords(value, delta)
    expected[low:low + 2] = expected_low.to_bytes(2, 'big')
    expected[high:high + 2] = expected_high.to_bytes(2, 'big')
    allowed_writes = {(address + low, 2), (address + high, 2), (SP - 4, 4)}
    allowed_reads = {(INDEX, 2), (address + low, 2), (address + high, 2),
                     (SP - 4, 4), (0x0600A358, 4), (0x0600A35C, 4)}

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.writes, self.data_reads = [], []

        def write(self, target, size, operand):
            if (target, size) not in allowed_writes:
                raise ValueError("Write outside record outputs or four-byte MACL slot")
            self.writes.append((target, size))
            return super().write(target, size, operand)

        def read(self, target, size):
            if size == 2 and entry <= target < end and target % 2 == 0:
                pass  # Instruction fetch, including the original RTS delay slot.
            elif (target, size) in allowed_reads:
                self.data_reads.append((target, size))
            else:
                raise ValueError("Read outside inspected code, literals and explicit data slots")
            return super().read(target, size)

    memory = Memory()
    map_inputs(memory, data, [(INDEX, index.to_bytes(2, 'big')),
                             (address, bytes(record)), (SP - 4, bytes([0xCD]) * 4)])
    baseline = [(lo, bytes(buf)) for lo, _, buf in memory.regions]

    class CPU(emu.CPU):
        def __init__(self, mem):
            super().__init__(mem)
            self.visited = []

        def exec(self, instruction, pc, in_slot=False):
            if len(self.visited) >= LIMIT or pc % 2 or not entry <= pc < end:
                raise ValueError("Execution outside function or instruction budget")
            self.visited.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [0xA5A5A5A5] * 16
    cpu.r[4], cpu.r[15] = delta, SP
    cpu.macl, cpu.mach, cpu.sr = 0x13579BDF, 0x2468ACE0, 0x3F3
    cpu.pr = emu.RETURN_SENTINEL
    names = [f'r{i}' for i in range(16)] + ['sr', 'macl', 'mach', 'pr', 'gbr', 'vbr']

    def registers():
        return {name: cpu.r[int(name[1:])] if name.startswith('r') and name[1:].isdigit()
                else getattr(cpu, name) for name in names}

    before = registers()
    cpu.call(entry, max_steps=LIMIT)
    after = registers()
    changed = sorted(name for name in names if before[name] != after[name])
    if cpu.pc != emu.RETURN_SENTINEL or cpu.steps != len(cpu.visited):
        raise ValueError("Missing return or delay-slot accounting")
    if set(changed) - {'r0', 'r1', 'r2', 'r3', 'r5', 'r6'}:
        raise ValueError("Register/stack restoration failed")
    if len(memory.writes) != 3 or set(memory.writes) != allowed_writes:
        raise ValueError("Missing, repeated or extra output store")
    if sorted(memory.data_reads) != sorted(allowed_reads):
        raise ValueError("Missing, repeated or extra data read")
    allowed_bytes = {target + offset for target, size in allowed_writes for offset in range(size)}
    for lo, hi, buf in memory.regions:
        if lo == address and bytes(buf) != bytes(expected):
            raise ValueError("Split-halfword result differs from independent 32-bit contract")
    for (lo, original), (_, _, buf) in zip(baseline, memory.regions):
        if bytes(buf) != original and any(a != b and lo + offset not in allowed_bytes
                                         for offset, (a, b) in enumerate(zip(original, buf))):
            raise ValueError("Unaffected mapped byte changed")
    return {'entry': hex(entry), 'index_bits': index, 'value_bits': value, 'delta_bits': delta,
            'record_address': hex(address), 'low_halfword': expected_low, 'high_halfword': expected_high,
            'instructions': cpu.steps, 'pcs': [hex(pc) for pc in cpu.visited],
            'data_reads': [[hex(a), size] for a, size in memory.data_reads],
            'writes': [[hex(a), size] for a, size in memory.writes],
            'changed_registers': changed, 'unaffected_bytes_equal': True, 'return_sentinel_reached': True}


def execute(data, emu):
    selected = cases()
    if len(selected) != 560:
        raise ValueError('Case selection changed')
    rows = [run_case(data, emu, entry, *case) for entry in FUNCTIONS for case in selected]
    controls = {}
    for entry, (low, high, end) in FUNCTIONS.items():
        # Each offset is derived from the inspected original instruction stream.
        positions = (0x0600A27C, 0x0600A282, 0x0600A286, 0x0600A28A, 0x0600A26C) if entry == 0x0600A25E else (
            0x0600A2F6, 0x0600A2FC, 0x0600A300, 0x0600A304, 0x0600A2E6)
        for kind, pc in zip(('add_to_subtract', 'missing_high_store', 'missing_low_store',
                             'missing_MACL_restore', 'missing_index_truncation'), positions):
            ins = emu.sh2.decode(int.from_bytes(data[pc-pinned.BASE:pc-pinned.BASE+2], 'big'), pc)
            required_op = {'add_to_subtract': 'add', 'missing_high_store': 'mov.w', 'missing_low_store': 'mov.w',
                           'missing_MACL_restore': 'lds.l', 'missing_index_truncation': 'extu.w'}[kind]
            if ins.op != required_op:
                raise ValueError('Original mutation site changed')
            word = 0x3008 | (ins.n << 8) | (ins.m << 4) if kind == 'add_to_subtract' else 0x0009
            altered = bytearray(data)
            altered[pc-pinned.BASE:pc-pinned.BASE+2] = word.to_bytes(2, 'big')
            rejected, reasons = 0, set()
            # Covers every index with several overflow/non-overflow scalar pairs.
            control_cases = selected[::9]
            for case in control_cases:
                try:
                    run_case(bytes(altered), emu, entry, *case)
                except (ValueError, emu.MemoryError_) as error:
                    rejected += 1
                    reasons.add(str(error))
            if not rejected:
                raise ValueError('Original instruction mutation survived')
            controls[hex(entry) + ':' + kind] = {'pc': hex(pc), 'rejected': rejected,
                'tested': len(control_cases), 'reasons': sorted(reasons),
                'mutated_kernel_sha256': pinned.digest(altered)}
    return {'cases': len(rows), 'cases_per_function': len(selected), 'results': rows,
            'results_sha256': pinned.digest(json.dumps(rows, sort_keys=True).encode()),
            'instruction_controls': controls,
            'function_ranges': {hex(entry): {'file_offset': hex(entry-pinned.BASE),
                'exclusive_end': hex(end), 'sha256': pinned.digest(data[entry-pinned.BASE:end-pinned.BASE])}
                for entry, (_, _, end) in FUNCTIONS.items()},
            'literal_range': {'start': '0x0600A358', 'exclusive_end': '0x0600A360',
                'sha256': pinned.digest(data[0x4358:0x4360])}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--saturn-recomp', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': 'neptune.split-add-probe.v1', 'experiment': EXPERIMENT, 'status': 'failure',
        'game': 'USA MK-81070 V1.003', 'kernel_sha256': pinned.KERNEL_SHA256,
        'interpreter_revision': pinned.INTERPRETER_REVISION, 'interpreter_sources': pinned.SOURCE_HASHES,
        'probe_sha256': pinned.digest(Path(__file__).read_bytes()),
        'adapter_sha256': pinned.digest(Path(pinned.__file__).read_bytes()),
        'shared_constants_sha256': pinned.digest(Path(__file__).with_name('probe_position_bounds.py').read_bytes()),
        'scope': 'Original instructions; initialized record/index/stack inputs; CPU-only',
        'limitations': ['No natural caller, gameplay role, timing, independent CPU oracle or whole-program completion',
                        'Sampled state preservation only; no return-value meaning established']}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print('FAIL: report requires a fresh writable path')
        return 1
    with os.fdopen(fd, 'w') as output:
        phase = 'source_identity'
        try:
            data = pinned.kernel_bytes(args.kernel)
            emu = pinned.interpreter(args.saturn_recomp)
            phase = 'original_execution'
            report.update(execute(data, emu), status='success')
        except Exception as error:
            report['error'] = {'phase': phase, 'type': type(error).__name__,
                               'reason': 'Identity, bounded execution or memory contract failed'}
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': report['status'], 'cases': report.get('cases', 0)}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
