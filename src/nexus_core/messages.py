"""Structured message protocol (version 1).

Every inter-component message is an Envelope with a typed, strictly validated payload.
An invalid Envelope cannot be constructed. Validation covers:
  * exact field sets (unknown fields are rejected, not ignored),
  * per-type payload schemas,
  * provenance: which kind of sender may emit which message type,
  * routing: AI output may only reach the orchestrator, never an executor directly,
  * cross-field consistency (e.g. exit code vs status).

`source` is a CLAIM made inside the message. The transport layer (Phase 2/3) must overwrite or
verify it from the authenticated channel; never trust it by itself.
"""

from __future__ import annotations

import copy
import enum
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .clock import format_ts, is_valid_ts, parse_ts, utc_now
from .ids import is_valid_id, new_id
from .limits import MAX_TIMEOUT_SECONDS
from .outcomes import ExecutionStatus, OutcomeError, validate_outcome
from .paths import PathSecurityError, validate_relative_path
from .states import TaskState

PROTOCOL_VERSION = 1
MAX_ENVELOPE_BYTES = 1_048_576
MAX_SHORT = 4096
MAX_TEXT = 900_000
MAX_CHUNK = 65_536


class ProtocolError(ValueError):
    pass


class MessageType(str, enum.Enum):
    AI_REQUEST = "AI_REQUEST"
    AI_RESPONSE = "AI_RESPONSE"
    CODE_BLOCK = "CODE_BLOCK"
    SHELL_COMMAND = "SHELL_COMMAND"
    FILE_PATCH = "FILE_PATCH"
    TERMINAL_STDOUT = "TERMINAL_STDOUT"
    TERMINAL_STDERR = "TERMINAL_STDERR"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    TEST_RESULT = "TEST_RESULT"
    APPROVAL_REQUEST = "APPROVAL_REQUEST"
    APPROVAL_RESPONSE = "APPROVAL_RESPONSE"
    ERROR_REPORT = "ERROR_REPORT"
    TASK_STATUS = "TASK_STATUS"


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    FAILED = "failed"
    REJECTED = "rejected"


RISK_CATEGORIES = (
    "delete_files", "destructive_command", "overwrite_work", "git_history", "git_push",
    "deploy", "publish_package", "production_database", "credentials", "outside_workspace",
    "system_install", "elevated_privileges", "broad_access", "network_access", "clarification",
)
CODE_PURPOSES = ("source_file", "config_file", "test_file", "snippet_only")
SHELL_TARGETS = ("cloud", "local")


# --------------------------------------------------------------------------- field checking
_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ENDPOINT_RE = re.compile(r"^(user|worker|device|ai|orchestrator|system)(:[A-Za-z0-9._-]{1,64})?$")


