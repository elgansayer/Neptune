#!/usr/bin/env python3
"""Config-driven splitter: cut original Saturn modules into GNU as source.

Reads ``config/<release>.toml``.  For every module it verifies the original
bytes (SHA-256), then writes ``asm/<release>/<module>/*.s`` plus a linker script
and a make fragment.  Assembling and linking those files with the pinned GNU
binutils reproduces the original module byte for byte (``make check``).

SH-2 modules with a code map (``code`` file of absolute halfword ranges) are
emitted as instructions; all other bytes are emitted as data directives, or as
``.incbin`` of an extracted blob for ``bin`` segments.  Files are cut only at
4-byte aligned addresses (GNU as resolves ``mov.l``/``mova`` alignment relative
to the section start) and, in ``functions`` mode, only at function entries that
no PC-relative branch or literal load crosses.  A PC-relative instruction
whose target lies in another file is emitted as a raw word with a comment,
because GNU as has no relocation for those fixed-width displacements.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import os
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sh2_gas  # noqa: E402
import m68k_gas  # noqa: E402

ROOT = Path(os.environ.get("SATURN_SPLIT_ROOT", Path.cwd()))  # config-relative paths resolve here
GENERATOR = "tools/saturn_lab/saturn_split.py"


# ---------------------------------------------------------------------------
# config and inputs

def load_config(path: Path) -> dict:
    with path.open("rb") as stream:
        cfg = tomllib.load(stream)
    if "release" not in cfg or "module" not in cfg:
        raise SystemExit(f"{path}: needs 'release' and [[module]] tables")
    return cfg


def files_dir(cfg: dict, override: str | None) -> Path:
    if override:
        return Path(override)
    env = cfg.get("files_env", "SATURN_USA_FILES")
    if os.environ.get(env):
        return Path(os.environ[env])
    if cfg.get("files_default"):
        return Path(cfg["files_default"])
    raise SystemExit(f"set {env} to the directory of extracted original disc files")


def read_module(cfg: dict, mod: dict, files: Path) -> bytes:
    raw = (files / mod["path"]).read_bytes()
    if "file_sha256" in mod and hashlib.sha256(raw).hexdigest() != mod["file_sha256"]:
        raise SystemExit(f"{mod['name']}: {mod['path']} SHA-256 differs from config file_sha256")
    offset = mod.get("offset", 0)
    size = mod.get("size", len(raw) - offset)
    data = raw[offset:offset + size]
    if len(data) != size:
        raise SystemExit(f"{mod['name']}: slice {offset:#x}+{size:#x} exceeds {mod['path']}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != mod["sha256"]:
        raise SystemExit(f"{mod['name']}: SHA-256 {digest} differs from config {mod['sha256']}")
    return data


def read_ranges(path: Path) -> list[tuple[int, int]]:
    out = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            lo, hi = line.split()[:2]
            out.append((int(lo, 16), int(hi, 16)))
    return sorted(out)


def read_symbols(path: Path) -> dict[int, tuple[str, str]]:
    """``ADDRESS NAME [KIND]`` per line (hex address, KIND func/data/label)."""
    out: dict[int, tuple[str, str]] = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        out[int(parts[0], 16)] = (parts[1], parts[2] if len(parts) > 2 else "func")
    return out


# ---------------------------------------------------------------------------
# SH-2 analysis

class Sh2Module:
    def __init__(self, name: str, data: bytes, vram: int, code_ranges, symbols, cfg_mod: dict):
        self.name, self.data, self.vram, self.end = name, data, vram, vram + len(data)
        self.symbols = symbols
        self.code: set[int] = set()
        for lo, hi in code_ranges:
            lo, hi = max(lo, vram), min(hi, self.end)
            self.code.update(range(lo - lo % 2, hi, 2))
        self.cfg = cfg_mod
        self.refs = []  # (pc, kind, target)
        for pc in sorted(self.code):
            ref = sh2_gas.reference(self.word(pc), pc)
            if ref is not None and sh2_gas.format_insn(self.word(pc), pc, lambda t, k: "x") is not None:
                self.refs.append((pc, ref[0], ref[1]))

    def word(self, address: int) -> int:
        off = address - self.vram
        return (self.data[off] << 8) | self.data[off + 1]

    def cuts(self) -> list[int]:
        """Segment start addresses (always includes the module start)."""
        mode = self.cfg.get("split", "single")
        explicit = sorted(int(str(a), 16) if isinstance(a, str) else a for a in self.cfg.get("cuts", []))
        if mode == "single":
            candidates = explicit
        elif mode == "functions":
            candidates = sorted(set(explicit) | {a for a, (_, kind) in self.symbols.items() if kind == "func"})
        else:
            raise SystemExit(f"{self.name}: unknown split mode {mode}")
        candidates = [c for c in candidates if self.vram < c < self.end and c % 4 == 0]
        if not candidates:
            return [self.vram]
        allow_bsr = self.cfg.get("cross_file_bsr", True)
        blocked = [0] * (len(candidates) + 1)
        for pc, kind, target in self.refs:
            if allow_bsr and kind == "branch" and (self.word(pc) >> 12) == 0xB:
                continue
            lo, hi = min(pc, target), max(pc, target)
            i = bisect.bisect_right(candidates, lo)
            j = bisect.bisect_right(candidates, hi)
            if i < j:
                blocked[i] += 1
                blocked[j] -= 1
        out, depth = [self.vram], 0
        for index, c in enumerate(candidates):
            depth += blocked[index]
            if depth == 0:
                out.append(c)
        return out


def label_name(module: Sh2Module, address: int) -> str:
    sym = module.symbols.get(address)
    return sym[0] if sym else ".L%08X" % address


def emit_sh2(module: Sh2Module, start: int, end: int, header: str, c_functions: dict | None = None) -> tuple[str, dict]:
    stats = {"insns": 0, "raw_code_words": 0, "data_bytes": 0, "cross_refs": 0, "c_bytes": 0}
    c_functions = {a: v for a, v in (c_functions or {}).items() if start <= a < end}
    labels: set[int] = set()
    for pc, kind, target in module.refs:
        if start <= pc < end and start <= target < end:
            labels.add(target)
    for address in module.symbols:
        if start <= address < end:
            labels.add(address)
    func_addresses = {a for a, (_, k) in module.symbols.items() if k == "func"}
    end_refs: set[int] = set()
    lines = [header, "\t.section .text", ""]
    address = start
    boundaries = sorted(labels)
    while address < end:
        if address in c_functions:
            size, include = c_functions[address]
            # labels inside the function are fine when only the function itself uses them
            # (the compiled C has its own); refuse references from outside or symbols inside
            inner = sorted({t for pc, kind, t in module.refs
                            if address < t < address + size and not address <= pc < address + size}
                           | {a for a in module.symbols if address < a < address + size})
            if inner or address + size > end:
                raise SystemExit("C function at %08X: labels inside it %s or it crosses the file end"
                                 % (address, ["%08X" % a for a in inner[:4]]))
            sym = module.symbols.get(address)
            if sym:
                lines += ["\t.global %s" % sym[0], "%s:" % sym[0]]
            elif address in labels:
                lines.append(".L%08X:" % address)
            lines.append('\t.include "%s"  /* C: %08X-%08X */' % (include, address, address + size))
            stats["c_bytes"] += size
            address += size
            continue
        if address in labels:
            sym = module.symbols.get(address)
            if sym:
                lines.append("\t.global %s" % sym[0])
                if sym[1] == "func":
                    lines.append("\t.type %s, @function" % sym[0])
                lines.append("%s:" % sym[0])
            else:
                lines.append(".L%08X:" % address)
        if address in module.code and address % 2 == 0 and address + 2 <= end:
            w = module.word(address)
            refused = []

            def lab(target, kind):
                if target == end and kind in ("mova", "branch"):
                    end_refs.add(end)
                    return ".L%08X" % end  # local label after the last byte of this file
                if start <= target < end:
                    return label_name(module, target)
                refused.append((kind, target))
                return None

            text = sh2_gas.format_insn(w, address, lab)
            if text is not None:
                lines.append("/* %08X %04X */\t%s" % (address, w, text))
                stats["insns"] += 1
            else:
                note = ""
                if refused:
                    kind, target = refused[0]
                    mn = sh2_gas.format_insn(w, address, lambda t, k: label_name(module, t))
                    note = " /* %s */" % mn
                    stats["cross_refs"] += 1
                lines.append("/* %08X %04X */\t.2byte 0x%04X%s" % (address, w, w, note))
                stats["raw_code_words"] += 1
            address += 2
            continue
        # data: up to the next label or code halfword
        nxt = end
        i = bisect.bisect_right(boundaries, address)
        if i < len(boundaries):
            nxt = min(nxt, boundaries[i])
        probe = address + (address % 2)
        while probe < nxt and probe not in module.code:
            probe += 2
        nxt = min(nxt, probe)
        if nxt <= address:
            nxt = address + 1
        emit_data(module, address, nxt, lines, func_addresses)
        stats["data_bytes"] += nxt - address
        address = nxt
    if end_refs:
        lines.append(".L%08X:  /* end of file: start of the next segment */" % end)
    lines.append("")
    return "\n".join(lines), stats


def emit_data(module, start: int, end: int, lines: list, func_addresses: set):
    address = start
    while address < end:
        off = address - module.vram
        if address % 4 == 0 and address + 4 <= end:
            value = int.from_bytes(module.data[off:off + 4], "big")
            if value in func_addresses:
                lines.append("/* %08X */\t.4byte %s" % (address, module.symbols[value][0]))
            else:
                lines.append("/* %08X */\t.4byte 0x%08X" % (address, value))
            address += 4
        elif address % 2 == 0 and address + 2 <= end:
            lines.append("/* %08X */\t.2byte 0x%04X" % (address, int.from_bytes(module.data[off:off + 2], "big")))
            address += 2
        else:
            lines.append("/* %08X */\t.byte 0x%02X" % (address, module.data[off]))
            address += 1


def emit_plain_data(data: bytes, vram: int, start: int, end: int, header: str) -> str:
    lines = [header, "\t.section .text", ""]
    address = start
    while address < end:
        off = address - vram
        if address % 4 == 0 and address + 4 <= end:
            lines.append("/* %08X */\t.4byte 0x%08X" % (address, int.from_bytes(data[off:off + 4], "big")))
            address += 4
        elif address % 2 == 0 and address + 2 <= end:
            lines.append("/* %08X */\t.2byte 0x%04X" % (address, int.from_bytes(data[off:off + 2], "big")))
            address += 2
        else:
            lines.append("/* %08X */\t.byte 0x%02X" % (address, data[off]))
            address += 1
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# outputs

def write_if_changed(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    path.write_text(text)


def module_outputs(cfg: dict, mod: dict, data: bytes, out_root: Path) -> dict:
    release, name = cfg["release_dir"], mod["name"]
    mdir = out_root / "asm" / release / name
    bdir = out_root / "build" / "bin" / release / name
    vram, cpu = mod["vram"], mod.get("cpu", "sh2")
    header_base = "/* %s %s: generated by %s from config/%s.toml; do not edit */" % (
        release, name, GENERATOR, cfg["config_stem"])
    segments = []  # (start, end, kind)
    report = {"module": name, "cpu": cpu, "bytes": len(data), "segments": 0, "insns": 0,
              "raw_code_words": 0, "data_bytes": 0, "cross_refs": 0, "incbin_bytes": 0}
    bins = sorted((int(b["start"], 16) if isinstance(b["start"], str) else b["start"],
                   int(b["end"], 16) if isinstance(b["end"], str) else b["end"]) for b in mod.get("bin", []))
    includes = {}  # start -> (end, module name): byte-identical copies of another configured module
    for inc in mod.get("include", []):
        other = next(m for m in cfg["module"] if m["name"] == inc["module"])
        other_data = read_module(cfg, other, cfg["files"])
        lo = inc["start"]
        if data[lo - vram:lo - vram + len(other_data)] != other_data:
            raise SystemExit(f"{name}: include of {other['name']} at {lo:#x} differs from that module")
        includes[lo] = (lo + len(other_data), other["name"])
    if cpu == "m68k" and mod.get("code"):
        code = m68k_gas.read_code(ROOT / mod["code"])
        symbols = read_symbols(ROOT / mod["symbols"]) if mod.get("symbols") else {}
        header = header_base + "\n/* %08X-%08X */" % (vram, vram + len(data))
        text, stats = m68k_gas.emit_verified(data, vram, code, symbols, header)
        for key in ("insns", "raw_code_words", "data_bytes"):
            report[key] += stats[key]
        write_if_changed(mdir / ("seg_%08X.s" % vram), text)
        for old in mdir.glob("*.s"):
            if old.stem != "seg_%08X" % vram:
                old.unlink()
        report["segments"] = 1
        report["demoted"] = stats["demoted"]
        files = ["seg_%08X" % vram]
        return finish_module(cfg, mod, report, files, mdir, release, name, vram, cpu)
    c_functions, c_rules = {}, []
    for cf in mod.get("c_function", []):
        # compiled assembly path follows the source path, so one source can serve several modules
        out_s = "build/csrc/" + Path(cf["source"]).relative_to("src").with_suffix(".s").as_posix()
        c_functions[cf["address"]] = (cf["size"], out_s)
        c_rules += ["%s: %s" % (out_s, cf["source"]), "%s: CFLAGS_C := %s" % (out_s, cf.get("cflags", ""))]
    if cpu == "sh2" and mod.get("code"):
        code_ranges = read_ranges(ROOT / mod["code"])
        symbols = read_symbols(ROOT / mod["symbols"]) if mod.get("symbols") else {}
        module = Sh2Module(name, data, vram, code_ranges, symbols, mod)
        cuts = module.cuts()
    else:
        module = None
        cuts = [vram]
    # bin segments split the cut list
    points = sorted(set(cuts) | {b for lo, hi in bins for b in (lo, hi) if vram < b < vram + len(data)}
                    | {b for lo, (hi, _) in includes.items() for b in (lo, hi) if vram < b < vram + len(data)})
    inside_include = [(lo, hi) for lo, (hi, _) in includes.items()]
    points = [p for p in points if p in includes or not any(lo < p < hi for lo, hi in inside_include)]
    bounds = points + [vram + len(data)]
    files = []
    extra_deps = []
    for lo, hi in zip(bounds, bounds[1:]):
        if lo in includes:
            stem = "inc_%08X" % lo
            other = includes[lo][1]
            text = header_base + "\n/* %08X-%08X: byte-identical copy of module %s */\n\t.section .text\n\t.incbin \"build/%s/%s.bin\"\n" % (
                lo, hi, other, release, other)
            write_if_changed(mdir / (stem + ".s"), text)
            files.append(stem)
            segments.append((lo, hi))
            extra_deps.append("build/obj/%s/%s/%s.o: build/%s/%s.bin" % (release, name, stem, release, other))
            report["incbin_bytes"] += hi - lo
            continue
        is_bin = any(blo <= lo and hi <= bhi for blo, bhi in bins)
        stem = "%s_%08X" % ("bin" if is_bin else "seg", lo)
        header = header_base + "\n/* %08X-%08X */" % (lo, hi)
        if is_bin:
            blob = data[lo - vram:hi - vram]
            bpath = bdir / (stem + ".bin")
            bpath.parent.mkdir(parents=True, exist_ok=True)
            if not bpath.exists() or bpath.read_bytes() != blob:
                bpath.write_bytes(blob)
            rel = os.path.relpath(bpath, out_root)
            text = header + '\n\t.section .text\n\t.incbin "%s"\n' % rel
            report["incbin_bytes"] += hi - lo
        elif module is not None:
            text, stats = emit_sh2(module, lo, hi, header, c_functions)
            for key, value in stats.items():
                report[key] = report.get(key, 0) + value
            for a, (size, out_s) in c_functions.items():
                if lo <= a < hi:
                    extra_deps.append("build/obj/%s/%s/%s.o: %s" % (release, name, stem, out_s))
        else:
            text = emit_plain_data(data, vram, lo, hi, header)
            report["data_bytes"] += hi - lo
        write_if_changed(mdir / (stem + ".s"), text)
        files.append(stem)
        segments.append((lo, hi))
    extra_deps += c_rules
    report["segments"] = len(files)
    # stale files from an earlier split
    for old in mdir.glob("*.s"):
        if old.stem not in files:
            old.unlink()
    return finish_module(cfg, mod, report, files, mdir, release, name, vram, cpu, extra_deps)


def finish_module(cfg, mod, report, files, mdir, release, name, vram, cpu, extra_deps=()):
    objs = ["build/obj/%s/%s/%s.o" % (release, name, stem) for stem in files]
    ld = ["/* generated by %s; do not edit */" % GENERATOR,
          "OUTPUT_ARCH(%s)" % ("sh" if cpu == "sh2" else "m68k")]
    # globals referenced by C functions, at their original addresses
    ld += ["%s = 0x%08X;" % (sym, addr) for sym, addr in sorted(mod.get("c_globals", {}).items())]
    ld += [
          "SECTIONS", "{",
          "  .text 0x%08X : {" % vram]
    ld += ["    %s(.text)" % o for o in objs]
    ld += ["  }", "  /DISCARD/ : { *(*) }", "}", ""]
    write_if_changed(mdir / "module.ld", "\n".join(ld))
    key = "%s/%s" % (release, name)
    mk = ["# generated by %s; do not edit" % GENERATOR,
          "MODULES += %s" % key,
          "%s_CPU := %s" % (key, cpu),
          "%s_SHA256 := %s" % (key, mod["sha256"]),
          "%s_OBJS := %s" % (key, " ".join(objs)),
          "build/%s.bin: build/%s.elf" % (key, key),
          "build/%s.elf: $(%s_OBJS) asm/%s/module.ld" % (key, key, key),
          "$(%s_OBJS): CPU := %s" % (key, cpu), *extra_deps, ""]
    write_if_changed(mdir / "module.mk", "\n".join(mk))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path, nargs="+")
    parser.add_argument("--files", help="directory of extracted original disc files (overrides env)")
    parser.add_argument("--only", action="append", default=[], help="module name(s) to split")
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    total = []
    for cpath in args.config:
        cfg = load_config(cpath)
        cfg["config_stem"] = cpath.stem
        cfg.setdefault("release_dir", cpath.stem)
        files = files_dir(cfg, args.files)
        cfg["files"] = files
        for mod in cfg["module"]:
            if args.only and mod["name"] not in args.only:
                continue
            data = read_module(cfg, mod, files)
            report = module_outputs(cfg, mod, data, args.out)
            total.append(report)
            print("%-10s %-6s %8d bytes  %5d files  %7d insns  %6d raw-code  %8d data  %8d incbin  %5d x-file refs" % (
                report["module"], report["cpu"], report["bytes"], report["segments"], report["insns"],
                report["raw_code_words"], report["data_bytes"], report["incbin_bytes"], report["cross_refs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
