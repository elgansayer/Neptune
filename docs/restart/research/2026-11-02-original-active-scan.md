# Original complete active command scans

Issue [#625](https://github.com/elgansayer/Neptune-Bomberman/issues/625), under
#483/#488/#480/#464, continues#617's capture prefix through the actual#623
dispatcher returns. All **3,196 selected original130E calls complete**, twice.
The two full reports are byte-identical, SHA256
`35a49353aeaa0838a8d85d06994f05392dc0e6710e8a0bcf05c3d3b4c28649d8`.
They include eight active commands, original nested calls and real header-word
clearing/rescanning. All five instruction controls reject.
[Derived evidence](../evidence/2026-11-02-original-active-scan.json).

## Source and complete returning-path contract

USA MK-81070 V1.003 `NETLINK/SNDDRV.BIN`,23,920 bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
sound68000 mapping0 candidate, NetLink lifetime. Whole-source verification
precedes execution. Executed ranges130E..13B2 and17F2..18F2 remain original.
Positive runs do not relocate instructions or replace handlers/calls.

The [capture contract](2026-11-02-original-netlink-capture.md) still applies:
gate4E1 bit7 selects direct scan versus4E0 bit7 handshake, eight16-byte source
slots at0700..0770,14-byte command plus timestamp in the128-slot log, and optional
16 **raw source bytes** forwarded through the circular byte buffer when gatebit5
is set. This experiment now completes each selected active path:

1. Original139A pushes139E and calls17F2. It runs actual skip/no-op code and,
   when indexed, original nested JSR/table/return instructions. The selected
   nonzero command domain contains223 bytes whose#623 paths completely return.
   It excludes nontrivial handlers and illegal8C/8F; those remain unresolved.
2. After the real return,139E reloads the saved slot word from A6+1834.13A2 sets
   A0 from it.13A4 clears the **entire source header word**, including its second
   byte, not just the command byte.
3. 13A8 increments D0.low8 by10hex and rescans until all eight slots have been
   visited. Full eight-active cases use eight real dispatcher calls and eight
   source word clears. Mixed classes include high8D's actual ORI.B006E,D0;
   139E then reloads the slot before clearing, so that modification cannot select
   a wrong source address.
4. The timestamp word A6+1838 is consumed/cleared on the first active record;
   later active records in this call log timestamp0. Forwarding copies original
   bytes14/15 before source clearing, rather than the log's substituted timestamp.
   The log index masks with07F0 on every capture, including wrap after stored0800.
   The forwarding cursor advances16 per active record modulo256.
5. 13B0 really returns. A nested handshake then clears4E0 bit7 at131E and returns
   through1324. An unready handshake leaves slots, log and buffers untouched.

All registers, SR, exact PCs, read/write addresses/widths/values/order, entire
source/log/forward buffers, descriptor canaries and stack are independently
compared. The Python expected-state model does not execute a substituted handler
inside the native interpreter. Native calls execute all original instructions
through the outer return sentinel.

Eight regions are declared: handshake bytes,128 source bytes,8 state bytes,
2048 log bytes,041A word, forwarding cursor,256 forwarding bytes and28 stack/
sentinel bytes. Source slots are explicitly writable because13A4 really clears
them. The stack covers the actual outer/helper/dispatcher/indexed-call depth;
all unused bytes remain canaries. No device address or generic device RAM exists.

After a direct complete scan D0.low16=0780, A0=0770 and final CCR has N/V from
the last70+10=80 byte add, with X/C/Z clear. A nested acknowledged scan ends with
the memory ANDI.B's N/Z/V/C and preserved X0; ACK80 gives Z, ACKFF gives a positive
7F. D7 differs between never-active and active-then-empty scans because the
dispatcher normalizes its low word; the probe checks that distinction. D0/A1
MOVEM saves, A5/A6 indexed saves and all three real return addresses are checked.

## Coverage, bounds and controls

The3,196-case union covers every223 returning nonzero command at selected first/
last positions, uniform full-eight scans, all256 active masks with mixed classes,
all256 forwarding cursor bytes, all128 masked log positions with high/low noise,
two base/SR/timestamp variants and selected gate/ACK boundaries. Every position
and full-eight occupancy occur. It is not every machine state, all possible
command mixtures, or the entire1326 function for unresolved handlers.

Observed complete paths span5..809 instructions and3..559 events, with at most
eight processed slots. A full mixed eight-active call was first attempted on the
unchanged short ABI1. It stopped at its real128-event guard after183 instructions,
before its required778 instructions/517 events completed. The rejection is
retained as `completed_original_call:false`, with its PC/data trace and hash.
It is not counted as a successful scan.

Full runs reuse the **already accepted ABI2 generation**, with native capacities
2048 instructions/1024 events and an explicit1024-instruction request. Its source,
binary, receipt, CPU implementation, memory guards and capacities are unchanged.
No new native preparation, device model or host/provider allowance is introduced.
Owned overflow/recovery smokes remain separate from original evidence.

| Altered instruction | Rejected /12 |
| --- | --- |
| remove source header-word clear |12|
| scan stride32 instead of16 |12|
| remove handshake acknowledgement clear |6|
| remove original dispatcher call |12|
| forward15 instead of16 bytes |6|

Separate altered copies/hashes and unaffected controls are retained. Five new
owned tests cover fixed full-eight, timestamp/raw-forward, middle-ORI/slot reload,
unready and direct-return cases; all242 current research tooling tests pass.
Those tests are separate from the original native execution reports.

## Custody and continuation

Original execution head `b0d472a10e79b9f36979ca1138236ada7c5d2aa2`.
Private reports `/home/dev/neptune-research-private/625/nlsnd-active-scan-001/`
include `short-proof.json` and `run{1,2}.json`. Supervisors/commands/logs are in
`/home/dev/neptune-evidence/code625-20261102/`.
Accepted ABI2 `.factory-tools/code606-001/prepared`, binary SHA256
`abd26a109c1e854925625e11c924b39829d2921d07a249d5c782b08d4eb6aa63`.
Accepted ABI1 and ABI3 remain intact.

Actual configured host shared limit3,180-second own leases,60-second command
timeouts and nice10 stayed unchanged. Own leases were released; other owners
were untouched. Original/code/tool mounts stayed read-only in guarded jobs and
broker authority hidden. No provider/model call, scheduler, paid fallback,
allowance reset or continuity activation; #536 remains open, spend unknown.

After existing admission/read-only mounting, choose fresh reports:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_active_scan.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code606-001/prepared \
  --report /home/dev/neptune-research-private/625/NEW-run1.json
```

Continue nontrivial command handlers and their real side effects. Also return
to original SH-2 task/scheduler6B38/940A/942E, slave/overlays and further common
sound/DSP/save/network/Japan code. These complete scans apply to the declared
returning command domain; natural command traffic, boot/audio/hardware timing,
independent-engine comparisons and whole-module/program/function/dynamic-target
denominators remain unknown. The all-original-code programme stays active.
