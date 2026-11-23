"""Execution limits and the sandbox command line derived from them.

Every execution carries explicit limits. Defaults are the safest values: no network, bounded
time/memory/CPU/processes/output, non-root, read-only root filesystem, no capabilities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .ids import is_valid_id
from .paths import PathSecurityError, validate_relative_path

MAX_TIMEOUT_SECONDS = 3600
MAX_MEMORY_MB = 8192
MAX_CPUS = 4.0
MAX_PIDS = 1024
MAX_OUTPUT_BYTES = 100 * 1024 * 1024

_HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")
_IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/:@-]{0,254}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_BAD_MOUNT_CHARS = re.compile(r"[,\n\r\x00=]")


class LimitsError(ValueError):
    pass


class UnsupportedInThisPhase(NotImplementedError):
    pass


@dataclass(frozen=True)
class NetworkPolicy:
    mode: str = "none"  # "none" | "scoped"
    allowed_hosts: tuple[str, ...] = ()
    approval_id: str | None = None

    def validate(self) -> None:
        if self.mode == "none":
            if self.allowed_hosts or self.approval_id is not None:
                raise LimitsError("network mode 'none' must not list hosts or an approval")
        elif self.mode == "scoped":
            if not self.allowed_hosts:
                raise LimitsError("scoped network requires an explicit host allow-list")
            for host in self.allowed_hosts:
                if host in ("*", "") or not _HOST_RE.match(host):
                    raise LimitsError(f"invalid allowed host: {host!r}")
            if not is_valid_id(self.approval_id):
                raise LimitsError("scoped network requires the id of a granted approval")
        else:
            raise LimitsError(f"unknown network mode: {self.mode!r}")


@dataclass(frozen=True)
class ExecutionLimits:
    timeout_seconds: int = 300
    memory_mb: int = 1024
    cpus: float = 1.0
    pids: int = 256
    max_output_bytes: int = 10 * 1024 * 1024
    filesystem: str = "workspace_rw"  # "workspace_rw" | "workspace_ro"
    network: NetworkPolicy = field(default_factory=NetworkPolicy)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        def ranged(name: str, value: Any, low: float, high: float) -> None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise LimitsError(f"{name} must be a number")
            if not (low <= value <= high):
                raise LimitsError(f"{name} must be between {low} and {high}")

        ranged("timeout_seconds", self.timeout_seconds, 1, MAX_TIMEOUT_SECONDS)
        ranged("memory_mb", self.memory_mb, 64, MAX_MEMORY_MB)
        ranged("cpus", self.cpus, 0.1, MAX_CPUS)
        ranged("pids", self.pids, 8, MAX_PIDS)
        ranged("max_output_bytes", self.max_output_bytes, 1024, MAX_OUTPUT_BYTES)
        if self.filesystem not in ("workspace_rw", "workspace_ro"):
            raise LimitsError("filesystem must be 'workspace_rw' or 'workspace_ro'")
        self.network.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "memory_mb": self.memory_mb,
            "cpus": self.cpus,
            "pids": self.pids,
            "max_output_bytes": self.max_output_bytes,
            "filesystem": self.filesystem,
            "network": {
                "mode": self.network.mode,
                "allowed_hosts": list(self.network.allowed_hosts),
                "approval_id": self.network.approval_id,
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionLimits":
        allowed = {"timeout_seconds", "memory_mb", "cpus", "pids", "max_output_bytes",
                   "filesystem", "network"}
        extra = set(data) - allowed
        if extra:
            raise LimitsError(f"unknown limit fields: {sorted(extra)}")
        kwargs = {k: v for k, v in data.items() if k != "network"}
        net = data.get("network")
        if net is not None:
            if set(net) - {"mode", "allowed_hosts", "approval_id"}:
                raise LimitsError("unknown network fields")
            kwargs["network"] = NetworkPolicy(
                mode=net.get("mode", "none"),
                allowed_hosts=tuple(net.get("allowed_hosts", ())),
                approval_id=net.get("approval_id"),
            )
        return cls(**kwargs)


def docker_run_args(
    limits: ExecutionLimits,
    *,
    image: str,
    workspace_host_path: str,
    container_name: str,
    cwd: str,
    command: Sequence[str],
) -> list[str]:
    """Build the `docker run` argv for a sandboxed execution. Pure function; does not run Docker.

    The wall-clock timeout is NOT a docker flag: the runner must enforce it (docker kill).
    """
    limits.validate()
    if limits.network.mode != "none":
        raise UnsupportedInThisPhase(
            "scoped network needs the egress-proxy network introduced in Phase 5"
        )
    if not _IMAGE_RE.match(image):
        raise LimitsError("invalid image reference")
    if not _NAME_RE.match(container_name):
        raise LimitsError("invalid container name")
    if not workspace_host_path.startswith("/") or _BAD_MOUNT_CHARS.search(workspace_host_path):
        raise LimitsError("workspace path must be absolute and free of ',' '=' and newlines")
    try:
        rel = validate_relative_path(cwd, allow_root=True)
    except PathSecurityError as exc:
        raise LimitsError(f"invalid cwd: {exc}") from exc
    if not command or any(not isinstance(c, str) or "\x00" in c for c in command):
        raise LimitsError("command must be a non-empty argv list")

    mem = f"{limits.memory_mb}m"
    mount = f"type=bind,source={workspace_host_path},target=/workspace"
    if limits.filesystem == "workspace_ro":
        mount += ",readonly"
    workdir = "/workspace" if rel == "." else f"/workspace/{rel}"
    return [
        "docker", "run", "--rm", "--init",
        "--name", container_name,
        "--network", "none",
        "--memory", mem, "--memory-swap", mem,
        "--cpus", str(limits.cpus),
        "--pids-limit", str(limits.pids),
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "10001:10001",
        "--mount", mount,
        "--workdir", workdir,
        image,
        *command,
    ]
