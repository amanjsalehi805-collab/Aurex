# Message protocol v1 (exact definition: `src/nexus_core/messages.py`)

## Envelope (all 12 fields required; unknown fields rejected)
`protocol_version`(=1) `message_id` `task_id` `project_id` `session_id` (UUIDv4) `message_type`
`source` `destination` (`kind` or `kind:id`, kind in user|worker|device|ai|orchestrator|system)
`timestamp` (`YYYY-MM-DDTHH:MM:SS.ffffffZ`) `payload` `correlation_id` (UUIDv4 or null) `status`
(pending|delivered|processed|failed|rejected). Max 1 MiB; JSON with duplicate keys / NaN / Infinity
is rejected. An invalid Envelope cannot be constructed. `owner_id` is deliberately not in the
envelope: it is derived from authentication, never from message content.

## Payloads (all fields required unless marked optional; unknown fields rejected)
| Type | Fields |
|---|---|
| AI_REQUEST | provider, model, purpose, context_message_ids[], redacted (must be true) |
| AI_RESPONSE | provider, model, text; opt: stop_reason, usage, request_id |
| CODE_BLOCK | block_id, language, purpose (source_file/config_file/test_file/snippet_only), destination_path (path or null), content; opt content_sha256 |
| SHELL_COMMAND | command_id, command, cwd, target (cloud/local - explicit), timeout_seconds (1..3600), idempotency_key, purpose, network (none/scoped); opt approval_id (only with scoped) |
| FILE_PATCH | patch_id, path, operation (modify: diff+base_sha256 / create: content / delete: base_sha256) |
| TERMINAL_STDOUT / STDERR | execution_id, command_id, seq, data |
| EXECUTION_RESULT | execution_id, command_id, status, exit_code, started_at, finished_at, duration_ms, cwd, target, stdout_chunks, stderr_chunks, output_truncated |
| TEST_RESULT | execution_id, runner, status (passed/failed/error/not_run), exit_code, passed, failed, skipped |
| APPROVAL_REQUEST | approval_id, risk_category (15 values), action, affected[], reason, consequences, action_sha256; opt expires_at |
| APPROVAL_RESPONSE | approval_id, decision (approved/rejected), decided_by; opt comment |
| ERROR_REPORT | code, message, retryable; opt details |
| TASK_STATUS | state; opt previous_state, reason, iteration |

## Separation guarantees (each has tests)
* Code, commands and output have different types with disjoint field sets: a code block cannot carry
  `command`; terminal output cannot be parsed as a patch; code payload under a shell type is rejected.
* A code block names its language, purpose and destination; `snippet_only` must have no destination.
* A command must name its target explicitly (`auto` is rejected) and a `cwd` that cannot escape.
* Success is defined by exit status only; `succeeded` with exit != 0, `failed` with exit 0,
  `unknown`/`not_executed` with an exit code are all rejected. Truncation must be declared.

## Provenance and routing
| Message | Allowed senders | Allowed destination |
|---|---|---|
| AI_RESPONSE | ai | orchestrator |
| CODE_BLOCK, SHELL_COMMAND, FILE_PATCH | ai, user (proposals) | orchestrator only |
| same, dispatch | orchestrator | worker or device |
| TERMINAL_*, EXECUTION_RESULT, TEST_RESULT | worker, device | orchestrator |
| APPROVAL_REQUEST | orchestrator, system | user |
| APPROVAL_RESPONSE | **user only** | orchestrator |
The model can only *propose*; it can never emit results, output, approvals or status, and its output
can never reach an executor without passing through the orchestrator. `source` inside a message is a
claim; the transport must verify it from the authenticated channel (Phase 2/3).
