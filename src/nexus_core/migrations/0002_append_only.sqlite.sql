-- Tamper resistance enforced inside the database (SQLite dialect).
-- PostgreSQL equivalent (triggers + REVOKE UPDATE/DELETE on the application role) arrives in
-- Phase 2 together with a Postgres CI job; it is NOT claimed as done in Phase 1.

CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

CREATE TRIGGER task_events_no_update BEFORE UPDATE ON task_events
BEGIN SELECT RAISE(ABORT, 'task_events are append-only'); END;

CREATE TRIGGER task_events_no_delete BEFORE DELETE ON task_events
BEGIN SELECT RAISE(ABORT, 'task_events are append-only'); END;

CREATE TRIGGER file_changes_no_update BEFORE UPDATE ON file_changes
BEGIN SELECT RAISE(ABORT, 'file_changes are append-only'); END;

CREATE TRIGGER output_chunks_no_update BEFORE UPDATE ON output_chunks
BEGIN SELECT RAISE(ABORT, 'output_chunks are append-only'); END;

-- messages are immutable except for their delivery status
CREATE TRIGGER messages_status_only BEFORE UPDATE ON messages
WHEN NEW.id IS NOT OLD.id OR NEW.owner_id IS NOT OLD.owner_id OR NEW.project_id IS NOT OLD.project_id
  OR NEW.task_id IS NOT OLD.task_id OR NEW.session_id IS NOT OLD.session_id
  OR NEW.message_type IS NOT OLD.message_type OR NEW.source IS NOT OLD.source
  OR NEW.destination IS NOT OLD.destination OR NEW.correlation_id IS NOT OLD.correlation_id
  OR NEW.protocol_version IS NOT OLD.protocol_version OR NEW.payload IS NOT OLD.payload
  OR NEW.payload_sha256 IS NOT OLD.payload_sha256 OR NEW.created_at IS NOT OLD.created_at
  OR NEW.received_at IS NOT OLD.received_at
BEGIN SELECT RAISE(ABORT, 'messages are immutable except status'); END;
