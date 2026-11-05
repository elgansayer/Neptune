"""68000 assembly for the splitter: GNU objdump text, verified through GNU as.

Instruction boundaries come from a code map (``START LENGTH`` per instruction).
Each contiguous run of instructions is disassembled by GNU objdump
(``-m m68k:68000``); branch and PC-relative targets inside the module become
labels.  The result is then assembled with GNU as and checked instruction by
instruction: any instruction whose assembled size or bytes differ from the
original is replaced by raw ``.short`` words, and the check repeats until the
module is byte-identical.  So every emitted mnemonic is proven to reassemble
to the original bytes with the pinned binutils.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import saturn_binutils as binutils

LINE = re.compile(r"^\s*([0-9a-f]+):\t([0-9a-f ]+?)\s*\t(\S+)(?:\s+(.*))?$")
BRANCH = re.compile(r"^(b[a-z]{2,3}[sw]?|db[a-z]{1,2})$")
PCREL = re.compile(r"%pc@\(0x([0-9a-f]+)")


def read_code(path: Path) -> dict[int, int]:
    out = {}
    for line in path.read_text().splitlines():
        body = line.split("#", 1)[0].split()
        if len(body) >= 2:
            out[int(body[0], 16)] = int(body[1], 16)
    return out


def objdump_runs(data: bytes, vram: int, code: dict[int, int]) -> dict[int, tuple[int, str]]:
    """Disassemble each contiguous instruction run; returns address -> (length, text)."""
    starts = sorted(code)
    runs, cur = [], None
    for a in starts:
        if cur and a == cur[1]:
            cur[1] = a + code[a]
        else:
            if cur:
                runs.append(cur)
            cur = [a, a + code[a]]
    if cur:
        runs.append(cur)
    out: dict[int, tuple[int, str]] = {}
    with tempfile.TemporaryDirectory() as name:
        blob = Path(name) / "m.bin"
        blob.write_bytes(data)
        for lo, hi in runs:
            text = subprocess.run(
                [binutils.tool(binutils.M68K, "objdump"), "-D", "-b", "binary", "-m", "m68k:68000",
                 "--adjust-vma=0x%x" % vram, "--start-address=0x%x" % lo, "--stop-address=0x%x" % hi, str(blob)],
                check=True, capture_output=True, text=True, env=binutils.env()).stdout
            pending = None
            for line in text.splitlines():
                m = LINE.match(line)
                if m:
                    addr = int(m.group(1), 16)
                    raw = m.group(2).replace(" ", "")
                    pending = addr
                    out[addr] = (len(raw) // 2, (m.group(3) + " " + (m.group(4) or "")).strip())
                elif pending is not None:
                    parts = line.strip().split(":\t")
                    if len(parts) == 2 and re.fullmatch(r"[0-9a-f ]+", parts[1].strip()):
                        length, txt = out[pending]
                        out[pending] = (length + len(parts[1].replace(" ", "").strip()) // 2, txt)
    return out


BRIEF = re.compile(r"@\((-?)(?!0x)([0-9a-f]+),")
ZERO_D16 = re.compile(r"@\(0\)")
NEG_IMM = re.compile(r"#-(\d+)")
ABS = re.compile(r"^0x[0-9a-f]+$")


def split_ops(ops: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in ops:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def gas_syntax(text: str) -> str:
    """objdump m68k text -> GNU as input with the same encoding (common cases)."""
    mnem, _, ops = text.partition(" ")
    if not ops:
        return text
    # objdump prints brief-extension (index) displacements in hex without 0x
    ops = BRIEF.sub(lambda m: "@(%s0x%s," % (m.group(1), m.group(2)), ops)
    # a zero 16-bit displacement would otherwise be optimised to plain (An)
    ops = ZERO_D16.sub("@(0:w)", ops)
    # byte-size immediates: GNU as sign-extends negative values into the extension word
    if mnem.endswith("b") and mnem != "moveq":
        ops = NEG_IMM.sub(lambda m: "#%d" % (256 - int(m.group(1))) if int(m.group(1)) <= 128 else m.group(0), ops)
    return mnem + " " + ops


def variants(text: str) -> list[str]:
    """Encoding alternatives tried in order when the plain form does not reassemble."""
    mnem, _, ops = text.partition(" ")
    if not ops or BRANCH.match(mnem):
        return [text]
    parts = split_ops(ops)
    if not any(ABS.match(p) for p in parts):
        return [text]
    out = [text]
    for suffix in (":l", ":w"):
        out.append(mnem + " " + ",".join(p + suffix if ABS.match(p) else p for p in parts))
    return out


def relabel(text: str, inside, label, inside_data=None) -> str:
    """Replace in-module branch / PC-relative targets with labels."""
    inside_data = inside_data or inside
    mnem, _, ops = text.partition(" ")
    if BRANCH.match(mnem) and ops:
        head, sep, tail = ops.rpartition(",")
        target_text = tail if sep else ops
        if target_text.startswith("0x"):
            target = int(target_text, 16)
            if inside(target):
                return "%s %s%s%s" % (mnem, head, sep, label(target))
        return text

    def sub(m):
        target = int(m.group(1), 16)
        return "%%pc@(%s" % label(target) if inside_data(target) else m.group(0)

    return mnem + (" " + PCREL.sub(sub, ops) if ops else "")


def emit(data: bytes, vram: int, code: dict[int, int], symbols: dict, header: str, raw: set[int],
         markers: bool = False, choice: dict | None = None) -> tuple[str, dict]:
    end = vram + len(data)
    dis = objdump_runs(data, vram, code)
    labels = set(a for a in symbols if vram <= a < end)
    texts = {}
    stats = {"insns": 0, "raw_code_words": 0, "data_bytes": 0}

    covered = set()
    for a0, n0 in code.items():
        covered.update(range(a0 + 1, a0 + n0))

    def inside(t):
        return vram <= t < end and t in code

    def inside_data(t):
        return vram <= t < end and t not in covered

    def lab(t):
        # local labels: GNU as resolves them at assembly time (globals stay relocations)
        labels.add(t)
        return ".L%08X" % t

    accepted = {}
    for a in sorted(code):
        n = code[a]
        got = dis.get(a)
        if a in raw or got is None or got[0] != n or got[1].startswith(".short") or "(bad)" in got[1] \
                or a + n > end:
            continue
        accepted[a] = n
    choice = choice or {}
    for a, n in accepted.items():
        options = variants(gas_syntax(relabel(dis[a][1], inside, lab, inside_data)))
        texts[a] = options[min(choice.get(a, 0), len(options) - 1)]
    lines = [header, "\t.section .text", ""]
    a = vram
    starts = sorted(code)
    import bisect
    while a < end:
        if a in symbols:
            lines += ["\t.global %s" % symbols[a][0], "%s:" % symbols[a][0]]
        if a in labels:
            lines.append(".L%08X:" % a)
        if markers and a in code:
            lines.append("M%08X:" % a)
        if a in accepted:
            off = a - vram
            lines.append("/* %08X %s */\t%s" % (a, data[off:off + accepted[a]].hex(), texts[a]))
            stats["insns"] += 1
            a += accepted[a]
            continue
        # raw: up to the next code start / label (instructions in code map emitted as .short words)
        i = bisect.bisect_right(starts, a)
        nxt = min([end] + [s for s in starts[i:i + 1]] + [l for l in labels if l > a] + [s for s in symbols if a < s < end])
        if a in code:
            nxt = min(nxt, a + code[a]) if a + code[a] > a else nxt
            stats["raw_code_words"] += (nxt - a) // 2
        else:
            stats["data_bytes"] += nxt - a
        while a < nxt:
            off = a - vram
            if a % 2 == 0 and a + 2 <= nxt:
                lines.append("/* %08X */\t.short 0x%04X" % (a, int.from_bytes(data[off:off + 2], "big")))
                a += 2
            else:
                lines.append("/* %08X */\t.byte 0x%02X" % (a, data[off]))
                a += 1
    lines.append("")
    return "\n".join(lines), stats


def assemble(text: str, vram: int = 0) -> tuple[bytes, dict[int, int]]:
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        (tmp / "m.s").write_text(text)
        env = binutils.env()
        subprocess.run([binutils.tool(binutils.M68K, "as"), *binutils.M68K_AS_FLAGS, "-o", str(tmp / "m.o"),
                        str(tmp / "m.s")], check=True, env=env, capture_output=True, text=True)
        # link so branches to global symbols (left as relocations by GNU as) are resolved
        subprocess.run([binutils.tool(binutils.M68K, "ld"), "-Ttext=0x%x" % vram, "-e", "0x%x" % vram, "-o",
                        str(tmp / "m.elf"), str(tmp / "m.o")], check=True, env=env, capture_output=True)
        subprocess.run([binutils.tool(binutils.M68K, "objcopy"), "-O", "binary", "-j", ".text", str(tmp / "m.elf"),
                        str(tmp / "m.bin")], check=True, env=env)
        nm = subprocess.run([binutils.tool(binutils.M68K, "nm"), str(tmp / "m.elf")], check=True, env=env,
                            capture_output=True, text=True).stdout
        marks = {}
        for line in nm.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[2].startswith("M") and len(parts[2]) == 9:
                marks[int(parts[2][1:], 16)] = int(parts[0], 16) - vram
        return (tmp / "m.bin").read_bytes(), marks


def emit_verified(data: bytes, vram: int, code: dict[int, int], symbols: dict, header: str) -> tuple[str, dict]:
    """Emit, then demote instructions to raw words until GNU as reproduces ``data``."""
    # overlapping instruction starts (descent "bad paths") cannot both be instructions
    code = dict(code)
    for a in sorted(code):
        if a in code and any(b in code for b in range(a + 1, a + code[a])):
            del code[a]
    raw: set[int] = set()
    choice: dict[int, int] = {}

    def bump(bad):
        for a in bad:
            choice[a] = choice.get(a, 0) + 1
            if choice[a] >= 3:
                raw.add(a)

    for _ in range(24):
        text, _ = emit(data, vram, code, symbols, header, raw, markers=True, choice=choice)
        try:
            out, marks = assemble(text, vram)
        except subprocess.CalledProcessError as error:
            # assembler errors name source lines: map them back to instruction addresses
            lines, bad = text.splitlines(), set()
            for num in re.findall(r"m\.s:(\d+):", error.stderr or ""):
                m = re.match(r"/\* ([0-9A-F]{8}) ", lines[int(num) - 1])
                if m:
                    bad.add(int(m.group(1), 16))
            if not bad - raw:
                raise RuntimeError("68000 assembly failed outside instructions: " + (error.stderr or "")[:2000])
            raw |= bad
            continue
        sizes = sorted(marks.items())
        size_bad = set()
        for (a1, o1), (a2, o2) in zip(sizes, sizes[1:]):
            if o2 - o1 != a2 - a1 and a1 not in raw:
                size_bad.add(a1)
        if sizes and len(out) != len(data) and sizes[-1][0] not in raw:
            size_bad.add(sizes[-1][0])
        if size_bad:
            bump(size_bad)
            continue
        content_bad = {a for a, off in sizes if a not in raw and a in code
                       and out[a - vram:a - vram + code[a]] != data[a - vram:a - vram + code[a]]}
        if not content_bad and out == data:
            text, stats = emit(data, vram, code, symbols, header, raw, choice=choice)
            stats["demoted"] = len(raw)
            return text, stats
        if not content_bad:
            raise RuntimeError("68000 module not identical but no instruction to demote")
        bump(content_bad)
    raise RuntimeError("68000 verification did not converge")
