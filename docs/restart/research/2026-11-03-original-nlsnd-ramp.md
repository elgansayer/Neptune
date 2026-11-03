# Original NLSND ramp preparation

[675](https://github.com/elgansayer/Neptune-Bomberman/issues/675) recovers the
bounded helper at5290..535E within the original USA1.003 NLSND driver. It is a
dependency of [671](https://github.com/elgansayer/Neptune-Bomberman/issues/671),
which remains open for535E, complete51B2 and command11/caller semantics.
The [evidence record](../evidence/2026-11-03-original-nlsnd-ramp.json) binds the
input, native profile, candidate probe and repeated actual original execution.

## Recovered call contract

A6 addresses the record. The low bytes of D5/D6/D7 supply the three current
parameters. Record bytes12/14/16 supply targets;1A/1C/1E supply step bytes.
These are numbered parameters: their natural sound roles and reachable input
domains have not been established.

The call sets bit0 at record2C. Parameter0 stores the absolute unsigned target
distance at20, its seven-bit step magnitude at26, and the magnitude or its byte
negation at06 according to target/current order. Parameters1/2 preserve raw
step bytes at08/0A, store signed-byte magnitudes at28/2A, and distances at22/24.
Their subtraction direction depends on the raw step's sign bit. An unsigned
borrow adds128 using byte arithmetic. This is not a general modulo128 operation
for arbitrary full-byte inputs. Targets are copied to0C/0E/10.

Zero steps stay zero here. Raw128 gives parameter0 magnitude0 and the other
parameters magnitude128. Normalisation in the enclosing51B2 function is a
separate contract, rather than an assumption inside this helper.

D0 becomes the final byte distance. D1's low byte becomes the final magnitude;
D2/D3/D4 low bytes become targets. Their upper24 bits are preserved. D5..D7
and all address registers except the returning SP are preserved. RTS consumes
the explicit return address. Final N/Z come from the last target, V/C are clear,
and X retains the final byte subtraction/addition carry. Upper SR bits remain
unchanged. The comparator verifies every mapped byte, stack canaries, ordered
transaction width/value and executed PC, including alternate branch paths.

## Actual comparison

The independent model does not read original instruction bytes or captured
output to generate expected results. The original runs in the accepted ABI5
CPU interpreter, with only explicit record/stack RAM and an executable5290..535E
span. No device transaction is expected; SCSP state must remain unchanged.

The declared37,424 cases cover full byte sweeps of every current/target/step
field, additional edge combinations, four initial SR values and two register/
address variants. All complete in40,41 or43 instructions. This is a finite
constructed selection, not every tuple of all possible bytes or a natural game
distribution. Two fresh guarded processes produced identical complete reports.

Three wrong original-copy changes alter the record bit, subtraction direction
branch and wrap amount. Each reaches terminal return in four declared cases and
is rejected by the semantic comparator. Guard failures or incomplete prefixes
are not counted as detected semantic regressions.

Run with supplied private input and the qualified ABI5 preparation:

```sh
python3 tools/saturn_lab/probe_netlink_ramp.py \
  --source-file "$NEPTUNE_NLSND_SOURCE" \
  --prepared "$NEPTUNE_ABI5_PREPARED" \
  --report "$NEPTUNE_PRIVATE_REPORT"
```

The private coordinator uses the existing shared host gate and actual offline
process guard, with source/input/native read-only and broker/auth/signing
authority hidden. Bounds are512MiB address space,75s CPU,90s wall per original
process,96 instructions per call and a300s shared lease. A real Elgl exclusive
verification delayed admission; no competing work or lease clearing bypassed it.
Both original runs and the isolation check exited0 without cancellation, timeout,
truncation or a surviving guardian. Tooling tests alone are not this evidence.

## Remaining work

Natural callers/parameter roles,535E/full51B2/command11, hardware timing, actual
audio, campaign/battle Godot comparisons and whole-game/code coverage remain
unverified. The experiment shares the pinned CPU lineage, so it is not independent
hardware corroboration. Account/CI spend is unknown; these deterministic tests
made zero model requests. No service, provider allowance, quota, infrastructure
or Neptune continuity was changed. Publication/CI status belongs to live GitHub
and the coordinator checkpoint, not a presumed green claim in this document.
