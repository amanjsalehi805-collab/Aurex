-- NEXUS AI core schema. Portable SQL subset (runs on SQLite and PostgreSQL).
-- Conventions: ids are UUIDv4 text; timestamps are fixed-width UTC text
-- (YYYY-MM-DDTHH:MM:SS.ffffffZ, so string order == time order); JSON is stored as text and is
-- validated by the application protocol layer; booleans are INTEGER 0/1.
-- Isolation: every owned table carries owner_id; child rows reference their parent through
-- COMPOSITE foreign keys, so a row can never point at a task/project/owner that differs from
-- its parent's.

CREATE TABLE users (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  email TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin', 'member')),
  created_at TEXT NOT NULL,
  disabled_at TEXT
);

CREATE TABLE projects (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL REFERENCES users (id),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  repo_url TEXT,
  local_workspace_path TEXT,
  cloud_workspace_path TEXT UNIQUE,
  languages TEXT NOT NULL DEFAULT '[]',
  frameworks TEXT NOT NULL DEFAULT '[]',
  build_command TEXT,
  test_command TEXT,
  instructions TEXT NOT NULL DEFAULT '',
  current_branch TEXT,
  current_commit TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT,
  UNIQUE (owner_id, name),
  UNIQUE (owner_id, local_workspace_path),
  UNIQUE (id, owner_id)
);

CREATE TABLE devices (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL REFERENCES users (id),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  platform TEXT NOT NULL,
  public_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
  paired_at TEXT NOT NULL,
  revoked_at TEXT,
  last_seen_at TEXT,
  CHECK ((status = 'revoked') = (revoked_at IS NOT NULL)),
  UNIQUE (id, owner_id)
);

CREATE TABLE pairing_tokens (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL REFERENCES users (id),
  token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash) = 64),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  revoked_at TEXT,
  device_id TEXT,
  CHECK ((used_at IS NULL) = (device_id IS NULL)),
  FOREIGN KEY (device_id, owner_id) REFERENCES devices (id, owner_id)
);

CREATE TABLE workers (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  kind TEXT NOT NULL CHECK (kind IN ('cloud_container')),
  status TEXT NOT NULL CHECK (status IN ('idle', 'busy', 'draining', 'offline')),
  created_at TEXT NOT NULL,
  last_heartbeat_at TEXT
);

CREATE TABLE tasks (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
  description TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL CHECK (state IN (
    'RECEIVE_TASK', 'IDENTIFY_PROJECT', 'LOAD_CONTEXT', 'ANALYZE_REQUIREMENTS', 'CREATE_PLAN',
    'REQUEST_APPROVAL_IF_NEEDED', 'GENERATE_CHANGES', 'VALIDATE_CHANGES', 'APPLY_CHANGES',
    'EXECUTE_COMMANDS', 'COLLECT_OUTPUT', 'ANALYZE_RESULTS', 'RETURN_RESULTS_TO_AI',
    'CONTINUE_OR_RETRY', 'RUN_FINAL_TESTS', 'GENERATE_COMPLETION_REPORT',
    'PAUSED', 'WAITING_APPROVAL', 'COMPLETED', 'FAILED', 'CANCELLED')),
  resume_state TEXT CHECK (resume_state IN (
    'RECEIVE_TASK', 'IDENTIFY_PROJECT', 'LOAD_CONTEXT', 'ANALYZE_REQUIREMENTS', 'CREATE_PLAN',
    'REQUEST_APPROVAL_IF_NEEDED', 'GENERATE_CHANGES', 'VALIDATE_CHANGES', 'APPLY_CHANGES',
    'EXECUTE_COMMANDS', 'COLLECT_OUTPUT', 'ANALYZE_RESULTS', 'RETURN_RESULTS_TO_AI',
    'CONTINUE_OR_RETRY', 'RUN_FINAL_TESTS', 'GENERATE_COMPLETION_REPORT')),
  iteration_count INTEGER NOT NULL DEFAULT 0 CHECK (iteration_count >= 0),
  max_iterations INTEGER NOT NULL DEFAULT 25 CHECK (max_iterations > 0),
  budget_cents INTEGER NOT NULL DEFAULT 500 CHECK (budget_cents >= 0),
  spent_cents INTEGER NOT NULL DEFAULT 0 CHECK (spent_cents >= 0),
  inactivity_timeout_seconds INTEGER NOT NULL DEFAULT 1800 CHECK (inactivity_timeout_seconds > 0),
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_activity_at TEXT NOT NULL,
  completed_at TEXT,
  CHECK (iteration_count <= max_iterations),
  CHECK ((state IN ('PAUSED', 'WAITING_APPROVAL')) = (resume_state IS NOT NULL)),
  FOREIGN KEY (project_id, owner_id) REFERENCES projects (id, owner_id),
  UNIQUE (id, project_id, owner_id)
);
CREATE INDEX ix_tasks_owner_state ON tasks (owner_id, state);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  ended_at TEXT,
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id),
  UNIQUE (id, task_id)
);

