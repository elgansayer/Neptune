#!/usr/bin/env python3
"""Prepare and call the pinned bounded Musashi adapter, without original media."""
from __future__ import annotations

import argparse
import ctypes as c
import json
import os
from pathlib import Path
import subprocess
import tempfile

import probe_kernel as pinned

HERE = Path(__file__).resolve().parent
SOURCE_LOCK = HERE / 'm68k-probe-source-lock.json'
BACKEND = HERE / 'm68k_probe_backend.c'
MAX_STEPS, MAX_EVENTS = 256, 128
STATUS = {1: 'stop-reached', 2: 'instruction-budget', 3: 'instruction-access',
          4: 'unmapped-data-read', 5: 'forbidden-write', 6: 'event-budget',
          7: 'unexpected-step-or-cycles', 8: 'invalid-request', 9: 'reset-initialization'}
FLAGS = ['-std=c11', '-O2', '-shared', '-fPIC', '-DM68K_INSTRUCTION_HOOK=1',
         '-DM68K_SEPARATE_READS=1', '-Wl,-z,defs']


class Region(c.Structure):
    _fields_ = [('lo', c.c_uint32), ('size', c.c_uint32), ('writable', c.c_uint32), ('data', c.POINTER(c.c_uint8))]


class Range(c.Structure):
    _fields_ = [('lo', c.c_uint32), ('end', c.c_uint32)]


class Request(c.Structure):
    _fields_ = [('code', c.POINTER(c.c_uint8)), ('code_size', c.c_uint32),
                ('regions', c.POINTER(Region)), ('region_count', c.c_uint32),
                ('ranges', c.POINTER(Range)), ('range_count', c.c_uint32),
                ('entry', c.c_uint32), ('stop', c.c_uint32), ('budget', c.c_uint32),
                ('registers', c.c_uint32 * 18)]


class Event(c.Structure):
    _fields_ = [(name, c.c_uint32) for name in ('kind', 'address', 'size', 'value')]


class Result(c.Structure):
    _fields_ = [(name, c.c_uint32) for name in ('status', 'error_address', 'error_size', 'steps', 'event_count')] + [
        ('pcs', c.c_uint32 * MAX_STEPS), ('after', c.c_uint32 * 18),
        ('model_cycles', c.c_int32), ('events', Event * MAX_EVENTS)]


def identity():
    return {'source_lock_sha256': pinned.digest(SOURCE_LOCK.read_bytes()),
            'backend_sha256': pinned.digest(BACKEND.read_bytes()), 'flags': FLAGS}


class Library:
    def __init__(self, directory, require_receipt=True):
        directory = Path(directory)
        self.path = directory / 'libneptune_m68k.so'
        if require_receipt:
            receipt = json.loads(pinned.read_bounded(directory / 'receipt.json', 65536))
            if (receipt.get('identity') != identity() or receipt.get('status') != 'ready'
                    or pinned.digest(pinned.read_bounded(self.path, 8*1024*1024)) != receipt.get('binary_sha256')
                    or receipt.get('owned_smoke', {}).get('original_game_bytes_executed') is not False):
                raise ValueError('Prepared Musashi receipt or native library identity failed')
        self.library = c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype = c.c_uint32
        if self.library.neptune_m68k_abi() != 1:
            raise ValueError('Unsupported native probe ABI')
        self.library.neptune_m68k_run.argtypes = [c.POINTER(Request), c.POINTER(Result)]
        self.library.neptune_m68k_run.restype = c.c_int

    def run(self, code, entry, stop, ranges, regions, registers, budget=128):
        if (not 0 < len(code) <= 0x80000 or len(registers) != 18
                or not 0 < len(regions) <= 8 or not 0 < len(ranges) <= 4
                or not 0 < budget <= MAX_STEPS
                or any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in registers)):
            raise ValueError('Invalid bounded CPU request')
        memory = (c.c_uint8 * len(code)).from_buffer_copy(code)
        buffers = [(c.c_uint8 * len(data)).from_buffer_copy(data) for _, data, _ in regions]
        data_regions = (Region * len(regions))(*[
            Region(lo, len(data), int(writable), buf) for (lo, data, writable), buf in zip(regions, buffers)])
        allowed = (Range * len(ranges))(*[Range(lo, end) for lo, end in ranges])
        req = Request(memory, len(code), data_regions, len(regions), allowed, len(ranges),
                      entry, stop, budget, (c.c_uint32 * 18)(*registers))
        out = Result()
        returned = self.library.neptune_m68k_run(c.byref(req), c.byref(out))
        if returned != out.status or out.steps > MAX_STEPS or out.event_count > MAX_EVENTS:
            raise ValueError('Native result ABI/count mismatch')
        return {'status': STATUS.get(out.status, 'unknown-native-status'), 'status_code': out.status,
                'error_address': out.error_address, 'error_size': out.error_size,
                'steps': out.steps, 'pcs': list(out.pcs)[:out.steps], 'registers': list(out.after),
                'model_cycles': out.model_cycles,
                'events': [[e.kind, e.address, e.size, e.value] for e in out.events[:out.event_count]],
                'regions_after': [bytes(buf) for buf in buffers], 'code_unchanged': bytes(memory) == code}


