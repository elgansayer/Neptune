#!/usr/bin/env python3
"""Run one bounded natural command-observer window from the accepted boot seed."""
import argparse, hashlib, json, os, resource, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/factory'))
import provision, provision_command_trace_abi as observer, probe_kernel, state_graphics
from run_call_trace import reference,confined,read_json,sha
from run_context_trace import read_boot_checkpoint

def source_words(kernel):
    return [int.from_bytes(kernel[a-probe_kernel.BASE+2*i:a-probe_kernel.BASE+2*i+2],'big')
            for a,n in observer.WITNESS_RANGES for i in range(n)]
def resident(state,kernel):
    parsed=state_graphics.parse(state)
    high=state_graphics.cpu_words(state_graphics.field(parsed,'MAIN','WorkRAMH',0x100000),'little')
    spans=[]
    for a,n in observer.WITNESS_RANGES:
        raw=kernel[a-probe_kernel.BASE:a-probe_kernel.BASE+2*n]
        if high[a-0x06000000:a-0x06000000+len(raw)]!=raw: raise ValueError('Original command source witness absent from High Work RAM')
        spans.append({'address':f'0x{a:08x}','bytes':len(raw),'sha256':sha(raw)})
    return spans
def run(a):
    if a.profile not in (1,2) or a.mode not in ('reference','disabled','enabled') or not 1<=a.frames<=600 or not 0<=a.start_frames<=a.frames: raise ValueError('Invalid bounded command window')
    if a.output.exists(): raise ValueError('Fresh private output required')
    a.output.mkdir(mode=0o700,parents=True)
    result={'schema':'neptune.explicit-command-trace-experiment.v1','status':'failure','mode':a.mode,'profile':a.profile,'frames_requested':a.frames,'port_zero_start_frames':a.start_frames,'model_calls':0,'driver_sha256':sha(Path(__file__).read_bytes())}
    driver=tracer=None; frames=[]; phase='identity'
    try:
        module,lock,profile,identity,seed=reference(a.reference_root,a.lock,a.expected_lock)
        original,state=read_boot_checkpoint(module,a.boot_checkpoint,identity,a.expected_lock)
        kernel=probe_kernel.kernel_bytes(a.kernel)
        if original['frame']+a.frames>4800: raise ValueError('4800-frame original experiment bound exceeded')
        if any(not os.statvfs(p).f_flag & os.ST_RDONLY for p in (a.reference_root,a.boot_checkpoint.parent,a.kernel.parent)):
            raise ValueError('Original media, boot checkpoint and kernel must be read-only')
        core=confined(a.reference_root,lock['inputs']['emulator'])
        result.update(reference_identity=identity,reference_lock_file_sha256=a.expected_lock,reference_checkpoint_file_sha256=sha(a.boot_checkpoint.read_bytes()),reference_frame=original['frame'],original_kernel_sha256=sha(kernel),input_boot_checkpoint_verified=True)
        if a.mode!='reference':
            if a.prepared is None or not os.statvfs(a.prepared).f_flag & os.ST_RDONLY: raise ValueError('Instrumented core must be the immutable prepared generation')
            _,_,recipe=provision.identity('beetle-saturn-command-trace',ROOT)
            core=provision.cached(a.prepared,'beetle-saturn-command-trace',recipe,ROOT); result['prepared_recipe_sha256']=recipe
        result['selected_core_sha256']=provision.digest(core)
        phase='load_and_import'; save=a.output/'save'; save.mkdir()
        disc=confined(a.reference_root,lock['inputs']['disc'])
        for name in (disc.stem+'.smpc','mednafen_saturn_libretro_shared.smpc'): (save/name).write_bytes(bytes(seed))
        driver=module.Core(core,a.reference_root/profile['system_directory'],save,profile['options'],confined(a.reference_root,profile['log_shim']['path']))
        av=driver.load(disc,profile['controller_devices']); driver.restore(state); driver.frame,driver.video=original['frame'],original['last_video']
        imported=driver.save_state(); witness=resident(imported,kernel); (a.output/'imported.state').write_bytes(imported)
        result.update(av=av,imported_state_sha256=sha(imported),imported_state_bytes=len(imported),resident_code_before=witness)
        if a.mode!='reference':
            tracer=observer.Trace(driver.dll)
            if a.mode=='enabled':
                tracer.start(a.profile,source_words(kernel))
                if tracer.witness()!=source_words(kernel): raise ValueError('Native source witness differs before execution')
        phase='original_frame_execution'; started=time.monotonic(); trace_done=a.mode!='enabled'
        for i in range(a.frames):
            if a.mode=='enabled' and not trace_done:
                tracer.frame(driver.frame)
            frames.append(driver.step([8 if i<a.start_frames else 0]+[0]*11))
            if a.mode=='enabled' and not trace_done:
                rows,status=tracer.snapshot()
                if rows and rows[-1].kind==7:
                    trace_done=True
                    result['trace_observation_frame']=driver.frame
        elapsed=time.monotonic()-started; final=driver.save_state(); (a.output/'final.state').write_bytes(final)
        (a.output/'observations.json').write_text(json.dumps({'av':av,'frames':frames},sort_keys=True)+'\n')
        result.update(frames=len(frames),final_state_sha256=sha(final),frame_observations_sha256=module.digest(frames),video_sha256=module.digest([f['video'] for f in frames]),audio_sha256=module.digest([(f['audio_sha256'],f['audio_frames']) for f in frames]),audio_frames=sum(f['audio_frames'] for f in frames),emulation_wall_seconds=elapsed,input_polls=driver.polls,delivered_masks=[sorted(v) for v in driver.delivered],resident_code_after=resident(final,kernel))
        if a.mode=='enabled':
            if not trace_done: raise ValueError('No root return within the native 120-frame observer budget')
            phase='trace_validation'; trace=tracer.finish(); raw=(json.dumps(trace,indent=2,sort_keys=True)+'\n').encode(); (a.output/'command-trace.json').write_bytes(raw); result.update(trace_sha256=sha(raw),trace_records=len(trace['records']),completed_roots=1)
        result['status']='success'
    except Exception as e:
        result['error']={'phase':phase,'type':type(e).__name__,'reason':str(e)}; raise
    finally:
        result.update(completed_original_frames=len(frames),original_execution_attempted=bool(frames),original_game_bytes_executed=bool(frames))
        if driver is not None: driver.close()
        (a.output/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result
def main():
    for limit,bound in ((resource.RLIMIT_AS,2*1024**3),(resource.RLIMIT_CORE,0),(resource.RLIMIT_FSIZE,64*1024**2),(resource.RLIMIT_CPU,60)):
        soft,hard=resource.getrlimit(limit); cap=min([bound]+[v for v in (soft,hard) if v!=resource.RLIM_INFINITY]); resource.setrlimit(limit,(cap,cap))
    p=argparse.ArgumentParser();
    for name in ('reference-root','lock','boot-checkpoint','kernel','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--expected-lock',required=True); p.add_argument('--prepared',type=Path); p.add_argument('--profile',type=int,choices=(1,2),required=True); p.add_argument('--mode',choices=('reference','disabled','enabled'),required=True); p.add_argument('--frames',type=int,default=600); p.add_argument('--start-frames',type=int,default=0)
    print(json.dumps(run(p.parse_args()),sort_keys=True))
if __name__=='__main__': main()
