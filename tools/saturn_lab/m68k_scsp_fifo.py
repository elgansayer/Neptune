#!/usr/bin/env python3
"""Prepare ABI3: bounded Musashi plus pinned, clock-frozen SCSP MIDI output FIFO.

Extract reference functions from external hash-pinned sources, including their
interrupt side effects. No game bytes or vendor implementation live here.
"""
from __future__ import annotations

import argparse
import ctypes as c
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import m68k_probe as short
import probe_kernel as pinned

LOCK = Path(__file__).with_name('scsp-fifo-source-lock.json')
BASE_SHA256 = '1ae72479a22f91955343cb9fe157f261218e9c3a9ee8b8e7a6d519cda766cceb'
ABI = 3
FIELDS = tuple([f'output{i}' for i in range(4)] +
               ['rp', 'wp', 'count', 'flags'] + [f'input{i}' for i in range(4)] +
               ['input_rp', 'input_wp', 'input_count', 'divider', 'transmit_bits',
                'transmit_buffer', 'scipd', 'mcipd', 'sound_irq', 'main_irq'])
FUNCTIONS = ('SS_SCSP_RecalcSoundInt', 'SS_SCSP_RecalcMainInt',
             'SS_SCSP_MIDI_Reset', 'SS_SCSP_MIDI_WriteOutput')


def function(source, name):
    matches = list(re.finditer(r'^static (?:INLINE )?void ' + re.escape(name) +
                              r'\([^\n]*\)[^\n;]*\n\{', source, re.M))
    if len(matches) != 1:
        raise ValueError('Reference definition not unique: ' + name)
    match = matches[0]
    depth = 0
    # Comments and literals cannot contribute braces to the function boundary.
    tokens = re.finditer(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]',
                         source[match.end()-1:])
    for token in tokens:
        if token.group() == '{': depth += 1
        elif token.group() == '}':
            depth -= 1
            if depth == 0:
                end = match.end()-1+token.end()
                return source[match.start():end]+'\n'
    raise ValueError('Unterminated reference definition')


def extract_component(sources):
    sources = Path(sources)
    lock = json.loads(LOCK.read_text())
    blobs = {}
    for relative, sha in lock['files'].items():
        data = pinned.read_bounded(sources/relative, 2*1024*1024)
        if pinned.digest(data) != sha:
            raise ValueError('Pinned SCSP source changed: ' + relative)
        blobs[relative] = data.decode()
    header, source = blobs['mednafen/ss/scsp.h'], blobs['mednafen/ss/scsp.inc']
    enum = re.findall(r'enum\n\{\n MIDIF_INPUT_EMPTY[^}]+\};', header)
    midi = re.findall(r' struct\n \{\n  uint8_t InputFIFO\[4\];[\s\S]+?\n \} MIDI;', header)
    irq = re.findall(r' uint16_t SCIEB;[\s\S]+? uint8_t SCILV\[3\];', header)
    if len(enum) != 1 or len(midi) != 1 or len(irq) != 1:
        raise ValueError('Reference data declarations not unique')
    # Preserve the complete upstream file/license notice, ahead of the TODO block.
    notice = source[:source.index('\n/*\n TODO:')]
    prefix = notice + '''
/* Generated narrow component. Serial clock frozen; interrupt enables zero.
 * Subset structure contains every field accessed by the verbatim functions.
 */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define INLINE inline
'''
    prefix += enum[0]+'\ntypedef struct {\n'+midi[0]+'\n'+irq[0]+'\n} SS_SCSP;\n'
    prefix += '''static SS_SCSP fifo;
static uint32_t sound_irq, main_irq;
static void SCSP_SoundIntChanged(unsigned level) { sound_irq=level; m68k_set_irq(level); }
static void SCSP_MainIntChanged(bool active) { main_irq=active; }
'''
    definitions = '\n'.join(function(source, name) for name in FUNCTIONS)
    wrappers = '''
int neptune_fifo_configure(uint32_t count, uint32_t rp, uint32_t seed, uint32_t pending) {
    if(count>4 || rp>3 || (pending!=0 && pending!=0x200)) return 0;
    memset(&fifo,0,sizeof(fifo));
    SS_SCSP_MIDI_Reset(&fifo);
    fifo.MIDI.OutputRP=fifo.MIDI.OutputWP=rp;
    for(uint32_t i=0;i<count;i++) SS_SCSP_MIDI_WriteOutput(&fifo,(seed>>(24-8*i))&255);
    fifo.SCIPD=fifo.MCIPD=pending;
    SS_SCSP_RecalcSoundInt(&fifo); SS_SCSP_RecalcMainInt(&fifo);
    return 1;
}
void neptune_fifo_snapshot(uint32_t *out) {
    for(unsigned i=0;i<4;i++) out[i]=fifo.MIDI.OutputFIFO[i];
    out[4]=fifo.MIDI.OutputRP; out[5]=fifo.MIDI.OutputWP;
    out[6]=fifo.MIDI.OutputCount; out[7]=fifo.MIDI.Flags;
    for(unsigned i=0;i<4;i++) out[8+i]=fifo.MIDI.InputFIFO[i];
    out[12]=fifo.MIDI.InputRP; out[13]=fifo.MIDI.InputWP; out[14]=fifo.MIDI.InputCount;
    out[15]=fifo.MIDI.SimuClockDivider; out[16]=fifo.MIDI.TransmitBitCounter;
    out[17]=fifo.MIDI.TransmitBuffer; out[18]=fifo.SCIPD; out[19]=fifo.MCIPD;
    out[20]=sound_irq; out[21]=main_irq;
}
'''
    return (prefix+definitions+wrappers).encode()


