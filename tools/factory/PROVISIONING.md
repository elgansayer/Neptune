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
```

Both recipes currently target Linux x86_64. Godot delegates downloads and hash
validation to the existing pinned installer, then checks the actual version and
native addon identities. Beetle fetches the exact recorded official Git commit,
verifies checkout identity and builds with one job and the accepted software/CHD
options. It needs existing `git`, `make`, `cc` and `c++`. Its smoke loads the real
library in a fresh bounded process and checks API symbols/version and Saturn/CUE
identity without a BIOS or game. This is not a boot or compatibility test.

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
downloads/builds both pinned tools, runs their smoke checks and demonstrates
cache reuse. Read its exact-head result before claiming those real installations.
The protected aggregate check also runs all applicable existing tests.

VPS acceptance is separate: use a fresh disposable cache, record the real install
and reuse results, then use an authorised private game fixture with a new input
lock. Prove the existing factory provisions and resumes after interruption and a
provider/tool failure. #518 stays open until that integration and evidence exist.
