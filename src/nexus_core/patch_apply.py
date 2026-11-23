"""Safe, approval-gated file patch application for NEXUS."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .messages import Envelope, MessageType
from .paths import (
    assert_workspaces_disjoint,
    resolve_in_workspace,
    validate_workspace_root,
)


class PatchApplyError(ValueError):
    """Raised when a patch cannot be safely applied."""


@dataclass(frozen=True)
class PatchResult:
    patch_id: str
    operation: str
    path: str
    before_sha256: str | None
    after_sha256: str | None
    backup_path: str | None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def _write_manifest(
    backup_dir: Path,
    *,
    patch_id: str,
    operation: str,
    path: str,
    before_sha256: str | None,
    after_sha256: str | None,
) -> None:
    manifest = {
        "version": 1,
        "patch_id": patch_id,
        "operation": operation,
        "path": path,
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "before_exists": before_sha256 is not None,
    }
    manifest_path = backup_dir / "manifest.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())

def _read_regular_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PatchApplyError("target must be a regular file")
    return path.read_bytes()


def _parse_unified_diff(original: bytes, diff: str) -> bytes:
    """Apply one strict, single-file unified diff."""
    try:
        source = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PatchApplyError("modify currently supports UTF-8 files only") from exc

    if "\x00" in source or "\x00" in diff:
        raise PatchApplyError("NUL bytes are not supported")

    lines = source.splitlines(keepends=True)
    patch_lines = diff.splitlines(keepends=True)

    if len(patch_lines) < 3:
        raise PatchApplyError("invalid unified diff")

    if not patch_lines[0].startswith("--- "):
        raise PatchApplyError("unified diff must start with --- header")
    if not patch_lines[1].startswith("+++ "):
        raise PatchApplyError("unified diff must contain +++ header")

    output: list[str] = []
    source_pos = 0
    patch_pos = 2
    header_re = re.compile(
        r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?\n?$"
    )

    while patch_pos < len(patch_lines):
        header = patch_lines[patch_pos].rstrip("\r\n")
        match = header_re.fullmatch(header)
        if match is None:
            raise PatchApplyError("invalid or unsupported hunk header")

        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        new_count = int(match.group(4) or "1")

        if old_start < 0:
            raise PatchApplyError("invalid hunk line number")

        target_pos = old_start if old_count == 0 else old_start - 1
        if target_pos < source_pos or target_pos > len(lines):
            raise PatchApplyError("overlapping or out-of-range hunks")

        output.extend(lines[source_pos:target_pos])
        source_pos = target_pos
        patch_pos += 1

        consumed_old = 0
        produced_new = 0

        while patch_pos < len(patch_lines):
            line = patch_lines[patch_pos]

            if line.startswith("@@ "):
                break

            if line.startswith("\\ No newline at end of file"):
                raise PatchApplyError("no-newline markers are not supported")

            if not line or line[0] not in " +-":
                raise PatchApplyError("invalid unified diff line")

            content = line[1:]
            if line[0] in " -":
                if source_pos >= len(lines) or lines[source_pos] != content:
                    raise PatchApplyError("diff context does not match source")
                source_pos += 1
                consumed_old += 1

            if line[0] in " +":
                output.append(content)
                produced_new += 1

            patch_pos += 1

        if consumed_old != old_count or produced_new != new_count:
            raise PatchApplyError("hunk line counts do not match header")

    output.extend(lines[source_pos:])
    return "".join(output).encode("utf-8")


def _atomic_replace(path: Path, data: bytes, expected_hash: str) -> None:
    """Replace a file atomically after rechecking its current content."""
    fd, temp_name = tempfile.mkstemp(prefix=".nexus-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

        if path.is_symlink() or not path.is_file():
            raise PatchApplyError("target changed type during patch")

        if _sha256(path.read_bytes()) != expected_hash:
            raise PatchApplyError("target changed during patch")

        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _atomic_create(path: Path, data: bytes) -> None:
    """Create a new file without overwriting an existing path."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise PatchApplyError("create target already exists") from exc

    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _validate_envelope(envelope: Envelope) -> dict[str, Any]:
    if not isinstance(envelope, Envelope):
        raise PatchApplyError("a validated Envelope is required")
    if envelope.message_type is not MessageType.FILE_PATCH:
        raise PatchApplyError("message must be FILE_PATCH")
    return envelope.payload


