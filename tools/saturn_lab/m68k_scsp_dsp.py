#!/usr/bin/env python3
"""ABI4: source-pinned SCSP DSP word registers, with all device clocks frozen.

External reference bodies are extracted, never treated as a flat memory region.
Only even word writes700..BFE and defined word reads are supported.
"""
from __future__ import annotations
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import m68k_probe as short
import m68k_scsp_fifo as fifo
import probe_kernel as pinned

ABI = 4
LOCK = Path(__file__).with_name('scsp-dsp-source-lock.json')
BASE_SHA256 = fifo.BASE_SHA256


def extract_component(sources):
    lock = json.loads(LOCK.read_text())
    blobs = {}
    for name, sha in lock['files'].items():
        data = pinned.read_bounded(Path(sources)/name, 2*1024*1024)
        if pinned.digest(data) != sha:
            raise ValueError('Pinned SCSP source changed: '+name)
        blobs[name] = data.decode()
    header, source = blobs['mednafen/ss/scsp.h'], blobs['mednafen/ss/scsp.inc']
    declarations = []
    for name in ('SS_SCSP_DSPStep', 'SS_SCSP_DSPS'):
        matches = re.findall(r'struct '+name+r'\n\{[\s\S]+?\n\};', header)
        if len(matches) != 1: raise ValueError('Ambiguous DSP declaration')
        declarations.append('typedef struct '+name+' '+name+';\n'+matches[0])
    macros = source[source.index('#ifdef MSB_FIRST'):source.index('/* internal forward declarations')]
    definitions = []
    for suffix in ('W0', 'W1'):
        name = 'SS_SCSP_RW_u16_'+suffix
        full = fifo.function(source.replace('\nINLINE void ', '\nstatic INLINE void '), name)
        tail = full[full.index(' if(A >= 0x700 && A <= 0x77F)'):]
        tail = tail[:tail.index(' //\n // z->DSP work buffer')]
        definitions.append('static void '+name+'(SS_SCSP* z, uint32_t A, uint16_t* DBV_p)\n{\n'+tail+'}\n')
    prefix = source[:source.index('\n/*\n TODO:')]+"""
/* Generated selected register branches, not a complete SCSP implementation.
 * Adapter restricts A to even700..BFE, after upstream register address masking.
 * Gap7C0..7FF writes fall through unchanged; reads are deliberately unsupported.
 * No clock, decode, interrupt, slot or audio processing is called.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
"""
    wrappers = """
typedef struct { uint64_t before[4]; SS_SCSP_DSPS DSP; uint64_t after[4]; } SS_SCSP;
static SS_SCSP dsp;
"""
    postfix = """
int neptune_dsp_configure(uint32_t seed, uint32_t dirty) {
    if(dirty>1) return 0;
    uint8_t *p=(uint8_t*)&dsp;
    for(unsigned i=0;i<sizeof(dsp);i++) p[i]=(uint8_t)((seed>>(8*(i%4))) ^ (i*37));
    for(unsigned i=0;i<64;i++) dsp.DSP.COEF[i]&=0x1FFF;
    dsp.DSP.WritePending=(seed&1)!=0;
    dsp.DSP.MPROG_Dirty=dirty!=0;
    return 1;
}
void neptune_dsp_snapshot(uint64_t *out, uint8_t *untouched) {
    for(unsigned i=0;i<64;i++) out[i]=dsp.DSP.COEF[i];
    for(unsigned i=0;i<32;i++) out[64+i]=dsp.DSP.MADRS[i];
    for(unsigned i=0;i<128;i++) out[96+i]=dsp.DSP.MPROG[i];
    out[224]=dsp.DSP.MPROG_Dirty;
    SS_SCSP saved;
    memcpy(&saved,&dsp,sizeof(saved));
    memset(saved.DSP.COEF,0,sizeof(saved.DSP.COEF));
    memset(saved.DSP.MADRS,0,sizeof(saved.DSP.MADRS));
    memset(saved.DSP.MPROG,0,sizeof(saved.DSP.MPROG));
    saved.DSP.MPROG_Dirty=false;
    memcpy(untouched,&saved,sizeof(saved));
}
uint32_t neptune_dsp_state_size(void) { return sizeof(dsp); }
int neptune_dsp_access(uint32_t write, uint32_t address, uint32_t size, uint32_t *value) {
    if(write>1 || size!=2 || (address&1) || address<0x100700 || address>0x100BFE ||
       (!write && address>=0x1007C0 && address<0x100800)) return 0;
    uint16_t bus=*value;
    if(write) SS_SCSP_RW_u16_W1(&dsp,address&0xFFF,&bus);
    else SS_SCSP_RW_u16_W0(&dsp,address&0xFFF,&bus);
    *value=bus;
    return 1;
}
"""
    return (prefix+'\n'.join(declarations)+'\n'+macros+wrappers+'\n'.join(definitions)+postfix).encode()