def smoke(library):
    # Owned instructions: LEA abs.l,A4; RTS. They are unrelated to the game helper.
    code = bytearray(0x200)
    code[0x100:0x108] = bytes.fromhex('49f9 0001 2340 4e75')
    regs = [0xA5A5A5A5] * 18
    regs[8] = 0x60000  # aligned, deliberately unmapped data address
    regs[15:18] = [0x70000, 0x100, 0x2715]
    regions = [(0x70000, (0xFFF000).to_bytes(4, 'big'), False)]
    good = library.run(code, 0x100, 0xFFF000, [(0x100, 0x108)], regions, regs)
    if not (good['status_code'] == 1 and good['steps'] == 2 and good['registers'][12] == 0x12340
            and good['registers'][15] == 0x70004 and good['registers'][17] == regs[17]
            and good['code_unchanged'] and good['regions_after'] == [regions[0][1]]
            and good['events'] == [[1, 0x70000, 4, 0xFFF000]]):
        raise ValueError('Owned positive/native ABI smoke failed')
    controls = {}
    for name, words, expected in (
        ('nonreturning', '60fe', 2),
        ('unmapped_read', '2010', 4),  # MOVE.L (A0),D0
        ('forbidden_write', '2080', 5),  # MOVE.L D0,(A0)
        ('execution_escape', '4ef9 0000 0180', 3),
    ):
        altered = bytearray(code)
        owned = bytes.fromhex(words)
        altered[0x100:0x100+len(owned)] = owned
        observed = library.run(altered, 0x100, 0xFFF000, [(0x100, 0x108)], regions, regs, budget=8)
        if observed['status_code'] != expected:
            raise ValueError('Owned native failure guard smoke failed: ' + name)
        controls[name] = observed['status']
    # State after a failed native call cannot contaminate the next CPU run.
    repeated = library.run(code, 0x100, 0xFFF000, [(0x100, 0x108)], regions, regs)
    if repeated != good:
        raise ValueError('Fresh CPU context after failed calls is not deterministic')
    return {'original_game_bytes_executed': False, 'positive_steps': 2,
            'failure_controls': controls, 'fresh_after_failure': True}


def prepare(source_root, cache):
    source_root, cache = Path(source_root), Path(cache)
    lock = json.loads(SOURCE_LOCK.read_text())
    for relative, sha in lock['files'].items():
        if pinned.digest(pinned.read_bounded(source_root / relative, 2*1024*1024)) != sha:
            raise ValueError('Pinned execution source differs: ' + relative)
    if cache.exists():
        library = Library(cache)
        smoke(library)
        return json.loads((cache / 'receipt.json').read_text())
    cache.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.m68k-prepare-', dir=cache.parent))
    vendor = source_root / 'runtime/third_party/musashi'
    command = ['/usr/bin/cc', *FLAGS, '-I', str(vendor), '-o', str(stage/'libneptune_m68k.so'),
               str(BACKEND), str(vendor/'m68kcpu.c'), str(vendor/'m68kops.c'),
               str(vendor/'softfloat/softfloat.c'), '-lm']
    completed = subprocess.run(command, capture_output=True, timeout=60)
    (stage/'build.stdout').write_bytes(completed.stdout)
    (stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode:
        raise ValueError('Native preparation compile failed; retained stage diagnostics')
    library = Library(stage, require_receipt=False)
    owned = smoke(library)
    receipt = {'schema': 'neptune.prepared-m68k.v1', 'status': 'ready', 'identity': identity(),
               'source_revision': lock['revision'], 'source_files': lock['files'],
               'binary_sha256': pinned.digest((stage/'libneptune_m68k.so').read_bytes()),
               'owned_smoke': owned, 'compiler': subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],
               'compile_exit': completed.returncode, 'compile_timeout_seconds': 60,
               'preparation_has_original_inputs': False,
               'limitations': ['CPU interpreter only; no device or SCSP model; serialized process-global CPU',
                               'Synthetic reset then explicit registers; no original reset executed',
                               'Model cycles are not hardware timing or audio samples']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    os.rename(stage, cache)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare(args.sources, args.cache)
    print(json.dumps({'status': result['status'], 'binary_sha256': result['binary_sha256'],
                      'original_game_bytes_executed': False}))


if __name__ == '__main__':
    main()
