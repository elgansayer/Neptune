# Japan A610 timing-word change poll

## Original-byte execution

This probe directly executes original Japanese `0KRNL.BIN` at
`0x0600A610–0x0600A61E`, including the RTS delay slot, with the pinned
`saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9` interpreter and
identity-checked frame-1200 WorkRAM-H. Eight cases (four explicit sample
sequences times two register seeds) run twice. The sequence at `0x060B3D40`
is supplied as an explicit changing WorkRAM observation stream; it is not
claimed as naturally captured device timing.

Identical reports are under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-218/`.
Each report SHA-256 is
`61ba22951a228104a013e5520d15320e97db4b676a73fea0be7df7306e859fa3`; normalized
results SHA-256 is
`fd6cefcca845de5ae67e41d419da97244ee884b782228db11f5326d3cd17bd73`. The
probe SHA-256 is
`44bcd87524e400269df9fb5849cfa1a68ec2be6cb9071b6747ca74467f323b9d`.

## Recovered poll rule

The original code reads the initial halfword once into R4. It then repeatedly
reads the same address into R2 and compares R2 with R4. Equal observations
branch back to the read; the first unequal observation exits. R4 retains the
initial sign-extended halfword, R2 holds the changed sign-extended halfword,
and the function performs no memory writes. The corpus includes immediate
change, repeated equality, and the signed `0x7FFF`/`0x8000` boundary. A changed
address literal is rejected by the strict read contract.

The initial attempt `execution-216` retained a mistyped normalized RAM hash;
`execution-217` exposed a signed-versus-unsigned host comparison at `0x8000`.
Both were corrected in the paired `execution-218` reports.

## Limits and continuation

The poll samples and function entry are constructed. This does not establish
the original caller, how the WorkRAM word changes, or console timing. The next
step is to compose the already-tested A472 service path, A638 initialization,
and return into A4C8/A546; its loop calls A610 and additional VDP1, SMPC, SCSP,
and DMA routines. Whole-kernel code and asset recovery remain open.
