# Japanese kernel A6C94 index-0 busy dispatch

This result uses original Japan `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Composed original-byte execution

The dispatcher at `0x060A6C94` reads the request index from `context+40`,
multiplies it by 16, and loads the target from the table at `0x060B2168`. Index
0 selects `0x060A8154`. This probe composes dispatcher range
`[0x060A6C94,0x060A6CB2)` with A8154's occupied-slot path
`[0x060A8154,0x060A8178)` and its return cleanup
`[0x060A820C,0x060A8218)`. A constructed queue global and slot show occupancy;
the target returns R0=0 without queue writes, while both stack frames restore.

Forty-eight constructed occupancy/R5/seed cases ran twice. The paired private
reports in `execution-112` are byte-identical at SHA-256
`8ba5d0040070d9dd71151596870fd9d88fee53e1f517b08517b6f31d2d14c632`; the
ordered result digest is
`130cc6ace9e5c2be0a7b5512cb6dde79b119047d4154fc7b5792ef262afddaad`. The
composed code, original 96-byte table and source literal hashes are
`4959fc1f1f7912bf99c2e1344bb214b163f747146018fb1bf68aac6d0de08c37`,
`b702b1ecab6c76bb6e29d7a294423f5d1ad56cddb40f9818bffbbecdc7354c79`, and
`fd895d2a6de6a33518a388c9eeaf2e3087af8c2ff48c8ee612a13a47d3f279b8`. The
probe hash is `6a0a5fa602bfd21921f9bf6470ae7e29a6b907df43c20a4c4ecb5d78ef2d05d2`.

Changing the index-0 table target to `0x060A8178` is rejected when execution
attempts to fetch that address outside the declared busy-path fence.

This establishes the original dispatch and occupied-slot return for a
constructed index-0 context. It does not establish natural queue construction,
the successful request path and callbacks, service-loop reachability, hardware
effects, or gameplay behavior. Static table byte residency and these bounded
CPU executions remain distinct evidence.
