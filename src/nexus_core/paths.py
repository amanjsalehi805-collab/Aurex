"""Workspace confinement and path-traversal protection.

All paths that originate from an AI model, a message or a user are untrusted. They must pass
through validate_relative_path (lexical) and resolve_in_workspace (symlink-aware) before use.

Known limit (documented in docs/TRUST_MODEL.md): a path check followed by a later open() is
subject to symlink races. Phase 5 closes this by executing inside a container whose only mount is
the workspace, and by using dir-fd based opens for writes.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

# Directory names an AI-driven write may never touch (git hooks/config = code execution).
PROTECTED_NAMES = frozenset({".git"})
MAX_PATH_LEN = 4096

_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class PathSecurityError(ValueError):
    pass


def validate_relative_path(path: str, *, allow_root: bool = False) -> str:
    """Lexically validate an untrusted workspace-relative path and return it normalised."""
    if not isinstance(path, str) or not path:
        raise PathSecurityError("path must be a non-empty string")
    if len(path) > MAX_PATH_LEN:
        raise PathSecurityError("path too long")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in path):
        raise PathSecurityError("path contains control characters")
    if "\\" in path:
        raise PathSecurityError("backslashes are not allowed in paths")
    if path.startswith("/") or path.startswith("~") or _DRIVE_RE.match(path):
        raise PathSecurityError("absolute or home-relative paths are not allowed")
    parts = path.split("/")
    if any(part == ".." for part in parts):
        raise PathSecurityError("'..' segments are not allowed")
    cleaned = [part for part in parts if part not in ("", ".")]
    if not cleaned:
        if allow_root:
            return "."
        raise PathSecurityError("path must not refer to the workspace root itself")
    return "/".join(cleaned)


def _within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def validate_workspace_root(root: str | os.PathLike[str]) -> Path:
    real = Path(os.path.realpath(root))
    if not Path(root).is_absolute():
        raise PathSecurityError("workspace root must be an absolute path")
    if real == Path(real.anchor):
        raise PathSecurityError("filesystem root cannot be a workspace")
    if not real.is_dir():
        raise PathSecurityError("workspace root must be an existing directory")
    return real


def resolve_in_workspace(
    root: str | os.PathLike[str],
    relative: str,
    *,
    for_write: bool = False,
    allow_root: bool = False,
) -> Path:
    """Resolve an untrusted relative path inside root, following symlinks, or raise."""
    root_real = validate_workspace_root(root)
    normalised = validate_relative_path(relative, allow_root=allow_root)
    candidate = Path(os.path.realpath(root_real / normalised))
    if not _within(candidate, root_real):
        raise PathSecurityError("path escapes the workspace")
    if for_write:
        lexical_parts = [p.lower() for p in normalised.split("/")]
        resolved_parts = [p.lower() for p in candidate.relative_to(root_real).parts]
        if any(p in PROTECTED_NAMES for p in lexical_parts + resolved_parts):
            raise PathSecurityError("writing to protected paths (.git) is not allowed")
    return candidate


def assert_workspaces_disjoint(roots: Mapping[str, str | os.PathLike[str]]) -> None:
    """No project workspace may equal or contain another project's workspace."""
    real = {pid: Path(os.path.realpath(path)) for pid, path in roots.items()}
    items = list(real.items())
    for i, (pid_a, path_a) in enumerate(items):
        for pid_b, path_b in items[i + 1 :]:
            if _within(path_a, path_b) or _within(path_b, path_a):
                raise PathSecurityError(f"workspaces of projects {pid_a} and {pid_b} overlap")
