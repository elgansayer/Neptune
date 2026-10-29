# Research feature catalogue

Run from the repository root with Python 3.11+; no external dependencies:

```sh
python3 tools/research_catalog/check.py
python3 tools/research_catalog/cli.py validate
python3 tools/research_catalog/cli.py report
```

`--catalogue PATH` selects another JSON file. Reports go to stdout. The CLI
never executes recorded commands, fetches URLs, changes GitHub or writes files.

The canonical starter dataset is `docs/restart/feature-catalogue.json`. Each entry
has a stable ID, reference/version, source claims, target profile, implementation
status, acceptance checks, dependencies, issue and separate evidence slots.
Unknown/unaudited is not the same as absent. This is not an exhaustive catalogue.

Observed references require input-manifest/capture SHA-256 digests, scenario,
command and limitations. Verified implementations require a tested commit,
command, passing result and artifact digest; external parity additionally requires
an observed reference. Unknown IDs, dependency cycles, empty catalogues and duplicate
JSON keys fail validation. Reports keep reference and implementation states apart.

These checks validate metadata structure only. A digest may refer to missing or
fabricated evidence; this tool cannot establish authenticity, reproduce an experiment
or prove the current checkout still passes an older verification. The coordinator
must resolve retained artifacts and independent checks at the exact candidate
commit. Catalogue edits must not bypass protected runtime/review gates.
