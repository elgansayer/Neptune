"""Locate the pinned GNU binutils used by the split/build tools.

The toolchain is Debian's ``binutils-sh4-linux-gnu`` and ``binutils-m68k-linux-gnu``
2.44-3 packages unpacked without root (``apt-get download`` + ``dpkg -x``; no root needed).  The
assembler is driven with ``-big --isa=sh2`` for SH-2 and ``-m68000`` for the
68000, so the Linux target triplets do not matter for flat binaries.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ROOT = "/var/lib/repo-factory/saturn-re-lanes/tools/cross-binutils-2.44-3"


def root() -> Path:
    return Path(os.environ.get("SATURN_BINUTILS", DEFAULT_ROOT))


def tool(prefix: str, name: str) -> str:
    return str(root() / "usr" / "bin" / f"{prefix}-{name}")


def env() -> dict:
    out = dict(os.environ)
    lib = str(root() / "usr" / "lib" / "x86_64-linux-gnu")
    out["LD_LIBRARY_PATH"] = lib + (":" + out["LD_LIBRARY_PATH"] if out.get("LD_LIBRARY_PATH") else "")
    return out


SH = "sh4-linux-gnu"
M68K = "m68k-linux-gnu"
SH_AS_FLAGS = ["-big", "--isa=sh2"]
M68K_AS_FLAGS = ["-m68000"]
