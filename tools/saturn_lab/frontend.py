#!/usr/bin/env python3
"""Bounded software libretro driver. Captures/state files remain private.

ABI definitions follow libretro.h (MIT, RetroArch team); this independent driver
does not include emulator implementation code. The loaded core keeps its licence.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
import math
import os
import platform
import resource
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from cli import LabError, confined_file, create_lock, disc_files, fingerprint, output_json, read_json, verify_lock
from media import FIRMWARE, verify_media
from pcm import MAX_FRAME_SAMPLES, PCMWriter

SETTINGS = "neptune.libretro-settings.v1"
CHECKPOINT = "neptune.libretro-checkpoint.v1"
MAX_STATE = 64 * 1024 * 1024
RTC_SEED = bytes([1, 0x20, 0x00, 0x61, 0x01, 0, 0, 0, 0, 0, 0, 0])
BUTTONS = {"b": 0, "y": 1, "select": 2, "start": 3, "up": 4, "down": 5,
           "left": 6, "right": 7, "a": 8, "x": 9, "l": 10, "r": 11,
           "l2": 12, "r2": 13, "l3": 14, "r3": 15}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class Geometry(C.Structure):
    _fields_ = [("base_width", C.c_uint), ("base_height", C.c_uint),
                ("max_width", C.c_uint), ("max_height", C.c_uint), ("aspect_ratio", C.c_float)]


class Timing(C.Structure):
    _fields_ = [("fps", C.c_double), ("sample_rate", C.c_double)]


class AVInfo(C.Structure):
    _fields_ = [("geometry", Geometry), ("timing", Timing)]


ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
BATCH = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
POLL = C.CFUNCTYPE(None)
INPUT = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
LOG = C.CFUNCTYPE(None, C.c_int, C.c_char_p)


def validate_actions(actions, frames, ports=12):
    if type(frames) is not int or not 1 <= frames <= 60000 or type(ports) is not int or not 1 <= ports <= 12:
        raise LabError("Invalid frame/controller bound")
    if not isinstance(actions, list) or len(actions) > 4096:
        raise LabError("Actions must be a bounded list")
    result = []
    for action in actions:
        if not isinstance(action, dict) or set(action) != {"start", "end", "port", "buttons"}:
            raise LabError("Unknown/missing input action fields")
        if any(type(action[key]) is not int for key in ("start", "end", "port")):
            raise LabError("Action frame/port values must be integers")
        if not 0 <= action["start"] < action["end"] <= frames or not 0 <= action["port"] < ports:
            raise LabError("Action frame/port out of bounds")
        buttons = action["buttons"]
        if not isinstance(buttons, list) or not buttons or len(buttons) > 16 or any(not isinstance(b, str) or b not in BUTTONS for b in buttons) or len(set(buttons)) != len(buttons):
            raise LabError("Invalid or repeated joypad buttons")
        result.append({**action, "mask": sum(1 << BUTTONS[b] for b in buttons)})
    return result


class Core:
    def __init__(self, path, system, save, options=None, log_shim=None, retain_audio=False):
        if sys.byteorder != "little": raise LabError("This frontend currently requires a little-endian host")
        self.dll = C.CDLL(str(path))
        self.system = str(system).encode()
        self.save = str(save).encode()
        self.options = options
        self.declared = {}
        self.effective = {}
        self.buffers = []
        self.events = {}
        self.errors = []
        self.masks = [0] * 12
        self.polls = [0] * 12
        self.delivered = [set() for _ in range(12)]
        self.video = None
        self.video_called = False
        self.pixels = None
        self.audio = hashlib.sha256()
        self.audio_frames = 0
        self.retain_audio = retain_audio
        self.audio_pcm = bytearray() if retain_audio else None
        self.audio_window = False
        self.loaded = False
        self.initialized = False
        self.frame = 0
        if log_shim is None: raise LabError("A pinned variadic log shim is required")
        self.log_messages = []
        self.log_callback = LOG(self._log)
        self.log_shim = C.CDLL(str(log_shim))
        self.log_shim.neptune_set_log_sink.argtypes = [LOG]
        self.log_shim.neptune_set_log_sink.restype = None
        self.log_shim.neptune_set_log_sink(self.log_callback)
        self.callbacks = [ENV(self._environment), VIDEO(self._video), AUDIO(self._audio),
                          BATCH(self._batch), POLL(lambda: None), INPUT(self._input)]
        for name, callback in zip(("environment", "video_refresh", "audio_sample", "audio_sample_batch", "input_poll", "input_state"), self.callbacks):
            function = getattr(self.dll, "retro_set_" + name)
            function.argtypes = [type(callback)]
            function.restype = None
            function(callback)
        self.dll.retro_api_version.restype = C.c_uint
        if self.dll.retro_api_version() != 1:
            raise LabError("Unsupported libretro ABI")
        self.dll.retro_load_game.argtypes = [C.POINTER(GameInfo)]
        self.dll.retro_load_game.restype = C.c_bool
        self.dll.retro_get_system_av_info.argtypes = [C.POINTER(AVInfo)]
        self.dll.retro_get_system_av_info.restype = None
        self.dll.retro_set_controller_port_device.argtypes = [C.c_uint, C.c_uint]
        self.dll.retro_set_controller_port_device.restype = None
        self.dll.retro_serialize_size.restype = C.c_size_t
        for name in ("retro_serialize", "retro_unserialize"):
            function = getattr(self.dll, name)
            function.argtypes = [C.c_void_p, C.c_size_t]
            function.restype = C.c_bool
        for name in ("retro_init", "retro_deinit", "retro_unload_game", "retro_run"):
            getattr(self.dll, name).restype = None
        self.check()
        if options is not None:
            if set(options) != set(self.declared) or any(options[k] not in self.declared[k] for k in options):
                raise LabError("Pinned options differ from actual core declarations")
        self.dll.retro_init()
        self.initialized = True
        self.check()

    def check(self):
        if self.errors:
            raise LabError("Core/callback failure: " + "; ".join(self.errors[:5]))

    def _log(self, level, message):
        try:
            text = message.decode("utf-8", errors="replace") if message else ""
            if len(self.log_messages) < 1024: self.log_messages.append({"level": level, "message": text})
            if level >= 3: self.errors.append("core: " + text)
        except Exception as error: self.errors.append(str(error))

    def _environment(self, command, data):
        try:
            self.events[str(command)] = self.events.get(str(command), 0) + 1
            base = command & 0xffff
            if base == 27:
                C.cast(data, C.POINTER(C.c_void_p))[0] = C.cast(self.log_shim.neptune_log, C.c_void_p).value
                return True
            if base in (9, 30, 31):
                value = self.save if base == 31 else self.system
                buffer = C.create_string_buffer(value)
                self.buffers.append(buffer)
                C.cast(data, C.POINTER(C.c_char_p))[0] = C.cast(buffer, C.c_char_p)
                return True
            if base == 16:
                variables = C.cast(data, C.POINTER(Variable))
                for index in range(256):
                    item = variables[index]
                    if not item.key: return True
                    key, value = item.key.decode(), item.value.decode()
                    self.declared[key] = value.split(";", 1)[1].strip().split("|")
                raise LabError("Unbounded core options")
            if base == 15:
                item = C.cast(data, C.POINTER(Variable)).contents
                key = item.key.decode()
                if key not in self.declared: return False
                value = self.options[key] if self.options is not None else self.declared[key][0]
                if value not in self.declared[key]: raise LabError("Invalid core option")
                self.effective[key] = value
                buffer = C.create_string_buffer(value.encode())
                self.buffers.append(buffer)
                item.value = C.addressof(buffer)
                return True
            if base in (2, 3, 17, 49):
                C.cast(data, C.POINTER(C.c_bool))[0] = base == 3
                return True
            if base in (39, 52, 61):
                C.cast(data, C.POINTER(C.c_uint))[0] = 12 if base == 61 else 0
                return True
            if base == 10:
                if C.cast(data, C.POINTER(C.c_uint))[0] != 1:
                    raise LabError("Only software XRGB8888 is supported")
                return True
            if base == 24:
                C.cast(data, C.POINTER(C.c_uint64))[0] = 1 << 1
                return True
            if base == 47:
                C.cast(data, C.POINTER(C.c_int))[0] = 3
                return True
            if base == 32 and self.retain_audio:
                raise LabError("Dynamic AV timing changes are unsupported during PCM capture")
            if base in (51, 6, 8, 11, 18, 32, 35, 37, 44, 87): return True
            if base == 7: raise LabError("Core requested shutdown")
            return False # Optional unknown interfaces are explicitly unsupported.
        except Exception as error:
            self.errors.append(str(error))
            return False

    def _video(self, data, width, height, pitch):
        try:
            self.video_called = True
            if not data:
                if self.video is None: raise LabError("Duplicate video before an initial frame")
                return
            if data == C.c_void_p(-1).value or not 0 < width <= 1024 or not 0 < height <= 1024 or pitch < width * 4:
                raise LabError("Invalid/software-unsupported video geometry")
            raw = bytearray(b"".join(C.string_at(data + y * pitch, width * 4) for y in range(height)))
            raw[3::4] = bytes(width * height) # X bits are not visible RGB data.
            self.pixels = raw
            self.video = {"width": width, "height": height, "pixel_format": "XRGB8888-le",
                          "sha256": hashlib.sha256(raw).hexdigest()}
        except Exception as error: self.errors.append(str(error))

    def _record_audio(self, raw, frames):
        if self.retain_audio:
            if not self.audio_window:
                raise LabError("Audio callback outside the captured retro_run window")
            if self.audio_frames + frames > MAX_FRAME_SAMPLES:
                raise LabError("PCM per-frame sample budget exceeded")
            self.audio_pcm.extend(raw)
        self.audio.update(raw)
        self.audio_frames += frames

    def _audio(self, left, right):
        try:
            self._record_audio(int(left).to_bytes(2, "little", signed=True) + int(right).to_bytes(2, "little", signed=True), 1)
        except Exception as error: self.errors.append(str(error))

    def _batch(self, data, frames):
        try:
            if frames > 65536: raise LabError("Unbounded audio batch")
            if frames and not data: raise LabError("Null audio batch pointer")
            if self.retain_audio and self.audio_frames + frames > MAX_FRAME_SAMPLES:
                raise LabError("PCM per-frame sample budget exceeded")
            self._record_audio(C.string_at(data, frames * 4) if frames else b"", frames)
            return frames
        except Exception as error:
            self.errors.append(str(error))
            return 0

    def _input(self, port, device, index, button):
        try:
            if port >= 12 or device & 0xff != 1 or index != 0: return 0
            self.polls[port] += 1
            self.delivered[port].add(self.masks[port])
            return C.c_int16(self.masks[port]).value if button == 256 else int(bool(self.masks[port] & (1 << button))) if button < 16 else 0
        except Exception as error:
            self.errors.append(str(error))
            return 0

    def load(self, disc, devices):
        info = GameInfo(str(disc).encode(), None, 0, None)
        if not self.dll.retro_load_game(C.byref(info)): raise LabError("retro_load_game failed")
        self.loaded = True
        for port, device in enumerate(devices): self.dll.retro_set_controller_port_device(port, device)
        av = AVInfo()
        self.dll.retro_get_system_av_info(C.byref(av))
        self.check()
        if not math.isfinite(av.timing.fps) or not 0 < av.timing.fps <= 1000 or not math.isfinite(av.timing.sample_rate) or not 0 < av.timing.sample_rate <= 384000:
            raise LabError("Invalid core timing")
        return {"fps": av.timing.fps, "fps_binary64": av.timing.fps.hex(), "sample_rate": av.timing.sample_rate,
                "base_width": av.geometry.base_width, "base_height": av.geometry.base_height}

    def step(self, masks):
        self.masks = masks
        self.audio = hashlib.sha256()
        self.audio_frames = 0
        if self.retain_audio: self.audio_pcm = bytearray()
        self.video_called = False
        self.audio_window = True
        try:
            self.dll.retro_run()
        finally:
            self.audio_window = False
        self.check()
        if not self.video_called or self.video is None: raise LabError("Frame execution produced no video callback")
        observation = {"frame": self.frame, "video": dict(self.video), "audio_sha256": self.audio.hexdigest(), "audio_frames": self.audio_frames, "inputs": list(masks)}
        self.frame += 1
        return observation

    def save_state(self):
        size = self.dll.retro_serialize_size()
        if not 0 < size <= MAX_STATE: raise LabError("Invalid state size")
        buffer = C.create_string_buffer(size)
        if not self.dll.retro_serialize(buffer, size): raise LabError("Core serialization failed")
        self.check()
        return buffer.raw

    def restore(self, state):
        if not 0 < len(state) <= MAX_STATE: raise LabError("Invalid checkpoint size")
        buffer = C.create_string_buffer(state, len(state))
        if not self.dll.retro_unserialize(buffer, len(state)): raise LabError("Core restore failed")
        self.check()

    def close(self):
        if self.loaded: self.dll.retro_unload_game()
        if self.initialized: self.dll.retro_deinit()
        self.loaded = self.initialized = False
        self.check()


def copy_checked(source, target):
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
        raise LabError("Component destination contains a symlink")
    if target.exists():
        if fingerprint(target) != fingerprint(source): raise LabError("Refusing to overwrite differing input component")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if fingerprint(source) != fingerprint(target): raise LabError("Component copy differs")


def configure(args):
    manifest = read_json(args.media_report)
    verify_media(args.media_root, manifest)
    root = args.root.resolve()
    if root == args.media_root.resolve() or root.is_relative_to(args.media_root.resolve()):
        raise LabError("Stage input copies outside original media")
    root.mkdir(parents=True, exist_ok=True)
    for relative in disc_files(args.media_root, manifest["disc"]):
        copy_checked(confined_file(args.media_root, relative), root / relative)
    bios_name = FIRMWARE[manifest["region"]]["filename"]
    copy_checked(confined_file(args.media_root, manifest["bios"]), root / "system" / bios_name)
    core_sha = fingerprint(args.core)["sha256"]
    core_path = root / "emulator" / (core_sha + ".so")
    copy_checked(args.core, core_path)
    source = Path(__file__).resolve()
    frontend_sha = fingerprint(source)["sha256"]
    module_hashes = {name: fingerprint(source.parent / name)["sha256"] for name in ("frontend.py", "cli.py", "media.py", "pcm.py", "log_shim.c")}
    bundle = "frontends/" + digest(module_hashes)
    for name in module_hashes: copy_checked(source.parent / name, root / bundle / name)
    shim_build = args.output / "log_shim.so"
    compiled = subprocess.run(["cc", "-shared", "-fPIC", "-O2", str(source.parent / "log_shim.c"), "-o", str(shim_build)], capture_output=True, text=True, timeout=30)
    (args.output / "log-shim-build.log").write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode: raise LabError("Log shim compilation failed")
    shim_sha = fingerprint(shim_build)["sha256"]
    shim_relative = bundle + "/log-shim-" + shim_sha + ".so"
    copy_checked(shim_build, root / shim_relative)
    (args.output / "probe-save").mkdir()
    driver = Core(core_path, root / "system", args.output / "probe-save", log_shim=root / shim_relative)
    try:
        options = {key: values[0] for key, values in driver.declared.items()}
    finally: driver.close()
    for key, value in {"beetle_saturn_autortc": "disabled", "beetle_saturn_region": "Japan" if manifest["region"] == "japan" else "North America" if manifest["region"] == "usa" else "Europe", "beetle_saturn_multitap_port1": "enabled", "beetle_saturn_multitap_port2": "enabled"}.items():
        if key not in options: raise LabError("Required option is not declared: " + key)
        options[key] = value
    rtc_seed = bytearray(RTC_SEED)
    if manifest["region"] == "japan":
        rtc_seed[-1] = 5
        options["beetle_saturn_autortc_lang"] = "japanese"
    profile = {"schema": SETTINGS, "options": options, "controller_devices": [1] * 12,
               "frontend_sha256": frontend_sha, "frontend_path": bundle + "/frontend.py",
               "source_modules": {name: {"path": bundle + "/" + name, "sha256": value} for name, value in module_hashes.items()},
               "log_shim": {"path": shim_relative, "sha256": shim_sha},
               "python_sha256": fingerprint(Path(sys.executable).resolve())["sha256"],
               "python_version": sys.version, "platform": platform.platform(),
               "rtc_seed_hex": bytes(rtc_seed).hex(), "system_directory": "system", "region": manifest["region"]}
    profile_sha = digest(profile)
    settings_relative = "settings/" + profile_sha + ".json"
    output_json(profile, root / settings_relative)
    lock = create_lock(root, manifest["disc"], "system/" + bios_name, core_path.relative_to(root).as_posix(), settings_relative, manifest["region"])
    lock_path = root / "locks" / (profile_sha + ".json")
    output_json(lock, lock_path)
    verify_lock(root, lock)
    return {"command": "configure", "lock": str(lock_path), "root": str(root), "frontend_sha256": frontend_sha,
            "settings_sha256": fingerprint(root / settings_relative)["sha256"], "declared_options": options,
            "scope": "Real components staged and fingerprinted; applied settings/boot remain to be measured"}


def checkpoint_identity(root, lock, profile):
    return {"lock_sha256": digest(lock), "core_sha256": fingerprint(confined_file(root, lock["inputs"]["emulator"]))["sha256"],
            "settings_sha256": fingerprint(confined_file(root, lock["inputs"]["settings"]))["sha256"],
            "frontend_sha256": profile["frontend_sha256"], "python_sha256": profile["python_sha256"]}


def validate_profile(root, profile):
    """Verify executable components transitively pinned by the locked settings."""
    modules = {"frontend.py", "cli.py", "media.py", "pcm.py", "log_shim.c"}
    if profile.get("schema") != SETTINGS or set(profile.get("source_modules", {})) != modules:
        raise LabError("Incomplete frontend settings/modules")
    if profile.get("frontend_sha256") != fingerprint(Path(__file__).resolve())["sha256"] or fingerprint(confined_file(root, profile["frontend_path"]))["sha256"] != profile["frontend_sha256"] or profile.get("python_sha256") != fingerprint(Path(sys.executable).resolve())["sha256"]:
        raise LabError("Frontend/settings/interpreter identity mismatch")
    if profile.get("python_version") != sys.version or profile.get("platform") != platform.platform():
        raise LabError("Pinned host/interpreter version mismatch")
    for name, item in profile["source_modules"].items():
        if fingerprint(confined_file(root, item["path"]))["sha256"] != item["sha256"] or fingerprint(Path(__file__).parent / name)["sha256"] != item["sha256"]:
            raise LabError("Frontend support module identity mismatch")
    shim = profile["log_shim"]
    if fingerprint(confined_file(root, shim["path"]))["sha256"] != shim["sha256"]:
        raise LabError("Frontend log shim identity mismatch")
    region = profile.get("region")
    if region not in FIRMWARE: raise LabError("Unknown pinned region")
    expected_seed = bytearray(RTC_SEED)
    if region == "japan": expected_seed[-1] = 5
    devices = profile.get("controller_devices")
    if not isinstance(devices, list) or len(devices) != 12 or any(type(d) is not int or d != 1 for d in devices) or profile.get("rtc_seed_hex") != bytes(expected_seed).hex() or profile["options"].get("beetle_saturn_autortc") != "disabled":
        raise LabError("Unsupported controller/RTC configuration")
    expected_region = {"usa": "North America", "japan": "Japan", "europe": "Europe"}[region]
    if profile["options"].get("beetle_saturn_region") != expected_region or any(profile["options"].get("beetle_saturn_multitap_port" + str(p)) != "enabled" for p in (1, 2)):
        raise LabError("Pinned region/controller topology mismatch")
    if profile.get("system_directory") != "system": raise LabError("Unexpected firmware directory")
    return bytes(expected_seed)


def read_checkpoint(path, identity):
    meta = read_json(path)
    if meta.get("schema") != CHECKPOINT or meta.get("identity") != identity:
        raise LabError("Checkpoint component identity mismatch")
    if type(meta.get("frame")) is not int or meta["frame"] < 0 or type(meta.get("state_bytes")) is not int or not 0 < meta["state_bytes"] <= MAX_STATE:
        raise LabError("Invalid checkpoint frame/size")
    state_path = confined_file(path.parent, meta["state_path"])
    if state_path.stat().st_size != meta["state_bytes"]: raise LabError("Checkpoint state digest/size mismatch")
    state = state_path.read_bytes()
    if hashlib.sha256(state).hexdigest() != meta["state_sha256"]:
        raise LabError("Checkpoint state digest/size mismatch")
    return meta, state


def write_capture(driver, path):
    if driver.pixels is None or driver.video is None:
        raise LabError("Requested capture has no pixel buffer after restore")
    video, raw = driver.video, driver.pixels
    if len(raw) != video["width"] * video["height"] * 4:
        raise LabError("Capture buffer/geometry mismatch")
    rgb = bytearray(video["width"] * video["height"] * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]
    path.write_bytes(f'P6\n{video["width"]} {video["height"]}\n255\n'.encode() + rgb)


def run(args):
    root = args.root.resolve()
    lock = read_json(args.lock)
    verify_lock(root, lock)
    profile = read_json(confined_file(root, lock["inputs"]["settings"]))
    expected_seed = validate_profile(root, profile)
    if profile["region"] != lock["region"]: raise LabError("Settings/lock region mismatch")
    if lock["inputs"]["bios"] != "system/" + FIRMWARE[profile["region"]]["filename"]:
        raise LabError("Locked BIOS differs from the firmware path consumed by the core")
    shim = profile["log_shim"]
    identity = checkpoint_identity(root, lock, profile)
    actions = validate_actions(read_json(args.actions) if args.actions else [], args.frames)
    save = args.output / "save"
    save.mkdir()
    disc = confined_file(root, lock["inputs"]["disc"])
    for name in [disc.stem + ".smpc", "mednafen_saturn_libretro_shared.smpc"]:
        (save / name).write_bytes(bytes(expected_seed))
    capture_audio = getattr(args, "capture_audio", False)
    driver = Core(confined_file(root, lock["inputs"]["emulator"]), root / profile["system_directory"], save, profile["options"], confined_file(root, shim["path"]), retain_audio=capture_audio)
    pcm_writer = None
    restored_state_sha256 = None
    frames = []
    captures = set(args.capture)
    try:
        if capture_audio: pcm_writer = PCMWriter(args.output)
        av = driver.load(disc, profile["controller_devices"])
        if args.restore:
            meta, state = read_checkpoint(args.restore, identity)
            restored_state_sha256 = meta["state_sha256"]
            driver.restore(state)
            driver.frame = meta["frame"]
            driver.video = meta["last_video"]
        for relative in range(args.frames):
            masks = [0] * 12
            for action in actions:
                if action["start"] <= relative < action["end"]: masks[action["port"]] |= action["mask"]
            frames.append(driver.step(masks))
            if pcm_writer is not None: pcm_writer.append(frames[-1], bytes(driver.audio_pcm))
            if args.checkpoint_at == relative + 1 or (args.checkpoint and relative + 1 == args.frames):
                state = driver.save_state()
                (args.output / "checkpoint.state").write_bytes(state)
                output_json({"schema": CHECKPOINT, "identity": identity, "state_path": "checkpoint.state", "state_sha256": hashlib.sha256(state).hexdigest(), "state_bytes": len(state), "frame": driver.frame, "last_video": driver.video}, args.output / "checkpoint.json")
            if relative in captures:
                write_capture(driver, args.output / f"frame-{relative:06}.ppm")
    finally:
        try:
            driver.close()
        finally:
            if pcm_writer is not None: pcm_writer.close()
    observations = {"schema": "neptune.libretro-observations.v1", "identity": identity, "av": av, "frames": frames}
    output_json(observations, args.output / "observations.json")
    result = {"command": "run", "identity": identity, "frames": len(frames), "av": av,
            "canonical_digest": digest(frames), "video_digest": digest([frame["video"] for frame in frames]),
            "audio_digest": digest([(frame["audio_sha256"], frame["audio_frames"]) for frame in frames]),
            "input_polls": driver.polls, "delivered_masks": [sorted(values) for values in driver.delivered],
            "effective_options": driver.effective, "environment_events": driver.events,
            "core_logs": driver.log_messages,
            "save_files": [{"path": path.name, **fingerprint(path)} for path in sorted(save.iterdir()) if path.is_file()],
            "scope": "Observed outputs for this pinned experiment only; no extraction or game-wide parity claim"}
    if pcm_writer is not None:
        result["audio_capture"] = pcm_writer.finish(args.output / "observations.json", checkpoint_sha256=restored_state_sha256)
    return result


def compare_observations(reference, candidate, start=0):
    if type(start) is not int or start < 0: raise LabError("Invalid reference slice")
    for item in (reference, candidate):
        if not isinstance(item, dict) or item.get("schema") != "neptune.libretro-observations.v1" or not isinstance(item.get("frames"), list) or not 0 < len(item["frames"]) <= 60000:
            raise LabError("Missing/empty/invalid observations")
        if not isinstance(item.get("identity"), dict) or not item["identity"] or not isinstance(item.get("av"), dict) or not item["av"]:
            raise LabError("Missing observation identity/timing")
    if reference["identity"] != candidate["identity"] or reference["av"] != candidate["av"]:
        raise LabError("Observation component/timing identity mismatch")
    expected, actual = reference["frames"][start:], candidate["frames"]
    if not expected or len(expected) != len(actual): raise LabError("Observation frame count mismatch")
    for index, (left, right) in enumerate(zip(expected, actual)):
        required = {"frame", "video", "audio_sha256", "audio_frames", "inputs"}
        if not isinstance(left, dict) or not isinstance(right, dict) or set(left) != required or set(right) != required:
            raise LabError("Malformed observation frame")
        for frame in (left, right):
            video = frame["video"]
            if type(frame["frame"]) is not int or frame["frame"] < 0 or type(frame["audio_frames"]) is not int or not 0 <= frame["audio_frames"] <= 1000000:
                raise LabError("Malformed frame index/audio count")
            if not isinstance(video, dict) or set(video) != {"width", "height", "pixel_format", "sha256"} or video["pixel_format"] != "XRGB8888-le" or any(type(video[k]) is not int or not 0 < video[k] <= 1024 for k in ("width", "height")):
                raise LabError("Malformed video observation")
            for sha in (video["sha256"], frame["audio_sha256"]):
                if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                    raise LabError("Malformed observation digest")
            if not isinstance(frame["inputs"], list) or len(frame["inputs"]) != 12 or any(type(mask) is not int or not 0 <= mask <= 65535 for mask in frame["inputs"]):
                raise LabError("Malformed controller observation")
        if index and (left["frame"] != expected[index-1]["frame"] + 1 or right["frame"] != actual[index-1]["frame"] + 1):
            raise LabError("Noncontiguous observation frames")
        if left != right: raise LabError(f"First divergence at candidate index {index}, reference frame {left['frame']}")
    return {"command": "compare", "matched_frames": len(actual), "canonical_digest": digest(actual)}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("configure", "run", "compare"))
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--media-root", type=Path)
    p.add_argument("--media-report", type=Path)
    p.add_argument("--core", type=Path)
    p.add_argument("--lock", type=Path)
    p.add_argument("--frames", type=int, default=1)
    p.add_argument("--actions", type=Path)
    p.add_argument("--restore", type=Path)
    p.add_argument("--checkpoint", action="store_true")
    p.add_argument("--checkpoint-at", type=int, help="Save after this many frames, then continue uninterrupted")
    p.add_argument("--capture", type=int, action="append", default=[])
    p.add_argument("--capture-audio", action="store_true", help="Retain bounded native callback PCM for same-core replay comparison")
    p.add_argument("--reference", type=Path)
    p.add_argument("--candidate", type=Path)
    p.add_argument("--reference-start", type=int, default=0)
    return p


def worker(argv):
    args = parser().parse_args(argv)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Verified CD tracks commonly exceed capture/state budgets. Configure
        # copies actual media; run/compare must retain the smaller output bound.
        file_bound = (2 * 1024**3) if args.command == "configure" else (64 * 1024**2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_bound, file_bound))
        resource.setrlimit(resource.RLIMIT_CPU, (args.timeout + 5, args.timeout + 5))
        if args.command == "configure" and (args.media_root is None or args.media_report is None or args.core is None):
            raise LabError("configure requires actual media/report/core")
        if args.command == "run" and (args.lock is None or not 1 <= args.frames <= 60000):
            raise LabError("run requires a lock and 1..60000 frames")
        if args.capture_audio and args.command != "run":
            raise LabError("capture-audio applies only to run")
        if args.checkpoint_at is not None and (args.checkpoint or not 1 <= args.checkpoint_at <= args.frames):
            raise LabError("checkpoint-at must be in range and excludes checkpoint")
        if len(args.capture) > 32 or len(set(args.capture)) != len(args.capture) or any(not 0 <= f < args.frames for f in args.capture):
            raise LabError("Capture indices must be unique, in range and at most 32")
        if args.command == "compare":
            if args.reference is None or args.candidate is None: raise LabError("compare requires reference and candidate observations")
            result = compare_observations(read_json(args.reference), read_json(args.candidate), args.reference_start)
        else:
            result = configure(args) if args.command == "configure" else run(args)
        output_json(result, args.output / "result.json")
        print("NEPTUNE_LIBRETRO_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
        return 0
    except (LabError, OSError, ValueError, KeyError, AttributeError, TypeError) as error:
        print("saturn-frontend: " + str(error), file=sys.stderr)
        return 1


def supervise(command, output, timeout, env, log_limit=16 * 1024 * 1024):
    """A zero exit is insufficient: require exactly one matching result receipt."""
    started = time.monotonic()
    with (output / "worker.log").open("w") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        reason = None
        while process.poll() is None:
            if time.monotonic() - started > timeout or log.tell() > log_limit:
                reason = "execution/log bound exceeded"
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                break
            time.sleep(0.05)
    record = {"command": command, "exit": process.returncode, "reason": reason, "seconds": round(time.monotonic()-started, 3)}
    output_json(record, output / "process.json")
    if (output / "worker.log").stat().st_size > log_limit: return False
    text = (output / "worker.log").read_text(errors="replace")
    markers = [line for line in text.splitlines() if line.startswith("NEPTUNE_LIBRETRO_RESULT=")]
    if process.returncode or reason or len(markers) != 1 or not (output / "result.json").is_file():
        return False
    try:
        result = read_json(output / "result.json")
        if not isinstance(result, dict) or not result or json.loads(markers[0].split("=", 1)[1]) != result: return False
    except (ValueError, OSError): return False
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_worker": return worker(argv[1:])
    args = parser().parse_args(argv)
    if not 5 <= args.timeout <= 600: raise SystemExit("timeout must be 5..600 seconds")
    if args.output.exists(): raise SystemExit("Use a fresh private output directory")
    if args.output.resolve().is_relative_to(args.root.resolve()) or (args.media_root and args.output.resolve().is_relative_to(args.media_root.resolve())):
        raise SystemExit("Output must be separate from media/input roots")
    args.output.mkdir(parents=True, mode=0o700)
    env = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG", "LC_ALL", "USER", "LOGNAME")}
    command = [sys.executable, str(Path(__file__).resolve()), "_worker", *argv]
    if not supervise(command, args.output, args.timeout, env):
        print("FAIL: inspect " + str(args.output / "worker.log"))
        return 1
    print("NEPTUNE_LIBRETRO_RESULT=" + json.dumps(read_json(args.output / "result.json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
