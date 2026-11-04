# NLSND boot RAM probe: validation pending

The probe in `tools/saturn_lab/probe_netlink_boot_ram.py` and its unit tests
stage the proposed isolated USA NLSND routine contract at `0x35DE..0x3629`.
This is testable research tooling, not an accepted original-game result.
Issue [#703](https://github.com/elgansayer/Neptune-Bomberman/issues/703) remains
open with its original acceptance requirements.

The expected 6,345 instructions and 3,107 accesses come from the proposed
contract. They have not been observed in an original execution of this probe.
The table permutation, register/CCR results, RAM bounds and six source-mutation
controls still require the independent original-source runs.

Ten unit tests cover contract consistency, observable mismatches, incomplete
mutation execution, input rejection, exclusive private reports and preparation
failures. Missing native identity inputs now produce a failure report before
native loading, without claiming original-byte execution. These tests use owned
or mocked data and do not establish original semantics.

## Resume original validation

The previous guarded attempt on 3 November stopped before acquiring a lease or
starting a child because the data filesystem was below the unchanged 5 GiB
reserve plus 8 MiB scratch requirement. That historical measurement is not a
current capacity reading. Use the existing VPS guard and shared lease, recheck
both reserves, and preserve all owners and budgets.

The private runner and receipts were recorded at
`/home/dev/neptune-evidence/nlsnd-boot-ram-20261103` and
`/home/dev/neptune-research-private/703/original-001`.
Refresh the prepared source identity for the merged probe before resuming; the
old prepared revision `8b0f3239033cde35753ee2c566ce5bd6b3925f5e` is historical.

Through that guard, run the probe twice in fresh processes with the pinned USA
NLSND source, the verified ABI8 preparation, and new private report paths:

```sh
python3 tools/saturn_lab/probe_netlink_boot_ram.py \
  --source-file "$NLSND_SOURCE" --prepared "$NLSND_ABI8_PREPARED" \
  --report "$NEW_PRIVATE_REPORT"
```

Require matching complete original reports and all 48 normally terminating
semantic mutation rejections before accepting #703's source claim. Preserve
failures and publish only derived identities/results. Do not lower reserves,
replace the contract with candidate output, or infer natural boot, hardware
timing, SCSP/audio or production Godot parity from these isolated checks.
