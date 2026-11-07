"""Splitter and 68000 GNU as rewriting: synthetic modules only, no original game bytes."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import m68k_gas  # noqa: E402
import saturn_binutils  # noqa: E402
import saturn_split  # noqa: E402


def words(*values):
    return b"".join(v.to_bytes(2, "big") for v in values)


# A synthetic SH-2 module at 0x06004000: two functions, a literal pool with a
# function pointer, plain data, and a bsr from the first file into the second.
BASE = 0x06004000
SYNTHETIC = (words(0xD003, 0x400B, 0x0009, 0xB00B, 0x0009, 0x000B, 0x0009, 0x0009)  # 4000-400F
             + (BASE + 0x20).to_bytes(4, "big") + bytes.fromhex("12345678") + bytes(range(8))  # 4010-401F
             + words(0xE001, 0x000B, 0x0009, 0x0009))  # 4020-4027


def have_binutils():
    return Path(saturn_binutils.tool(saturn_binutils.SH, "as")).exists()


class M68kRewriteTests(unittest.TestCase):
    def test_objdump_forms_are_rewritten_to_encoding_preserving_gnu_as_input(self):
        self.assertEqual(m68k_gas.gas_syntax("moveb #-2,%a2@(0,%d0:w)"), "moveb #254,%a2@(0x0,%d0:w)")
        self.assertEqual(m68k_gas.gas_syntax("moveal %fp@(1c,%d0:w),%a1"), "moveal %fp@(0x1c,%d0:w),%a1")
        self.assertEqual(m68k_gas.gas_syntax("movel %a0@(0),%a1@+"), "movel %a0@(0:w),%a1@+")
        self.assertEqual(m68k_gas.gas_syntax("moveq #-1,%d0"), "moveq #-1,%d0")
        self.assertEqual(m68k_gas.gas_syntax("andiw #-7968,%d0"), "andiw #-7968,%d0")

    def test_absolute_operands_get_explicit_size_variants_but_branches_do_not(self):
        self.assertEqual(m68k_gas.variants("movew %d4,0x141e"),
                         ["movew %d4,0x141e", "movew %d4,0x141e:l", "movew %d4,0x141e:w"])
        self.assertEqual(m68k_gas.variants("bras 0x1000"), ["bras 0x1000"])
        self.assertEqual(m68k_gas.split_ops("%a0@(4,%d0:w),%d1"), ["%a0@(4,%d0:w)", "%d1"])

    def test_in_module_targets_become_local_labels(self):
        label = lambda target: ".L%04X" % target  # noqa: E731
        inside = lambda target: target < 0x2000  # noqa: E731
        self.assertEqual(m68k_gas.relabel("bsrw 0x1178", inside, label), "bsrw .L1178")
        self.assertEqual(m68k_gas.relabel("dbf %d0,0x1234", inside, label), "dbf %d0,.L1234")
        self.assertEqual(m68k_gas.relabel("bras 0x8000", inside, label), "bras 0x8000")
        self.assertEqual(m68k_gas.relabel("lea %pc@(0x1266),%a0", inside, label), "lea %pc@(.L1266),%a0")
        self.assertEqual(m68k_gas.relabel("jsr %pc@(0x1ada,%d7:w)", inside, label), "jsr %pc@(.L1ADA,%d7:w)")


class SplitterTests(unittest.TestCase):
    def split(self, tmp: Path, extra: str = "") -> Path:
        (tmp / "files").mkdir()
        (tmp / "files" / "MOD.BIN").write_bytes(SYNTHETIC)
        (tmp / "mod.code.txt").write_text("06004000 0600400E\n06004020 06004028\n")
        (tmp / "mod.symbols.txt").write_text("06004000 func_06004000 func\n06004020 func_06004020 func\n")
        (tmp / "cfg.toml").write_text(
            'release = "synthetic"\nfiles_env = "SATURN_SYNTHETIC_FILES"\n'
            '[[module]]\nname = "mod"\npath = "MOD.BIN"\nsha256 = "%s"\nvram = 0x06004000\ncpu = "sh2"\n'
            'code = "%s"\nsymbols = "%s"\nsplit = "functions"\n%s' % (
                hashlib.sha256(SYNTHETIC).hexdigest(), tmp / "mod.code.txt", tmp / "mod.symbols.txt", extra))
        with contextlib.redirect_stdout(io.StringIO()):
            saturn_split.main([str(tmp / "cfg.toml"), "--files", str(tmp / "files"), "--out", str(tmp / "out")])
        return tmp / "out" / "asm" / "cfg" / "mod"

    def test_cuts_at_function_entries_with_labels_literals_and_end_label(self):
        with tempfile.TemporaryDirectory() as name:
            out = self.split(Path(name))
            self.assertEqual(sorted(p.name for p in out.glob("*.s")), ["seg_06004000.s", "seg_06004020.s"])
            first = (out / "seg_06004000.s").read_text()
            self.assertIn("mov.l .L06004010,r0", first)
            self.assertIn("bsr .L06004020", first)  # target is the first byte after this file
            self.assertIn(".L06004020:  /* end of file", first)
            self.assertIn(".4byte func_06004020", first)  # literal equal to a function entry
            self.assertIn(".4byte 0x12345678", first)
            ld = (out / "module.ld").read_text()
            self.assertLess(ld.index("seg_06004000.o"), ld.index("seg_06004020.o"))
            self.assertIn(".text 0x06004000", ld)

    def test_c_function_ranges_become_includes_with_globals_in_the_linker_script(self):
        extra = ('c_globals = { "_g_data" = 0x06004014 }\n'
                 '[[module.c_function]]\naddress = 0x06004020\nsize = 8\n'
                 'source = "src/mod/func_06004020.c"\ncflags = "-m2 -O2"\n')
        with tempfile.TemporaryDirectory() as name:
            out = self.split(Path(name), extra)
            second = (out / "seg_06004020.s").read_text()
            self.assertIn('.include "build/csrc/mod/func_06004020.s"', second)
            self.assertNotIn("mov #1,r0", second)  # the C range is not disassembled
            self.assertIn("_g_data = 0x06004014;", (out / "module.ld").read_text())
            mk = (out / "module.mk").read_text()
            self.assertIn("build/csrc/mod/func_06004020.s: src/mod/func_06004020.c", mk)
            self.assertIn("CFLAGS_C := -m2 -O2", mk)

    def test_c_function_containing_another_entry_is_refused(self):
        extra = ('[[module.c_function]]\naddress = 0x06004000\nsize = 16\n'
                 'source = "src/mod/f.c"\n')
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            (tmp / "files").mkdir()
            # a second function entry inside the C range: other code may call it, so refuse
            with self.assertRaises(SystemExit):
                self.split_with_symbols(tmp, extra, "06004000 func_06004000 func\n06004008 inner func\n")

    def split_with_symbols(self, tmp: Path, extra: str, symbols: str):
        (tmp / "files" / "MOD.BIN").write_bytes(SYNTHETIC)
        (tmp / "mod.code.txt").write_text("06004000 0600400E\n06004020 06004028\n")
        (tmp / "mod.symbols.txt").write_text(symbols)
        (tmp / "cfg.toml").write_text(
            'release = "synthetic"\n[[module]]\nname = "mod"\npath = "MOD.BIN"\nsha256 = "%s"\n'
            'vram = 0x06004000\ncpu = "sh2"\ncode = "%s"\nsymbols = "%s"\nsplit = "functions"\n%s' % (
                hashlib.sha256(SYNTHETIC).hexdigest(), tmp / "mod.code.txt", tmp / "mod.symbols.txt", extra))
        with contextlib.redirect_stdout(io.StringIO()):
            saturn_split.main([str(tmp / "cfg.toml"), "--files", str(tmp / "files"), "--out", str(tmp / "out")])

    def test_wrong_input_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            (tmp / "files").mkdir()
            (tmp / "files" / "MOD.BIN").write_bytes(SYNTHETIC[:-2] + b"\x00\x00")
            (tmp / "cfg.toml").write_text('release = "s"\n[[module]]\nname = "m"\npath = "MOD.BIN"\nsha256 = "%s"\n'
                                          'vram = 0\ncpu = "sh2"\n' % hashlib.sha256(SYNTHETIC).hexdigest())
            with self.assertRaises(SystemExit):
                saturn_split.main([str(tmp / "cfg.toml"), "--files", str(tmp / "files"), "--out", str(tmp / "out")])

    def test_split_rebuilds_byte_identically_with_gnu_binutils(self):
        if not have_binutils():
            self.skipTest("GNU binutils for SH not installed (set SATURN_BINUTILS)")
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            out = self.split(tmp)
            env = saturn_binutils.env()
            objs = []
            for src in sorted(out.glob("*.s")):
                obj = tmp / (src.stem + ".o")
                subprocess.run([saturn_binutils.tool(saturn_binutils.SH, "as"), *saturn_binutils.SH_AS_FLAGS,
                                "-o", str(obj), str(src)], check=True, env=env, cwd=tmp / "out")
                objs.append(str(obj))
            script = tmp / "m.ld"
            script.write_text("SECTIONS { .text 0x06004000 : { %s } /DISCARD/ : { *(*) } }\n"
                              % " ".join("%s(.text)" % o for o in objs))
            subprocess.run([saturn_binutils.tool(saturn_binutils.SH, "ld"), "-EB", "--no-relax", "-T", str(script),
                            "-o", str(tmp / "m.elf"), *objs], check=True, env=env)
            subprocess.run([saturn_binutils.tool(saturn_binutils.SH, "objcopy"), "-O", "binary", "-j", ".text",
                            str(tmp / "m.elf"), str(tmp / "m.bin")], check=True, env=env)
            self.assertEqual((tmp / "m.bin").read_bytes(), SYNTHETIC)


M68K_SOURCE = """
\t.text
start:\tlea %pc@(table),%a0
\tmoveb #254,%a2@(0x10,%d0:w)
\tmovew %d4,0x141e:l
\tmovel %a0@(0:w),%a1@+
\tbsrw sub
\tdbf %d0,start
\tjsr %pc@(sub)
\tbras done
sub:\tmoveq #-1,%d0
\trts
done:\tbras done
\t.even
table:\t.short 1,2,3,4
"""


class M68kVerifiedEmitterTests(unittest.TestCase):
    def test_synthetic_68000_program_is_reemitted_byte_identically(self):
        if not Path(saturn_binutils.tool(saturn_binutils.M68K, "as")).exists():
            self.skipTest("GNU binutils for m68k not installed (set SATURN_BINUTILS)")
        env = saturn_binutils.env()
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            (tmp / "p.s").write_text(M68K_SOURCE)
            subprocess.run([saturn_binutils.tool(saturn_binutils.M68K, "as"), "-m68000", "-o", str(tmp / "p.o"),
                            str(tmp / "p.s")], check=True, env=env)
            subprocess.run([saturn_binutils.tool(saturn_binutils.M68K, "objcopy"), "-O", "binary", "-j", ".text",
                            str(tmp / "p.o"), str(tmp / "p.bin")], check=True, env=env)
            data = (tmp / "p.bin").read_bytes()
            table = data.rindex(bytes.fromhex("0001000200030004"))
            # instruction lengths from a linear objdump of the code part (the synthetic program has no data in it)
            listing = m68k_gas.objdump_runs(data, 0, {0: table})
            code, address = {}, 0
            while address < table:
                code[address] = listing[address][0]
                address += code[address]
            text, stats = m68k_gas.emit_verified(data, 0, code, {0: ("start", "func")}, "/* synthetic */")
            self.assertEqual(stats["demoted"], 0)
            self.assertIn("moveb #254,", text)
            self.assertIn("bsrw .L", text)
            self.assertIn("%pc@(.L", text)
            rebuilt, _ = m68k_gas.assemble(text, 0)
            self.assertEqual(rebuilt, data)


if __name__ == "__main__":
    unittest.main()
