"""Task state machine definition (pure data + validation, no I/O)."""

from __future__ import annotations

import enum


class InvalidTransition(ValueError):
    pass


class TaskState(str, enum.Enum):
    RECEIVE_TASK = "RECEIVE_TASK"
    IDENTIFY_PROJECT = "IDENTIFY_PROJECT"
    LOAD_CONTEXT = "LOAD_CONTEXT"
    ANALYZE_REQUIREMENTS = "ANALYZE_REQUIREMENTS"
    CREATE_PLAN = "CREATE_PLAN"
    REQUEST_APPROVAL_IF_NEEDED = "REQUEST_APPROVAL_IF_NEEDED"
    GENERATE_CHANGES = "GENERATE_CHANGES"
    VALIDATE_CHANGES = "VALIDATE_CHANGES"
    APPLY_CHANGES = "APPLY_CHANGES"
    EXECUTE_COMMANDS = "EXECUTE_COMMANDS"
    COLLECT_OUTPUT = "COLLECT_OUTPUT"
    ANALYZE_RESULTS = "ANALYZE_RESULTS"
    RETURN_RESULTS_TO_AI = "RETURN_RESULTS_TO_AI"
    CONTINUE_OR_RETRY = "CONTINUE_OR_RETRY"
    RUN_FINAL_TESTS = "RUN_FINAL_TESTS"
    GENERATE_COMPLETION_REPORT = "GENERATE_COMPLETION_REPORT"
    # Suspended states remember the state to return to (tasks.resume_state).
    PAUSED = "PAUSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    # Terminal states.
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


S = TaskState
SUSPENDED = frozenset({S.PAUSED, S.WAITING_APPROVAL})
TERMINAL = frozenset({S.COMPLETED, S.FAILED, S.CANCELLED})
ACTIVE = frozenset(set(TaskState) - SUSPENDED - TERMINAL)

_FORWARD: dict[TaskState, frozenset[TaskState]] = {
    S.RECEIVE_TASK: frozenset({S.IDENTIFY_PROJECT}),
    S.IDENTIFY_PROJECT: frozenset({S.LOAD_CONTEXT}),
    S.LOAD_CONTEXT: frozenset({S.ANALYZE_REQUIREMENTS}),
    S.ANALYZE_REQUIREMENTS: frozenset({S.CREATE_PLAN}),
    S.CREATE_PLAN: frozenset({S.REQUEST_APPROVAL_IF_NEEDED}),
    S.REQUEST_APPROVAL_IF_NEEDED: frozenset({S.GENERATE_CHANGES}),
    S.GENERATE_CHANGES: frozenset({S.VALIDATE_CHANGES}),
    S.VALIDATE_CHANGES: frozenset({S.APPLY_CHANGES, S.GENERATE_CHANGES}),
    S.APPLY_CHANGES: frozenset({S.EXECUTE_COMMANDS}),
    S.EXECUTE_COMMANDS: frozenset({S.COLLECT_OUTPUT}),
    S.COLLECT_OUTPUT: frozenset({S.ANALYZE_RESULTS}),
    S.ANALYZE_RESULTS: frozenset({S.RETURN_RESULTS_TO_AI}),
    S.RETURN_RESULTS_TO_AI: frozenset({S.CONTINUE_OR_RETRY}),
    S.CONTINUE_OR_RETRY: frozenset({S.GENERATE_CHANGES, S.EXECUTE_COMMANDS, S.RUN_FINAL_TESTS}),
    S.RUN_FINAL_TESTS: frozenset({S.GENERATE_COMPLETION_REPORT, S.CONTINUE_OR_RETRY}),
    S.GENERATE_COMPLETION_REPORT: frozenset({S.COMPLETED}),
}


def allowed_transitions(
    state: TaskState, resume_state: TaskState | None = None
) -> frozenset[TaskState]:
    if state in TERMINAL:
        return frozenset()
    if state in SUSPENDED:
        if resume_state is None or resume_state not in ACTIVE:
            raise InvalidTransition("suspended state requires an active resume_state")
        return frozenset({resume_state, S.CANCELLED, S.FAILED})
    return _FORWARD[state] | SUSPENDED | {S.CANCELLED, S.FAILED}


def check_transition(
    src: TaskState, dst: TaskState, resume_state: TaskState | None = None
) -> None:
    if dst not in allowed_transitions(src, resume_state):
        raise InvalidTransition(f"{src.value} -> {dst.value} is not allowed")