CREATE TABLE task_events (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  seq INTEGER NOT NULL CHECK (seq >= 1),
  from_state TEXT,
  to_state TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id),
  UNIQUE (task_id, seq)
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  message_type TEXT NOT NULL CHECK (message_type IN (
    'AI_REQUEST', 'AI_RESPONSE', 'CODE_BLOCK', 'SHELL_COMMAND', 'FILE_PATCH', 'TERMINAL_STDOUT',
    'TERMINAL_STDERR', 'EXECUTION_RESULT', 'TEST_RESULT', 'APPROVAL_REQUEST',
    'APPROVAL_RESPONSE', 'ERROR_REPORT', 'TASK_STATUS')),
  source TEXT NOT NULL,
  destination TEXT NOT NULL,
  correlation_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'delivered', 'processed', 'failed', 'rejected')),
  protocol_version INTEGER NOT NULL,
  payload TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
  created_at TEXT NOT NULL,
  received_at TEXT NOT NULL,
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id),
  FOREIGN KEY (session_id, task_id) REFERENCES sessions (id, task_id)
);
CREATE INDEX ix_messages_task_time ON messages (task_id, created_at);
CREATE INDEX ix_messages_correlation ON messages (correlation_id);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('shell_command', 'file_patch')),
  target TEXT NOT NULL CHECK (target IN ('cloud', 'local')),
  device_id TEXT,
  worker_id TEXT REFERENCES workers (id),
  status TEXT NOT NULL CHECK (status IN (
    'queued', 'claimed', 'running', 'succeeded', 'failed', 'timed_out', 'cancelled', 'unknown')),
  idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 128),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
  limits TEXT NOT NULL,
  created_at TEXT NOT NULL,
  claimed_at TEXT,
  finished_at TEXT,
  CHECK (attempts <= max_attempts),
  -- a job never silently changes target: cloud jobs have no device, local jobs have no worker
  CHECK ((target = 'cloud' AND device_id IS NULL) OR (target = 'local' AND worker_id IS NULL)),
  CHECK (status = 'queued' OR (target = 'local' AND device_id IS NOT NULL)
         OR (target = 'cloud' AND worker_id IS NOT NULL)),
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id),
  FOREIGN KEY (device_id, owner_id) REFERENCES devices (id, owner_id),
  UNIQUE (owner_id, idempotency_key),
  UNIQUE (id, task_id, project_id, owner_id)
);
CREATE INDEX ix_jobs_status_target ON jobs (status, target);

CREATE TABLE executions (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  command_id TEXT NOT NULL UNIQUE,
  target TEXT NOT NULL CHECK (target IN ('cloud', 'local')),
  command TEXT NOT NULL,
  cwd TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN (
    'succeeded', 'failed', 'timed_out', 'cancelled', 'not_executed', 'unknown')),
  exit_code INTEGER,
  started_at TEXT,
  finished_at TEXT,
  duration_ms INTEGER CHECK (duration_ms >= 0),
  stdout_chunks INTEGER NOT NULL DEFAULT 0 CHECK (stdout_chunks >= 0),
  stderr_chunks INTEGER NOT NULL DEFAULT 0 CHECK (stderr_chunks >= 0),
  output_truncated INTEGER NOT NULL DEFAULT 0 CHECK (output_truncated IN (0, 1)),
  -- success is defined by exit status only (mirrors nexus_core.outcomes.validate_outcome)
  CHECK (status <> 'succeeded' OR (exit_code IS NOT NULL AND exit_code = 0)),
  CHECK (status <> 'failed' OR (exit_code IS NOT NULL AND exit_code <> 0)),
  CHECK (status <> 'not_executed' OR (exit_code IS NULL AND started_at IS NULL)),
  CHECK (status <> 'unknown' OR exit_code IS NULL),
  CHECK (status <> 'timed_out' OR started_at IS NOT NULL),
  CHECK (status NOT IN ('succeeded', 'failed') OR (started_at IS NOT NULL AND finished_at IS NOT NULL)),
  FOREIGN KEY (job_id, task_id, project_id, owner_id) REFERENCES jobs (id, task_id, project_id, owner_id),
  UNIQUE (id, owner_id)
);
CREATE INDEX ix_executions_task ON executions (task_id);

