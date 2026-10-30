"""Synthetic positive/negative unit tests for tools/saturn_disc (proves tool invariants, not game parity)."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saturn_disc.classify import classify_disc_file
from saturn_disc.cli import main as cli_main
from saturn_disc.cue import DiscError, compute_edc, frames_to_msf, parse_cue_sheet
from saturn_disc.diff import detect_cdda_sample_shift, diff_disc_inventories
from saturn_disc.ipbin import SYSTEM_AREA_BYTES, parse_ip_bin
from saturn_disc.iso9660 import inspect_disc


def _to_bcd(val: int) -> int:
    return ((val // 10) << 4) | (val % 10)


def _wrap_mode1_sector(lba: int, payload2048: bytes) -> bytes:
    assert len(payload2048) == 2048
    msf_str = frames_to_msf(150 + lba)
    mm, ss, ff = (int(part) for part in msf_str.split(":"))
    sync_hdr = b"\x00" + (b"\xff" * 10) + b"\x00" + bytes((_to_bcd(mm), _to_bcd(ss), _to_bcd(ff), 1))
    body = sync_hdr + payload2048
    edc = compute_edc(body)
    return body + struct.pack("<I", edc) + (b"\x00" * 8) + (b"\x00" * 276)


def _both_u16(val: int) -> bytes:
    return struct.pack("<H", val) + struct.pack(">H", val)


def _both_u32(val: int) -> bytes:
    return struct.pack("<I", val) + struct.pack(">I", val)


def _make_dir_record(extent_lba: int, data_len: int, raw_name: bytes, *, is_dir: bool = False) -> bytes:
    flags = 0x02 if is_dir else 0x00
    rec_len = 33 + len(raw_name) + (1 if len(raw_name) % 2 == 0 else 0)
    buf = bytearray(rec_len)
    buf[0] = rec_len
    buf[1] = 0
    buf[2:10] = _both_u32(extent_lba)
    buf[10:18] = _both_u32(data_len)
    buf[18:25] = bytes((96, 7, 19, 12, 0, 0, 0))
    buf[25] = flags
    buf[28:32] = _both_u16(1)
    buf[32] = len(raw_name)
    buf[33 : 33 + len(raw_name)] = raw_name
    return bytes(buf)


def _make_ip_bin(
    *,
    product: str = "MK-81070",
    version: str = "V1.003",
    release_date: str = "19970722",
    area: str = "U",
    title: str = "SYNTHETIC SATURN FIXTURE",
    first_read_size: int = 2048,
) -> bytes:
    buf = bytearray(b" " * SYSTEM_AREA_BYTES)
    buf[0x00:0x10] = b"SEGA SEGASATURN "
    buf[0x10:0x20] = b"SEGA TP T-143   "
    buf[0x20:0x2A] = product.ljust(10).encode("ascii")[:10]
    buf[0x2A:0x30] = version.ljust(6).encode("ascii")[:6]
    buf[0x30:0x38] = release_date.ljust(8).encode("ascii")[:8]
    buf[0x38:0x40] = b"CD-1/1  "
    buf[0x40:0x4A] = area.ljust(10).encode("ascii")[:10]
    buf[0x4A:0x50] = b"      "
    buf[0x50:0x60] = b"JT              "
    buf[0x60:0xD0] = title.ljust(112).encode("ascii")[:112]
    buf[0xD0:0xE0] = b"\x00" * 16
    buf[0xE0:0xF8] = struct.pack(">6I", 0x1000, 0, 0x06002000, 0x06001000, 0x06004000, first_read_size)
    buf[0x100:] = b"\xaa" * (SYSTEM_AREA_BYTES - 0x100)
    return bytes(buf)


def _make_sega_film(video_bytes: bytes = b"\x11" * 64, *, truncate_by: int = 0) -> bytes:
    fdsc = b"FDSC" + struct.pack(">I", 32) + b"cvid" + struct.pack(">IIBBBBH", 160, 320, 24, 2, 8, 0, 22050) + b"\x00" * 6
    stab_entry = struct.pack(">IIII", 0, len(video_bytes), 0, 1)
    stab = b"STAB" + struct.pack(">III", 16 + len(stab_entry), 30, 1) + stab_entry
    header_len = 16 + len(fdsc) + len(stab)
    header = b"FILM" + struct.pack(">I", header_len) + b"1.04" + b"\x00\x00\x00\x00" + fdsc + stab
    full = header + video_bytes
    return full[: len(full) - truncate_by] if truncate_by else full


def _build_synthetic_disc(
    root: Path,
    subdir: str,
    *,
    product: str = "MK-81070",
    version: str = "V1.003",
    area: str = "U",
    extra_unreferenced_nonzero: bool = False,
    corrupt_edc_lba: int | None = None,
    cdda_shift_samples: int = 0,
) -> str:
    d_dir = root / subdir
    d_dir.mkdir(parents=True, exist_ok=True)

    boot_code = b"\x09\x00\x09\x00" * 512  # 2048 bytes
    cpk_data = _make_sega_film(b"\x55" * 128)
    txt_data = b"COPYRIGHT SYNTHETIC TEST\r\n"

    # Layout:
    # 0..15: IP.BIN
    # 16: PVD
    # 17: VD Terminator
    # 18: Path Table L
    # 19: Path Table M
    # 20: Root Directory
    # 21: 0BOOT.BIN (2048 B)
    # 22: MOVIE.CPK
    # 23: COPY.TXT
    # 24: Zero padding (or unreferenced nonzero)
    total_blocks = 25
    sectors = [b"\x00" * 2048 for _ in range(total_blocks)]

    ip_bytes = _make_ip_bin(product=product, version=version, area=area, first_read_size=len(boot_code))
    for i in range(16):
        sectors[i] = ip_bytes[i * 2048 : (i + 1) * 2048]

    # Root directory at LBA 20
    dot = _make_dir_record(20, 2048, b"\x00", is_dir=True)
    dotdot = _make_dir_record(20, 2048, b"\x01", is_dir=True)
    r_boot = _make_dir_record(21, len(boot_code), b"0BOOT.BIN;1")
    r_cpk = _make_dir_record(22, len(cpk_data), b"MOVIE.CPK;1")
    r_txt = _make_dir_record(23, len(txt_data), b"COPY.TXT;1")
    root_sec = bytearray(2048)
    raw_dir = dot + dotdot + r_boot + r_cpk + r_txt
    root_sec[: len(raw_dir)] = raw_dir
    sectors[20] = bytes(root_sec)

    # Path tables (root entry: len_di=1, xar=0, extent=20, parent=1, name=0x00, pad=0x00)
    pt_l = bytearray(2048)
    pt_l[:10] = bytes((1, 0)) + struct.pack("<IH", 20, 1) + b"\x00\x00"
    pt_m = bytearray(2048)
    pt_m[:10] = bytes((1, 0)) + struct.pack(">IH", 20, 1) + b"\x00\x00"
    sectors[18] = bytes(pt_l)
    sectors[19] = bytes(pt_m)

    # PVD at LBA 16
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"SEGA SEGASATURN".ljust(32)
    pvd[40:72] = f"SYNTH_{area}".encode("ascii").ljust(32)
    pvd[80:88] = _both_u32(total_blocks)
    pvd[120:124] = _both_u16(1)
    pvd[124:128] = _both_u16(1)
    pvd[128:132] = _both_u16(2048)
    pvd[132:140] = _both_u32(10)
    pvd[140:144] = struct.pack("<I", 18)
    pvd[148:152] = struct.pack(">I", 19)
    pvd[156 : 156 + len(dot)] = dot
    pvd[881] = 1
    sectors[16] = bytes(pvd)

    # Terminator at LBA 17
    term = bytearray(2048)
    term[0] = 255
    term[1:6] = b"CD001"
    term[6] = 1
    sectors[17] = bytes(term)

    sectors[21] = boot_code
    sectors[22] = cpk_data.ljust(2048, b"\x00")
    sectors[23] = txt_data.ljust(2048, b"\x00")
    if extra_unreferenced_nonzero:
        sectors[24] = b"HIDDEN_LBA_DATA!" + b"\x7f" * 2032

    raw_track1 = bytearray()
    for lba, sec in enumerate(sectors):
        wrapped = bytearray(_wrap_mode1_sector(lba, sec))
        if corrupt_edc_lba == lba:
            wrapped[2064] ^= 0xFF
        raw_track1.extend(wrapped)

    t1_path = d_dir / "track01.bin"
    t1_path.write_bytes(bytes(raw_track1))

    # Track 02 CD-DA: 4 sectors (1 pregap + 3 active) with optional stereo sample shift
    pcm_core = b"".join(struct.pack("<hh", (i * 37) % 30000 - 15000, (i * 53) % 30000 - 15000) for i in range(1500))
    total_cdda_bytes = 6 * 2352
    pad_left = 2352 + cdda_shift_samples * 4
    pad_right = total_cdda_bytes - pad_left - len(pcm_core)
    t2_bytes = (b"\x00" * pad_left) + pcm_core + (b"\x00" * pad_right)
    (d_dir / "track02.bin").write_bytes(t2_bytes)

    cue_text = (
        'FILE "track01.bin" BINARY\n'
        "  TRACK 01 MODE1/2352\n"
        "    INDEX 01 00:00:00\n"
        'FILE "track02.bin" BINARY\n'
        "  TRACK 02 AUDIO\n"
        "    INDEX 00 00:00:00\n"
        "    INDEX 01 00:00:01\n"
    )
    cue_path = d_dir / "disc.cue"
    cue_path.write_text(cue_text, encoding="utf-8")
    return f"{subdir}/disc.cue"


class SaturnDiscSyntheticTests(unittest.TestCase):
    def test_valid_disc_100_percent_accounting_and_cli_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saturn-disc-test-") as tmp:
            root = Path(tmp)
            cue_usa = _build_synthetic_disc(root, "usa", product="MK-81070", version="V1.003", area="U")
            cue_jp = _build_synthetic_disc(
                root,
                "jp",
                product="T-14302G",
                version="V1.000",
                area="J",
                extra_unreferenced_nonzero=True,
                cdda_shift_samples=12,
            )

            priv_usa = root / "out" / "usa.full.json"
            sum_usa = root / "out" / "usa.summary.json"
            rc = cli_main(
                [
                    "inspect",
                    "--root",
                    str(root),
                    "--cue",
                    cue_usa,
                    "--private-out",
                    str(priv_usa),
                    "--summary-out",
                    str(sum_usa),
                ]
            )
            self.assertEqual(rc, 0)

            priv_jp = root / "out" / "jp.full.json"
            sum_jp = root / "out" / "jp.summary.json"
            self.assertEqual(
                cli_main(
                    [
                        "inspect",
                        "--root",
                        str(root),
                        "--cue",
                        cue_jp,
                        "--private-out",
                        str(priv_jp),
                        "--summary-out",
                        str(sum_jp),
                    ]
                ),
                0,
            )

            usa_doc = json.loads(sum_usa.read_text(encoding="utf-8"))
            self.assertEqual(usa_doc["accounting"]["track01_total_logical_blocks"], 25)
            self.assertEqual(usa_doc["accounting"]["track01_accounted_logical_blocks"], 25)
            self.assertEqual(usa_doc["accounting"]["track01_unaccounted_logical_blocks"], 0)
            self.assertEqual(usa_doc["track01_edc"]["edc_checked_sectors"], 25)
            self.assertEqual(len(usa_doc["accounting"]["unreferenced_nonzero_intervals"]), 0)

            jp_doc = json.loads(sum_jp.read_text(encoding="utf-8"))
            self.assertEqual(len(jp_doc["accounting"]["unreferenced_nonzero_intervals"]), 1)
            self.assertEqual(jp_doc["accounting"]["unreferenced_nonzero_intervals"][0]["lba_start"], 24)

            diff_out = root / "out" / "diff.json"
            self.assertEqual(
                cli_main(
                    [
                        "diff",
                        "--left",
                        str(sum_usa),
                        "--right",
                        str(sum_jp),
                        "--left-root",
                        str(root),
                        "--right-root",
                        str(root),
                        "--output",
                        str(diff_out),
                    ]
                ),
                0,
            )
            diff_doc = json.loads(diff_out.read_text(encoding="utf-8"))
            self.assertEqual(diff_doc["iso9660_summary"]["identical_path_and_sha256_count"], 3)
            cdda_align = diff_doc["track_comparison"][1]["cdda_alignment"]
            self.assertTrue(cdda_align["sample_shifted_pcm_match"])
            self.assertEqual(cdda_align["stereo_sample_shift_b_minus_a"], 12)

            self.assertEqual(
                cli_main(["verify", "--summary", str(sum_usa), "--summary", str(sum_jp), "--diff", str(diff_out)]),
                0,
            )
            self.assertEqual(
                cli_main(["diff", "--left", str(sum_usa), "--right", str(sum_usa), "--output", str(root / "out" / "self.json")]),
                1,
            )

    def test_corrupted_mode1_edc_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saturn-disc-edc-") as tmp:
            root = Path(tmp)
            cue_rel = _build_synthetic_disc(root, "bad", corrupt_edc_lba=21)
            cue = parse_cue_sheet(root, cue_rel)
            with self.assertRaisesRegex(DiscError, "Mode 1 EDC mismatch"):
                inspect_disc(cue)

    def test_symlink_and_traversal_in_cue_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saturn-disc-sec-") as tmp:
            root = Path(tmp)
            outside = root.parent / f"outside-{root.name}.bin"
            outside.write_bytes(b"\x00" * 2352)
            try:
                (root / "escape.cue").write_text(
                    f'FILE "../{outside.name}" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n',
                    encoding="utf-8",
                )
                with self.assertRaises(DiscError):
                    parse_cue_sheet(root, "escape.cue")

                link = root / "sym.bin"
                link.symlink_to(outside)
                (root / "sym.cue").write_text(
                    'FILE "sym.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n',
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(DiscError, "Symlink"):
                    parse_cue_sheet(root, "sym.cue")
            finally:
                outside.unlink(missing_ok=True)

    def test_invalid_ip_bin_magic_and_area_symbol_rejected(self) -> None:
        bad_magic = bytearray(_make_ip_bin())
        bad_magic[:4] = b"NOPE"
        with self.assertRaisesRegex(DiscError, "Invalid Sega Saturn hardware ID"):
            parse_ip_bin(bytes(bad_magic))

        bad_area = _make_ip_bin(area="Z")
        with self.assertRaisesRegex(DiscError, "unrecognised area symbol"):
            parse_ip_bin(bad_area)

    def test_classifiers_detect_truncated_cpk_m68k_scsp_map_and_containers(self) -> None:
        trunc_cpk = _make_sega_film(b"\x22" * 256, truncate_by=32)
        res_cpk = classify_disc_file("BROKEN.CPK", trunc_cpk)
        self.assertEqual(res_cpk["detected_format"], "sega_film_cpk")
        self.assertFalse(res_cpk["valid"])

        # Synthetic 68000 sound driver vector table
        vectors = [0x004000, 0x000400] + [0x000420] * 30
        m68k_bin = struct.pack(">32I", *vectors) + (b"\x4e\x75" * 450)
        res_drv = classify_disc_file("SDDRVS.TSK", m68k_bin)
        self.assertEqual(res_drv["detected_format"], "saturn_m68k_sound_driver")
        self.assertEqual(res_drv["accounting_class"], "executable")

        # Synthetic SCSP sound area map (3 entries + 0xFF terminator)
        scsp_map = (
            struct.pack(">II", (0 << 28) | 0x008000, 0x010000)
            + struct.pack(">II", (1 << 28) | 0x018000, 0x020000)
            + struct.pack(">II", (2 << 28) | 0x038000, 0x004000)
            + b"\xff\x00\x00\x00"
        )
        res_map = classify_disc_file("BOOTSND.MAP", scsp_map)
        self.assertEqual(res_map["detected_format"], "saturn_scsp_area_map")
        self.assertEqual(res_map["entry_count"], 3)

        # Synthetic BE count + (offset, length) container
        e1, e2, e3 = b"AAAA" * 16, b"BBBB" * 20, b"CCCC" * 12
        hdr_len = 4 + 3 * 8
        pack = (
            struct.pack(">I", 3)
            + struct.pack(">II", hdr_len, len(e1))
            + struct.pack(">II", hdr_len + len(e1), len(e2))
            + struct.pack(">II", hdr_len + len(e1) + len(e2), len(e3))
            + e1
            + e2
            + e3
        )
        res_pack = classify_disc_file("DATA.BIN", pack)
        self.assertEqual(res_pack["detected_format"], "binary_container_candidate")
        self.assertEqual(res_pack["container_hypothesis"]["scheme"], "be_count_offset_length_pairs")

        # Synthetic Hudson Low-WRAM bank archive (4 banks across 64 KiB)
        banks_raw = bytearray(65536)
        for idx, (sec, bname, base) in enumerate(
            ((0, b"s_init", 0x00254000), (8, b"base1", 0x00200000), (16, b"normal1", 0x00254000), (24, b"battle1", 0x00254000))
        ):
            off = sec * 2048
            struct.pack_into(">I", banks_raw, off + 0x00, base + 0x34)
            struct.pack_into(">I", banks_raw, off + 0x28, base + 0x1800)
            banks_raw[off + 0x2C : off + 0x34] = bname.ljust(8, b"\xff")
            banks_raw[off + 0x40 : off + 0x80] = bytes([idx + 1]) * 64
        res_hudson = classify_disc_file("BOMSS/PROGRAM.BIN", bytes(banks_raw))
        self.assertEqual(res_hudson["detected_format"], "hudson_lwr_bank_archive")
        self.assertEqual(res_hudson["bank_count"], 4)
        self.assertEqual(res_hudson["core_and_sound_bank_names"], ["s_init", "base1", "normal1", "battle1"])

        # Synthetic SH-2 trampoline prologue
        sh2_bin = struct.pack(">4HI", 0xD301, 0x432B, 0x0009, 0x0009, 0x06006174) + (b"\x00\x09" * 32)
        self.assertEqual(classify_disc_file("0KRNL.BIN", sh2_bin)["detected_format"], "saturn_sh2_executable")

        # DOS ^Z (0x1a) terminated ASCII text vs binary control-byte width table
        self.assertEqual(
            classify_disc_file("BOMSS_CP.TXT", b"Copyright by HUDSON\r\n\x1a")["detected_format"],
            "ascii_text",
        )
        self.assertEqual(
            classify_disc_file("LUCIB.WDT", b"\x29\x0b\x20" + b"\x21" * 64)["detected_format"],
            "unclassified_binary",
        )

    def test_cdda_shift_detector_distinguishes_shifted_vs_different_audio(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saturn-cdda-") as tmp:
            p_a = Path(tmp) / "a.bin"
            p_b = Path(tmp) / "b.bin"
            p_c = Path(tmp) / "c.bin"
            body = b"".join(struct.pack("<hh", (i * 97) % 20000 - 10000, (i * 31) % 20000 - 10000) for i in range(3000))
            p_a.write_bytes((b"\x00" * 400) + body + (b"\x00" * 400))
            p_b.write_bytes((b"\x00" * 448) + body + (b"\x00" * 352))
            p_c.write_bytes((b"\x00" * 448) + body[:6000] + (b"\x11\x22\x33\x44" * 1500) + (b"\x00" * 352))

            res_ab = detect_cdda_sample_shift(p_a, p_b)
            self.assertTrue(res_ab["sample_shifted_pcm_match"])
            self.assertEqual(res_ab["stereo_sample_shift_b_minus_a"], 12)

            res_ac = detect_cdda_sample_shift(p_a, p_c)
            self.assertFalse(res_ac["sample_shifted_pcm_match"])


    def test_cli_help_renders_for_every_subcommand(self) -> None:
        # Regression: an unescaped '%' in argparse help text crashed `--help`.
        import contextlib
        import io

        for argv in (["--help"], ["inspect", "--help"], ["diff", "--help"], ["verify", "--help"]):
            with self.subTest(argv=argv), contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as ctx:
                    cli_main(argv)
                self.assertEqual(ctx.exception.code, 0)
                self.assertIn("usage:", out.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
