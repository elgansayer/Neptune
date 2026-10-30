#!/usr/bin/env python3
"""Fresh-process, no-media libretro capability smoke, not gameplay validation."""
import ctypes as C
import json
from pathlib import Path
import sys


class SystemInfo(C.Structure):
    _fields_ = [("library_name", C.c_char_p), ("library_version", C.c_char_p),
                ("valid_extensions", C.c_char_p), ("need_fullpath", C.c_bool),
                ("block_extract", C.c_bool)]


def probe(path):
    core = C.CDLL(str(Path(path).resolve()))
    required = ("retro_init", "retro_deinit", "retro_run", "retro_reset",
                "retro_load_game", "retro_unload_game", "retro_set_environment",
                "retro_set_video_refresh", "retro_set_audio_sample",
                "retro_set_audio_sample_batch", "retro_set_input_poll",
                "retro_set_input_state", "retro_set_controller_port_device",
                "retro_serialize_size", "retro_serialize", "retro_unserialize",
                "retro_get_system_av_info", "retro_get_memory_data",
                "retro_get_memory_size")
    for name in required:
        getattr(core, name)
    core.retro_api_version.argtypes = []
    core.retro_api_version.restype = C.c_uint
    if core.retro_api_version() != 1:
        raise ValueError("Unsupported libretro API version")
    core.retro_get_system_info.argtypes = [C.POINTER(SystemInfo)]
    core.retro_get_system_info.restype = None
    info = SystemInfo()
    core.retro_get_system_info(C.byref(info))
    name = (info.library_name or b"").decode("utf-8", "strict")
    extensions = (info.valid_extensions or b"").decode("ascii", "strict").split("|")
    if "saturn" not in name.lower() or "cue" not in extensions:
        raise ValueError("Loaded core is not a Saturn/CUE capability")
    return {"scope": "no-media ABI smoke only", "api": 1, "library": name,
            "version": (info.library_version or b"").decode("utf-8", "strict"),
            "extensions": extensions}


if __name__ == "__main__":
    try:
        print(json.dumps(probe(sys.argv[1]), sort_keys=True))
    except (OSError, ValueError, AttributeError, IndexError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