def generated_source():
    source = short.BACKEND.read_bytes()
    if pinned.digest(source) != BASE_SHA256: raise ValueError('Accepted backend changed; reconcile ABI4')
    substitutions = (
        (b'#include "m68k.h"', b'#include "m68k.h"\n#include "scsp_dsp_component.h"'),
        (b'uint32_t neptune_m68k_abi(void) { return 1; }', b'uint32_t neptune_m68k_abi(void) { return 4; }'),
        (b'static uint32_t read_data(uint32_t address, uint32_t size) {', b"""static uint32_t read_data(uint32_t address, uint32_t size) {
    uint32_t bus=0;
    if(neptune_dsp_access(0,address,size,&bus)) { event(1,address,size,bus); return bus; }"""),
        (b'static void write_data(uint32_t address, uint32_t size, uint32_t value) {', b"""static void write_data(uint32_t address, uint32_t size, uint32_t value) {
    uint32_t bus=value;
    if(neptune_dsp_access(1,address,size,&bus)) { event(2,address,size,value&0xFFFF); return; }"""))
    for old, new in substitutions:
        if source.count(old)!=1: raise ValueError('Ambiguous ABI4 substitution')
        source=source.replace(old,new)
    return source


def identity():
    return {'base_identity':short.identity(), 'abi':ABI,
            'scsp_source_lock_sha256':pinned.digest(LOCK.read_bytes()),
            'derived_backend_sha256':pinned.digest(generated_source()),
            'component_sha256':json.loads(LOCK.read_text())['component_sha256'],
            'profile':'SCSP-DSP-even-word-registers-clock-frozen-no-gap-read'}


