"""Validated local workspace configuration for AUREX."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from nexus_core.paths import (
    PathSecurityError,
    assert_workspaces_disjoint,
    validate_workspace_root,
)

NEXUS_ROOT = Path(__file__).resolve().parents[2]
AUREX_ROOT = Path("/storage/emulated/0/Download/aurex/aurex")
BACKUP_ROOT = NEXUS_ROOT / "backups" / "aurex"


class WorkspaceConfigError(RuntimeError):
    """A configured workspace is unsafe or unavailable."""


@dataclass(frozen=True)
class WorkspaceConfig:
    nexus_root: Path
    aurex_root: Path
    backup_root: Path


def get_aurex_workspace_config() -> WorkspaceConfig:
    try:
        nexus = validate_workspace_root(NEXUS_ROOT)
        aurex = validate_workspace_root(AUREX_ROOT)
        assert_workspaces_disjoint({"nexus": nexus, "aurex": aurex})

        result = subprocess.run(
            [
                "git",
                "-c", f"safe.directory={aurex}",
                "-C", str(aurex),
                "rev-parse", "--show-toplevel",
            ],
            check=True, capture_output=True, text=True, timeout=10,
        )
        if Path(result.stdout.strip()).resolve() != aurex:
            raise WorkspaceConfigError("AUREX path is not the Git repository root")

        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        backup = validate_workspace_root(BACKUP_ROOT)
        if backup == nexus or nexus not in backup.parents:
            raise WorkspaceConfigError("Backup must remain inside NEXUS")
        assert_workspaces_disjoint({"aurex": aurex, "backup": backup})
        return WorkspaceConfig(nexus, aurex, backup)
    except (OSError, subprocess.SubprocessError, PathSecurityError) as exc:
        raise WorkspaceConfigError(f"AUREX workspace validation failed: {exc}") from exc


def apply_aurex_patch(envelope, *, approved: bool = False):
    from nexus_core.patch_apply import apply_patch
    config = get_aurex_workspace_config()
    return apply_patch(
        envelope, workspace=config.aurex_root,
        backup_root=config.backup_root, approved=approved,
    )


def rollback_aurex_patch(patch_id: str, *, approved: bool = False):
    from nexus_core.patch_apply import rollback_patch
    config = get_aurex_workspace_config()
    return rollback_patch(
        patch_id, workspace=config.aurex_root,
        backup_root=config.backup_root, approved=approved,
    )
