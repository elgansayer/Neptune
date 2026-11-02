#!/usr/bin/env python3
"""Pinned static original-USA sound-driver discovery, not original CPU execution."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import probe_kernel as pinned

SOURCES = {
    'SND': (12976962, 'f5154d4aabdf9f3434b966a0d09fe5d08aa1ddabfa8848b836be630f506596d5', 0x44, 25556),
    'XBSND': (565040, '8343b6024271094cc9c1473d767e140f0c26089bae78b69811435be7941488d9', 0x11868, 25556),
    'NLSND': (23920, 'f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296', 0, 23920),
}
TOOL_HASHES = {
    'src/saturnrecomp/m68k.py': '9ef1cd11fc11cdac0a3c1c92f93260cb8c35063507f4701a03d6a8f87cfb9f47',
    'runtime/third_party/musashi/m68kdasm.c': 'c31b1d3a9863c4271fd0ddcddf3cde8fadac691909ca994db6ec41941696dca2',
    'runtime/third_party/musashi/m68k.h': '7fb10f51ee36d45f6e2be38d72aa0c57853810a816f1cf19e0f0c600bd1afa4a',
    'runtime/third_party/musashi/m68kconf.h': '236bfbbae2d19c2bc3c3455340dafd3a086a86d2de6f19371eb9c27be8de8abf',
}


def source_bytes(path, module):
    size, sha, offset, length = SOURCES[module]
    data = pinned.read_bounded(path, size)
    if len(data) != size or pinned.digest(data) != sha:
        raise ValueError('Original sound source identity differs from accepted disc inventory')
    return data[offset:offset + length]


def decoder(root):
    for relative, sha in TOOL_HASHES.items():
        if pinned.digest(pinned.read_bounded(root / relative, 262144)) != sha:
            raise ValueError('Pinned sound decoder source changed')
    spec = importlib.util.spec_from_file_location('_neptune_pinned_m68k', root / 'src/saturnrecomp/m68k.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector_summary(data):
    if len(data) < 0x400:
        raise ValueError('Sound driver lacks complete vector table')
    vectors = [int.from_bytes(data[a:a + 4], 'big') for a in range(0, 0x400, 4)]
    reset = vectors[1]
    if reset % 2 or not 0x400 <= reset < len(data):
        raise ValueError('Reset PC outside even in-image code candidate')
    entries = sorted({v for v in vectors[1:] if v % 2 == 0 and 0x400 <= v < len(data)})
    return {'initial_stack_pointer': hex(vectors[0]), 'reset_pc': hex(reset),
            'vector_table_sha256': pinned.digest(data[:0x400]),
            'vector_entries': [hex(v) for v in entries],
            'vector_target_counts': {hex(v): vectors[1:].count(v) for v in sorted(set(vectors[1:]))}}


def analyze(data, module, library):
    # Decode owned synthetic bytes before interpreting original code. No original
    # CPU is run by either this smoke or the original static traversal.
    owned = module.Image(bytes.fromhex('4e71 4e75 60fc'), library)
    for address, mnemonic in ((0, 'nop'), (2, 'rts'), (4, 'bra')):
        size, text = owned.insn(address)
        if size != 2 or not text.lower().startswith(mnemonic):
            raise ValueError('Owned decoder interoperability smoke failed')
    summary = vector_summary(data)
    image = module.Image(data, library)
    program = module.Program(image)
    code_bytes = program.code_bytes()
    if code_bytes & program.data:
        raise ValueError('Static decoder classified the same byte as code and data')
    gaps = program.gaps()
    if len(code_bytes) + len(program.data) + sum(n for _, n in gaps) != len(data):
        raise ValueError('Static candidate partition does not account for source extent')
    altered = bytearray(data)
    altered[4:8] = (int(summary['reset_pc'], 16) | 1).to_bytes(4, 'big')
    try:
        vector_summary(altered)
    except ValueError:
        control = True
    else:
        raise ValueError('Odd reset-vector negative control survived')
    return {**summary, 'owned_decoder_smoke_passed': True, 'odd_reset_vector_rejected': control,
            'driver_sha256': pinned.digest(data), 'driver_bytes': len(data),
            'candidate_instruction_count': len(program.code), 'candidate_code_bytes': len(code_bytes),
            'candidate_data_bytes': len(program.data),
            'unclassified_bytes': sum(n for _, n in gaps),
            'unclassified_ranges': [[hex(a), n] for a, n in gaps],
            'unresolved_transfers': [hex(a) for a in sorted(program.unresolved)],
            'bad_paths': {hex(a): why for a, why in sorted(program.bad.items())},
            'table_leads': [[hex(jump), kind, hex(first), n] for jump, kind, first, n in program.tables],
            'candidate_instructions_sha256': pinned.digest(json.dumps(sorted(program.code.items())).encode()),
            'original_game_bytes_executed': False,
            'first_reset_instruction_bytes': image.insn(int(summary['reset_pc'], 16))[0]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file', type=Path, required=True)
    parser.add_argument('--module', choices=tuple(SOURCES), required=True)
    parser.add_argument('--saturn-recomp', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': 'neptune.sound-code-discovery.v1', 'status': 'failure', 'module': args.module,
              'release': 'usa-mk81070-v1003', 'cpu': 'm68000', 'candidate_load_address': 0,
              'source_identity': list(SOURCES[args.module]), 'decoder_sources': TOOL_HASHES,
              'decoder_revision': pinned.INTERPRETER_REVISION,
              'wrapper_sha256': pinned.digest(Path(__file__).read_bytes()),
              'limitations': ['Static control-flow leads only, not execution or recovered function semantics',
                              'No natural load, self-modification, DSP, sound-event or audio validation',
                              'Candidate code/data partition is not complete executable coverage',
                              'Function denominator unknown; sound modules at zero have separate lifetimes']}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print('FAIL: report requires a fresh writable path')
        return 1
    with os.fdopen(fd, 'w') as output:
        phase = 'source_identity'
        try:
            data = source_bytes(args.source_file, args.module)
            module = decoder(args.saturn_recomp)
            phase = 'decoder_preparation'
            library = module.library(str(args.cache))
            phase = 'static_analysis'
            report.update(analyze(data, module, library), status='success')
        except (Exception, SystemExit) as error:
            report['error'] = {'phase': phase, 'type': type(error).__name__, 'reason': 'Source, decoder or analysis failed'}
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': report['status'], 'module': args.module,
                      'original_game_bytes_executed': False}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
