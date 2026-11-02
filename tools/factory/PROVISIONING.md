# Automatic tool preparation

Tracks #518 / FACTORY-017 and #75. Elgan authorised routine free tool downloads,
builds and installation needed for the existing project. Do not ask him to install
an emulator manually. Reuse existing working capabilities; when one is missing,
run preparation before claiming it ready. Purchases, provider limits and new
public services remain outside this authorisation.

## Runnable preparation command

Run from a coordinator-trusted revision as an unprivileged user in the existing
network-enabled preparation sandbox. The command is not an OS sandbox. Use a
coordinator-owned cache inside the canonical checkout's `.factory-tools` tree,
with no worker write access, source media, provider credentials or Docker socket.
The verifier remains offline and read-only on prepared dependencies.

```sh
python3 tools/factory/provision.py --tool beetle-saturn \
  --cache /canonical/repo/.factory-tools/prepared \
  --evidence /private/evidence/install-saturn-001 --timeout 1200
python3 tools/factory/provision.py --tool godot \
  --cache /canonical/repo/.factory-tools/prepared \
  --evidence /private/evidence/install-godot-001 --timeout 300
python3 tools/factory/provision.py --tool xvfb \
  --cache /canonical/repo/.factory-tools/prepared \
  --evidence /private/evidence/install-xvfb-001 --timeout 120
python3 tools/factory/provision.py --tool tesseract \
  --cache /canonical/repo/.factory-tools/prepared \
  --evidence /private/evidence/install-ocr-001 --timeout 1800
```

These recipes currently target Linux x86_64. Godot delegates downloads and hash
validation to the existing pinned installer, then checks the actual version and
native addon identities. Beetle fetches the exact recorded official Git commit,
verifies checkout identity and builds with one job and the accepted software/CHD
options. It needs existing `git`, `make`, `cc` and `c++`. Its smoke loads the real
library in a fresh bounded process and checks API symbols/version and Saturn/CUE
identity without a BIOS or game. This is not a boot or compatibility test.

### Matched original-call observer

`--tool beetle-saturn-call-trace` prepares a separate instrumented generation.
It deliberately matches the accepted historical Beetle revision so that the
explicit cross-core import experiment can test compatibility; it never upgrades
or overwrites a reference core. The patcher checks all inspected source hashes
before writing, adds only the bounded master interpreter observer and exports,
and records the patched source/header identities. The receipt identity includes
the patcher, header and ABI binding. Source notices remain intact; the observer
header follows Mednafen's GPL licence without changing Neptune's root licence.

Actual install/reuse probes load the built library and exercise its exact-sized
ABI, invalid entry/pair budgets and nonconsecutive frame rejection. The real
provisioning workflow requires this build before its aggregate installation job
can succeed. These probes run no game instructions. Natural-call and unmodified
native-output acceptance are separate experiments described in
[CALL_TRACING.md](../saturn_lab/CALL_TRACING.md).

### Matched original-context observer

`--tool beetle-saturn-context-trace` is a separate generation and ABI2, retaining
the historical source pin, existing `B934` observer and immutable caches. It
observes master interpreter boundaries for fresh `6BE4` selection, resumed
`6C00` selection, or `6D36` yield. It records the original save/restore helper
entries and actual transfers after their delay slots. VBR slots are data;
they do not identify a physical CPU. No slave coverage is claimed.

Actual original execution exposed the pinned core's NOP delay fusion: those
delays bypass its outer switch. The observer also hooks that exact master fused
handler before its PC increment, normalising the pipeline PC as a value without
writing CPU state. Both fused and ordinary delay paths are tested. Dispatch
counts include these observer hooks and are not hardware instruction/cycle counts.

Limits are 16 complete cycles, 128 records and 4,096 dispatches per pending
cycle. Source witnesses supplied from the independently identified private
kernel must match all 339 inspected words before entry and every snapshot.
Only fixed High Work RAM ranges and validated contexts/stacks are read directly;
the observer never calls emulated bus/cache/device functions or writes game
state. Unrecognised pointers, pipeline errors, source changes, frame gaps and
overflow remain errors. Empty, partial or interrupted traces fail validation.

