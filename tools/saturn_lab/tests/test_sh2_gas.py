"""SH-2 GNU as formatter: synthetic words only, no original game bytes."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sh2_discover  # noqa: E402
import sh2_gas  # noqa: E402

ANY = lambda target, kind: "L"  # noqa: E731


def binutils_prefix():
    root = os.environ.get("SATURN_BINUTILS")
    if root:
        candidate = Path(root) / "usr" / "bin" / "sh4-linux-gnu-"
        if Path(str(candidate) + "as").exists():
            return str(candidate), str(Path(root) / "usr" / "lib" / "x86_64-linux-gnu")
    for prefix in ("sh-elf-", "sh4-linux-gnu-"):
        if shutil.which(prefix + "as"):
            return prefix, None
    return None, None


class Sh2GasFormatterTests(unittest.TestCase):
    def test_accepts_exactly_the_words_the_discovery_decoder_accepts(self):
        disagreements = [w for w in range(0x10000)
                         if (sh2_gas.format_insn(w, 0x1000, ANY) is None) != sh2_discover.decode(w).illegal]
        self.assertEqual(disagreements, [])
        accepted = sum(1 for w in range(0x10000) if sh2_gas.format_insn(w, 0x1000, ANY) is not None)
        self.assertEqual(accepted, 53752)

    def test_pc_relative_targets_agree_with_the_discovery_decoder(self):
        for pc in (0x06006000, 0x06006002):
            for w in range(0x10000):
                ins = sh2_discover.decode(w)
                ref = sh2_gas.reference(w, pc)
                if ins.illegal:
                    continue
                if ins.pcrel:
                    self.assertEqual(ref[1], sh2_discover.pcrel_address(ins, pc), hex(w))
                elif ins.flow in ("bra", "bsr", "bt", "bf", "bt/s", "bf/s"):
                    self.assertEqual(ref[1], sh2_discover.branch_target(ins, pc), hex(w))
                else:
                    self.assertIsNone(ref, hex(w))

    def test_known_encodings_use_gnu_as_operand_order_and_byte_displacements(self):
        cases = {
            0xD301: (0x0600A000, "mov.l L_0600A008,r3"),
            0x432B: (0, "jmp @r3"),
            0x1234: (0, "mov.l r3,@(16,r2)"),
            0x5674: (0, "mov.l @(16,r7),r6"),
            0x8145: (0, "mov.w r0,@(10,r4)"),
            0xC6FF: (0, "mov.l @(1020,gbr),r0"),
            0x88FF: (0, "cmp/eq #-1,r0"),
            0xC9FF: (0, "and #255,r0"),
            0x0F1F: (0, "mac.l @r1+,@r15+"),
            0x8DFE: (0x100, "bt/s L_00000100"),
            0x0009: (0, "nop"),
        }
        label = lambda target, kind: "L_%08X" % target  # noqa: E731
        for word, (pc, text) in cases.items():
            self.assertEqual(sh2_gas.format_insn(word, pc, label), text)

    def test_refused_targets_and_illegal_words_return_none(self):
        self.assertIsNone(sh2_gas.format_insn(0xB000, 0x1000, lambda target, kind: None))  # bsr
        self.assertIsNone(sh2_gas.format_insn(0xFFFF, 0x1000, ANY))  # SH-4 FPU space
        self.assertIsNone(sh2_gas.format_insn(0x0108, 0x1000, ANY))  # clrt needs n == 0
        self.assertEqual(sh2_gas.mnemonic(0x000B), "rts")

    def test_every_accepted_word_round_trips_through_gnu_as(self):
        prefix, libdir = binutils_prefix()
        if prefix is None:
            self.skipTest("GNU binutils for SH not installed (set SATURN_BINUTILS)")
        env = dict(os.environ)
        if libdir:
            env["LD_LIBRARY_PATH"] = libdir
        base = 0x4000
        lines, pc = ["\t.text", "S:", "\t.space %d" % base], base
        for w in range(0x10000):
            text = sh2_gas.format_insn(w, pc, lambda target, kind: "S+0x%x" % target)
            lines.append("\t" + (text if text is not None else ".2byte 0x%04x" % w))
            pc += 2
        lines.append("\t.space 0x4000")
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            (tmp / "t.s").write_text("\n".join(lines) + "\n")
            subprocess.run([prefix + "as", "-big", "--isa=sh2", "-o", str(tmp / "t.o"), str(tmp / "t.s")],
                           check=True, env=env)
            subprocess.run([prefix + "objcopy", "-O", "binary", "-j", ".text", str(tmp / "t.o"),
                            str(tmp / "t.bin")], check=True, env=env)
            body = (tmp / "t.bin").read_bytes()[base:base + 0x20000]
        expected = b"".join(w.to_bytes(2, "big") for w in range(0x10000))
        self.assertEqual(body, expected)


if __name__ == "__main__":
    unittest.main()