CREATE TABLE output_chunks (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  execution_id TEXT NOT NULL,
  seq INTEGER NOT NULL CHECK (seq >= 0),
  stream TEXT NOT NULL CHECK (stream IN ('stdout', 'stderr')),
  data TEXT NOT NULL,
  redacted INTEGER NOT NULL DEFAULT 1 CHECK (redacted IN (0, 1)),
  created_at TEXT NOT NULL,
  FOREIGN KEY (execution_id, owner_id) REFERENCES executions (id, owner_id),
  UNIQUE (execution_id, stream, seq)
);

CREATE TABLE checkpoints (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  ref TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  label TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  rolled_back_at TEXT,
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id),
  UNIQUE (id, project_id)
);

CREATE TABLE file_changes (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  path TEXT NOT NULL,
  operation TEXT NOT NULL CHECK (operation IN ('create', 'modify', 'delete')),
  before_sha256 TEXT,
  after_sha256 TEXT,
  patch TEXT,
  checkpoint_id TEXT,
  created_at TEXT NOT NULL,
  CHECK (operation <> 'create' OR (before_sha256 IS NULL AND after_sha256 IS NOT NULL)),
  CHECK (operation <> 'delete' OR (before_sha256 IS NOT NULL AND after_sha256 IS NULL)),
  CHECK (operation <> 'modify' OR (before_sha256 IS NOT NULL AND after_sha256 IS NOT NULL)),
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id),
  FOREIGN KEY (checkpoint_id, project_id) REFERENCES checkpoints (id, project_id)
);
CREATE INDEX ix_file_changes_task ON file_changes (task_id);

CREATE TABLE approvals (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  risk_category TEXT NOT NULL CHECK (risk_category IN (
    'delete_files', 'destructive_command', 'overwrite_work', 'git_history', 'git_push', 'deploy',
    'publish_package', 'production_database', 'credentials', 'outside_workspace', 'system_install',
    'elevated_privileges', 'broad_access', 'network_access', 'clarification')),
  action TEXT NOT NULL,
  action_sha256 TEXT NOT NULL CHECK (length(action_sha256) = 64),  -- approval binds to ONE exact action
  affected TEXT NOT NULL DEFAULT '[]',
  reason TEXT NOT NULL,
  consequences TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
  requested_at TEXT NOT NULL,
  expires_at TEXT,
  decided_at TEXT,
  decided_by TEXT REFERENCES users (id),
  CHECK ((status = 'pending') = (decided_at IS NULL)),
  CHECK (status NOT IN ('approved', 'rejected') OR decided_by IS NOT NULL),
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id)
);
CREATE INDEX ix_approvals_status ON approvals (owner_id, status);

CREATE TABLE audit_log (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL REFERENCES users (id),
  seq INTEGER NOT NULL CHECK (seq >= 1),
  created_at TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'ai', 'orchestrator', 'worker', 'device', 'system')),
  actor_id TEXT,
  action TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id TEXT,
  details TEXT NOT NULL,
  prev_hash TEXT NOT NULL CHECK (length(prev_hash) = 64),
  entry_hash TEXT NOT NULL CHECK (length(entry_hash) = 64),
  UNIQUE (owner_id, seq)
);

CREATE TABLE memory_items (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (scope IN ('global', 'user', 'project', 'task')),
  project_id TEXT,
  task_id TEXT,
  key TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  -- project memories never mix: project/task scope must name their project (and task)
  CHECK (scope NOT IN ('global', 'user') OR (project_id IS NULL AND task_id IS NULL)),
  CHECK (scope <> 'project' OR (project_id IS NOT NULL AND task_id IS NULL)),
  CHECK (scope <> 'task' OR (project_id IS NOT NULL AND task_id IS NOT NULL)),
  FOREIGN KEY (project_id, owner_id) REFERENCES projects (id, owner_id),
  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id)
);
CREATE UNIQUE INDEX ux_memory_scope_key
  ON memory_items (owner_id, scope, COALESCE(project_id, ''), COALESCE(task_id, ''), key);

CREATE TABLE provider_configs (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  owner_id TEXT NOT NULL REFERENCES users (id),
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  -- a REFERENCE to a secret (env:NAME, file:/path, vault:path); raw keys can never be stored
  secret_ref TEXT NOT NULL CHECK (secret_ref LIKE 'env:%' OR secret_ref LIKE 'file:%' OR secret_ref LIKE 'vault:%'),
  settings TEXT NOT NULL DEFAULT '{}',
  is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  created_at TEXT NOT NULL,
  UNIQUE (owner_id, provider, model)
);