def transition(before, address, value):
    """Independent logical register oracle, not a native byte-array alias."""
    if type(address) is not int or address&1 or not 0x100700<=address<=0x100BFE:
        raise ValueError('Unsupported word destination')
    if type(value) is not int or not 0<=value<=0xFFFF: raise ValueError('Not a word')
    after={key:list(v) if isinstance(v,list) else v for key,v in before.items()}
    offset=address-0x100000
    if offset<0x780: after['coef'][(offset-0x700)//2]=value>>3
    elif offset<0x7C0: after['madrs'][(offset-0x780)//2]=value
    elif offset>=0x800:
        index=(offset-0x800)//8
        shift=(3-((offset-0x800)%8)//2)*16
        after['mprog'][index]=(after['mprog'][index]&~(0xFFFF<<shift))|(value<<shift)
        after['dirty']=1
    return after


class Library(short.Library):
    def __init__(self, directory, require_receipt=True):
        directory=Path(directory)
        self.path=directory/'libneptune_m68k_scsp_dsp.so'
        if pinned.digest(pinned.read_bounded(directory/'scsp_dsp_component.h',65536))!=json.loads(LOCK.read_text())['component_sha256']:
            raise ValueError('Prepared DSP component differs')
        if require_receipt:
            receipt=json.loads(pinned.read_bounded(directory/'receipt.json',65536))
            if (receipt.get('identity')!=identity() or receipt.get('status')!='ready' or
                receipt.get('binary_sha256')!=pinned.digest(pinned.read_bounded(self.path,8*1024*1024))):
                raise ValueError('Prepared DSP identity failed')
        self.library=c.CDLL(str(self.path.resolve()))
        self.library.neptune_m68k_abi.restype=c.c_uint32
        if self.library.neptune_m68k_abi()!=ABI: raise ValueError('DSP requires ABI4')
        self.library.neptune_m68k_run.argtypes=[c.POINTER(short.Request),c.POINTER(short.Result)]
        self.library.neptune_m68k_run.restype=c.c_int
        self.library.neptune_dsp_configure.argtypes=[c.c_uint32,c.c_uint32]
        self.library.neptune_dsp_configure.restype=c.c_int
        self.library.neptune_dsp_snapshot.argtypes=[c.POINTER(c.c_uint64),c.POINTER(c.c_uint8)]
        self.library.neptune_dsp_snapshot.restype=None
        self.library.neptune_dsp_state_size.restype=c.c_uint32
        self.state_size=self.library.neptune_dsp_state_size()
        if not 4000<=self.state_size<=16384: raise ValueError('Unexpected reference DSP structure size')
        self.library.neptune_dsp_access.argtypes=[c.c_uint32]*3+[c.POINTER(c.c_uint32)]
        self.library.neptune_dsp_access.restype=c.c_int

    def configure(self, device):
        if (len(device)!=2 or any(type(v) is not int or not 0<=v<=0xFFFFFFFF for v in device)
                or not self.library.neptune_dsp_configure(*device)): raise ValueError('Invalid DSP fixture')

    def snapshot(self):
        values=(c.c_uint64*225)(); untouched=(c.c_uint8*self.state_size)()
        self.library.neptune_dsp_snapshot(values,untouched)
        return {'coef':list(values[:64]),'madrs':list(values[64:96]),'mprog':list(values[96:224]),
                'dirty':values[224], 'unrelated_sha256':hashlib.sha256(bytes(untouched)).hexdigest()}

    def run(self,*args,device=(0x12345678,0),**kwargs):
        self.configure(device); before=self.snapshot()
        actual=super().run(*args,**kwargs)
        return {**actual,'device_before':before,'device_after':self.snapshot()}


def smoke(library):
    inherited=short.smoke(library)
    selected=0
    for seed,dirty in ((0,0),(0x12345678,0),(0xFFFFFFFF,1)):
        for address in range(0x100700,0x100C00,2):
            for value in (0,1,7,8,0x7FFF,0x8000,0xFFFF,0x5555,0xAAAA):
                library.configure((seed,dirty)); before=library.snapshot(); bus=c.c_uint32(value)
                if library.library.neptune_dsp_access(1,address,2,c.byref(bus))!=1:
                    raise ValueError('Defined reference write rejected')
                expected=transition(before,address,value)
                if library.snapshot()!=expected: raise ValueError('Reference register effect differs from oracle')
                if not 0x1007C0<=address<0x100800:
                    if library.library.neptune_dsp_access(0,address,2,c.byref(bus))!=1 or bus.value!=(value&0xFFF8 if address<0x100780 else value):
                        raise ValueError('Reference word readback failed')
                    if library.snapshot()!=expected: raise ValueError('Reference read changed device state')
                selected+=1
    code=bytearray(0x200)
    regs=[0xA5A5A5A5]*18; regs[1]=0x9B7D; regs[15:18]=[0x70000,0x100,0x2700]
    regions=[(0x70000,(0xFFF000).to_bytes(4,'big'),False)]
    cpu=0
    for address in range(0x100700,0x100C00,2):
        gap=0x1007C0<=address<0x100800
        words=bytes.fromhex('33c1')+address.to_bytes(4,'big')
        if not gap: words+=bytes.fromhex('3039')+address.to_bytes(4,'big')
        words+=bytes.fromhex('4e75'); code[0x100:0x100+len(words)]=words
        actual=library.run(code,0x100,0xFFF000,[(0x100,0x100+len(words))],regions,regs)
        events=[[2,address,2,regs[1]]]
        if not gap: events.append([1,address,2,regs[1]&0xFFF8 if address<0x100780 else regs[1]])
        events.append([1,0x70000,4,0xFFF000])
        if (actual['status_code']!=1 or actual['events']!=events or
                actual['device_after']!=transition(actual['device_before'],address,regs[1])):
            raise ValueError('Owned CPU register write/read/return failed')
        cpu+=1
    guards={}
    for name,opcode,address,expected in (
        ('odd_word_write','33c1',0x100701,3),('odd_word_read','3039',0x100801,3),
        ('byte_write','13c1',0x100700,5),('long_write','23c1',0x100800,5),
        ('byte_read','1039',0x100780,4),('long_read','2039',0x100800,4),
        ('gap_read','3039',0x1007C0,4),('before_range','33c1',0x1006FE,5),
        ('after_range','33c1',0x100C00,5)):
        words=bytes.fromhex(opcode)+address.to_bytes(4,'big')+bytes.fromhex('4e75')
        code[0x100:0x100+len(words)]=words
        actual=library.run(code,0x100,0xFFF000,[(0x100,0x100+len(words))],regions,regs)
        if actual['status_code']!=expected or actual['device_after']!=actual['device_before']:
            raise ValueError('Device guard failed: '+name)
        guards[name]=actual['status']
    if short.smoke(library)!=inherited: raise ValueError('CPU context recovery failed')
    return {**inherited,'reference_word_cases':selected,'cpu_word_cases':cpu,'mmio_guards':guards,
            'device_clocks_advanced':False,'interrupt_processing_called':False}


def prepare(sources,scsp_sources,cache):
    sources,cache=Path(sources),Path(cache)
    lock=json.loads(short.SOURCE_LOCK.read_text())
    for relative,sha in lock['files'].items():
        if pinned.digest(pinned.read_bounded(sources/relative,2*1024*1024))!=sha:
            raise ValueError('Pinned CPU source changed')
    component=extract_component(scsp_sources)
    if pinned.digest(component)!=json.loads(LOCK.read_text())['component_sha256']:
        raise ValueError('Reference extraction identity changed')
    if cache.exists():
        library=Library(cache); smoke(library)
        return json.loads((cache/'receipt.json').read_text())
    cache.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.m68k-dsp-prepare-',dir=cache.parent))
    (stage/'scsp_dsp_component.h').write_bytes(component)
    (stage/'COPYING.SCSP').write_bytes((Path(scsp_sources)/'COPYING').read_bytes())
    backend=stage/'bounded_dsp_backend.c'; backend.write_bytes(generated_source())
    vendor=sources/'runtime/third_party/musashi'
    command=['/usr/bin/cc',*short.FLAGS,'-I',str(vendor),'-o',str(stage/'libneptune_m68k_scsp_dsp.so'),
             str(backend),str(vendor/'m68kcpu.c'),str(vendor/'m68kops.c'),str(vendor/'softfloat/softfloat.c'),'-lm']
    completed=subprocess.run(command,capture_output=True,timeout=60)
    (stage/'build.stdout').write_bytes(completed.stdout); (stage/'build.stderr').write_bytes(completed.stderr)
    if completed.returncode: raise ValueError('ABI4 compile failed; stage diagnostics retained')
    library=Library(stage,require_receipt=False); owned=smoke(library)
    receipt={'schema':'neptune.prepared-m68k-scsp-dsp.v1','status':'ready','identity':identity(),
             'source_revision':lock['revision'],'source_files':lock['files'],
             'scsp_source_lock':json.loads(LOCK.read_text()),'owned_smoke':owned,
             'binary_sha256':pinned.digest(library.path.read_bytes()),
             'compiler':subprocess.check_output(['/usr/bin/cc','--version'],text=True).splitlines()[0],
             'compile_timeout_seconds':60,'compile_exit':completed.returncode,'preparation_has_original_inputs':False,
             'limitations':['Device clocks frozen; no DSP execution, samples, slot or interrupt processing',
                            'Only even word writes100700..100BFE and defined reads; gap writes have no effect',
                            'Odd access is a native guard, not a68000 exception implementation',
                            'Pinned reference component, not independent hardware validation; ABIs1/2/3 intact']}
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    os.rename(stage,cache)
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True)
    parser.add_argument('--scsp-sources',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True)
    args=parser.parse_args(argv)
    result=prepare(args.sources,args.scsp_sources,args.cache)
    print(json.dumps({'status':result['status'],'abi':ABI,'binary_sha256':result['binary_sha256'],
                      'original_game_bytes_executed':False}))


if __name__=='__main__':main()
