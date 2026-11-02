# Authenticated original experiment receipts

First bounded #511/#579 slice. The trusted coordinator records three actual pinned
original replays through the installed Repo Factory sandbox and exclusive host
gate, executes two existing frontend comparisons, then seals complete evidence
with Ed25519. This does not start providers, services or Godot comparisons.

## Trust and authority

Run coordinator-trusted source with the existing installed factory Python. Never
run candidate-modified signing code with a production authority. Public issue prose
and worker-supplied hashes are not capture policy. Pin public-key and policy hashes
in trusted coordinator state independently of the returned certificate. A
self-selected key establishes no authority. Ordinary workers get no private key
or permission to invoke the signing host.

```sh
python3 tools/factory/reference_receipt.py keygen \
  --authority /home/dev/.local/state/neptune-reference-authority-UNIQUE
```

The fresh authority directory is0700, its `private.pem` is0600 and `public.der`
contains only the public key. Existing generations are preserved. Only the public
key hash is printed. The tool reuses OS OpenSSL's tested Ed25519 API without
replacing host libraries or installing packages. It records actual executable
hash/version; this is capability evidence, not a dependency-freshness claim.
Latest-version preparation/maintenance remains under #518.

## Trusted capture policy

The current intake/task schema and source binding are unchanged. Supply fresh
accepted intake and a clean complete Git candidate with one bounded committed
diff. Do not change an actively leased implementation task to add capture hashes.
Use an independently admitted research/verification step with known inputs.

The local policy is execution configuration, not another task schema:

| Field | Required value |
| --- | --- |
| `root`, `lock`, `lock_sha256` | Private media root, relative input lock, raw lock-file digest |
| `identity` | Existing five-field core/frontend/canonical-lock/settings/interpreter checkpoint identity |
| `restore`, `restore_sha256` | Retained checkpoint JSON and its raw digest; state bytes/hash are checked separately |
| `actions`, `actions_sha256` | Controller recording JSON and raw digest |
| `frames` | 1..600 frames, repeated in three fresh processes |
| `owner`, `scenario` | Actual resource owner and honest observed scenario |
| `python`, `python_sha256` | Existing pinned original interpreter and binary hash |
| `factory_tree_sha256` | SHA-256 of canonical sorted installed factory `*.py` path-to-file-hash object |
| `host_gate` | Actual configured shared `host-resource-gate.json`; never a fresh per-project pool |

The authority stays under the masked coordinator home, outside every capture mount.
The media root becomes the read-only canonical mount. Checkpoint/input parents
inside that home are restored read-only; output is a separate writable workspace.
The recorder first proves that media is read-only and authority/broker state are
hidden. The installed factory source must match the policy before and after runs.

```sh
/opt/hellotalk-factory/venv/bin/python3 tools/factory/reference_receipt.py capture \
  --policy /private/coordinator/experiment-policy.json \
  --intake /private/coordinator/accepted-task.json --source /complete/candidate \
  --authority /home/dev/.local/state/neptune-reference-authority-UNIQUE \
  --output /private/experiments/unique-run
```

The actual frontend validates transitive locked code/settings/interpreter/core
identities. The coordinator also checks the complete lock, checkpoint/state,
input record, actual result markers/files and expected frame/component identity.
Each replay gets a fresh save directory and90-second guard bound. Comparisons
execute in fresh namespaces. Output is bounded to64MiB/128files; the CLI's480-second
deadline includes exclusive admission. Failure/interruption preserves diagnostics
and never produces a successful certificate. Existing service limits still apply.

Only `capture` is a supported signing entrypoint. It constructs actual results,
never signs caller-authored success JSON. The internal primitive has synthetic
crypto tests; possessing a private key remains authority, not evidence of execution.
No network, provider credentials, model call or host-root worker is needed.

## Public verification

`reference-certificate.json` binds existing task revision/head/base, policy,
owner/scenario, actual component and isolation observations, three runs, two
comparisons, crypto identity and all retained file hashes. It contains no private
key, ROM, BIOS or state bytes. Keep raw captures/logs private.

```sh
python3 tools/factory/reference_receipt.py verify \
  --certificate /private/experiments/unique-run/reference-certificate.json \
  --public-key /trusted/authority/public.der --key-sha256 TRUSTED_PUBLIC_KEY_SHA256 \
  --binding /trusted/expected-task-binding.json --policy-sha256 TRUSTED_POLICY_SHA256 \
  --artifacts /private/experiments/unique-run
```

Expected binding/key/policy come from trusted state, not unquestioned fields in the
certificate. No private key is required. Wrong/substituted keys, forged/malformed
signatures, stale bindings, skipped/failed/empty runs, missing comparisons and
changed/truncated/unexpected files fail. Baseline planning declares OpenSSL;
missing crypto support fails tests rather than skipping them.

## Remaining acceptance

This attests the declared original observation/repeatability experiment within the
trusted recorder boundary. It does not prove hardware accuracy, extracted content,
entered campaign/battle coverage or production-Godot state/pixel/audio parity.
A filename such as `normal2` is not scenario evidence; inspect frames and controls.
Loop hashes cannot replace retained native PCM or measured game-state semantics.

Historical authentic original captures can later be referenced by independently
pinned certificate identity. They do not acquire a new candidate head by editing
JSON. #76/#511 must bind these attestations and independently executed Godot
artifacts to current verification tasks and enforce them in the shared adapter.
This command alone does not integrate the supplied-trace contract or enable that
service. Namespace evidence also does not prove all existing manual host sessions
are isolated; #536 and its live rollout remain open.
