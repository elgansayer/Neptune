"""Pinned SH-2 stepping with explicit RAM aliases and non-executable handoffs.

This separate experiment profile leaves accepted readonly alias profiles intact.
No CPU instructions or device behaviour are implemented here.
"""
import probe_kernel as pinned
from probe_kernel_records import NAMES
from probe_split_add import map_inputs

MAX_STEPS=128


def observe(data,emu,entry,regions,before,*,ranges,literals,aliases,terminals,budget=MAX_STEPS):
    """Regions/aliases: (canonical/raw, bytes/canonical, writable/span[, writable])."""
    if not 0<budget<=MAX_STEPS:raise ValueError('Invalid handoff instruction budget')
    if len(data)!=pinned.SIZE:raise ValueError('Unexpected module size')
    if not ranges or not any(lo<=entry<hi for lo,hi in ranges):raise ValueError('Entry outside declared code')
    for lo,hi in ranges:
        if lo&1 or hi&1 or not pinned.BASE<=lo<hi<=pinned.BASE+len(data):raise ValueError('Invalid code range')
    if not terminals or any(any(lo<=pc<hi for lo,hi in ranges) for pc in terminals):
        raise ValueError('Terminal must be explicitly non-executable')
    if any(value not in ('returned','handoff') for value in terminals.values()):raise ValueError('Invalid terminal kind')
    for lit in literals:
        if lit&3 or not pinned.BASE<=lit<lit+4<=pinned.BASE+len(data):raise ValueError('Invalid literal')
    for i,(lo,buf,writable) in enumerate(regions):
        if type(writable) is not bool or not buf or not 0x06000000<=lo<lo+len(buf)<=0x06100000:
            raise ValueError('Invalid canonical high RAM input')
        if any(lo<hi and start<lo+len(buf) for start,hi in ranges):raise ValueError('Input overlaps code')
        if any(lo<lit+4 and lit<lo+len(buf) for lit in literals):raise ValueError('Input overlaps literal')
        if any(lo<other+len(value) and other<lo+len(buf) for other,value,_ in regions[:i]):
            raise ValueError('Overlapping input regions')
    for i,(raw,canonical,span,writable) in enumerate(aliases):
        if (raw>>28!=2 or raw&0x1FFFFFFF!=canonical or span<=0 or raw+span>0x30000000
            or type(writable) is not bool):raise ValueError('Invalid explicit RAM alias')
        if not any(lo<=canonical and canonical+span<=lo+len(buf) and (not writable or write)
                   for lo,buf,write in regions):raise ValueError('Alias backing/permission differs')
        if any(raw<other+size and other<raw+span for other,_,size,_ in aliases[:i]):raise ValueError('Overlapping aliases')

    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False;self.events=[]
        def canonical(self,address,size,write=False):
            if address>>28!=2:return address
            found=next(((raw,physical,writable) for raw,physical,span,writable in aliases
                         if raw<=address and address+size<=raw+span),None)
            if found is None:raise ValueError('Access through undeclared RAM alias')
            raw,physical,writable=found
            if write and not writable:raise ValueError('Write through readonly RAM alias')
            return physical+address-raw
        def read(self,address,size):
            if self.fetching:
                if size!=2 or address&1 or not any(lo<=address and address+2<=hi for lo,hi in ranges):
                    raise ValueError('Instruction fetch outside declared code')
            else:
                physical=self.canonical(address,size)
                if not (address in literals and size==4 or
                        any(lo<=physical and physical+size<=lo+len(buf) for lo,buf,_ in regions)):
                    raise ValueError('Read outside literals and controlled inputs')
            value=super().read(address,size)
            if not self.fetching:self.events.append([1,address,size,value])
            return value
        def write(self,address,size,value):
            physical=self.canonical(address,size,True)
            if not any(write and lo<=physical and physical+size<=lo+len(buf) for lo,buf,write in regions):
                raise ValueError('Write outside writable canonical inputs')
            super().write(address,size,value)
            self.events.append([2,address,size,value&((1<<(size*8))-1)])
    memory=Memory();map_inputs(memory,data,[(lo,buf) for lo,buf,_ in regions])
    baseline=[(lo,bytes(buf)) for lo,_,buf in memory.regions]
    class CPU(emu.CPU):
        def __init__(self,mem):super().__init__(mem);self.trace=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if len(self.trace)>=budget:raise ValueError('Handoff instruction budget exceeded')
            if not any(lo<=pc<hi for lo,hi in ranges):raise ValueError('Execution outside declared code')
            self.trace.append([pc,bool(in_slot)]);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory);cpu.r=[before[f'r{i}'] for i in range(16)]
    for name in ('sr','pr','macl','mach','gbr','vbr','pc'):setattr(cpu,name,before[name])
    cpu.pc=entry;error=None
    try:
        while cpu.pc not in terminals:cpu.step()
    except Exception as fault:error={'type':type(fault).__name__,'reason':str(fault)}
    mapped={lo:bytes(buf) for lo,_,buf in memory.regions};controlled={lo for lo,_,_ in regions}
    return {'status':terminals[cpu.pc] if error is None and cpu.pc in terminals else 'failed','error':error,
            'registers':{name:(cpu.r[int(name[1:])] if name.startswith('r') and name[1:].isdigit()
                              else getattr(cpu,name)) for name in NAMES},
            'trace':cpu.trace,'events':memory.events,'steps':cpu.steps,
            'regions_after':[mapped[lo] for lo,_,_ in regions],
            'original_unaffected_bytes_equal':all(mapped[lo]==buf for lo,buf in baseline if lo not in controlled)}
