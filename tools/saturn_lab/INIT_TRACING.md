# Original initialization observations

`run_init_trace.py` uses the separate prepared`beetle-saturn-init-trace` ABI1.
Profile1 observes original89C8 with link6240; profile2 observes95B04 with link8A18.
It records named calls/delays/callee entries/returns and the actual complete root
RTS/restore-delay/return. Internal library/device/callback semantics and hardware/
gameplay parity remain separate open work; a native root return is not complete
code reconstruction.

Run under existing host admission and the credential-free offline guard, with
source, media, verified boot checkpoint, kernel and prepared tool read-only.
Use shared3, own180-second leases,60-second/nice10/downward2GiB bounds and new
private output directories. The driver does not create an OS sandbox itself.
Historical reference core/lock/checkpoints remain unchanged.

The original frame1200 checkpoint can precede the last kernel sectors: measured
A6790 code is absent there and present unchanged at1800. Only boot checkpoints
with the existing verified cold-boot/reference provenance are accepted. Their
incomplete initial witness is explicitly recorded. All2572 words must still match
at native entry, every snapshot and in the final state; neither a malformed state
nor an unfinished trace can qualify. Source-presence and state hashes are checked
independently in the six-run comparator.

```sh
python3 tools/saturn_lab/run_init_trace.py \
  --reference-root /private/original-reference --lock /private/original-reference/locks/LOCK.json \
  --expected-lock COORDINATOR_PINNED_LOCK_SHA256 \
  --boot-checkpoint /private/verified-boot/reference/checkpoint.json \
  --kernel /private/original-kernel/0KRNL.BIN --prepared /private/prepared/EXACT_GENERATION \
  --profile 2 --mode enabled --frames 600 --start-frames 0 --output /private/evidence/enabled-1
```

Collect two fresh runs of each mode`reference`,`disabled`,`enabled`, all using
the same original checkpoint, profile, frame count and inputs. Compare all files:

```sh
python3 tools/saturn_lab/run_init_trace.py compare \
  /private/evidence/reference-1 /private/evidence/reference-2 \
  /private/evidence/disabled-1 /private/evidence/disabled-2 \
  /private/evidence/enabled-1 /private/evidence/enabled-2 \
  --kernel /private/original-kernel/0KRNL.BIN --report /private/evidence/comparison.json
```

The comparator requires exact imported/final state, native video/audio/input,
source identities/witnesses and repeated validated traces. It rehashes and parses
actual private state/record artifacts. Unknown library windows are tagged unknown.
Logs, partial state/frames and rejected native records are retained on failures;
an attempted incomplete first frame is not mislabeled as zero execution.
Raw states, traces, media, BIOS and credentials remain outside Git. Owned fixture
tests check this tooling only; actual original execution needs separate evidence.

Actual two-profile/twelve-window VPS results and retained failures are recorded
in [the natural initialization report](../../docs/restart/research/2026-11-02-first-task-natural-init.md).
Both named roots return naturally; internal library/device semantics remain open.
