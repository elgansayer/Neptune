"""Actual bounded command10 outcomes; unsupported paths are never completion."""
import sys,json,hashlib,itertools,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze_sound_driver as sound
import m68k_scsp_state as old_native
import m68k_reset_capacity as native
import probe_netlink_records as records
import probe_netlink_pointer as leaf
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-file',type=Path,required=True)
parser.add_argument('--previous-prepared',type=Path,required=True)
parser.add_argument('--prepared',type=Path,required=True)
parser.add_argument('--report',type=Path,required=True)
args=parser.parse_args()
if args.report.exists():raise ValueError('Use a new private comparison report')
code=sound.source_bytes(args.source_file,'NLSND')
oldlib=old_native.Library(args.previous_prepared);lib=native.Library(args.prepared)
# Explicit measured instruction spans; tables and MMIO are never executable.
ranges=[(0x1640,0x167A),(0x1DEA,0x1E2E),(0x1E68,0x1EEE),(0x3530,0x35BC),
        (0x4412,0x4442),(0x4B00,0x4B6E),(0x4BB6,0x4BE0),(0x4C2A,0x4C9A),
        (0x17F2,0x18F2)]
rows=[]
for mode,variant,mask in itertools.product(('handler','dispatcher'),(0,1),range(32)):
 entry=0x1E68 if mode=='handler' else 0x17F2;regs=records.base_regs(entry,0x271F if variant==0 else 0x2015)
 if variant:regs[:15]=[r^0xFFFFFFFF for r in regs[:15]]
 regs[7]=(regs[7]&0xFFFF0000)|0x10;regs[8]=0x40000;regs[13]=0x100000;regs[14]=0x24000
 pool=bytearray(0x2800);ram=bytearray(0x2000)
 for i in range(8):pool[0x2100+i*0x60+1]=i
 if variant:
  pool[0x1840]=254
  for i in range(32):
   at=0x2400+i*12;pool[at]=0x80|(i&1);pool[at+1:at+4]=bytes((i,127,64));pool[at+8:at+12]=(0x20000+0x2100+(i%8)*0x60).to_bytes(4,'big')
  ram[0x1890:0x18A0]=bytes(0x80+i for i in range(16))
 payload=bytes(1 if mask&(1<<i) else 0 for i in range(5))
 regions=[(0x450,(0x20000).to_bytes(4,'big'),False),(0x404,(0x30000).to_bytes(4,'big'),False),
          (0x7000,bytes(ram),True),(0x20000,bytes(pool),True),(0x30000,bytes([0xAD])*768,True),
          (0x40000,payload,False),(leaf.SP-256,bytes([0xCD])*256+leaf.STOP.to_bytes(4,'big'),True)]
 assert all(lo+len(data)<=0x100000 for lo,data,w in regions),'No fake device RAM allowed'
 before=oldlib.run(code,entry,leaf.STOP,ranges,regions,regs,budget=2048)
 actual=lib.run(code,entry,leaf.STOP,ranges,regions,regs,budget=8192)
 if before['status_code']==6:
  assert len(before['events'])==1024
  assert actual['events'][:len(before['events'])]==before['events'],(mode,variant,mask,'event prefix')
  assert actual['pcs'][:before['steps']]==before['pcs'],(mode,variant,mask,'PC prefix')
  assert actual['steps']>before['steps'] and len(actual['events'])>1024,(mode,variant,mask,'progress')
  assert actual['status_code'] not in (2,6),(mode,variant,mask,'still capacity limited',actual['status'],actual['steps'],len(actual['events']))
  comparison='old-event-fence-extended'
 else:
  assert before==actual,(mode,variant,mask,'unchanged non-capacity result differs',[k for k in before if before[k]!=actual[k]])
  comparison='all-result-fields-identical'
 assert actual['code_unchanged']
 rows.append({'comparison':comparison,'prior_steps':before['steps'],'prior_events':len(before['events']),'mode':mode,'active_record_variant':variant,'mask':mask,'payload':list(payload),
              'status':actual['status'],'status_code':actual['status_code'],'steps':actual['steps'],
              'events':len(actual['events']),'error_address':hex(actual['error_address']),'error_size':actual['error_size'],
              'last_pc':hex(actual['pcs'][-1]) if actual['pcs'] else None,'registers':actual['registers'],
              'tail_pcs':[hex(v) for v in actual['pcs'][-8:]],'tail_events':actual['events'][-8:],
              'regions_after_sha256':[hashlib.sha256(b).hexdigest() for b in actual['regions_after']],
              'code_unchanged':actual['code_unchanged'],'completed_original_call':actual['status_code']==1,
              'independent_full_semantics_accepted':False})
report={'schema':'neptune.original-command10-capacity-comparison.v1','original_game_bytes_executed':True,'module':'NLSND',
        'driver_sha256':hashlib.sha256(code).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ranges':ranges,'previous_binary_sha256':hashlib.sha256(oldlib.path.read_bytes()).hexdigest(),'previous_native_identity':old_native.identity(),'native_identity':native.identity(),'binary_sha256':hashlib.sha256(lib.path.read_bytes()).hexdigest(),
        'noncapacity_exact_matches':sum(r['comparison']=='all-result-fields-identical' for r in rows),'old_fence_extensions':sum(r['comparison']=='old-event-fence-extended' for r in rows),'cases':rows,'completed':sum(r['completed_original_call'] for r in rows),'all_code_unchanged':all(r['code_unchanged'] for r in rows),
        'full_semantic_contract_accepted':False,'scope':'Paired ABI5/6 exact backward comparison and old-fence extension; six diagnostic returns do not establish independent command10 semantics'}
assert report['noncapacity_exact_matches']==96 and report['old_fence_extensions']==32
with args.report.open('x') as output:output.write(json.dumps(report,indent=2)+'\n')
from collections import Counter
print(json.dumps({'status':'diagnostic-recorded','cases':len(rows),'outcomes':dict(Counter(r['status'] for r in rows)),'completed':report['completed'],'full_semantic_contract_accepted':False}))
