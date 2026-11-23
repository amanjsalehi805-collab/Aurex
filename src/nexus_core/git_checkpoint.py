"""Git checkpoints and rollback that never touch the user's branch, HEAD or index.

A checkpoint is a commit of the whole working tree (tracked + untracked, honouring .gitignore)
stored under refs/nexus/checkpoints/<id>. It is built with a throw-away index file, so staged
changes, the current branch and HEAD are left exactly as they were.

Rollback is two-step: plan_rollback() lists exactly what would be restored/deleted; rollback()
only executes a plan, and only with confirm=True (the approval layer decides who may confirm).
Ignored files are never captured and never deleted.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .ids import new_id
from .paths import PathSecurityError, PROTECTED_NAMES, resolve_in_workspace, validate_relative_path

REF_PREFIX = "refs/nexus/checkpoints/"
_SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
_IDENTITY = {
    "GIT_AUTHOR_NAME": "nexus", "GIT_AUTHOR_EMAIL": "nexus@localhost",
    "GIT_COMMITTER_NAME": "nexus", "GIT_COMMITTER_EMAIL": "nexus@localhost",
}


class GitError(RuntimeError):
    pass


class NotARepository(GitError):
    pass


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    ref: str
    commit_sha: str
    label: str


@dataclass(frozen=True)
class RollbackPlan:
    checkpoint: Checkpoint
    restore: tuple[str, ...]  # paths whose content will be reset to the checkpoint
    delete: tuple[str, ...]   # files created after the checkpoint

    @property
    def is_empty(self) -> bool:
        return not self.restore and not self.delete


def _git(workspace: Path, *args: str, env: dict[str, str] | None = None,
         input_bytes: bytes | None = None) -> bytes:
    full_env = {k: v for k, v in os.environ.items()
                if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    full_env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
                     "GIT_LITERAL_PATHSPECS": "1", "GIT_CONFIG_NOSYSTEM": "1"})
    if env:
        full_env.update(env)
    cmd = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args]
    try:
        proc = subprocess.run(cmd, cwd=workspace, env=full_env, input=input_bytes,
                              capture_output=True, timeout=120, check=False)
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {args[0]} timed out") from exc
    if proc.returncode != 0:
        raise GitError(f"git {args[0]} failed ({proc.returncode}): {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def _root(workspace: str | os.PathLike[str]) -> Path:
    ws = Path(os.path.realpath(workspace))
    if not ws.is_dir():
        raise NotARepository("workspace does not exist")
    try:
        top = _git(ws, "rev-parse", "--show-toplevel").decode().strip()
    except GitError as exc:
        raise NotARepository("workspace is not a git repository") from exc
    if Path(os.path.realpath(top)) != ws:
        raise NotARepository("workspace must be the repository root, not a subdirectory")
    return ws


def _head(ws: Path) -> str | None:
    try:
        return _git(ws, "rev-parse", "--verify", "-q", "HEAD^{commit}").decode().strip()
    except GitError:
        return None


def _snapshot_tree(ws: Path) -> str:
    """Tree object of the current working tree, built in a temporary index."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": os.path.join(tmp, "index")}
        head = _head(ws)
        if head:
            _git(ws, "read-tree", head, env=env)
        _git(ws, "add", "-A", "--", ".", env=env)
        return _git(ws, "write-tree", env=env).decode().strip()


def create_checkpoint(workspace: str | os.PathLike[str], label: str) -> Checkpoint:
    ws = _root(workspace)
    clean = "".join(ch for ch in label if ch.isprintable())[:200] or "checkpoint"
    tree = _snapshot_tree(ws)
    head = _head(ws)
    args = ["commit-tree", tree, "-m", f"nexus checkpoint: {clean}"]
    if head:
        args += ["-p", head]
    sha = _git(ws, *args, env=_IDENTITY).decode().strip()
    cid = new_id()
    ref = REF_PREFIX + cid
    _git(ws, "update-ref", ref, sha)
    return Checkpoint(cid, ref, sha, clean)


def _verify(ws: Path, cp: Checkpoint) -> None:
    if not _SHA_RE.match(cp.commit_sha) or not cp.ref.startswith(REF_PREFIX):
        raise GitError("malformed checkpoint")
    resolved = _git(ws, "rev-parse", "--verify", "-q", cp.ref).decode().strip()
    if resolved != cp.commit_sha:
        raise GitError("checkpoint ref does not match recorded commit")


def plan_rollback(workspace: str | os.PathLike[str], cp: Checkpoint) -> RollbackPlan:
    ws = _root(workspace)
    _verify(ws, cp)
    now_tree = _snapshot_tree(ws)
    out = _git(ws, "diff-tree", "-r", "--no-renames", "-z", "--name-status", cp.commit_sha, now_tree)
    fields = out.split(b"\0")
    restore: list[str] = []
    delete: list[str] = []
    i = 0
    while i + 1 < len(fields):
        status, name = fields[i].decode(), fields[i + 1].decode("utf-8", "surrogateescape")
        i += 2
        # diff-tree compares checkpoint -> now: 'A' means the file exists now but not at checkpoint
        (delete if status == "A" else restore).append(name)
    return RollbackPlan(cp, tuple(sorted(restore)), tuple(sorted(delete)))


def _safe_unlink(ws: Path, rel: str) -> None:
    norm = validate_relative_path(rel)
    parent_rel = os.path.dirname(norm) or "."
    parent = resolve_in_workspace(ws, parent_rel, for_write=True, allow_root=True)
    if norm.split("/")[-1].lower() in PROTECTED_NAMES:
        raise PathSecurityError("refusing to delete protected path")
    target = parent / os.path.basename(norm)
    if target.is_symlink() or target.is_file():
        os.unlink(target)
    # prune directories emptied by the deletion, never above the workspace root
    current = parent
    while current != ws and current.is_dir() and not any(current.iterdir()):
        current.rmdir()
        current = current.parent


def rollback(workspace: str | os.PathLike[str], plan: RollbackPlan, *, confirm: bool) -> None:
    if confirm is not True:
        raise GitError("rollback requires explicit confirm=True")
    ws = _root(workspace)
    _verify(ws, plan.checkpoint)
    for rel in plan.delete:
        _safe_unlink(ws, rel)
    if plan.restore:
        for rel in plan.restore:
            resolve_in_workspace(ws, os.path.dirname(rel) or ".", for_write=True, allow_root=True)
        payload = b"\0".join(p.encode("utf-8", "surrogateescape") for p in plan.restore)
        _git(ws, "restore", f"--source={plan.checkpoint.commit_sha}", "--worktree",
             "--pathspec-from-file=-", "--pathspec-file-nul", input_bytes=payload)
    if not plan_rollback(ws, plan.checkpoint).is_empty:
        raise GitError("working tree does not match checkpoint after rollback")


def drop_checkpoint(workspace: str | os.PathLike[str], cp: Checkpoint) -> None:
    ws = _root(workspace)
    _verify(ws, cp)
    _git(ws, "update-ref", "-d", cp.ref)
