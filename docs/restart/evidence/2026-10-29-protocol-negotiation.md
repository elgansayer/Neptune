# Native pre-connection compatibility evidence

Issue #460, parent #108/SIM-015. Base main `d562d4627690e871725f1e7c6af29a9cffb7b59c`.
API and limits: [PROTOCOL_NEGOTIATION.md](../PROTOCOL_NEGOTIATION.md).

Pinned engine: Godot `4.5.stable.official.876b29033`, Linux x86_64, from
`tools/godot/toolchain.json`; existing LimboAI/SQLite native addons. Host Debian 13,
4 vCPU/~8 GB RAM. Xvfb/software Mesa exercises the actual graphical ClientMain.
No provider calls, purchases, production deployment or content/reference inputs.

## Reproduced failures

- Before implementation, the expanded runtime supervisor failed: no explicit
  server incompatibility-rejection evidence. The legacy server did not negotiate
  a gameplay protocol. The raw future-offer client itself timed out; this is not
  claimed as an admitted incompatible game session.
- First parser suite: 12 pass, one fail with script errors on a numeric format
  comparison. Explicit format-type validation fixes the error instead of ignoring it.
- Immediate rejection/disconnect raced server-offer delivery. The production
  client reported a generic timeout/disconnect; its incompatibility probe failed.
  Rejected peers now remain blocked within the three-second pending deadline,
  allowing offers to arrive and both endpoints to explain incompatibility.
- A later native regression reproduced stale previous-session map data after a
  failed connection: 15 pass, one fail, no script error. ClientMain now clears map
  cache at connection attempt, failure and disconnect alongside auth/version state.

All failed logs remain on the host; no existing test threshold was relaxed.

## Executed checks

Commands from the repository, with `GODOT` the pinned binary above and `EVIDENCE`
an absolute host directory outside Git:

```sh
python3 tools/godot/check_project_contracts.py --godot "$GODOT" --evidence "$EVIDENCE/project"
bash run_bot_tests.sh --godot "$GODOT" --run-specific test_protocol_negotiation --timeout 55 --max-fps 60 --log "$EVIDENCE/focused.log"
python3 tools/godot/check_runtime.py --godot "$GODOT" --graphical --evidence "$EVIDENCE/runtime"
bash run_bot_tests.sh --godot "$GODOT" --timeout 300 --max-log-mib 16 --log "$EVIDENCE/full.log"
python3 tools/saturn_lab/check.py
python3 tools/research_catalog/check.py
python3 tools/research_catalog/cli.py validate
python3 tools/factory/check.py
python3 tools/merge_gate/check.py
python3 docs/restart/backlog/build_catalogue.py --check
```

- Native import/null-fail/true-pass/addon contracts pass.
- Final focused native suite: **16 pass**, zero failed.
- Final network supervisor passes: default/explicit headless and graphical real
  clients select version 1 before ping/pong; production incompatible client reports
  incompatibility and clears state. Nine untrusted probes (future, retry after
  rejection, malformed JSON, boolean version, duplicate versions, oversized bytes,
  invalid UTF-8, numeric format and silent peer) never reach server peer_connected.
  Existing occupied-port, single owner and invalid role/port checks still pass.
- Full local suite before the final cache-cleanup change/case: **182 pass / 25 files**,
  243.125 seconds, zero engine errors/warnings. Final full-suite coverage is required
  in exact-head/current-base CI; it is not inferred from this earlier local run.
- Input 28, catalogue 14, factory contracts 27, merge-gate contracts 17 and catalogue
  validation pass. These are tooling/metadata checks, not live factory health or
  emulator/reference evidence.

Host manifest `/home/dev/neptune-evidence/protocol-local-evidence.json` stores
commands/log paths/digests, including failed experiments. The PR's required CI
artifact records exact source head/base, final native results and network logs.

No save migration, complete room lifecycle, browser transport, reference parity or
continuous factory acceptance is claimed. #108 remains open for its save contract;
#100 retains network reconnect/grace scope; #121/#31 remain separate room work.
