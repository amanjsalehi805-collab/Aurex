"""Single source of truth for what an execution outcome may look like.

Used by the message protocol, the agent journal and mirrored by SQL CHECK constraints.
Success is defined ONLY by exit status, never by what the output text says.
"""

from __future__ import annotations

import enum


class OutcomeError(ValueError):
    pass


class ExecutionStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    NOT_EXECUTED = "not_executed"
    UNKNOWN = "unknown"


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_outcome(
    status: ExecutionStatus | str,
    exit_code: int | None,
    *,
    started_at: str | None,
    finished_at: str | None,
) -> ExecutionStatus:
    try:
        st = ExecutionStatus(status)
    except ValueError as exc:
        raise OutcomeError(f"unknown execution status: {status!r}") from exc
    if exit_code is not None and not (_is_int(exit_code) and -(2**31) <= exit_code < 2**31):
        raise OutcomeError("exit_code must be a 32-bit integer or None")

    if st is ExecutionStatus.SUCCEEDED:
        if exit_code != 0:
            raise OutcomeError("succeeded requires exit_code == 0")
        if started_at is None or finished_at is None:
            raise OutcomeError("succeeded requires started_at and finished_at")
    elif st is ExecutionStatus.FAILED:
        if exit_code is None or exit_code == 0:
            raise OutcomeError("failed requires a non-zero exit_code")
        if started_at is None or finished_at is None:
            raise OutcomeError("failed requires started_at and finished_at")
    elif st is ExecutionStatus.TIMED_OUT:
        if started_at is None:
            raise OutcomeError("timed_out requires started_at")
    elif st is ExecutionStatus.NOT_EXECUTED:
        if exit_code is not None or started_at is not None:
            raise OutcomeError("not_executed must have no exit_code and no started_at")
    elif st is ExecutionStatus.UNKNOWN:
        if exit_code is not None:
            raise OutcomeError("unknown must not claim an exit_code")
    return st
