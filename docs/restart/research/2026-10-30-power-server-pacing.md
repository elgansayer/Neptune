# Recovered Power Bomberman 0.7.8c server update-pacing logic

Actual original-source analysis, 30 October 2026. This recovers a bounded part of
Power's optional network server. It does not establish client physics, a Saturn
routine, network-performance parity or a newly extracted spritesheet.

## Original input and provenance

The developer's [release post](https://www.bombermanboard.com/viewtopic.php?t=1925)
links the [0.7.8c optional server archive](https://drive.google.com/file/d/1pB09NZ7_cDm34LnN5TS1g3m-Oar86vBG/view).
That archive was actually downloaded and analysed, rather than substituted with
existing asset exports or another project's reimplementation.

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `powerbomberman078c_server.zip` | 594897 | `8c6384ec8623939f2dd6063cb4f8af890e2d2f9950175727ee3d9bf984bd3f9d` |
| `PBServer2.dll` | 129536 | `9e435a445cef37cf4d3f8911099caeb074feb24a455cc3656d95d75d88a199e1` |

The included readme identifies Power Bomberman 0.7.8c Server, PBTeam, 2026 and
.NET 8/C#. The runtime configuration independently identifies `net8.0`. The
advertised version is not proof that no same-version hotfix exists: use these
exact file hashes. The complete binaries remain outside Git.

## Original methods and recovered behaviour

The original CLR metadata names the class `PBServer2.Utilities.PacingTracker`.
These method names are retained original metadata, not invented semantic names.

| Method | MethodDef token | Body RVA | Native-file body offset | CIL bytes |
| --- | --- | --- | --- | ---: |
| `Reset` | `0x06000051` | `0x3424` | `0x1624` | 72 |
| `IncreaseCount` | `0x06000052` | `0x3488` | `0x1688` | 13 |
| `GetMax` | `0x06000053` | `0x3498` | `0x1698` | 38 |
| `EndPhase` | `0x06000054` | `0x34DC` | `0x16DC` | 105 |

Body RVAs include the CIL method header, not just the first instruction. The
[machine-readable receipt](../evidence/2026-10-30-power-server-pacing.json)
includes code-start RVAs, body lengths and hashes for exact regeneration.

The constructor starts the cached maximum at one. `Reset` fills the history array
with ones, clears the pending count and sets its write position to zero. It
**does not reset the cached maximum**. `IncreaseCount` increments the pending
count through `Interlocked.Increment`. `GetMax` returns the cached maximum.

Under the emitted monitor/finally structure, `EndPhase` behaves as follows:

```text
if pending_count > 0:
    store pending_count in the next circular-history slot
    advance the slot modulo history length
    clear pending_count
    cache the maximum of the full history array
```

Consequently, empty phases do not insert zeroes or advance the history. A burst
can remain in the window across arbitrarily many empty phases. After `Reset`, a
previous high cached result remains visible until a subsequent non-empty phase
recomputes it. These are observations of the original code, not recommendations
for Neptune's implementation or claims that Power's behaviour is defective.

The original `Client` constructor at RVA `0x40E8` instantiates this tracker with
32 history slots. Actual original call sites connect it to `ReadClientMessage`
(RVA `0x9658`), `EndGameUpdatePacingTrackersPhase` (`0x713C`) and
`UpdateAndSendGameFrame` (`0x7190`). The last method reads `GetMax` in its queued
player-update handling. This establishes its relevance to network update pacing;
the complete packet protocol and every caller path remain unrecovered.

## Reproducible real-source analysis

`tools/power_lab/probe_pacing.py` checks the complete original DLL hash, class,
method RVAs/body hashes, external-call identities and dependency versions. It
parses those actual methods and interprets their CIL instructions with bounded
control flow. It does not replace them with generated synthetic method bodies.
The independent comparison model uses a deque of non-empty phase counts.

Observed result: **4,058 phase transitions matched**, using history sizes 1, 2,
3 and the original caller's 32; seeded counts, empty phases, ring wrap and reset
after an established history. Five empty phases preserve a maximum of nine;
reset also leaves that cached nine visible. Mutating the parsed original
`EndPhase` comparison from `ble.s` to `blt.s` is detected: the altered branch
incorrectly ages an empty phase. This control does not modify the source DLL.

```sh
python3 -m venv /PRIVATE-TOOLS/power-cil
/PRIVATE-TOOLS/power-cil/bin/pip install -r tools/power_lab/requirements.txt
/PRIVATE-TOOLS/power-cil/bin/python tools/power_lab/probe_pacing.py \
  --assembly /PRIVATE-INPUTS/PBServer2.dll \
  --report /PRIVATE-EVIDENCE/NEW-pacing-result.json
```

Download from the developer-linked mirror, verify the archive hash, and extract
only the selected assembly into private input storage. Replace the placeholder
paths with inspected paths. The report is exclusively created and never replaces
an existing result. Repeat to a second fresh path and compare receipts. Ordinary
CI runs eight synthetic interpreter/failure tests through the existing lab check;
it does not have the original DLL and cannot reproduce the original-source run.

## Limits and next work

This is CIL interpretation and reproducible source analysis, **not execution on
the .NET CLR**. Monitor, atomic increment and LINQ maximum calls are modelled;
the probe checks normal single-thread paths, not concurrency or exception races.
It does not measure frames, latency, client simulation or real online matches.
Input ranges are modest non-negative counts and positive history lengths.

Next: cross-check the methods under the real .NET runtime, trace the incoming
update packet path, and test the queue policy against an owned local client/server
pair under #506. Keep #476/#498/#499/#506 open: this is one recovered original
server component, not full Power recovery. No recovered reference implementation
is imported into Neptune's runtime or publicly relicensed.