def generated_source():
    source = short.BACKEND.read_bytes()
    if pinned.digest(source) != BASE_SHA256:
        raise ValueError('Accepted backend changed; reconcile ABI3 explicitly')
    substitutions = (
        (b'#include "m68k.h"', b'#include "m68k.h"\n#include "scsp_fifo_component.h"'),
        (b'uint32_t neptune_m68k_abi(void) { return 1; }',
         b'uint32_t neptune_m68k_abi(void) { return 3; }'),
        (b'static uint32_t read_data(uint32_t address, uint32_t size) {',
         b'''static uint32_t read_data(uint32_t address, uint32_t size) {
    if(address==0x100404 && size==1) {
        uint32_t value=fifo.MIDI.Flags; event(1,address,size,value); return value;
    }'''),
        (b'static void write_data(uint32_t address, uint32_t size, uint32_t value) {',
         b'''static void write_data(uint32_t address, uint32_t size, uint32_t value) {
    if(address==0x100407 && size==1) {
        event(2,address,size,value&255); SS_SCSP_MIDI_WriteOutput(&fifo,value&255); return;
    }'''))
    for old, new in substitutions:
        if source.count(old) != 1: raise ValueError('Ambiguous ABI3 substitution')
        source = source.replace(old, new)
    return source


def identity():
    return {'base_identity': short.identity(), 'abi': ABI,
            'scsp_source_lock_sha256': pinned.digest(LOCK.read_bytes()),
            'derived_backend_sha256': pinned.digest(generated_source()),
            'component_sha256': json.loads(LOCK.read_text())['component_sha256'],
            'profile': 'SCSP-MIDI-output-frozen-clock-interrupt-enables-zero'}


def fifo_contract(count=0, rp=0, seed=0x12345678, pending=0, push=None):
    """Independent Python oracle for the selected frozen FIFO transition."""
    data = [0]*4
    for i in range(count): data[(rp+i)&3] = (seed>>(24-8*i))&255
    wp = (rp+count)&3
    if push is not None and count < 4:
        data[wp] = push
        wp = (wp+1)&3
        count += 1
        pending = 0
    values = data + [rp, wp, count, 1 | (8 if count==0 else 0) | (16 if count==4 else 0)]
    values += [0]*10 + [pending, pending, 0, 0]
    return dict(zip(FIELDS, values))


class Library(short.Library):
    def __init__(self, directory, require_receipt=True):
        directory = Path(directory)
        self.path = directory/'libneptune_m68k_scsp_fifo.so'
        lock = json.loads(LOCK.read_text())
        if pinned.digest(pinned.read_bounded(directory/'scsp_fifo_component.h', 65536)) != lock['component_sha256']:
            raise ValueError('Prepared reference component differs')
        if require_receipt:
            receipt = json.loads(pinned.read_bounded(directory/'receipt.json', 65536))
            if (receipt.get('identity') != identity() or receipt.get('status') != 'ready'
                    or receipt.get('binary_sha256') != pinned.digest(pinned.read_bounded(self.path, 8*1024*1024))
                    or receipt.get('owned_smoke', {}).get('original_game_bytes_executed') is not False):
                raise ValueError('Prepared FIFO identity failed')
        self.library = c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype = c.c_uint32
        if self.library.neptune_m68k_abi() != ABI: raise ValueError('FIFO requires ABI3')
        self.library.neptune_m68k_run.argtypes = [c.POINTER(short.Request), c.POINTER(short.Result)]
        self.library.neptune_m68k_run.restype = c.c_int
        self.library.neptune_fifo_configure.argtypes = [c.c_uint32]*4
        self.library.neptune_fifo_configure.restype = c.c_int
        self.library.neptune_fifo_snapshot.argtypes = [c.POINTER(c.c_uint32)]
        self.library.neptune_fifo_snapshot.restype = None

    def snapshot(self):
        values = (c.c_uint32*len(FIELDS))()
        self.library.neptune_fifo_snapshot(values)
        return dict(zip(FIELDS, values))

    def run(self, *args, device=(0, 0, 0x12345678, 0), **kwargs):
        if (len(device)!=4 or any(type(v) is not int or not 0<=v<=0xFFFFFFFF for v in device)
                or not self.library.neptune_fifo_configure(*device)):
            raise ValueError('Invalid frozen FIFO fixture')
        before = self.snapshot()
        actual = super().run(*args, **kwargs)
        return {**actual, 'device_before': before, 'device_after': self.snapshot()}


