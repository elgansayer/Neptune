"""Saturn Bomberman PROGRAM.BIN kernel bank directory, Hudson ring/delta codec, and resident-memory verifier."""

from __future__ import annotations

TOOL_VERSION = "0.1.0"
KERNEL_BANK_DIRECTORY_SCHEMA = "neptune.saturn-archive.kernel-directory.v1"
BANK_DECODE_SCHEMA = "neptune.saturn-archive.bank-decode.v1"
RESIDENT_COMPARISON_SCHEMA = "neptune.saturn-archive.resident-comparison.v1"


class ArchiveError(ValueError):
    """Raised when a Saturn archive header, compressed stream, or receipt fails validation."""
