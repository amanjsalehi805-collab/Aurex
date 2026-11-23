# Phase 1 architecture

## Scope
Phase 1 builds the contract everything else depends on. Nothing here talks to the network, an AI
provider, Docker or Android. Later phases plug into these modules rather than redefine them.

## Stack decisions (approved)
| Concern | Choice | Why / trade-off |
|---|---|---|
| Language | Python >= 3.11, stdlib-only core | Fast to build, best AI SDKs; zero supply-chain surface in the safety core. Go would be leaner but slower to iterate. |
| DB (orchestrator, Phase 2+) | PostgreSQL | Concurrency, row-level security later. |
| DB (agent journal, tests, reference) | SQLite | Runs in Termux; Phase 1 verified here. |
| Schema style | Portable SQL subset + `.sqlite.sql` dialect files | Keeps VPS->managed-cloud migration cheap. **Postgres is not yet exercised** (Phase 2 CI job). |
| Cloud workers | One Docker container per job, no network by default | Command builder in `limits.py`; execution arrives in Phase 5. |

## Directory structure
```
nexus/
  pyproject.toml  Makefile  README.md  .gitignore
  .github/workflows/ci.yml        tests (py3.11/3.12), lint, mutation gate
  tools/mutation_check.py         deliberate-fault harness
  docs/                           this folder
  src/nexus_core/
    ids.py clock.py               UUIDv4 ids; fixed-width UTC timestamps
    outcomes.py                   what an execution outcome may look like (exit-code truth)
    states.py                     task state machine (21 states)
    messages.py                   envelope + 13 typed payloads, provenance + routing rules
    paths.py                      path-traversal protection, workspace isolation
    redaction.py                  secret detection/redaction, sensitive-file list
    limits.py                     time/CPU/memory/pids/output/network limits; docker argv builder
    git_checkpoint.py             checkpoints + planned, confirmed rollback
    journal.py                    durable execution journal / idempotency (agent side)
    audit.py                      hash-chained append-only audit log
    pairing.py                    one-time hashed pairing tokens, revocable devices
    db.py                         connection + checksummed migration runner
    migrations/0001_core.sql      portable schema (18 tables)
    migrations/0002_append_only.sqlite.sql   immutability triggers (SQLite)
  tests/                          145 tests
```

## Database (exact definitions: `migrations/0001_core.sql`)
Tables: users, projects, devices, pairing_tokens, workers, tasks, sessions, task_events, messages,
jobs, executions, output_chunks, checkpoints, file_changes, approvals, audit_log, memory_items,
provider_configs.

Isolation rules enforced **by the database**, not just application code:
* Every owned row has `owner_id`; children reference parents by **composite foreign keys**
  `(task_id, project_id, owner_id)`, so a message/job/execution/approval cannot point at a task of a
  different project or owner (tested).
* `jobs`: cloud jobs have no device, local jobs have no worker - a job cannot silently switch target.
* `executions`: success requires `exit_code = 0`; failure requires non-zero; `unknown` and
  `not_executed` cannot carry an exit code (mirrors `outcomes.py`; a test asserts Python, protocol and
  SQL agree on a 96-case grid).
* `tasks`: `iteration_count <= max_iterations` is a DB invariant (loop bound); suspended states must
  carry `resume_state`.
* `approvals` bind to one `action_sha256`; decisions need `decided_by`.
* `provider_configs.secret_ref` must start with `env:`/`file:`/`vault:` - raw keys cannot be stored.
* `memory_items` scopes (global/user/project/task) cannot mix; project memory must name its project.
* Append-only (SQLite triggers): audit_log, task_events, file_changes, output_chunks; messages are
  immutable except `status`.

Multi-user readiness: `users` + `owner_id` everywhere; single-user mode = one `admin` row.

## Task state machine
RECEIVE_TASK -> IDENTIFY_PROJECT -> LOAD_CONTEXT -> ANALYZE_REQUIREMENTS -> CREATE_PLAN ->
REQUEST_APPROVAL_IF_NEEDED -> GENERATE_CHANGES -> VALIDATE_CHANGES -> APPLY_CHANGES ->
EXECUTE_COMMANDS -> COLLECT_OUTPUT -> ANALYZE_RESULTS -> RETURN_RESULTS_TO_AI -> CONTINUE_OR_RETRY ->
RUN_FINAL_TESTS -> GENERATE_COMPLETION_REPORT -> COMPLETED.
Loops: VALIDATE_CHANGES->GENERATE_CHANGES, CONTINUE_OR_RETRY->{GENERATE_CHANGES, EXECUTE_COMMANDS,
RUN_FINAL_TESTS}, RUN_FINAL_TESTS->CONTINUE_OR_RETRY. Added (not in your list, needed for approvals
mid-loop and pause/resume): PAUSED, WAITING_APPROVAL (both remember `resume_state`), plus terminal
FAILED, CANCELLED. Steps cannot be skipped.

## Deviations from the spec (flagged)
* Added message type `AI_REQUEST` (orchestrator -> AI) so results returned to the model are structured
  too; it must attest `redacted: true`.
* Added states PAUSED / WAITING_APPROVAL / terminal states, as above.
