# Original NLSND state updater and command11

[671](https://github.com/elgansayer/Neptune-Bomberman/issues/671) adds independent
complete-call comparisons for original535E,51B2,41D4,1E56 and the17F2 command11
caller. It reuses the accepted [5290 ramp contract](2026-11-03-original-nlsnd-ramp.md)
and qualified ABI5 CPU/frozen-SCSP profile. The
[evidence JSON](../evidence/2026-11-03-original-nlsnd-state.json) binds the actual
private source, semantic dependencies, native identity, commands and outcomes.
Parent665 remains open for command10 and unknown natural domains.

## Recovered boundaries

The original USA1.003 `NETLINK/SNDDRV.BIN` is loaded at sound CPU address0.
Its NLSND lifetime and SHA256 are separate from the other sound drivers and SH-2
modules. The comparison executes original instructions; the Python contract uses
independent arithmetic, explicit RAM/device operations and declared PC paths.
Expected values never come from captured candidate execution. Original read-only
table bytes are reference inputs, not reconstructed output used as an oracle.

| Entry | Call contract |
| --- | --- |
|535E|A6 addresses the record; D2/D3/D4 low bytes are cached targets; D5/D6/D7 contain current parameters with seven-bit low words. Updates three ramps, lookup-derived coefficients and address registers.|
|51B2|Reads global pointer412, sets local record/current pointers, consumes a pending update, optionally prepares5290 and/or runs535E, publishes three current bytes, then restores saved registers before reading the caller A6 status.|
|41D4|Reads global byte4 maskedC0. Zero leaves D0 unchanged and sets its word flags at40FA. Nonzero publishes D0/D1/D2 low bytes, pending80 and three127 step bytes, then calls51B2 before the common return.|
|1E56|Reads three payload bytes through incrementing A0, calls41D4 and returns.|
|17F2/11|Uses the original indexed low-command dispatch, preserves/restores its caller address registers, and completes the handler/helper/state chain.|

535E clears record2C bit0, then sets it for each parameter that differs at the
start of this update. A differing parameter adds its signed-byte step, subtracts
its magnitude from the byte countdown, and snaps to target on zero or borrow;
otherwise it retains the stepped byte. The resulting byte is masked127. A zero
step with a positive countdown can remain unchanged. An exact countdown boundary
and a wrapped underflow are distinct checked cases. The flag can remain set on
the update that first reaches its target.

The routine writes all three current bytes, uses direct/folded lookup tables,
and computes the combined33-by33 address lookup. D6 bit6 chooses which source
address word receives the lookup addition; both source reads and destination
writes must occur in the original order. Six centred coefficient calculations
use signed multiplication, word-local rounding/arithmetic shift, re-centring and
a final word shift. The last mirrored index is128 minus the second current byte.
The model preserves product upper words and exact final CCR semantics rather
than replacing the calculation with floating-point interpolation.

These are numbered parameters. Their natural sound roles, command distributions
and timing are not inferred from the arithmetic. COEF/MADRS effects use the
accepted logical register oracle and pinned native component, never flat device
RAM. The original's final16-bit bus value and packed coefficient effects are
checked separately. All other captured device state must remain unchanged.

51B2 saves D0..D7/A0..A6 with the pinned CPU's ordered predecrement word stores.
It clears the pending flag, copies/normalises the queued fields where applicable,
selects ramp preparation or active update, and restores the saved registers.
Only then does it read `(restored A6+2C)&3` for D0. Aliased and separate caller
contexts are explicit cases. Stack return addresses, every untouched mapped byte,
all visible registers/SR, ordered transactions and executed PCs are compared.

The first expanded original diagnostic exposed an incorrect X assumption for a
disabled dispatcher call: the original reached186C with X clear, while the first
model preserved its input X. The two original ADD.W index doublings cannot carry
for command11. A retained failing-before/passing-after test now checks that
semantic fact. The original reference and comparison precision were unchanged.

## Actual original execution

| Entry mode | Declared cases per process | Observed instructions |
| --- | ---: | ---: |
|535E|19,798|134..168|
|51B2|3,414|31..254|
|41D4|4,305|6..267|
|1E56|4,305|11..272|
|17F2 command11|4,305|24..285|

The36,127-case selection includes four initial SR values, two register/address
variants, pending/flag boundaries, both caller-context arrangements, all byte
values of each declared step/magnitude/countdown field and all gate bytes. Current
and target domains are explicitly seven-bit. The direct-effects selection covers
all128-by128 second/third current pairs, reaching every addressed point of the
33-by33 combined lookup plus its33 scale bytes. Table coverage counts are recorded
without pretending unused padding or unknown domains have been recovered.

Two fresh guarded processes passed every declared complete call and produced the
same full report hash. There are five changed-original control families: countdown
comparison, active state bit, final coefficient shift, restored caller result
mask and command gate. All44 modified calls reach terminal return and are rejected
by semantic comparisons. Early guard termination is never counted as a successful
semantic mutation check.

Two additional odd-address experiments retain native status3 at the actual word
access. They are incomplete diagnostics, not terminal calls or a model of the
68000 exception handler. Source/input/native are read-only, network is onlylo,
broker/auth/signing authority is hidden, and the existing shared limit3 is used.
Each original process is bounded to768MiB address space,180s CPU,210s wall and
4MiB files; each call has a512-instruction budget. Lease600s and guard5s are
unchanged during the job. Isolation, tooling and both original runs exited0 with
no cancellation, timeout, truncation or surviving guardian.

```sh
python3 tools/saturn_lab/probe_netlink_state.py \
  --source-file "$NEPTUNE_NLSND_SOURCE" \
  --prepared "$NEPTUNE_ABI5_PREPARED" \
  --report "$NEPTUNE_PRIVATE_REPORT"
python3 tools/saturn_lab/check.py
```

The360 tooling tests are separate evidence. Initial wrapper limits conflicted
with the suite's deliberate resource-limit fixtures; those failures are retained.
The qualified tooling profile permits those fixtures while bounding the parent
to4GiB address space,2GiB files,150s CPU and90s wall. Original-call limits remain
the smaller profile above. No test assertion or production capture limit changed.
Reports keep RAM hashes after full byte comparison, avoiding raw ROM-table dumps.

## Still unverified

Natural command/parameter/function domains, sound roles, clock advancement,
hardware timing, DSP execution, actual PCM, Godot campaign/battle/pixels/audio and
whole-game/code coverage remain open. The reference CPU/component lineage is
shared, not independent hardware corroboration. Command10 remains in665. Source
publication and current-base CI are live GitHub states rather than assumed here.
No service, account allowance, quota, infrastructure or Neptune continuity was
changed. Deterministic model requests were zero; account/CI spend is unknown.
