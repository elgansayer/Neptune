#!/usr/bin/env python3
"""Prepare and read a separate natural-68000-coverage copy of the pinned Beetle core.

The reference checkout is never modified. `prepare` copies it (preserving
timestamps so only the patched translation unit rebuilds), applies four exact
anchor insertions plus an export-list change, builds, smoke-tests the observer
ABI without media and writes a receipt. `Coverage` reads the native tables
through ctypes from an already loaded core. Raw coverage and the built core
stay private; only tools, hashes and derived results are published.
"""
from __future__ import annotations

import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
HEADER = HERE / 'm68k_coverage.h'
REVISION = '01bc063fdd0fb5fc208850c9ecc658834df762ab'
TREE = '2522acca8b2b48394ff579e89f50717c4ad8b230'
REFERENCE_CORE = 'c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e'
SOURCES = {
    'mednafen/hw_cpu/m68k/m68k.c': 'f7cff529abb135b4a99722177dc667f5b33a7ab1a747f1e7ae3326a3ce47f818',
    'link.T': '20d8a69f1e68c44481005916c466dc6bda13b3c45d04f56f7176463f388f9298',
}
EXPORTS = ('abi', 'begin', 'frame', 'stop', 'status', 'header_get', 'words', 'edges')
# (anchor, insertion, position) applied to m68k.c; every anchor must occur once.
INSERTIONS = (
    (b'#include "m68k_private.h"\n', b'#include "neptune_m68k_coverage.h"\n', 'after'),
    (b'\t\t\t\t\t z->XPending &= ~XPENDING_MASK_RESET;\n', b'\t\t\t\t\t neptune_m68kcov_reset(z);\n', 'after'),
    (b' ReadOp(z);\n ReadOp(z);\n z->PC -= 4;\n', b' neptune_m68kcov_exception(z, vecnum, PC_save);\n', 'after'),
    (b'\t uint16_t instr = ReadOp(z);\n', b'\t neptune_m68kcov_step(z, instr);\n', 'after'),
)
BUILD = ['make', '-j2', 'platform=unix', 'LTO=0', 'HAVE_OPENGL=0', 'HAVE_CHD=1']
WORDS = 0x40000
EDGE_CAPACITY = 1 << 16
KINDS = {0: 'flow', 1: 'exception', 2: 'epoch'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patch_sources(content, header):
    """Return patched file contents for the pinned sources; raises on any drift."""
    if set(content) != set(SOURCES) or any(digest(content[k]) != v for k, v in SOURCES.items()):
        raise ValueError('Core source differs from the inspected reference pin')
    m68k = content['mednafen/hw_cpu/m68k/m68k.c']
    for anchor, insertion, _ in INSERTIONS:
        if m68k.count(anchor) != 1:
            raise ValueError('Missing or ambiguous 68000 observer anchor')
        m68k = m68k.replace(anchor, anchor + insertion)
    exports = content['link.T']
    if exports.count(b'global: retro_*;') != 1:
        raise ValueError('Missing inspected export boundary')
    names = b' '.join(('neptune_m68kcov_' + name + ';').encode() for name in EXPORTS)
    exports = exports.replace(b'global: retro_*;', b'global: retro_*; ' + names)
    return {'mednafen/hw_cpu/m68k/m68k.c': m68k, 'link.T': exports,
            'mednafen/hw_cpu/m68k/neptune_m68k_coverage.h': header}


def git(source, *args):
    return subprocess.run(['git', '-C', str(source), *args], capture_output=True, text=True, timeout=60)


def verify_reference(source):
    head = git(source, 'rev-parse', 'HEAD', 'HEAD^{tree}')
    if head.returncode or head.stdout.split() != [REVISION, TREE]:
        raise ValueError('Reference checkout is not the pinned Beetle revision/tree')
    if git(source, 'diff', '--quiet', 'HEAD').returncode:
        raise ValueError('Reference checkout has modified tracked files')
    if digest((source / 'mednafen_saturn_libretro.so').read_bytes()) != REFERENCE_CORE:
        raise ValueError('Reference checkout build products are not the accepted reference core')


class Header(c.Structure):
    _fields_ = [(name, c.c_uint32) for name in (
        'reset_pc', 'reset_ssp', 'first_frame', 'last_frame', 'opcode_changes', 'outside',
        'first_outside_pc', 'edges_used', 'edge_overflow', 'executed_words')] + [
        ('steps', c.c_uint64), ('exceptions', c.c_uint64 * 256)]


class Coverage:
    """ctypes view of the observer inside an already loaded instrumented core."""

    def __init__(self, dll):
        self.dll = dll
        for name in EXPORTS:
            getattr(dll, 'neptune_m68kcov_' + name)
        dll.neptune_m68kcov_abi.restype = c.c_uint32
        dll.neptune_m68kcov_begin.restype = c.c_int
        dll.neptune_m68kcov_frame.argtypes = [c.c_uint32]
        dll.neptune_m68kcov_frame.restype = None
        dll.neptune_m68kcov_stop.restype = None
        dll.neptune_m68kcov_status.argtypes = [c.POINTER(c.c_uint32)]
        dll.neptune_m68kcov_status.restype = None
        dll.neptune_m68kcov_header_get.argtypes = [c.c_uint32, c.POINTER(Header)]
        dll.neptune_m68kcov_header_get.restype = c.c_int
        dll.neptune_m68kcov_words.argtypes = [c.c_uint32, c.POINTER(c.c_uint32), c.POINTER(c.c_uint32),
                                              c.POINTER(c.c_uint16), c.POINTER(c.c_uint8)]
        dll.neptune_m68kcov_words.restype = c.c_int
        dll.neptune_m68kcov_edges.argtypes = [c.c_uint32, c.POINTER(c.c_uint64), c.POINTER(c.c_uint32),
                                              c.POINTER(c.c_uint32), c.c_uint32]
        dll.neptune_m68kcov_edges.restype = c.c_int
        if dll.neptune_m68kcov_abi() != 1:
            raise ValueError('Unsupported 68000 coverage observer ABI')
        if self.status()['header_bytes'] != c.sizeof(Header):
            raise ValueError('Observer header layout differs from the Python mirror')

    def status(self):
        raw = (c.c_uint32 * 8)()
        self.dll.neptune_m68kcov_status(raw)
        return {'abi': raw[0], 'on': raw[1], 'epochs': raw[2], 'epoch_overflow': raw[3],
                'alloc_failed': raw[4], 'unepoched_steps': raw[5] | raw[6] << 32, 'header_bytes': raw[7]}

    def begin(self):
        if self.dll.neptune_m68kcov_begin() != 0:
            raise ValueError('Observer already started; use a fresh core process')

    def frame(self, number):
        self.dll.neptune_m68kcov_frame(number)

    def stop(self):
        self.dll.neptune_m68kcov_stop()

    def epoch(self, index):
        header = Header()
        if self.dll.neptune_m68kcov_header_get(index, c.byref(header)) != 0:
            raise ValueError('Missing observer epoch')
        hits, first = (c.c_uint32 * WORDS)(), (c.c_uint32 * WORDS)()
        ops, changed = (c.c_uint16 * WORDS)(), (c.c_uint8 * WORDS)()
        if self.dll.neptune_m68kcov_words(index, hits, first, ops, changed) != 0:
            raise ValueError('Observer word table read failed')
        keys, counts, firsts = (c.c_uint64 * EDGE_CAPACITY)(), (c.c_uint32 * EDGE_CAPACITY)(), (c.c_uint32 * EDGE_CAPACITY)()
        n = self.dll.neptune_m68kcov_edges(index, keys, counts, firsts, EDGE_CAPACITY)
        if n < 0:
            raise ValueError('Observer edge table read failed')
        return decode_epoch(header, hits, first, ops, changed, [(keys[i], counts[i], firsts[i]) for i in range(n)])


def decode_edge(key):
    kind = (key >> 8) & 0xFF
    if not kind & 0x80 or kind & 0x7F not in KINDS:
        raise ValueError('Malformed observer edge key')
    return {'from': key >> 40 & 0xFFFFFF, 'to': key >> 16 & 0xFFFFFF, 'kind': KINDS[kind & 0x7F], 'vector': key & 0xFF}


def decode_epoch(header, hits, first, ops, changed, edges):
    words = []
    for index in range(WORDS):
        if hits[index]:
            words.append([index * 2, hits[index], first[index] - 1, ops[index], int(changed[index])])
        elif first[index] or changed[index]:
            raise ValueError('Observer word table is internally inconsistent')
    if len(words) != header.executed_words:
        raise ValueError('Observer executed-word count differs from its table')
    decoded = []
    for key, count, frame in edges:
        edge = decode_edge(key)
        decoded.append([edge['from'], edge['to'], edge['kind'], edge['vector'], count, frame])
    decoded.sort()
    if len(decoded) != header.edges_used:
        raise ValueError('Observer edge count differs from its table')
    return {'reset_pc': header.reset_pc, 'reset_ssp': header.reset_ssp, 'first_frame': header.first_frame,
            'last_frame': header.last_frame, 'steps': header.steps, 'outside_steps': header.outside,
            'first_outside_pc': None if header.outside == 0 else header.first_outside_pc,
            'opcode_changes': header.opcode_changes, 'edge_overflow': header.edge_overflow,
            'exceptions': {str(v): n for v, n in enumerate(header.exceptions) if n},
            'words': words, 'edges': decoded}


def smoke(path):
    """No-media ABI smoke in a child process: load, begin, status, stop, no epochs."""
    code = ('import ctypes,sys,json;sys.path.insert(0,%r);import m68k_coverage_core as m;'
            'd=ctypes.CDLL(%r);v=m.Coverage(d);s0=v.status();v.begin();v.frame(7);s1=v.status();v.stop();'
            'h=m.Header();r=d.neptune_m68kcov_header_get(0,ctypes.byref(h));'
            'again=d.neptune_m68kcov_begin();print(json.dumps([s0,s1,r,again]))') % (str(HERE), str(path))
    done = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise ValueError('Observer ABI smoke failed: ' + done.stderr[-400:])
    before, during, missing, again = json.loads(done.stdout)
    if (before['on'] or before['epochs'] or not during['on'] or during['epochs']
            or missing != -1 or again != -1):
        raise ValueError('Observer ABI smoke returned unexpected state')
    return {'before': before, 'during': during, 'missing_epoch_read': missing, 'second_begin': again,
            'original_game_bytes_executed': False}


def prepare(reference, output, timeout=900):
    reference, output = Path(reference).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Use a fresh prepared-core directory')
    verify_reference(reference)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.m68kcov-', dir=output.parent))
    tree = stage / 'beetle'
    shutil.copytree(reference, tree, symlinks=True, ignore=shutil.ignore_patterns('.git'), copy_function=shutil.copy2)
    content = {name: (tree / name).read_bytes() for name in SOURCES}
    patched = patch_sources(content, HEADER.read_bytes())
    for name, data in patched.items():
        (tree / name).write_bytes(data)
    (tree / 'mednafen_saturn_libretro.so').unlink()
    started = time.monotonic()
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'HOME', 'TMPDIR')}
    done = subprocess.run(['nice', '-n', '10', *BUILD], cwd=tree, capture_output=True, timeout=timeout, env=env)
    (stage / 'build.stdout').write_bytes(done.stdout)
    (stage / 'build.stderr').write_bytes(done.stderr)
    if done.returncode:
        raise ValueError('Instrumented core build failed; diagnostics retained in ' + str(stage))
    binary = tree / 'mednafen_saturn_libretro.so'
    rebuilt = sorted(line.split()[1] for line in done.stdout.decode(errors='replace').splitlines()
                     if line.startswith('CC ') and len(line.split()) == 2)
    receipt = {'schema': 'neptune.m68k-coverage-core.v1', 'status': 'ready', 'observer_abi': 1,
               'reference_revision': REVISION, 'reference_tree': TREE, 'reference_core_sha256': REFERENCE_CORE,
               'source_hashes': SOURCES, 'patched_hashes': {k: digest(v) for k, v in patched.items()},
               'header_sha256': digest(HEADER.read_bytes()), 'preparer_sha256': digest(Path(__file__).read_bytes()),
               'build_command': BUILD, 'build_seconds': round(time.monotonic() - started, 3),
               'compiler': subprocess.run(['cc', '--version'], capture_output=True, text=True).stdout.splitlines()[0],
               'recompiled_objects': rebuilt, 'binary_sha256': digest(binary.read_bytes()),
               'binary_bytes': binary.stat().st_size, 'exports': ['neptune_m68kcov_' + n for n in EXPORTS],
               'capacities': {'epochs': 16, 'pc_words': WORDS, 'edges': EDGE_CAPACITY, 'edge_limit': EDGE_CAPACITY * 3 // 4},
               'smoke': smoke(binary), 'licence': 'patched core is GPL-2.0+ (upstream COPYING retained in tree)',
               'limitations': ['Observation of the Beetle/Mednafen 68000 interpreter only, not hardware',
                               'PC/opcode/edge coverage, not data accesses, timing or SCSP state']}
    (stage / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    os.rename(stage, output)
    return receipt


def load_prepared(directory):
    directory = Path(directory)
    receipt = json.loads((directory / 'receipt.json').read_text())
    binary = directory / 'beetle/mednafen_saturn_libretro.so'
    if (receipt.get('status') != 'ready' or receipt.get('header_sha256') != digest(HEADER.read_bytes())
            or receipt.get('source_hashes') != SOURCES or digest(binary.read_bytes()) != receipt.get('binary_sha256')):
        raise ValueError('Prepared coverage core receipt/identity mismatch')
    return binary, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args(argv)
    try:
        receipt = prepare(args.reference, args.output, args.timeout)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps({k: receipt[k] for k in ('status', 'binary_sha256', 'build_seconds', 'recompiled_objects')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
