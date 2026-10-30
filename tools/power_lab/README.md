# Power original-code probes

`probe_pacing.py` verifies and interprets four original Power Bomberman 0.7.8c
server pacing methods. See the [actual source investigation](../../docs/restart/research/2026-10-30-power-server-pacing.md)
and its linked receipt for exact inputs, hashes, logic, reproduction and limits.
Original archives/assemblies stay private. Runtime code does not import this lab.

Install parser dependencies into an isolated environment using `requirements.txt`.
They are needed only by the real private-source experiment. Standard-library
synthetic interpreter tests run with `python3 tools/power_lab/check.py` and are
also included in `python3 tools/saturn_lab/check.py`. Synthetic test success is
separate from the committed original-source analysis receipt.