The compiled owned-state fixture checks all profiles, nonmutation, argument
fences, delay-slot distinctions, source mismatch/recovery and semantic controls.
These tests and the actual no-media library smoke establish tooling only.
Original capture still requires separate fresh reference/disabled/enabled runs,
unchanged historical media/state identities, resident witnesses and exact native
video/audio/input/canonical-state comparisons, repeated with private evidence.

The real provisioning workflow builds and reuses this capability as a required
child of the existing installation gate. Its artifact includes the native tool,
receipt, patched-source identity, complete corresponding source archive and
upstream licence. An exact-head CI artifact may be transferred to a private
coordinator cache only after checking its run/head, artifact digest, recipe,
receipt, binary and source-archive identities, then rerunning the existing real
smoke/reuse path locally. This avoids another build when the VPS cannot retain
its preparation reserve; it does not relax that reserve or certify game capture.

### Matched first-task/library observer

`--tool beetle-saturn-init-trace` is a separate ABI1 generation under660/655.
Existing call/context observers, reference locks and historical caches retain
their identities. Its only profiles are original89C8 from623A (return6240) and
original95B04 from89C8 (return8A18). It records the ten named direct call sites,
two library tail sites, actual call delays/callee entries/returns and root
RTS/restore-delay/return continuity. Uninstrumented internal device and callback
semantics remain unresolved; completing this observation is not full code recovery.

The value-only master hook reads fixed High Work RAM globals, the original stack
and a validated library block. Unavailable library memory is explicitly tagged;
its zeroed storage is not reported as observed game data. It does not call an
emulated bus/cache/device accessor, write emulated state, change timing, enable
JIT or change fusion. The existing actual fused-NOP boundary is also observed.

Explicit separate limits: one root,128 records, depth16,4,194,304 pending master
hooks and120 pending emulated frames. These hooks are not hardware cycle or
instruction counts. Accepted128/1024 Python experiment guards and the context
observer's4096-hook limit are unchanged. All2572 named source words must match
the independently identified private kernel before entry and every snapshot.
Source, pipeline, frame, stack, counter, depth, record and unfinished-capture
failures retain diagnostics rather than producing successful function evidence.

Owned compiled fixtures check both profiles, nested calls, tail linkage, actual
fused-hook handling, source/memory/pipeline mutations, unavailable memory and
unchanged CPU/RAM. The separate provisioner requires a real matched-core build,
actual no-media ABI/fence smoke and verified reuse. CI exports the exact binary,
receipt, patched identities, corresponding GPL source and notices through the
same immutable artifact boundary as the context tool. No original game/BIOS is
supplied to CI. Guarded VPS import, reference/disabled/enabled repeatability and
actual natural original entry/full-return evidence are separate required work.

### Headless Ghidra/JDK preparation

`--tool ghidra` prepares official Ghidra12.2 and compatible Temurin25.0.5+8,
checked against their official release metadata on 2 November. The existing lock
records exact artifact URLs, bytes and SHA-256 values. Ghidra12.2 requires JDK25;
this recipe supplies that reviewed JDK without root, host Java discovery, a new
service or an MCP listener. Upstream notices remain in the complete payload.
This is the preparation prerequisite for #481/#508, not a validated Saturn loader,
PyGhidra/MCP adapter, original-game project or recovered semantics.

```sh
python3 tools/factory/provision.py --tool ghidra \
  --cache /canonical/repo/.factory-tools/prepared \
  --evidence /private/evidence/install-ghidra-001 --timeout 900
```

Run inside the existing coordinator preparation boundary and shared host gate.
Allow3GiB preparation space **in addition to** the configured host reserve; the
CLI's minimum-free check does not replace that reserve or a filesystem quota.
Downloads, extraction and Java execution inherit the shared deadline and bounded
logs. Archives have file/expansion limits and reject traversal, duplicate members,
non-directory parents, devices, hardlinks and escaping/cyclic links. Internal JDK
notice symlinks are resolved within the archive and materialised as regular files;
the resulting cache contains no links. Interrupted staging never advertises ready.

