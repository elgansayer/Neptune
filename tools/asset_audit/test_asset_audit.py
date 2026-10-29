"""Unit and boundary tests for tools/asset_audit (synthetic fixtures only)."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.asset_audit.audit import AuditError, run_audit, verify_ledger, verify_summary
from tools.asset_audit.cli import main as cli_main
from tools.asset_audit.formats import PNG_SIGNATURE, inspect_file_bytes
from tools.saturn_lab.cli import LabError


def _png_chunk(ctype: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(ctype + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + ctype + payload + struct.pack(">I", crc)


def make_valid_png(width: int = 4, height: int = 3, rgba_byte: int = 0x7F) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + bytes([rgba_byte]) * (width * 4)
    raw = row * height
    idat = zlib.compress(raw)
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")


def make_sega_film(payload_bytes: int, declared_sample_len: int) -> bytes:
    fdsc = b"FDSC" + struct.pack(">I", 32) + b"cvid" + struct.pack(">II", 160, 320) + bytes([24, 2, 8, 0]) + struct.pack(">H", 22050) + b"\x00" * 6
    stab_entry = struct.pack(">IIII", 0, declared_sample_len, 0, 0)
    stab = b"STAB" + struct.pack(">III", 32, 30, 1) + stab_entry
    header_len = 16 + len(fdsc) + len(stab)
    header = b"FILM" + struct.pack(">I", header_len) + b"1.04\x00\x00\x00\x00" + fdsc + stab
    return header + (b"\xAA" * payload_bytes)


class FormatInspectionTests(unittest.TestCase):
    def test_valid_png_full_vs_header_only_distinguished(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sprite.png"
            p.write_bytes(make_valid_png(8, 6))
            full = inspect_file_bytes(p, full_png_decode=True)
            head = inspect_file_bytes(p, full_png_decode=False)
            self.assertTrue(full["valid"])
            self.assertEqual(full["decode_level"], "full_stream")
            self.assertEqual(full["dimensions"], [8, 6])
            self.assertTrue(head["valid"])
            self.assertEqual(head["decode_level"], "header_only")
            self.assertNotEqual(full["decode_level"], head["decode_level"])

    def test_corrupt_idat_caught_by_full_decode_not_header_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ihdr = struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0)
            bad_idat = b"not-a-valid-zlib-stream"
            corrupt_png = (
                PNG_SIGNATURE
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IDAT", bad_idat)
                + _png_chunk(b"IEND", b"")
            )
            p = Path(tmp) / "bad_idat.png"
            p.write_bytes(corrupt_png)
            self.assertTrue(inspect_file_bytes(p, full_png_decode=False)["valid"])
            full = inspect_file_bytes(p, full_png_decode=True)
            self.assertFalse(full["valid"])
            self.assertIn("zlib", full["error"])

    def test_corrupt_png_crc_and_wrong_scanline_length_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = bytearray(make_valid_png(2, 2))
            good[-6] ^= 0xFF  # flip CRC byte before IEND
            p_crc = Path(tmp) / "bad_crc.png"
            p_crc.write_bytes(bytes(good))
            res_crc = inspect_file_bytes(p_crc, full_png_decode=True)
            self.assertFalse(res_crc["valid"])
            self.assertIn("CRC", res_crc["error"])

            ihdr = struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0)
            short_idat = zlib.compress(b"\x00\x01\x02")
            p_short = Path(tmp) / "short_scanline.png"
            p_short.write_bytes(
                PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", short_idat) + _png_chunk(b"IEND", b"")
            )
            res_short = inspect_file_bytes(p_short, full_png_decode=True)
            self.assertFalse(res_short["valid"])
            self.assertIn("scanline byte count", res_short["error"])

    def test_truncated_sega_film_cpk_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ok_cpk = Path(tmp) / "BOMSS1.CPK"
            ok_cpk.write_bytes(make_sega_film(payload_bytes=64, declared_sample_len=64))
            res_ok = inspect_file_bytes(ok_cpk)
            self.assertTrue(res_ok["valid"])
            self.assertEqual(res_ok["detected_format"], "sega_film_cpk")
            self.assertEqual(res_ok["dimensions"], [320, 160])

            trunc_cpk = Path(tmp) / ".goutputstream-TEST"
            trunc_cpk.write_bytes(make_sega_film(payload_bytes=16, declared_sample_len=1024))
            res_trunc = inspect_file_bytes(trunc_cpk)
            self.assertFalse(res_trunc["valid"])
            self.assertFalse(res_trunc["extension_matches_format"])
            self.assertIn("Truncated Sega FILM payload", res_trunc["error"])

    def test_extension_magic_mismatch_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Valid BMP header saved with .png extension
            bmp_bytes = b"BM" + struct.pack("<IHHI", 70, 0, 0, 54) + struct.pack("<IiiHHIIIIII", 40, 2, 2, 1, 24, 0, 16, 0, 0, 0, 0) + b"\x00" * 16
            misnamed = Path(tmp) / "fake.png"
            misnamed.write_bytes(bmp_bytes)
            res = inspect_file_bytes(misnamed)
            self.assertEqual(res["detected_format"], "bmp")
            self.assertFalse(res["extension_matches_format"])

            garbage = Path(tmp) / "garbage.png"
            garbage.write_bytes(b"NOT_AN_IMAGE_AT_ALL")
            res_g = inspect_file_bytes(garbage)
            self.assertFalse(res_g["valid"])
            self.assertEqual(res_g["detected_format"], "magic_mismatch")


class AuditPipelineAndSafetyTests(unittest.TestCase):
    def _init_git_fixture(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "README.md").write_text("# Test Assets\n* ContributorA\n", encoding="utf-8")
        (root / "images" / "Sprite Sheets" / "characters").mkdir(parents=True)
        png_a = make_valid_png(4, 4, 0x22)
        (root / "images" / "Sprite Sheets" / "characters" / "Character White Bomberman.png").write_bytes(png_a)
        (root / "images" / "Single Sprites" / "players" / "WhiteBomberman").mkdir(parents=True)
        # Exact byte duplicate of the sprite sheet to test duplicate grouping
        (root / "images" / "Single Sprites" / "players" / "WhiteBomberman" / "dup.png").write_bytes(png_a)
        (root / "images" / "Single Sprites" / "single player" / "map1").mkdir(parents=True)
        (root / "images" / "Single Sprites" / "single player" / "map1" / "1.png").write_bytes(make_valid_png(2, 2, 0x33))
        (root / "images" / "maps").mkdir(parents=True)
        (root / "images" / "maps" / "original.png").write_bytes(make_valid_png(6, 6, 0x44))
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "initial"], check=True)

    def test_repeatable_runs_and_duplicate_grouping(self) -> None:
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as out_tmp:
            src = Path(src_tmp)
            out = Path(out_tmp)
            self._init_git_fixture(src)

            m1, s1 = out / "m1.json", out / "s1.json"
            m2, s2 = out / "m2.json", out / "s2.json"
            self.assertEqual(
                cli_main(["audit", str(src), "--private-manifest", str(m1), "--summary-output", str(s1), "--require-clean-git"]),
                0,
            )
            self.assertEqual(
                cli_main(["audit", str(src), "--private-manifest", str(m2), "--summary-output", str(s2), "--require-clean-git"]),
                0,
            )
            self.assertEqual(m1.read_bytes(), m2.read_bytes())
            self.assertEqual(s1.read_bytes(), s2.read_bytes())

            summary = json.loads(s1.read_text(encoding="utf-8"))
            self.assertEqual(summary["totals"]["file_count"], 5)
            self.assertEqual(summary["totals"]["duplicate_group_count"], 1)
            self.assertEqual(summary["totals"]["redundant_duplicate_files"], 1)
            self.assertTrue(summary["source_snapshot"]["is_clean"])
            self.assertEqual(cli_main(["verify-summary", str(s1)]), 0)

    def test_dirty_git_and_output_inside_source_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as out_tmp:
            src = Path(src_tmp)
            out = Path(out_tmp)
            self._init_git_fixture(src)

            # Refuses writing inside read-only source
            self.assertEqual(
                cli_main(["audit", str(src), "--private-manifest", str(src / "bad.json"), "--summary-output", str(out / "s.json")]),
                1,
            )

            # Untracked file fails --require-clean-git
            (src / "untracked.txt").write_text("dirty", encoding="utf-8")
            self.assertEqual(
                cli_main(["audit", str(src), "--private-manifest", str(out / "m.json"), "--summary-output", str(out / "s.json"), "--require-clean-git"]),
                1,
            )

    def test_symlink_and_unreadable_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as src_tmp:
            src = Path(src_tmp)
            (src / "real.png").write_bytes(make_valid_png())
            (src / "link.png").symlink_to(src / "real.png")
            with self.assertRaises(LabError):
                run_audit(src)
            (src / "link.png").unlink()

            if os.geteuid() != 0:
                secret = src / "unreadable.png"
                secret.write_bytes(make_valid_png())
                secret.chmod(0)
                try:
                    with self.assertRaises(OSError):
                        run_audit(src)
                finally:
                    secret.chmod(0o600)

    def test_verify_summary_rejects_blanket_license_or_fidelity_claims(self) -> None:
        with tempfile.TemporaryDirectory() as src_tmp:
            src = Path(src_tmp)
            self._init_git_fixture(src)
            _, summary = run_audit(src, require_clean_git=True)
            verify_summary(summary)

            bad_apache = copy.deepcopy(summary)
            bad_apache["provenance_scopes"][0]["neptune_apache_2_0_applies"] = True
            with self.assertRaises(AuditError):
                verify_summary(bad_apache)

            bad_perm = copy.deepcopy(summary)
            bad_perm["provenance_scopes"][0]["distribution_permission"] = "permitted"
            with self.assertRaises(AuditError):
                verify_summary(bad_perm)

            bad_fidelity = copy.deepcopy(summary)
            bad_fidelity["boundaries"]["saturn_fidelity_certified"] = True
            with self.assertRaises(AuditError):
                verify_summary(bad_fidelity)

    def test_committed_summary_and_ledger_contracts_and_rejections(self) -> None:
        summary_path = REPO_ROOT / "docs/restart/asset-audit/saturn-assets-b55b5a55.summary.json"
        ledger_path = REPO_ROOT / "docs/restart/asset-audit/saturn-coverage-ledger.json"
        self.assertTrue(summary_path.is_file(), "Missing committed asset-audit summary")
        self.assertTrue(ledger_path.is_file(), "Missing committed Saturn coverage ledger")
        self.assertEqual(cli_main(["verify-summary", str(summary_path)]), 0)
        self.assertEqual(cli_main(["verify-ledger", str(ledger_path)]), 0)

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        blended = copy.deepcopy(ledger)
        del blended["profiles"]["japan"]
        with self.assertRaises(AuditError):
            verify_ledger(blended)

        forced_ok = copy.deepcopy(ledger)
        forced_ok["accounting_policy"]["forced_or_debug_states_counted_as_normal_reachable"] = True
        with self.assertRaises(AuditError):
            verify_ledger(forced_ok)

        over_denom = copy.deepcopy(ledger)
        over_denom["domains"][1]["usa"]["observed"] = 99
        with self.assertRaises(AuditError):
            verify_ledger(over_denom)


if __name__ == "__main__":
    unittest.main()
