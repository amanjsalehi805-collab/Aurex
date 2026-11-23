"""Approval-gated command line interface for applying AUREX patches."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nexus_core.messages import Envelope, MessageType
from nexus_core.patch_apply import PatchApplyError
from nexus_core.workspace_config import (
    apply_aurex_patch,
    rollback_aurex_patch,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="nexus")
    commands = parser.add_subparsers(dest="command", required=True)

    apply_cmd = commands.add_parser("apply", help="Review and apply a FILE_PATCH JSON")
    apply_cmd.add_argument("file", type=Path)

    rollback_cmd = commands.add_parser("rollback", help="Review and rollback a patch")
    rollback_cmd.add_argument("patch_id")

    args = parser.parse_args()

    try:
        if args.command == "apply":
            raw = args.file.read_bytes()
            envelope = Envelope.from_json(raw)

            if envelope.message_type is not MessageType.FILE_PATCH:
                raise PatchApplyError("Input must be a FILE_PATCH envelope")

            payload = envelope.payload
            print("\nPatch preview")
            print("Operation:", payload["operation"])
            print("Target:", payload["path"])
            print("Patch ID:", payload["patch_id"])

            if "base_sha256" in payload:
                print("Base SHA-256:", payload["base_sha256"])

            if "content" in payload:
                print("Content bytes:", len(payload["content"].encode("utf-8")))
            if "diff" in payload:
                print("Unified diff:")
                print(payload["diff"])

            if input("\nType APPLY to approve: ").strip() != "APPLY":
                print("Cancelled. No files changed.")
                return 1

            result = apply_aurex_patch(envelope, approved=True)

        else:
            print("Rollback preview")
            print("Patch ID:", args.patch_id)

            if input("\nType ROLLBACK to approve: ").strip() != "ROLLBACK":
                print("Cancelled. No files changed.")
                return 1

            result = rollback_aurex_patch(args.patch_id, approved=True)

        print("\nSUCCESS")
        print("Operation:", result.operation)
        print("Path:", result.path)
        print("Patch ID:", result.patch_id)
        print("Backup:", result.backup_path or "Not required")
        return 0

    except (OSError, ValueError, PatchApplyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
