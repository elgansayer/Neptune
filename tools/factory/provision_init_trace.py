#!/usr/bin/env python3
"""Prepare a separate first-task/library observer in a disposable matched core."""
import argparse
import json
from pathlib import Path
import sys

from provision_call_trace import REVISION, SOURCES, digest, plain


def prepare(source, header=None):
    source = Path(source).absolute()
    header = header or Path(__file__).with_name('provision_init_trace.h')
    content = {name: plain(source/name) for name in SOURCES}
    if any(digest(content[name]) != expected for name, expected in SOURCES.items()):
        raise ValueError('Core source differs from the inspected reference pin')
    destination = source/'mednafen/ss/neptune_init_trace.h'
    if destination.exists() or destination.is_symlink():
        raise ValueError('Use a fresh disposable core checkout; initialization observer already exists')
    main = content['mednafen/ss/ss.c']; anchor = b'#include "sh7095.inc"'
    if main.count(anchor) != 1: raise ValueError('Ambiguous core inclusion point')
    main = main.replace(anchor, b'#include "neptune_init_trace.h"\n'+anchor)
    steps = content['mednafen/ss/sh7095.inc']; dispatch = b' const uint32_t instr = (uint16_t)z->Pipe_ID;'
    for name in (b'SH7095_Step_w0_C0', b'SH7095_Step_w0_C1'):
        signature = b'FORCE_INLINE void '+name+b'(SH7095* z)\n{'
        if steps.count(signature) != 1: raise ValueError('Missing/ambiguous matched master dispatch')
        start = steps.index(signature)+len(signature); offset = steps.index(dispatch, start)
        if offset-start > 2048: raise ValueError('Master pipeline anchor outside inspected boundary')
        steps = steps[:offset]+b' neptune_init_step(z);\n'+steps[offset:]
    exports = content['link.T']
    if exports.count(b'global: retro_*;') != 1: raise ValueError('Missing inspected export boundary')
    exports = exports.replace(b'global: retro_*;', b'global: retro_*; '+b' '.join(
        ('neptune_init_'+name+';').encode() for name in ('begin', 'frame', 'stop', 'status', 'records', 'witness')))
    ops = content['mednafen/ss/sh7095_ops.inc']
    start = ops.index(b' #define FUSE_DELAY_SLOT_NOP()'); end = ops.index(b' // Triplet fusion:', start)
    fusion = ops[start:end]; increment = b'   z->PC += 2;'
    if fusion.count(increment) != 1: raise ValueError('Missing/ambiguous inspected fused NOP boundary')
    fusion = fusion.replace(increment, b'   if(!which) neptune_init_fused_nop(z);\t\t\\\r\n'+increment)
    ops = ops[:start]+fusion+ops[end:]
    outputs = {'mednafen/ss/ss.c': main, 'mednafen/ss/sh7095.inc': steps,
               'mednafen/ss/sh7095_ops.inc': ops, 'link.T': exports,
               'mednafen/ss/neptune_init_trace.h': plain(header)}
    for name, data in outputs.items(): (source/name).write_bytes(data)
    return {'schema': 'neptune.init-trace-patch.v1', 'reference_revision': REVISION,
            'source_hashes': SOURCES, 'patched_hashes': {name: digest(data) for name, data in outputs.items()},
            'observer_abi': 1, 'cpu': 'master SH-2 interpreter only',
            'profiles': {'1': 'original89C8 from623A, return6240', '2': 'original95B04 from89C8, return8A18'},
            'capacity': 128, 'maximum_roots': 1, 'maximum_call_depth': 16,
            'maximum_pending_master_hooks': 4194304, 'maximum_pending_frames': 120,
            'source_witness_words': 2572, 'game_bytes_modified': False,
            'fused_nop_observation': 'actual master fused handler, value-only PC+2 normalization'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    try: print(json.dumps(prepare(args.source), sort_keys=True))
    except (ValueError, OSError) as error:
        print('FAIL: '+str(error), file=sys.stderr); raise SystemExit(1)