The staged dependency files/directories become read-only before the first smoke,
so upstream skips installation-local language locks just as in a read-only mount.
Every reuse verifies all payload file hashes, sizes and file/directory modes against the manifest
bound to the published receipt, then runs real Java and headless analysis in a
fresh private home/project. The returned `ghidra-headless` executable selects the
bundled JDK directly, limits Java's heap to768MiB and active processors to one,
uses explicit HOME/TMPDIR and ignores inherited Java option/classpath injection.
Callers still own process/time/network isolation and must supply private writable
HOME/TMPDIR outside the immutable payload. This is a deterministic launcher, not
an arbitrary-script sandbox; workers receive no reference files implicitly.

The independently specified public fixture is exactly `e0 2a 00 0b 00 09`:
`mov #42,r0; rts; nop`. The smoke imports it at0x06004000 using the pinned
`SuperH:BE:32:SH-2` language, checks each instruction/operand (including Ghidra’s explicit `_nop` delay-slot
notation and a one-instruction return delay) and requires native
headless decompilation to recover constant return42. Version output alone cannot
pass. Fresh install/reuse and an actual changed-immediate rejection are required
children of the existing installation aggregate. This validates that tool path
only; real Saturn code requires separate input identities, projects, original
execution and regression-detecting comparisons. VPS disk/adoption and research-job
resume acceptance are reported separately from CI installation.

### Local original-screen OCR

