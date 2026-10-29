# Canonical behaviour trace v1

`compare_trace.py` is a local exact comparator for #27/#29. It does not boot an
emulator, produce captures, authenticate input evidence or certify game fidelity.

```sh
python3 tools/saturn_lab/compare_trace.py reference.json candidate.json
```

Exit 0: supplied observations agree. Exit 1: valid traces diverge. Exit 2: malformed,
incompatible or unreadable inputs. JSON output identifies both canonical trace
digests and the first divergent frame/JSON pointer, without dumping private values.
Standard output can be redirected to a new evidence report by the capture runner.

Each input is at most 16MiB, contains 1..100000 samples and has these exact fields:

```json
{
  "schema": "neptune.behaviour-trace.v1",
  "contract": {
    "scenario": "synthetic/example",
    "ruleset": "synthetic-v1",
    "observation_schema": "example-fixed-point-v1",
    "input_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "timebase": {"numerator": 60, "denominator": 1}
  },
  "source": {
    "kind": "synthetic",
    "build_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "input_lock_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "capture_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "adapter_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
  },
  "samples": [
    {"frame": 0, "observations": {"player_x_fixed": 0, "events": []}}
  ]
}
```

This example is synthetic. Its placeholder hashes and rate must not be used for a
real reference. For actual captures, `kind` is `reference` or `implementation` and
all four source digests identify retained evidence. The input lock for an
implementation identifies its content/configuration/initial-condition manifest;
the reference lock identifies the actual original inputs. Their source hashes can
differ. The complete `contract` must match on both sides, including canonical input
recording and declared observation units/semantics. Scenario adapters establish
equivalent initial conditions and retain their own mapping evidence.

Frames are relative to the scenario start, begin at zero and are contiguous.
The timebase is frames per second as a positive rational, derived from the pinned
capture setup. No resampling, time alignment, dropping frames or tolerance change
is performed by the comparator. Capture longer sessions as bounded scenarios with
recorded start identities. A trace ending early is a mismatch.

Observations are nonempty objects of nested JSON objects/lists, integers, booleans,
strings and null, up to depth32. Floats are rejected: define fixed-point units in
the observation schema. Object key order is irrelevant; event/list order and value
types are significant. Missing fields, additional events and true-versus-1 differ.
Duplicate JSON keys fail. Whole-video/region hashes can be observations where exact
pixel equality is appropriate; the comparator does not align or interpret images.

Source labels and digests are attestations, not verified facts. Always pair a result
with the verified lock, raw capture, applied settings, controller recording,
checkpoint identity, adapter implementation and repeated original runs. A matching
synthetic fixture is never reference parity. A typed schema with plausible hashes
is not proof of an authentic emulator run.