def _fail(path: str, message: str) -> None:
    raise ProtocolError(f"{path}: {message}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _text(value: Any, path: str, limit: int, *, allow_empty: bool) -> None:
    if not isinstance(value, str):
        _fail(path, "must be a string")
    if not allow_empty and not value:
        _fail(path, "must not be empty")
    if len(value) > limit:
        _fail(path, f"longer than {limit} characters")
    if "\x00" in value:
        _fail(path, "must not contain NUL")


def _check(kind: str, value: Any, path: str) -> None:
    if kind.endswith("?"):
        if value is None:
            return
        kind = kind[:-1]
    if kind == "str":
        _text(value, path, MAX_SHORT, allow_empty=True)
    elif kind == "ne_str":
        _text(value, path, MAX_SHORT, allow_empty=False)
    elif kind == "text":
        _text(value, path, MAX_TEXT, allow_empty=True)
    elif kind == "chunk":
        _text(value, path, MAX_CHUNK, allow_empty=True)
    elif kind == "id":
        if not is_valid_id(value):
            _fail(path, "must be a canonical UUIDv4")
    elif kind == "key":
        if not isinstance(value, str) or not _KEY_RE.match(value):
            _fail(path, "must be 8-128 chars of [A-Za-z0-9._:-]")
    elif kind == "sha":
        if not isinstance(value, str) or not _SHA_RE.match(value):
            _fail(path, "must be a lowercase hex SHA-256")
    elif kind == "uint":
        if not _is_int(value) or value < 0:
            _fail(path, "must be a non-negative integer")
    elif kind == "int":
        if not _is_int(value):
            _fail(path, "must be an integer")
    elif kind == "bool":
        if not isinstance(value, bool):
            _fail(path, "must be a boolean")
    elif kind == "ts":
        if not is_valid_ts(value):
            _fail(path, "must be a UTC timestamp YYYY-MM-DDTHH:MM:SS.ffffffZ")
    elif kind in ("path", "cwd"):
        if not isinstance(value, str):
            _fail(path, "must be a string")
        try:
            validate_relative_path(value, allow_root=(kind == "cwd"))
        except PathSecurityError as exc:
            _fail(path, str(exc))
    elif kind == "list_str":
        if not isinstance(value, list) or len(value) > 1000:
            _fail(path, "must be a list of at most 1000 strings")
        for i, item in enumerate(value):
            _text(item, f"{path}[{i}]", MAX_SHORT, allow_empty=False)
    elif kind == "dict":
        if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
            _fail(path, "must be an object")
    elif kind.startswith("enum:"):
        if not isinstance(value, str) or value not in kind[5:].split("|"):
            _fail(path, f"must be one of {kind[5:].split('|')}")
    else:  # pragma: no cover - programming error
        raise AssertionError(f"unknown kind {kind}")


@dataclass(frozen=True)
class PayloadSpec:
    required: Mapping[str, str]
    optional: Mapping[str, str] = field(default_factory=dict)
    cross: Callable[[dict[str, Any]], None] | None = None


def _enum(*values: str) -> str:
    return "enum:" + "|".join(values)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- cross-field rules
def _x_ai_request(p: dict[str, Any]) -> None:
    if p["redacted"] is not True:
        _fail("payload.redacted", "AI requests must be built from redacted content (must be true)")


def _x_code(p: dict[str, Any]) -> None:
    dest = p["destination_path"]
    if p["purpose"] == "snippet_only":
        if dest is not None:
            _fail("payload.destination_path", "snippet_only blocks must have destination_path null")
    elif dest is None:
        _fail("payload.destination_path", f"required for purpose {p['purpose']}")
    if "content_sha256" in p and p["content_sha256"] != _sha256_text(p["content"]):
        _fail("payload.content_sha256", "does not match content")


def _x_shell(p: dict[str, Any]) -> None:
    if not 1 <= p["timeout_seconds"] <= MAX_TIMEOUT_SECONDS:
        _fail("payload.timeout_seconds", f"must be between 1 and {MAX_TIMEOUT_SECONDS}")
    scoped = p["network"] == "scoped"
    if scoped and "approval_id" not in p:
        _fail("payload.approval_id", "scoped network requires an approval_id")
    if not scoped and "approval_id" in p:
        _fail("payload.approval_id", "only valid with network 'scoped'")


def _x_patch(p: dict[str, Any]) -> None:
    op = p["operation"]
    has = {k: k in p for k in ("diff", "content", "base_sha256")}
    if op == "modify":
        if not (has["diff"] and has["base_sha256"]) or has["content"]:
            _fail("payload", "modify requires diff and base_sha256, and forbids content")
    elif op == "create":
        if not has["content"] or has["diff"] or has["base_sha256"]:
            _fail("payload", "create requires content only")
    else:  # delete
        if not has["base_sha256"] or has["diff"] or has["content"]:
            _fail("payload", "delete requires base_sha256 only")


def _x_result(p: dict[str, Any]) -> None:
    try:
        validate_outcome(
            p["status"], p["exit_code"], started_at=p["started_at"], finished_at=p["finished_at"]
        )
    except OutcomeError as exc:
        _fail("payload", str(exc))
    if p["started_at"] and p["finished_at"] and parse_ts(p["finished_at"]) < parse_ts(p["started_at"]):
        _fail("payload.finished_at", "is before started_at")


def _x_test(p: dict[str, Any]) -> None:
    if p["status"] == "passed" and (p["exit_code"] != 0 or p["failed"] != 0):
        _fail("payload.status", "passed requires exit_code 0 and zero failures")
    if p["status"] == "failed" and p["exit_code"] == 0 and p["failed"] == 0:
        _fail("payload.status", "failed requires a non-zero exit_code or failures")
    if p["status"] == "not_run" and p["exit_code"] is not None:
        _fail("payload.exit_code", "not_run must have no exit_code")


_TASK_STATES = _enum(*(s.value for s in TaskState))
_EXEC_STATUS = _enum(*(s.value for s in ExecutionStatus))

PAYLOAD_SPECS: dict[MessageType, PayloadSpec] = {
    MessageType.AI_REQUEST: PayloadSpec(
        {"provider": "ne_str", "model": "ne_str", "purpose": "ne_str",
         "context_message_ids": "list_str", "redacted": "bool"},
        cross=_x_ai_request,
    ),
    MessageType.AI_RESPONSE: PayloadSpec(
        {"provider": "ne_str", "model": "ne_str", "text": "text"},
        {"stop_reason": "str", "usage": "dict", "request_id": "str"},
    ),
    MessageType.CODE_BLOCK: PayloadSpec(
        {"block_id": "id", "language": "ne_str", "purpose": _enum(*CODE_PURPOSES),
         "destination_path": "path?", "content": "text"},
        {"content_sha256": "sha"},
        _x_code,
    ),
    MessageType.SHELL_COMMAND: PayloadSpec(
        {"command_id": "id", "command": "ne_str", "cwd": "cwd", "target": _enum(*SHELL_TARGETS),
         "timeout_seconds": "uint", "idempotency_key": "key", "purpose": "ne_str",
         "network": _enum("none", "scoped")},
        {"approval_id": "id"},
        _x_shell,
    ),
    MessageType.FILE_PATCH: PayloadSpec(
        {"patch_id": "id", "path": "path", "operation": _enum("modify", "create", "delete")},
        {"diff": "text", "content": "text", "base_sha256": "sha"},
        _x_patch,
    ),
    MessageType.TERMINAL_STDOUT: PayloadSpec(
        {"execution_id": "id", "command_id": "id", "seq": "uint", "data": "chunk"}
    ),
    MessageType.TERMINAL_STDERR: PayloadSpec(
        {"execution_id": "id", "command_id": "id", "seq": "uint", "data": "chunk"}
    ),
    MessageType.EXECUTION_RESULT: PayloadSpec(
        {"execution_id": "id", "command_id": "id", "status": _EXEC_STATUS, "exit_code": "int?",
         "started_at": "ts?", "finished_at": "ts?", "duration_ms": "uint?", "cwd": "cwd",
         "target": _enum(*SHELL_TARGETS), "stdout_chunks": "uint", "stderr_chunks": "uint",
         "output_truncated": "bool"},
        cross=_x_result,
    ),
    MessageType.TEST_RESULT: PayloadSpec(
        {"execution_id": "id", "runner": "ne_str", "status": _enum("passed", "failed", "error", "not_run"),
         "exit_code": "int?", "passed": "uint", "failed": "uint", "skipped": "uint"},
        cross=_x_test,
    ),
    MessageType.APPROVAL_REQUEST: PayloadSpec(
        {"approval_id": "id", "risk_category": _enum(*RISK_CATEGORIES), "action": "ne_str",
         "affected": "list_str", "reason": "ne_str", "consequences": "ne_str",
         "action_sha256": "sha"},
        {"expires_at": "ts"},
    ),
    MessageType.APPROVAL_RESPONSE: PayloadSpec(
        {"approval_id": "id", "decision": _enum("approved", "rejected"), "decided_by": "ne_str"},
        {"comment": "str"},
    ),
    MessageType.ERROR_REPORT: PayloadSpec(
        {"code": "ne_str", "message": "ne_str", "retryable": "bool"}, {"details": "dict"}
    ),
    MessageType.TASK_STATUS: PayloadSpec(
        {"state": _TASK_STATES}, {"previous_state": _TASK_STATES, "reason": "str", "iteration": "uint"}
    ),
}

# Who may emit what (provenance). AI is only ever a *proposer*; it can never emit results,
# terminal output, approvals, or status.
ALLOWED_SOURCES: dict[MessageType, frozenset[str]] = {
    MessageType.AI_REQUEST: frozenset({"orchestrator"}),
    MessageType.AI_RESPONSE: frozenset({"ai"}),
    MessageType.CODE_BLOCK: frozenset({"ai", "user", "orchestrator"}),
    MessageType.SHELL_COMMAND: frozenset({"ai", "user", "orchestrator"}),
    MessageType.FILE_PATCH: frozenset({"ai", "user", "orchestrator"}),
    MessageType.TERMINAL_STDOUT: frozenset({"worker", "device"}),
    MessageType.TERMINAL_STDERR: frozenset({"worker", "device"}),
    MessageType.EXECUTION_RESULT: frozenset({"worker", "device"}),
    MessageType.TEST_RESULT: frozenset({"worker", "device"}),
    MessageType.APPROVAL_REQUEST: frozenset({"orchestrator", "system"}),
    MessageType.APPROVAL_RESPONSE: frozenset({"user"}),
    MessageType.ERROR_REPORT: frozenset({"worker", "device", "orchestrator", "system"}),
    MessageType.TASK_STATUS: frozenset({"orchestrator", "system"}),
}

NEEDS_CORRELATION = frozenset({
    MessageType.TERMINAL_STDOUT, MessageType.TERMINAL_STDERR, MessageType.EXECUTION_RESULT,
    MessageType.TEST_RESULT, MessageType.APPROVAL_RESPONSE,
})
_EXECUTABLE = frozenset({MessageType.SHELL_COMMAND, MessageType.FILE_PATCH, MessageType.CODE_BLOCK})
_TO_ORCHESTRATOR = frozenset({
    MessageType.AI_RESPONSE, MessageType.TERMINAL_STDOUT, MessageType.TERMINAL_STDERR,
    MessageType.EXECUTION_RESULT, MessageType.TEST_RESULT, MessageType.APPROVAL_RESPONSE,
})


def validate_payload(message_type: MessageType, payload: Any) -> None:
    spec = PAYLOAD_SPECS[message_type]
    if not isinstance(payload, dict):
        _fail("payload", "must be an object")
    known = set(spec.required) | set(spec.optional)
    for key in payload:
        if key not in known:
            _fail(f"payload.{key}", "unknown field")
    for key, kind in spec.required.items():
        if key not in payload:
            _fail(f"payload.{key}", "missing required field")
        _check(kind, payload[key], f"payload.{key}")
    for key, kind in spec.optional.items():
        if key in payload:
            _check(kind, payload[key], f"payload.{key}")
    if spec.cross is not None:
        spec.cross(payload)


def endpoint_kind(endpoint: str) -> str:
    return endpoint.split(":", 1)[0]


def _check_routing(mt: MessageType, source: str, destination: str) -> None:
    src, dst = endpoint_kind(source), endpoint_kind(destination)
    if src not in ALLOWED_SOURCES[mt]:
        _fail("source", f"{src!r} may not emit {mt.value}")
    if mt in _EXECUTABLE:
        if src == "orchestrator":
            if dst not in ("worker", "device"):
                _fail("destination", f"{mt.value} from the orchestrator must go to a worker or device")
        elif dst != "orchestrator":
            _fail("destination", f"{mt.value} from {src!r} may only be sent to the orchestrator")
    elif mt in _TO_ORCHESTRATOR and dst != "orchestrator":
        _fail("destination", f"{mt.value} must be addressed to the orchestrator")
    elif mt is MessageType.AI_REQUEST and dst != "ai":
        _fail("destination", "AI_REQUEST must be addressed to an AI provider")
    elif mt is MessageType.APPROVAL_REQUEST and dst != "user":
        _fail("destination", "APPROVAL_REQUEST must be addressed to a user")
    elif mt is MessageType.ERROR_REPORT and dst not in ("orchestrator", "user"):
        _fail("destination", "ERROR_REPORT must be addressed to the orchestrator or a user")
    elif mt is MessageType.TASK_STATUS and dst not in ("orchestrator", "user"):
        _fail("destination", "TASK_STATUS must be addressed to the orchestrator or a user")


# --------------------------------------------------------------------------- JSON helpers
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ProtocolError(f"non-finite number not allowed: {name}")


_ENVELOPE_KEYS = (
    "protocol_version", "message_id", "task_id", "project_id", "session_id", "message_type",
    "source", "destination", "timestamp", "payload", "correlation_id", "status",
)


@dataclass(frozen=True)
class Envelope:
    message_id: str
    task_id: str
    project_id: str
    session_id: str
    message_type: MessageType
    source: str
    destination: str
    timestamp: str
    payload: dict[str, Any]
    correlation_id: str | None = None
    status: MessageStatus = MessageStatus.PENDING
    protocol_version: int = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "message_type", MessageType(self.message_type))
            object.__setattr__(self, "status", MessageStatus(self.status))
        except ValueError as exc:
            raise ProtocolError(str(exc)) from exc
        object.__setattr__(self, "payload", copy.deepcopy(self.payload))
        if self.protocol_version != PROTOCOL_VERSION or not _is_int(self.protocol_version):
            _fail("protocol_version", f"unsupported (expected {PROTOCOL_VERSION})")
        for name in ("message_id", "task_id", "project_id", "session_id"):
            if not is_valid_id(getattr(self, name)):
                _fail(name, "must be a canonical UUIDv4")
        if self.correlation_id is not None and not is_valid_id(self.correlation_id):
            _fail("correlation_id", "must be a canonical UUIDv4 or null")
        for name in ("source", "destination"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _ENDPOINT_RE.match(value):
                _fail(name, "must look like 'kind' or 'kind:id' with kind in "
                            "user|worker|device|ai|orchestrator|system")
        if not is_valid_ts(self.timestamp):
            _fail("timestamp", "must be a UTC timestamp YYYY-MM-DDTHH:MM:SS.ffffffZ")
        if self.message_type in NEEDS_CORRELATION and self.correlation_id is None:
            _fail("correlation_id", f"required for {self.message_type.value}")
        _check_routing(self.message_type, self.source, self.destination)
        validate_payload(self.message_type, self.payload)

    # ---- construction
    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        project_id: str,
        session_id: str,
        message_type: MessageType,
        source: str,
        destination: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        message_id: str | None = None,
        timestamp: str | None = None,
    ) -> "Envelope":
        return cls(
            message_id=message_id or new_id(),
            task_id=task_id,
            project_id=project_id,
            session_id=session_id,
            message_type=message_type,
            source=source,
            destination=destination,
            timestamp=timestamp or format_ts(utc_now()),
            payload=payload,
            correlation_id=correlation_id,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "Envelope":
        if not isinstance(data, dict):
            _fail("envelope", "must be an object")
        keys = set(data)
        for missing in sorted(set(_ENVELOPE_KEYS) - keys):
            _fail(missing, "missing required field")
        for extra in sorted(keys - set(_ENVELOPE_KEYS)):
            _fail(extra, "unknown field")
        return cls(
            protocol_version=data["protocol_version"],
            message_id=data["message_id"],
            task_id=data["task_id"],
            project_id=data["project_id"],
            session_id=data["session_id"],
            message_type=data["message_type"],
            source=data["source"],
            destination=data["destination"],
            timestamp=data["timestamp"],
            payload=data["payload"],
            correlation_id=data["correlation_id"],
            status=data["status"],
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> "Envelope":
        if len(raw) > MAX_ENVELOPE_BYTES:
            _fail("envelope", f"larger than {MAX_ENVELOPE_BYTES} bytes")
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            data = json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
        except (ValueError, UnicodeDecodeError) as exc:
            if isinstance(exc, ProtocolError):
                raise
            raise ProtocolError(f"invalid JSON: {exc}") from exc
        return cls.from_dict(data)

    # ---- serialisation
    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "message_id": self.message_id,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "message_type": self.message_type.value,
            "source": self.source,
            "destination": self.destination,
            "timestamp": self.timestamp,
            "payload": copy.deepcopy(self.payload),
            "correlation_id": self.correlation_id,
            "status": self.status.value,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def payload_sha256(self) -> str:
        return _sha256_text(canonical_json(self.payload))
