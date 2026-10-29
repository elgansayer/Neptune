#!/usr/bin/env python3
"""CLI for deterministic read-only Saturn asset auditing and summary validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.asset_audit.audit import AuditError, run_audit, verify_ledger, verify_summary, write_json_atomic
from tools.saturn_lab.cli import LabError


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"Duplicate JSON key: {k}")
        out[k] = v
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit_cmd = sub.add_parser("audit", help="Audit a read-only asset checkout and emit private/summary JSON")
    audit_cmd.add_argument("root", type=Path, help="Read-only asset checkout directory")
    audit_cmd.add_argument("--private-manifest", type=Path, required=True, help="Output path for full per-file manifest")
    audit_cmd.add_argument("--summary-output", type=Path, required=True, help="Output path for compact committed summary")
    audit_cmd.add_argument("--saturn-lab-inventory", type=Path, help="Optional saturn_lab inventory JSON to cross-check and link")
    audit_cmd.add_argument("--header-only-png", action="store_true", help="Inspect PNG IHDR only instead of full CRC+zlib decode")
    audit_cmd.add_argument("--require-clean-git", action="store_true", help="Fail if source Git working tree is dirty or has untracked files")

    verify_cmd = sub.add_parser("verify-summary", help="Validate a committed asset-audit summary JSON")
    verify_cmd.add_argument("summary", type=Path, help="Path to summary JSON")

    ledger_cmd = sub.add_parser("verify-ledger", help="Validate a Saturn coverage and unknowns ledger JSON")
    ledger_cmd.add_argument("ledger", type=Path, help="Path to ledger JSON")

    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            root_resolved = args.root.resolve()
            for out_path in (args.private_manifest, args.summary_output):
                if out_path.resolve().is_relative_to(root_resolved):
                    raise AuditError(f"Refusing to write output inside read-only asset source: {out_path}")
            manifest, summary = run_audit(
                args.root,
                full_png_decode=not args.header_only_png,
                require_clean_git=args.require_clean_git,
                saturn_lab_inventory_path=args.saturn_lab_inventory,
            )
            verify_summary(summary)
            manifest_sha = write_json_atomic(manifest, args.private_manifest)
            if manifest_sha != summary["private_manifest_sha256"]:
                raise AuditError("Internal error: private manifest digest mismatch")
            summary_sha = write_json_atomic(summary, args.summary_output)
            print(
                json.dumps(
                    {
                        "files": summary["totals"]["file_count"],
                        "bytes": summary["totals"]["total_bytes"],
                        "unique_sha256": summary["totals"]["unique_sha256_count"],
                        "duplicate_groups": summary["totals"]["duplicate_group_count"],
                        "anomalies": len(summary["anomalies"]),
                        "private_manifest_sha256": manifest_sha,
                        "summary_sha256": summary_sha,
                    }
                )
            )
        elif args.command == "verify-summary":
            raw = args.summary.read_text(encoding="utf-8")
            data = json.loads(raw, object_pairs_hook=_unique_pairs)
            verify_summary(data)
            print(
                f"Valid asset-audit summary: {data['totals']['file_count']} files, "
                f"{data['totals']['duplicate_group_count']} duplicate groups, "
                f"{len(data['anomalies'])} anomalies; Saturn fidelity not certified."
            )
        else:
            raw = args.ledger.read_text(encoding="utf-8")
            data = json.loads(raw, object_pairs_hook=_unique_pairs)
            verify_ledger(data)
            print(
                f"Valid Saturn coverage ledger: {len(data['domains'])} domains, "
                f"{len(data['next_experiments'])} queued experiments; unknown denominators preserved."
            )
    except (AuditError, LabError, OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"asset-audit: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
