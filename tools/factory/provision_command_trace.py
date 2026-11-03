#!/usr/bin/env python3
"""Patch a fresh matched core for the separate707 command observer.

This component requires an explicit observer header. It is not an installed tool,
native build or original-game experiment. The trusted provisioner owns those.
"""
import argparse
import json
from pathlib import Path
import sys

from provision_call_trace import REVISION, SOURCES, digest, plain

READ16 = b' #define WB_READ16(r, A) { uint16_t memrv; MemRead16(A, memrv); WB_WRITE((r), (int16_t)memrv); }'
OBSERVED_READ16 = (b' #define WB_READ16(r, A) { const uint32_t neptune_command_address = (A); '
                   b'uint16_t memrv; MemRead16(neptune_command_address, memrv); '
                   b'WB_WRITE((r), (int16_t)memrv); '
                   b'if(!which) neptune_command_read(z, neptune_command_address, memrv); }')


def observed_ops(content):
    """Keep all fusion/CPU/bus operations; append value-only transfer observers."""
    source = content
    if source.count(READ16) != 1: raise ValueError('Missing/ambiguous matched data-word load macro')
    source = source.replace(READ16, OBSERVED_READ16)
    marker = b' BEGIN_OP(MOV_W_REG_REGINDIR)'
    if source.count(marker) != 1: raise ValueError('Missing/ambiguous matched word-store handler')
    start = source.index(marker); end = source.index(b' END_OP', start)
    store = source[start:end]; anchor = b'MemWrite16(ea, val);'
    if store.count(anchor) != 1: raise ValueError('Missing/ambiguous actual word-store operation')
    store = store.replace(anchor, anchor+b'\r\n\tif(!which) neptune_command_write(z, ea, (uint16_t)val);')
    source = source[:start]+store+source[end:]
    start = source.index(b' #define FUSE_DELAY_SLOT_NOP()'); end = source.index(b' // Triplet fusion:', start)
    fusion = source[start:end]; increment = b'   z->PC += 2;'
    if fusion.count(increment) != 1: raise ValueError('Missing/ambiguous actual fused NOP boundary')
    fusion = fusion.replace(increment, b'   if(!which) neptune_command_fused_nop(z);\t\t\\\r\n'+increment)
    source = source[:start]+fusion+source[end:]
    # Triplet fusion itself must stay byte-identical, including its timing steps.
    begin = b' // Triplet fusion:'; finish = b' #else'
    old = content[content.index(begin):content.index(finish,content.index(begin))]
    new = source[source.index(begin):source.index(finish,source.index(begin))]
    if old != new: raise ValueError('Command observation changed existing triplet fusion')
    return source


def prepare(source, header):
    source = Path(source).absolute(); header = Path(header).absolute()
    content = {name:plain(source/name) for name in SOURCES}
    if any(digest(content[name]) != expected for name,expected in SOURCES.items()):
        raise ValueError('Core source differs from the inspected historical reference pin')
    observer = plain(header)
    destination = source/'mednafen/ss/neptune_command_trace.h'
    if destination.exists() or destination.is_symlink(): raise ValueError('Require fresh disposable command-observer checkout')
    main = content['mednafen/ss/ss.c']; anchor = b'#include "sh7095.inc"'
    if main.count(anchor) != 1: raise ValueError('Missing/ambiguous matched core inclusion boundary')
    main = main.replace(anchor,b'#include "neptune_command_trace.h"\n'+anchor)
    steps = content['mednafen/ss/sh7095.inc']; dispatch = b' const uint32_t instr = (uint16_t)z->Pipe_ID;'
    for name in (b'SH7095_Step_w0_C0',b'SH7095_Step_w0_C1'):
        signature = b'FORCE_INLINE void '+name+b'(SH7095* z)\n{'
        if steps.count(signature) != 1: raise ValueError('Missing/ambiguous matched master dispatch')
        start = steps.index(signature)+len(signature); offset = steps.index(dispatch,start)
        if offset-start > 2048: raise ValueError('Master pipeline anchor outside inspected boundary')
        steps = steps[:offset]+b' neptune_command_step(z);\n'+steps[offset:]
    exports = content['link.T']
    if exports.count(b'global: retro_*;') != 1: raise ValueError('Missing/ambiguous matched export boundary')
    exports = exports.replace(b'global: retro_*;',b'global: retro_*; '+b' '.join(
        ('neptune_command_'+name+';').encode() for name in ('begin','frame','stop','status','records','witness')))
    outputs = {'mednafen/ss/ss.c':main,'mednafen/ss/sh7095.inc':steps,'link.T':exports,
               'mednafen/ss/sh7095_ops.inc':observed_ops(content['mednafen/ss/sh7095_ops.inc']),
               'mednafen/ss/neptune_command_trace.h':observer}
    for name,data in outputs.items(): (source/name).write_bytes(data)
    return {'schema':'neptune.command-trace-patch-component.v1','reference_revision':REVISION,
            'source_hashes':SOURCES,'patched_hashes':{name:digest(data) for name,data in outputs.items()},
            'header_sha256':digest(observer),'cpu':'master SH-2 interpreter only',
            'transfer_hooks':'actual MemRead16 result after WB_WRITE; actual MemWrite16 value after transfer; no second bus access',
            'single_address_evaluation':True,'triplet_fusion_unchanged':True,
            'fused_nop_observation':'actual master handler, value-only normalization required by supplied header',
            'component_only':True,'native_tool_ready':False,'original_game_bytes_executed':False,
            'remaining':'separate observer header/ABI/compiled nonmutation fixtures, trusted recipe/CI build/smoke/reuse, original reference-disabled-enabled validation'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--header',type=Path,required=True)
    a=p.parse_args(argv)
    try:print(json.dumps(prepare(a.source,a.header),sort_keys=True));return 0
    except (ValueError,OSError) as error:print('FAIL: '+str(error),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
