# Real Saturn media and pinned core: first #462 increment

Base `957491ec44cec8b4c14e6bcfc461ed9cca3eb0f8`. Issue #462 is the Codex media
slice of #26; #27 supplies the actual frontend, applied settings and repeatability.
Gemini owns the independent #463/#464 asset/research audit. No original disc, BIOS,
capture, save or memory bytes are committed here.

## Actual inputs

The supplied `/home/dev/Sega-Saturn-BIOS/` root and both specified CUE files are
readable regular inputs. Each CUE actually references **30 BINARY track files**.
Existing inventory tooling hashed both extracted directories; ZIP backups were
not extracted or overwritten. Eleven top-level BIOS candidates were fingerprinted.

| Region | IP-header product | Revision | Area | Observed title |
| --- | --- | --- | --- | --- |
| USA | MK-81070 | V1.003 | U | SATURN BOMBERMAN |
| Japan | T-14302G | V1.000 | J | BOMBERMAN SS |

These fields come from TRACK 01, INDEX 01, MODE1/2352 user sector 0, not filenames.
The parser follows product/version offset 0x20/16 bytes, area 0x40/16 and name
0x60/112 in [pinned core disc.c](https://github.com/libretro/beetle-saturn-libretro/blob/01bc063fdd0fb5fc208850c9ecc658834df762ab/disc.c).
The filename's `1S` label is not independently certified as a pressing identity.
Header identity does not establish full-disc integrity or original-game execution.

Firmware matches the [official compatibility catalogue](https://docs.libretro.com/library/beetle_saturn/#bios):

| Region | Expected frontend name | MD5 lookup | SHA-256 identity |
| --- | --- | --- | --- |
| USA/EU | mpr-17933.bin | 3240872c70984b6cbfda1586cab68dbe | 96e106f740ab448cf89f0dd49dfbac7fe5391cb6bd6e14ad5e3061c13330266f |
| Japan | sega_101.bin | 85ec9ca47d8f6807718151cbcca8b964 | dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac |

Two supplied names match the same USA/EU bytes; both aliases are retained in the
metadata. Japan has one matching candidate. Selection is by bytes, with MD5 only
the catalogue lookup. Other candidates remain recorded without invented compatibility.

## Core build and actual ABI smoke

Public Beetle Saturn source commit `01bc063fdd0fb5fc208850c9ecc658834df762ab`, tree
`2522acca8b2b48394ff579e89f50717c4ad8b230`, was built on Debian 13 x86_64 using GCC
14.2.0 and GNU Make 4.4.1:

```sh
make -j2 platform=unix LTO=0 HAVE_OPENGL=0 HAVE_CHD=1
```

One heavy job, 600-second wall bound and 2 GiB per-process address-space limit.
Build exited 0 in 308.188 seconds. Binary `mednafen_saturn_libretro.so` is 9,329,088
bytes, SHA-256 `c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e`.
Its existing GPL-2.0 upstream notices are preserved privately; no binary or imported
core source is added to Neptune or relicensed under its Apache-2.0 licence.

Actual `ctypes.CDLL`, `retro_api_version` and `retro_get_system_info` calls return
API 1, Beetle Saturn v1.32.1, `cue|ccd|chd|toc|m3u|zip`, `need_fullpath=true` and
`block_extract=true`. This is an ABI/library-load smoke check only. `retro_init`,
original boot and effective option/RTC behavior have not been established yet.

## Reproducible verification

```sh
python3 tools/saturn_lab/cli.py inventory "$INPUTS/Saturn-Bomberman-EN" --output "$EVIDENCE/usa.inventory.json"
python3 tools/saturn_lab/cli.py inventory "$INPUTS/Saturn-Bomberman-JA" --output "$EVIDENCE/japan.inventory.json"
python3 tools/saturn_lab/media.py inspect --root "$INPUTS" --disc 'Saturn-Bomberman-EN/Saturn Bomberman (USA) (1S).cue' --region usa --output "$EVIDENCE/usa.media.json"
python3 tools/saturn_lab/media.py inspect --root "$INPUTS" --disc 'Saturn-Bomberman-JA/Saturn Bomberman (Japan).cue' --region japan --output "$EVIDENCE/japan.media.json"
python3 tools/saturn_lab/media.py verify --root "$INPUTS" --report "$EVIDENCE/usa.media.json"
python3 tools/saturn_lab/media.py verify --root "$INPUTS" --report "$EVIDENCE/japan.media.json"
python3 tools/saturn_lab/check.py
```

Each region report re-verifies 42 files: its CUE/30 tracks plus all eleven BIOS
candidates. Repeated original verification passes. In a separate ordinary USA copy:

- Unmodified control: exit 0.
- One audio-track byte changed: exit 1, report differs.
- Referenced track removed temporarily: exit 1, missing regular file.
- Japanese BIOS explicitly selected for USA: exit 1, expected firmware mismatch.
- Restored copy and both original region sets: exit 0.

The log/command ledger is `/home/dev/neptune-research-private/462/media-negative-checks.json`;
all original bytes remain unchanged. No complete emulator-lock claim is derived
from these media-report negatives. The lab suite now passes **39 synthetic tooling
tests**, including eleven new header, unsafe-path, firmware, tampering and report
cases. They do not establish original-game compatibility or reference fidelity.

## Remaining work and ownership

The exact remaining component is a real noninteractive frontend with applied
settings, fixed effective RTC/save/options and controller topology. #27 implements
that component; then complete `cli.py lock/verify` manifests must bind real core,
settings and inputs, with frontend identity recorded and validated too. No dummy
frontend or placeholder settings are used here. #462 stays open for those lock
acceptance items; #26 also retains Gemini's asset scope.

After this tested increment is accepted, Codex continues directly into #27. It
must boot real media, step inputs, save/restore and repeat the recorded scenario
in at least three fresh processes before claiming that acceptance. Video callbacks
alone are not VDP1/VDP2 extraction hooks. Gemini consumes versioned bridge outputs
instead of competing changes to the Codex-owned frontend.

This increment does not certify emulator accuracy, whole-game coverage, extraction,
campaign/battle parity, public distribution rights, backups or a running factory.
No infrastructure purchase or paid fallback was enabled. One earlier bounded
Gemini invocation used 11,781 tokens and produced no audit artifact; it is terminal
and was not resumed after the operator launched Gemini independently. Dollar and
account-wide spend remain unknown.