def smoke(library):
    inherited = short.smoke(library)
    code = bytearray(0x200)
    # Owned MOVE.B abs.l,D0; MOVE.B D1,abs.l; RTS: read status, then push.
    code[0x100:0x10E] = bytes.fromhex('1039 0010 0404 13c1 0010 0407 4e75')
    regs = [0xA5A5A5A5]*18
    regs[1] = 0xE7
    regs[15:18] = [0x70000, 0x100, 0x2700]
    regions = [(0x70000, (0xFFF000).to_bytes(4,'big'), False)]
    selected = 0
    for count in range(5):
        for rp in range(4):
            for pending in (0, 0x200):
                fixture = count, rp, 0x12345678, pending
                actual = library.run(code, 0x100, 0xFFF000, [(0x100,0x10E)], regions, regs, device=fixture)
                before, after = fifo_contract(*fixture), fifo_contract(*fixture, push=0xE7)
                if (actual['status_code']!=1 or actual['device_before']!=before or actual['device_after']!=after
                        or actual['events']!=[[1,0x100404,1,before['flags']], [2,0x100407,1,0xE7], [1,0x70000,4,0xFFF000]]):
                    raise ValueError('Owned reference FIFO reset/push/wrap/full/interrupt smoke failed')
                selected += 1
    controls = {}
    for name, words, expected in (
            ('wrong_status_width', '3039 0010 0404', 4),
            ('unsupported_input_read', '1039 0010 0405', 4),
            ('unsupported_even_write', '13c1 0010 0406', 5)):
        altered = bytearray(code); data = bytes.fromhex(words); altered[0x100:0x100+len(data)] = data
        actual = library.run(altered,0x100,0xFFF000,[(0x100,0x10E)],regions,regs)
        if actual['status_code'] != expected: raise ValueError('FIFO MMIO guard failed')
        controls[name] = actual['status']
    if short.smoke(library) != inherited: raise ValueError('FIFO context recovery failed')
    return {**inherited, 'reference_fifo_cases': selected, 'mmio_guards': controls,
            'serial_clock_advanced': False, 'interrupt_enables': 0}


def prepare(sources, scsp_sources, cache):
    sources, cache = Path(sources), Path(cache)
    lock = json.loads(short.SOURCE_LOCK.read_text())
    for relative, sha in lock['files'].items():
        if pinned.digest(pinned.read_bounded(sources/relative, 2*1024*1024)) != sha:
            raise ValueError('Pinned CPU source changed')
    component = extract_component(scsp_sources)
    if pinned.digest(component) != json.loads(LOCK.read_text())['component_sha256']:
        raise ValueError('Reference extraction identity changed')
    if cache.exists():
        library = Library(cache); smoke(library)
        return json.loads((cache/'receipt.json').read_text())
    cache.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.m68k-fifo-prepare-', dir=cache.parent))
    (stage/'scsp_fifo_component.h').write_bytes(component)
    (stage/'COPYING.SCSP').write_bytes((Path(scsp_sources)/'COPYING').read_bytes())
    backend = stage/'bounded_fifo_backend.c'; backend.write_bytes(generated_source())
    vendor = sources/'runtime/third_party/musashi'
    command = ['/usr/bin/cc', *short.FLAGS, '-I', str(vendor), '-o', str(stage/'libneptune_m68k_scsp_fifo.so'),
               str(backend), str(vendor/'m68kcpu.c'), str(vendor/'m68kops.c'), str(vendor/'softfloat/softfloat.c'), '-lm']
    completed = subprocess.run(command, capture_output=True, timeout=60)
    (stage/'build.stdout').write_bytes(completed.stdout); (stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode: raise ValueError('ABI3 compile failed; stage diagnostics retained')
    library = Library(stage, require_receipt=False); owned = smoke(library)
    receipt = {'schema':'neptune.prepared-m68k-scsp-fifo.v1', 'status':'ready', 'identity':identity(),
               'source_revision':lock['revision'], 'source_files':lock['files'],
               'scsp_source_lock':json.loads(LOCK.read_text()), 'owned_smoke':owned,
               'binary_sha256':pinned.digest(library.path.read_bytes()),
               'compiler':subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],
               'compile_timeout_seconds':60, 'compile_exit':completed.returncode, 'preparation_has_original_inputs':False,
               'limitations':['Frozen MIDI serial clock; no draining, samples, DSP or complete SCSP',
                              'Interrupt enables fixed zero; pending clear and real recalculation retained',
                              'Only read8 100404 and write8 100407; all other MMIO unmapped',
                              'Reference full-write discard remains upstream TODO, not hardware proof',
                              'Existing ABI1/ABI2 sources, caches and all host/provider limits preserved']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    os.rename(stage, cache)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True)
    parser.add_argument('--scsp-sources',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True)
    args = parser.parse_args(argv)
    result = prepare(args.sources,args.scsp_sources,args.cache)
    print(json.dumps({'status':result['status'], 'abi':ABI, 'binary_sha256':result['binary_sha256'],
                      'original_game_bytes_executed':False}))


if __name__ == '__main__': main()
