# Japanese kernel A61B0 first BIOS call boundary

This result uses original Japan `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Original-byte prefix execution

The probe executes A61B0 from `0x060A61B0` through the instruction immediately
before its first BIOS SYS_GETUINT call at `0x060A6220`. With constructed
`R4=0`, A61B0 saves its initial frame, masks interrupt priority, selects the
service value 75, loads the address in its constructed BIOS function table at
`0x06000304`, and prepares the call. The synthetic function pointer is
`0x06005000`; BIOS code is not executed. Eight interrupt-priority/seed cases
ran twice, with exact stack frame, PC fence and call setup checked.

The paired private reports in `execution-135` are byte-identical at SHA-256
`b6946486263d2303a13548f2a00532a541b79fc43c7a49e70e7a153822685986`; the
ordered result digest is
`6ef479bd8d8ee66a1b20939239fbcf92dde4a6ce2b9929299612c91a06e012d5`. The
source-code and source-literal hashes are
`be4b648241b3e1e1a7600d16afb9c484e2e0b21fd5373d74a7a0ac5649dce0a8` and
`fbe1d766eabb4550300a5a30ecc1e430f4f67d84da42d6e9b1fc2c4e02e3f084`. The
probe hash is
`d24a5c071b085c74cdb457a25a4e863b87c370fc7eed02ff823f60f1aa3b87cc`.

Changing the original SYS_GETUINT slot-address literal at `0x060A62BC` from
`0x06000304` to `0x06000308` loads a different constructed pointer and is
rejected by the call-boundary ABI check.

This proves only the game-code prefix and its prepared call state with
constructed BIOS table contents. It does not recover BIOS implementation,
return behavior, A61B0's later BIOS services or SCU D0EN effect, natural
function-pointer values, or device behavior.