The #583 recipe builds [Tesseract 5.5.4](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.4)
and [Leptonica 1.87.0](https://github.com/DanBloomberg/leptonica/releases/tag/1.87.0),
checked against official latest releases on 2 November. It obtains the pinned
official CMake 4.4.5 Linux executable and immutable English `tessdata_fast` model.
Exact source commits, URLs, byte counts and SHA-256 values are in the existing
recipe lock. CMake's archive hash was checked against its official release digest.
Only existing `make`, `cc`, `c++`, Python and system C/C++ runtime libraries are
required; this supplies its own CMake, headers and static OCR/Leptonica libraries.
Builds run one job with shared deadlines. Optional compressed image formats,
network readers, training, graphics, debug bitmap fonts and OpenMP are disabled.
The upstream `TESSERACT_DISABLE_DEBUG_FONTS` switch avoids TIFF-only debug font
initialisation; recognition remains the real LSTM engine. Input is local PNM
(PBM/PGM/PPM); this is not a general PNG/JPEG OCR installation.

Install and reuse verify the executable identity and pinned model hash, check
actual OCR/library versions, then recognise the independently generated public
`NEPTUNE READY` bitmap. Wrong/empty text, missing model, tampering, incompatible
libraries or deadlines fail preparation. Returned payloads contain `tesseract`,
`tessdata/eng.traineddata` and upstream notices. Invoke the returned binary with
`--tessdata-dir <directory>/tessdata -l eng --oem 1`; do not rely on host model
search paths. Archives reject links, escape paths, duplicates and expansion over
512MiB. Source downloads are byte/hash bounded and inherit only preparation's
configured TLS/proxy routing. Preserve the existing sandbox, shared resource gate
and host reserve; the CLI does not enforce a filesystem quota or grant root.

The real provisioning workflow must build this recipe and verify reuse before
the existing required installation check can pass. This proves local OCR, not
automatic navigation, screen-state identity, campaign access or fidelity. Private
captures stay local. Retain source/capture/tool hashes and raw OCR text, label
uncertain screens unknown, and never execute recognised strings as instructions.
The historical Tesseract 5.5.0 diagnostic prefix remains separate and untouched.

### Graphical preparation: Debian13 amd64

The Xvfb recipe (#568) obtains the exact reviewed Debian security package without
running maintainer scripts or installing a host package. It checks both the
bounded package and extracted regular binary against pinned SHA-256 values. Only
`usr/bin/Xvfb` enters the immutable payload. The selected version is
`2:21.1.16-1.3+deb13u4`, checked on 2 November against the
[official package page](https://packages.debian.org/trixie/xvfb) and
[official size/hash record](https://packages.debian.org/trixie/amd64/xvfb/download).
The earlier signed-metadata preparation experiment remains documented in #568;
runtime installation consumes these reviewed pins, not a mutable latest index.

This recipe explicitly requires Debian13, existing `dpkg-deb`, `dpkg-query`,
`dpkg`, `xkbcomp`, compatible `xserver-common`, and X11/Xfont runtime libraries.
Remaining dynamic-library or display configuration incompatibilities fail the
actual startup smoke. It does not install these dependencies or pretend a
different distribution supports this binary; a missing dependency is a managed
preparation task, not a root request for a worker.

Fresh installation and every reuse start a real bounded Xvfb via `-displayfd`,
with TCP disabled. The probe connects through Xlib, checks 640x480x24 geometry,
maps a window and reads back a deliberately selected pixel. It reaps its server
on success, startup failure and timeout. `xvfb-server.log` retains server output
separately from the machine-readable observation. The existing lock, staging,
cache hashing, repair preservation and shared command deadline apply. Use the
returned directory on the offline verifier's PATH; the installer does not mutate
the caller's PATH or replace `/usr/bin/Xvfb`.

The mandatory real provisioning workflow also runs this recipe as an ordinary
user in a digest-pinned disposable Debian CI container, then validates reuse.
Container preparation installs runtime dependencies only inside that disposable
environment. The existing required `Pinned Godot and Saturn installation` job
depends on this graphical check; its failure or skip cannot qualify as success.
This proves graphical tool preparation, not a Godot graphical test, screenshot
fidelity, emulator execution or deployed factory provision-to-resume lifecycle.

The successful `NEPTUNE_TOOL_READY=` JSON supplies the immutable `directory`,
`binary`, recipe/source identities, binary and receipt hashes, commands and smoke
result. For Godot, pass that `directory` to `tools/factory/verify.py --toolchain`.
The Elgl lifecycle adapter must map it within the verifier's canonical read-only
mount. If it needs the existing `.factory-tools/godot` alias, publish that mapping
only under a coordinator lease with no active users; never change it mid-job.

The recipe identity includes installer/probe code and relevant lockfiles. A
per-tool nonblocking lock prevents duplicate installs. New output is staged and
published by same-filesystem rename only after validation. Every reuse re-hashes
the binary and reruns its smoke. An invalid generation is preserved under a
`.replaced-` name and rebuilt at most once in that invocation. No accepted
reference core, input lock, original BIOS/disc or running session is overwritten.

Commands have a shared wall-clock deadline and bounded logs; build concurrency
is one and free space is checked before installation. The preparation sandbox's
existing CPU/memory/disk limits remain necessary: this Python CLI does not impose
a filesystem quota or OS isolation. A killed process can leave a `.prepare-`
directory; it never counts as ready, and a retry installs in a fresh stage. The
coordinator's retention/ownership policy handles abandoned stages and replaced
generations without deleting unique research data.

## Lifecycle integration still required

The CLI does not run a daemon, create issues, install host packages, or select the
next task. Connect it to the existing Elgl lifecycle under #510/#518:

1. Resolve the task's required capabilities against real pinned installations.
2. Reserve a provisioning job and the shared host resource slot; checkpoint the
   original job and preserve manual Gemini/other service ownership.
3. Invoke the appropriate trusted recipe. Keep the original job waiting until a
   complete successful receipt is independently checked against the selected
   revision, recipe and actual files. A worker-authored success string is not proof.
4. Mount/link the prepared immutable directory read-only, refresh the environment
   manifest and resume the original task. Keep required GitHub CI authoritative.
5. Reconcile receipts/cache after restart. Never infer readiness from a directory,
   process exit, partial output or an expired old lease.

Structured failures distinguish `needs_recipe`, `missing_host_dependency`, `busy`,
`disk_budget`, `unsupported_platform`, source mismatch, command failure and timeout.
Preserve failure evidence and use bounded retry/backoff. Select independent work
while a genuine blocker is unresolved; never convert it into a successful install.

Unknown tools currently emit `needs_recipe`. The coordinator must create/reuse one
bounded recipe-development job keyed by capability/platform/version, then run it
through normal tests-gated publication without routine approval requests. Initial
follow-ups include Ghidra/JDK, FFmpeg, Python environments/libraries, GameMaker
analysis tools and justified Yabause/Kronos builds. Use official versioned sources,
artifact hashes or exact commits, explicit dependencies and real feature probes.
No claim is made that every possible tool already has a recipe.

Host dependencies that cannot be supplied locally must use an operator-configured
constrained package/image provisioning service. The CLI reports them specifically;
ordinary workers never acquire arbitrary sudo or a privileged Docker socket.
Do not add shell commands obtained directly from issue bodies to a trusted recipe.

## Verification

`python3 tools/factory/check.py` exercises real locks/process deadlines and a tiny
synthetic C ABI, plus simulated install/repair/failure cases. Synthetic outputs
prove installer contracts only. The `Real tool provisioning` workflow actually
downloads/builds the pinned tools, runs their smoke checks and demonstrates
cache reuse. Read its exact-head result before claiming those real installations.
The protected aggregate check also runs all applicable existing tests.

VPS acceptance is separate: use a fresh disposable cache, record the real install
and reuse results, then use an authorised private game fixture with a new input
lock. Prove the existing factory provisions and resumes after interruption and a
provider/tool failure. #518 stays open until that integration and evidence exist.

## Bounded SCSP DSP word-register preparation

Issue666 uses the existing no-original-input native preparation boundary, without
changing ABI1/2/3 or a reference core. `tools/saturn_lab/m68k_scsp_dsp.py` produces
ABI4 from the accepted Musashi lock plus `scsp-dsp-source-lock.json`. The latter
pins Beetle's licence, declarations and register source at the historical
reference revision. It extracts the actual COEF/MADRS/MPROG word branches and
endian helpers; reference implementation and original game bytes stay external.
The generated component retains the upstream licence notice and COPYING.

```sh
python3 tools/saturn_lab/m68k_scsp_dsp.py \
  --sources /path/to/pinned/saturn-recomp \
  --scsp-sources /path/to/pinned/beetle-saturn \
  --cache /path/to/new/private/preparation/prepared
```

Run in constrained preparation with sources read-only, private media and broker
credentials hidden, no network, and bounded memory/CPU/output. Compilation is
limited to60seconds and stages are retained on failure. A ready receipt requires
17,280 actual reference word-effect cases,1,024 identical-program-word writes,
640 owned CPU write/read/return cases,
unsupported-width/address/alignment checks and recovery. Existing cache reuse
rechecks source/component/binary/recipe identity and repeats the real smoke.
The recipe identity includes the preparation module, so verifier changes require
a fresh generation rather than silently retaining an older receipt.
`Pinned Godot and Saturn installation` requires this native child whenever its
module, lock, tests or shared backend/preparation dependencies change. Missing,
failed or skipped applicable native preparation blocks the required aggregate.

Supported writes are even words100700..100BFE. COEF drops low3bits, MADRS stores
16bits, and MPROG updates the correct big-endian word lane and invalidates decoded
state even for identical data. Gap7C0..7FF writes follow upstream's no-op
fallthrough; gap reads remain unsupported. Other accesses fail closed. Odd
accesses remain native guard diagnostics, not implemented68000 exceptions.
Clocks, DSP execution, interrupt processing, audio and hardware independence are
outside this profile. Original command12 testing is a separate experiment using
verified private inputs, never a preparation smoke or complete sound-engine claim.