def apply_patch(
    envelope: Envelope,
    *,
    workspace: str | os.PathLike[str],
    backup_root: str | os.PathLike[str],
    approved: bool = False,
) -> PatchResult:
    """Apply one approved FILE_PATCH with a separate per-file backup."""
    payload = _validate_envelope(envelope)
    if not approved:
        raise PatchApplyError("explicit approval is required")

    root = validate_workspace_root(workspace)
    backups = validate_workspace_root(backup_root)
    assert_workspaces_disjoint({"workspace": root, "backups": backups})

    operation = payload["operation"]
    relative = payload["path"]
    target = resolve_in_workspace(root, relative, for_write=True)

    if target == root:
        raise PatchApplyError("workspace root is not a file target")

    if not target.parent.is_dir():
        raise PatchApplyError("parent directory must already exist")

    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file():
            raise PatchApplyError("target must be a regular file")
        before = _read_regular_file(target)
    else:
        before = None

    expected = payload.get("base_sha256")

    if operation == "create":
        if before is not None:
            raise PatchApplyError("create target already exists")
        after = payload["content"].encode("utf-8")
    else:
        if before is None:
            raise PatchApplyError("target file does not exist")
        if _sha256(before) != expected:
            raise PatchApplyError("base SHA-256 mismatch")

        if operation == "delete":
            after = None
        elif operation == "modify":
            after = _parse_unified_diff(before, payload["diff"])
        else:
            raise PatchApplyError("unsupported patch operation")

    backup_dir = backups / payload["patch_id"]
    backup_dir.mkdir(parents=False, exist_ok=False)
    backup_file = backup_dir / "original.bin"

    if before is not None:
        try:
            with backup_file.open("xb") as stream:
                stream.write(before)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                backup_file.unlink()
            except FileNotFoundError:
                pass
            try:
                backup_dir.rmdir()
            except OSError:
                pass
            raise

    _write_manifest(
        backup_dir,
        patch_id=payload["patch_id"],
        operation=operation,
        path=relative,
        before_sha256=_sha256(before) if before is not None else None,
        after_sha256=_sha256(after) if after is not None else None,
    )

    try:
        if operation == "create":
            _atomic_create(target, after)
        elif operation == "delete":
            if target.is_symlink() or not target.is_file():
                raise PatchApplyError("target changed type before delete")
            if _sha256(target.read_bytes()) != expected:
                raise PatchApplyError("target changed before delete")
            target.unlink()
        else:
            if expected is None:
                raise PatchApplyError("modify requires a base SHA-256")
            if after is None:
                raise PatchApplyError("modify produced no output")
            _atomic_replace(target, after, expected)
    except Exception:
        if before is None:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        raise

    return PatchResult(
        patch_id=payload["patch_id"],
        operation=operation,
        path=relative,
        before_sha256=_sha256(before) if before is not None else None,
        after_sha256=_sha256(after) if after is not None else None,
        backup_path=str(backup_file) if before is not None else None,
    )


def rollback_patch(
    patch_id: str,
    *,
    workspace: str | os.PathLike[str],
    backup_root: str | os.PathLike[str],
    approved: bool = False,
) -> PatchResult:
    """Restore the original state of one previously applied patch."""
    if not approved:
        raise PatchApplyError("explicit approval is required")

    if not isinstance(patch_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", patch_id
    ):
        raise PatchApplyError("invalid patch ID")

    root = validate_workspace_root(workspace)
    backups = validate_workspace_root(backup_root)
    assert_workspaces_disjoint({"workspace": root, "backups": backups})

    backup_dir = backups / patch_id
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        raise PatchApplyError("backup directory not found")

    manifest_path = backup_dir / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PatchApplyError("backup manifest not found")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatchApplyError("invalid backup manifest") from exc

    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise PatchApplyError("unsupported backup manifest")
    if manifest.get("patch_id") != patch_id:
        raise PatchApplyError("backup patch ID mismatch")

    operation = manifest.get("operation")
    relative = manifest.get("path")
    before_hash = manifest.get("before_sha256")
    after_hash = manifest.get("after_sha256")

    if operation not in {"create", "modify", "delete"}:
        raise PatchApplyError("invalid backup operation")
    if not isinstance(relative, str):
        raise PatchApplyError("invalid backup path")
    for digest in (before_hash, after_hash):
        if digest is not None and (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise PatchApplyError("invalid backup hash")

    if operation == "create":
        if before_hash is not None or after_hash is None:
            raise PatchApplyError("invalid create manifest")
    elif operation == "delete":
        if before_hash is None or after_hash is not None:
            raise PatchApplyError("invalid delete manifest")
    elif before_hash is None or after_hash is None:
        raise PatchApplyError("invalid modify manifest")

    target = resolve_in_workspace(root, relative, for_write=True)
    if target == root or not target.parent.is_dir():
        raise PatchApplyError("invalid rollback target")

    if operation == "create":
        if target.is_symlink() or not target.is_file():
            raise PatchApplyError("created file is missing or changed type")
        if _sha256(target.read_bytes()) != after_hash:
            raise PatchApplyError("file changed since patch; rollback refused")
        target.unlink()
    else:
        backup_file = backup_dir / "original.bin"
        if backup_file.is_symlink() or not backup_file.is_file():
            raise PatchApplyError("original backup file not found")

        original = backup_file.read_bytes()
        if _sha256(original) != before_hash:
            raise PatchApplyError("original backup hash mismatch")

        if operation == "delete":
            if target.exists() or target.is_symlink():
                raise PatchApplyError("rollback target already exists")
            _atomic_create(target, original)
        else:
            if target.is_symlink() or not target.is_file():
                raise PatchApplyError("modified file is missing or changed type")
            if _sha256(target.read_bytes()) != after_hash:
                raise PatchApplyError("file changed since patch; rollback refused")
            _atomic_replace(target, original, after_hash)

    return PatchResult(
        patch_id=patch_id,
        operation=f"rollback_{operation}",
        path=relative,
        before_sha256=after_hash,
        after_sha256=before_hash,
        backup_path=str(backup_dir / "original.bin")
        if before_hash is not None
        else None,
    )
