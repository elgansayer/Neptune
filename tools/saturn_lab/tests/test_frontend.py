"""Driver contract tests. The tiny C fixture is NOT a Saturn emulator."""
import copy
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import frontend as f


class ContractTests(unittest.TestCase):
    def test_actions_are_bounded_and_controller_specific(self):
        good = {"start": 0, "end": 2, "port": 1, "buttons": ["a", "right"]}
        self.assertEqual(f.validate_actions([good], 3)[0]["mask"], 384)
        bad = [None, {}, [dict(good, port=12)], [dict(good, port=True)],
               [dict(good, end=4)], [dict(good, start=-1)], [dict(good, end=0)],
               [dict(good, buttons=["a", "a"])], [dict(good, buttons=["execute"])],
               [dict(good, buttons=[])], [dict(good, extra="command")], [good]*4097]
        for actions in bad:
            with self.subTest(actions=str(actions)[:90]), self.assertRaises(f.LabError):
                f.validate_actions(actions, 3)
        for frames in (0, True, 60001, 1.5):
            with self.assertRaises(f.LabError): f.validate_actions([], frames)

    def test_compare_requires_evidence_and_detects_first_divergence(self):
        frame = {"frame": 7, "video": {"width":2,"height":1,"pixel_format":"XRGB8888-le","sha256": "a"*64}, "audio_sha256": "b"*64, "audio_frames": 1, "inputs": [0]*12}
        original = {"schema": "neptune.libretro-observations.v1", "identity": {"core": "pinned"}, "av": {"fps": 59.5}, "frames": [frame, dict(frame, frame=8)]}
        candidate = copy.deepcopy(original); candidate["frames"] = candidate["frames"][1:]
        self.assertEqual(f.compare_observations(original, candidate, 1)["matched_frames"], 1)
        candidate["frames"][0]["video"]["sha256"] = "c"*64
        with self.assertRaisesRegex(f.LabError, "First divergence.*frame 8"):
            f.compare_observations(original, candidate, 1)
        for field, value in (("identity", {}), ("av", {}), ("frames", []), ("schema", "future")):
            with self.assertRaises(f.LabError): f.compare_observations(original, dict(original, **{field:value}))
        with self.assertRaises(f.LabError): f.compare_observations(original, dict(original, identity={"core":"other"}))
        for field,value in (("video",{}),("audio_sha256",""),("inputs",[]),("frame",True)):
            bad=copy.deepcopy(original);bad["frames"][0][field]=value
            with self.assertRaises(f.LabError):f.compare_observations(bad,bad)
        bad=copy.deepcopy(original);bad["frames"][1]["frame"]=10
        with self.assertRaises(f.LabError):f.compare_observations(bad,bad)

    def test_copies_preserve_existing_components(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); a=root/"a"; b=root/"b"; a.write_bytes(b"first")
            f.copy_checked(a,b); f.copy_checked(a,b)
            a.write_bytes(b"different")
            with self.assertRaises(f.LabError): f.copy_checked(a,b)
            self.assertEqual(b.read_bytes(),b"first")
            b.unlink(); b.symlink_to(a)
            with self.assertRaises(f.LabError): f.copy_checked(a,b)
            (root/"alias").symlink_to(root,target_is_directory=True)
            with self.assertRaises(f.LabError): f.copy_checked(a,root/"alias/new-file")

    def test_requested_capture_cannot_silently_omit_missing_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"capture.ppm"
            driver=SimpleNamespace(pixels=None,video={"width":1,"height":1})
            with self.assertRaises(f.LabError):f.write_capture(driver,path)
            self.assertFalse(path.exists())
            driver.pixels=b"\x01\x02\x03\xff"
            f.write_capture(driver,path)
            self.assertEqual(path.read_bytes(),b"P6\n1 1\n255\n\x03\x02\x01")
            driver.pixels=b"short"
            with self.assertRaises(f.LabError):f.write_capture(driver,path)

    def test_checkpoint_rejects_wrong_identity_state_and_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); state=b"synthetic state"; (root/"state").write_bytes(state)
            identity={"core":"synthetic-pinned"}
            good={"schema":f.CHECKPOINT,"identity":identity,"state_path":"state","state_sha256":hashlib.sha256(state).hexdigest(),"state_bytes":len(state),"frame":3}
            def write(value): (root/"checkpoint.json").write_text(json.dumps(value))
            write(good); self.assertEqual(f.read_checkpoint(root/"checkpoint.json",identity)[1],state)
            for key,value in (("identity",{"core":"other"}),("frame",True),("state_bytes",f.MAX_STATE+1),("state_sha256","0"*64),("state_path","../escape"),("state_bytes",1)):
                write(dict(good,**{key:value}))
                with self.subTest(key=key),self.assertRaises(f.LabError): f.read_checkpoint(root/"checkpoint.json",identity)
            write(good); (root/"state").write_bytes(b"tampered state!")
            with self.assertRaises(f.LabError): f.read_checkpoint(root/"checkpoint.json",identity)

    def test_transitive_settings_identity_and_topology(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            modules={}
            for name in ("frontend.py","cli.py","media.py","pcm.py","log_shim.c"):
                f.copy_checked(Path(f.__file__).parent/name,root/name)
                modules[name]={"path":name,"sha256":f.fingerprint(root/name)["sha256"]}
            (root/"shim").write_bytes(b"synthetic shim identity")
            good={"schema":f.SETTINGS,"frontend_path":"frontend.py","frontend_sha256":modules["frontend.py"]["sha256"],"source_modules":modules,"python_sha256":f.fingerprint(Path(sys.executable).resolve())["sha256"],"python_version":sys.version,"platform":platform.platform(),"log_shim":{"path":"shim","sha256":f.fingerprint(root/"shim")["sha256"]},"region":"usa","controller_devices":[1]*12,"rtc_seed_hex":f.RTC_SEED.hex(),"system_directory":"system","options":{"beetle_saturn_autortc":"disabled","beetle_saturn_region":"North America","beetle_saturn_multitap_port1":"enabled","beetle_saturn_multitap_port2":"enabled"}}
            self.assertEqual(f.validate_profile(root,good),f.RTC_SEED)
            for key,value in (("source_modules",{}),("python_sha256","0"*64),("controller_devices",[True]*12),("controller_devices",[1]*11),("rtc_seed_hex","00"),("region","unknown"),("system_directory","../outside"),("platform","other")):
                with self.subTest(key=key),self.assertRaises(f.LabError): f.validate_profile(root,dict(good,**{key:value}))
            changed=copy.deepcopy(good); changed["options"]["beetle_saturn_region"]="Japan"
            with self.assertRaises(f.LabError): f.validate_profile(root,changed)
            (root/"cli.py").write_text("tampered")
            with self.assertRaises(f.LabError): f.validate_profile(root,good)
            (root/"cli.py").write_bytes((Path(f.__file__).parent/"cli.py").read_bytes())
            (root/"pcm.py").write_text("tampered audio helper")
            with self.assertRaises(f.LabError): f.validate_profile(root,good)

    def test_supervisor_rejects_false_green_and_bounds_execution(self):
        snippets=[("pass",False),("print('NEPTUNE_LIBRETRO_RESULT={}')",False),
                  ("from pathlib import Path; Path('result.json').write_text('{}'); print('NEPTUNE_LIBRETRO_RESULT={}')",False),
                  ("from pathlib import Path; Path('result.json').write_text('{\"ok\":1}'); print('NEPTUNE_LIBRETRO_RESULT={\"ok\":2}')",False),
                  ("print('x'*4000)",False),
                  ("import time; time.sleep(30)",False),
                  ("from pathlib import Path; Path('result.json').write_text('{\"ok\":1}'); print('NEPTUNE_LIBRETRO_RESULT={\"ok\":1}')",True)]
        for snippet,expected in snippets:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                # Child cwd is selected explicitly; no shell/eval or real core.
                command=[sys.executable,"-c","import os; os.chdir("+repr(directory)+"); "+snippet]
                self.assertEqual(f.supervise(command,root,.2,dict(os.environ),log_limit=2048),expected)
                self.assertTrue((root/"process.json").is_file())

    def test_media_copy_budget_is_separate_from_capture_budget(self):
        # Exercise the actual worker limits in a child: changing the configure
        # limit back to the capture limit must break a >64-MiB track copy.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/"large-synthetic-track.bin"
            with source.open("wb") as stream: stream.truncate(65*1024**2)
            script="""
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import frontend as f
mode,root=sys.argv[2],Path(sys.argv[3])
# No real media is loaded. The missing inputs deliberately stop worker setup
# after it applies limits; test copying under those actual process limits.
assert f.worker([mode,'--root',str(root),'--output',str(root)])==1
try:
 f.copy_checked(root/'large-synthetic-track.bin',root/(mode+'-copy'))
 copied=True
except OSError:
 copied=False
assert copied == (mode=='configure')
"""
            for command in ("configure","run"):
                result=subprocess.run([sys.executable,"-c",script,str(Path(f.__file__).parent),command,str(root)],capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(f.fingerprint(source),f.fingerprint(root/"configure-copy"))


class NativeABIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); cls.root=Path(cls.temp.name)
        source=Path(__file__).parent/"fixtures/core.c"
        for src,target in ((source,cls.root/"core.so"),(Path(f.__file__).parent/"log_shim.c",cls.root/"shim.so")):
            subprocess.run(["cc","-shared","-fPIC","-O2",str(src),"-o",str(target)],check=True,capture_output=True,timeout=30)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def core(self,mode=0,retain_audio=False):
        driver=f.Core(self.root/"core.so",self.root,self.root,{"fixture_option":"on"},self.root/"shim.so",retain_audio=retain_audio)
        self.addCleanup(driver.close)
        driver.dll.fixture_mode.argtypes=[C.c_uint]; driver.dll.fixture_mode(mode)
        return driver

    def test_real_abi_controller_video_audio_save_restore(self):
        driver=self.core(); av=driver.load(self.root/"synthetic.cue",[1]*12)
        self.assertEqual(av["fps"],59.5)
        masks=[8,256]+[0]*10
        first=driver.step(masks); state=driver.save_state(); expected=driver.step(masks)
        driver.restore(state); driver.frame=1
        self.assertEqual(driver.step(masks),expected)
        self.assertEqual(first["inputs"][:2],[8,256]); self.assertEqual(first["audio_frames"],1)
        self.assertEqual(driver.delivered[:2],[{8},{256}]); self.assertEqual(driver.effective,{"fixture_option":"on"})
        driver.dll.fixture_mode(2)
        with self.assertRaisesRegex(f.LabError,"no video"): driver.step(masks)

    def test_core_errors_and_missing_video_cannot_pass(self):
        for mode,message in ((1,"load_game"),(2,"no video"),(3,"synthetic failure"),(4,"shutdown"),(5,"serialization"),(6,"restore")):
            driver=self.core(mode)
            try:
                with self.subTest(mode=mode),self.assertRaisesRegex(f.LabError,message):
                    driver.load(self.root/"synthetic.cue",[1]*12)
                    if mode==5: driver.save_state()
                    elif mode==6: driver.restore(b"1234")
                    else: driver.step([0]*12)
            finally:
                # Expected failure remains sticky; cleanup cannot mask it.
                driver.errors.clear(); driver.close()

    def test_pcm_single_batch_and_mixed_callback_bytes_preserve_observations(self):
        for mode, expected in ((0, [(8,256)]), (7,[(-32768,32767),(-1,1)]),
                               (8,[(-32768,32767),(1,-1),(5,-5)])):
            with self.subTest(mode=mode):
                driver=self.core(mode,retain_audio=True)
                driver.load(self.root/"synthetic.cue",[1]*12)
                observed=driver.step([8,256]+[0]*10)
                raw=b"".join(struct.pack("<hh",*pair) for pair in expected)
                self.assertEqual(driver.audio_pcm,raw)
                self.assertEqual(observed["audio_frames"],len(expected))
                self.assertEqual(observed["audio_sha256"],hashlib.sha256(raw).hexdigest())
                driver.close()
                plain=self.core(mode)
                plain.load(self.root/"synthetic.cue",[1]*12)
                self.assertEqual(plain.step([8,256]+[0]*10),observed)
                self.assertIsNone(plain.audio_pcm)
                plain.close()

    def test_pcm_callback_budgets_null_pointer_and_dynamic_timing_fail(self):
        for mode, message in ((9,"budget"),(10,"Null audio"),(11,"Dynamic AV")):
            driver=self.core(mode,retain_audio=True)
            driver.load(self.root/"synthetic.cue",[1]*12)
            with self.subTest(mode=mode),self.assertRaisesRegex(f.LabError,message):
                driver.step([0]*12)
            self.assertFalse(driver.audio_window)
            driver.errors.clear(); driver.close()
        driver=self.core(7,retain_audio=True)
        driver.load(self.root/"synthetic.cue",[1]*12)
        with patch.object(f,"MAX_FRAME_SAMPLES",1),self.assertRaisesRegex(f.LabError,"budget"):
            driver.step([0]*12)
        driver.errors.clear(); driver.close()

    def test_pcm_callbacks_outside_capture_window_fail_and_buffers_reset(self):
        driver=self.core(14,retain_audio=True)
        with self.assertRaisesRegex(f.LabError,"outside"):
            driver.load(self.root/"synthetic.cue",[1]*12)
        driver.errors.clear(); driver.close()
        driver=self.core(8,retain_audio=True)
        driver.load(self.root/"synthetic.cue",[1]*12)
        first=driver.step([0]*12)
        self.assertEqual(first["audio_frames"],3)
        second=driver.step([0]*12)
        self.assertEqual(second["audio_frames"],4)
        self.assertEqual(len(driver.audio_pcm),16)
        self.assertEqual(second["audio_sha256"],hashlib.sha256(driver.audio_pcm).hexdigest())
        driver.dll.fixture_mode(15)
        with self.assertRaisesRegex(f.LabError,"outside"):
            driver.close()
        driver.errors.clear()

    def test_pcm_zero_sample_frame_and_fractional_native_rate(self):
        driver=self.core(13,retain_audio=True)
        driver.load(self.root/"synthetic.cue",[1]*12)
        self.assertEqual(driver.step([0]*12)["audio_frames"],1)
        empty=driver.step([0]*12)
        self.assertEqual(empty["audio_frames"],0)
        self.assertEqual(driver.audio_pcm,b"")
        self.assertEqual(empty["audio_sha256"],hashlib.sha256(b"").hexdigest())
        driver.close()
        driver=self.core(16,retain_audio=True)
        self.assertEqual(driver.load(self.root/"synthetic.cue",[1]*12)["sample_rate"],44100.5)
        driver.close()

    def run_synthetic(self, root, name, mode=8, capture=True, frames=3,
                      restore=None, checkpoint_at=None, writer_factory=None):
        """Exercise run() with the real C ABI; no real-media validation is claimed."""
        inputs=root/"inputs"; inputs.mkdir(exist_ok=True)
        (inputs/"system").mkdir(exist_ok=True)
        f.copy_checked(self.root/"core.so",inputs/"core.so")
        f.copy_checked(self.root/"shim.so",inputs/"shim.so")
        (inputs/"synthetic.cue").write_text("Synthetic C ABI fixture only")
        profile={"region":"usa", "system_directory":"system", "controller_devices":[1]*12,
                 "options":{"fixture_option":"on"}, "log_shim":{"path":"shim.so"},
                 "frontend_sha256":f.fingerprint(Path(f.__file__))["sha256"],
                 "python_sha256":f.fingerprint(Path(sys.executable).resolve())["sha256"]}
        (inputs/"settings.json").write_text(json.dumps(profile))
        lock={"region":"usa","inputs":{"settings":"settings.json","emulator":"core.so",
              "disc":"synthetic.cue","bios":"system/"+f.FIRMWARE["usa"]["filename"]}}
        (inputs/"lock.json").write_text(json.dumps(lock))
        output=root/name; output.mkdir()
        args=SimpleNamespace(root=inputs,lock=inputs/"lock.json",actions=None,
                             frames=frames,output=output,capture_audio=capture,capture=[],
                             restore=restore,checkpoint=False,checkpoint_at=checkpoint_at)
        core_type=f.Core
        def fixture_core(*positional,**keywords):
            driver=core_type(*positional,**keywords)
            driver.dll.fixture_mode.argtypes=[C.c_uint]
            driver.dll.fixture_mode(mode)
            return driver
        # The fixture deliberately is not a Saturn core or valid disc. Separate
        # tests exercise real input/profile pinning; here bypass those two gates
        # to test the actual capture lifecycle without private original media.
        with patch.object(f,"verify_lock"),patch.object(f,"validate_profile",return_value=f.RTC_SEED), \
             patch.object(f,"Core",side_effect=fixture_core):
            if writer_factory is None:
                return f.run(args)
            with patch.object(f,"PCMWriter",side_effect=writer_factory):
                return f.run(args)

    def test_run_pcm_retention_and_restored_suffix_preserve_default_observations(self):
        import pcm
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enabled=self.run_synthetic(root,"full",checkpoint_at=1)
            disabled=self.run_synthetic(root,"default",capture=False)
            self.assertEqual({k:v for k,v in enabled.items() if k!="audio_capture"},disabled)
            self.assertFalse((root/"default/audio.json").exists())
            self.assertFalse((root/"default/audio.s16le").exists())
            self.assertEqual((root/"full/observations.json").read_bytes(),
                             (root/"default/observations.json").read_bytes())
            self.assertEqual(enabled["audio_capture"]["manifest_sha256"],
                             f.fingerprint(root/"full/audio.json")["sha256"])
            self.run_synthetic(root,"restored",frames=2,restore=root/"full/checkpoint.json")
            report=pcm.compare_captures(root/"full/audio.json",root/"restored/audio.json",reference_start=1)
            self.assertTrue(report["match"])

    def test_run_pcm_failures_publish_no_success_manifest(self):
        import pcm
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for mode in (9,10,11,12,14,15):
                with self.subTest(mode=mode),self.assertRaises(f.LabError):
                    self.run_synthetic(root,"failed-"+str(mode),mode=mode)
                self.assertFalse((root/("failed-"+str(mode))/"audio.json").exists())
            with self.assertRaisesRegex(f.LabError,"budget"):
                self.run_synthetic(root,"budget",writer_factory=lambda output:pcm.PCMWriter(output,max_bytes=4))
            self.assertFalse((root/"budget/audio.json").exists())


if __name__=="__main__": unittest.main()
