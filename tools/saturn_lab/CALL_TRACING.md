# Bounded original master-SH2 calls

Issue #597 extends #482/#483 for the original USA kernel helper `0600B934`.
This is a separately prepared research core, not a change to the game, reference
locks or historical checkpoints. Read the live issue/PR evidence before treating
the experiment as accepted. A successful preparation or owned C fixture is not
natural original execution. Zero calls fail research acceptance.

The observer requires the master's interpreter path, with SH2 JIT disabled.
ABI v2 records at most 64 entry/return pairs for this one inspected helper. It
captures registers, flags, frame and signed core scheduler timestamp before
dispatch. Normal pipeline PC is four bytes ahead; delay slots use a different
PC relation and cannot establish an entry. The helper's inspected RTS and MACL
restore delay slot must precede its return. Old PC_ID/PC_IF fields are unused.
Pending calls have a 4096-dispatch limit. Unsupported mode, reentry, overflow,
missing return, clock gaps and missing/incorrect ABI fail. A positive master
dispatch count distinguishes an executed window with zero calls from an
unobserved interpreter path. It is not a count of hardware cycles.

The decoder verifies the recovered sampled arithmetic and scratch registers,
SR.T, SP, MACL and other preserved registers. It does not establish the helper's
gameplay role, the domain of natural arguments, every caller, slave execution,
whole-game timing or hardware accuracy. Recording stops at the declared pair
limit; subsequent frames have no claimed call coverage.

## Run through existing isolation

Prepare through `tools/factory/provision.py --tool beetle-saturn-call-trace` as
documented in [PROVISIONING.md](../factory/PROVISIONING.md). The trusted
coordinator supplies existing shared resource admission and bounded namespace/
process guards; this driver does not create a scheduler, sandbox or provider
reservation. Keep network, credentials and merge authority outside the worker.
Mount the pinned callback/media root, checkpoint parent, kernel parent, source
and immutable prepared generation read-only. Use a fresh private output path.

```sh
python3 tools/saturn_lab/run_call_trace.py \
  --reference-root /private/reference \
  --lock /private/reference/locks/accepted.json \
  --expected-lock <coordinator-pinned-file-sha256> \
  --checkpoint /private/checkpoint/checkpoint.json \
  --kernel /private/kernel/0KRNL.BIN \
  --prepared /canonical/repo/.factory-tools/prepared/generation \
  --mode enabled --frames 600 --start-frames 10 --pairs 1 \
  --output /private/experiment/enabled-1
```

`reference` selects only the accepted unmodified core. `disabled` loads the
separately prepared core without starting observation. `enabled` starts the
bounded observer. Each run uses a fresh process. The only optional input is a
declared initial port-zero Start pulse followed by release; default is no input.
The limit is 600 frames per run. No gameplay RAM is modified by this adapter.

Before import, verify the original lock file hash, all four pinned callback/
support sources, complete media/profile identity and checkpoint identity. Before
and after execution, verify the inspected helper and literals are resident with
the original word order. Explicitly record source/destination core identities
and canonical post-import state identity. This experiment does not declare
arbitrary cores' save states portable or rewrite a checkpoint's identity.

Run twice in each mode from the same checkpoint/input, then:

```sh
python3 tools/saturn_lab/run_call_trace.py compare \
  /private/reference-1 /private/reference-2 \
  /private/disabled-1 /private/disabled-2 \
  /private/enabled-1 /private/enabled-2 \
  --report /private/comparison.json
```

The comparator requires six distinct successful runs, identical declared inputs,
native video/audio observations, canonical imported/final state hashes and
repeatable validated positive call records. It checks actual artifacts against
their receipts; missing, failed, altered or empty evidence is rejected. Timing
ratios are bounded whole-run wall measurements including the period after the
record limit, not steady-state tracing overhead or recovered Saturn timing.

Failures retain a failure receipt, and where available native observations and
bounded rejected records. Private states/media/raw traces stay outside Git and
model submissions. Public evidence should contain derived measurements and
provenance hashes only. Full campaign/battle/Godot parity remains separate.
