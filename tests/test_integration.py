"""Cross-layer agreement: protocol, outcome rules and SQL constraints must accept/reject identically."""

import itertools
import sqlite3
import unittest

from nexus_core.clock import format_ts, utc_now
from nexus_core.ids import new_id
from nexus_core.messages import Envelope, MessageType, ProtocolError
from nexus_core.outcomes import ExecutionStatus, OutcomeError, validate_outcome
from nexus_core.redaction import Redactor

from .helpers import fresh_db, world
from .test_schema import add_exec, add_job, add_message

NOW = format_ts(utc_now())


class TestLayersAgree(unittest.TestCase):
    def test_outcome_rules_identical_in_python_protocol_and_sql(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        job = add_job(conn, o, p, t)
        statuses = [s.value for s in ExecutionStatus]
        grid = list(itertools.product(statuses, (None, 0, 1, -9), (None, NOW), (None, NOW)))
        accepted = 0
        for status, code, started, finished in grid:
            try:
                validate_outcome(status, code, started_at=started, finished_at=finished)
                py_ok = True
            except OutcomeError:
                py_ok = False
            payload = {
                "execution_id": new_id(),
                "command_id": new_id(),
                "status": status,
                "exit_code": code,
                "started_at": started,
                "finished_at": finished,
                "duration_ms": None,
                "cwd": ".",
                "target": "cloud",
                "stdout_chunks": 0,
                "stderr_chunks": 0,
                "output_truncated": False,
            }
            try:
                Envelope.create(
                    task_id=t,
                    project_id=p,
                    session_id=new_id(),
                    message_type=MessageType.EXECUTION_RESULT,
                    source="worker",
                    destination="orchestrator",
                    payload=payload,
                    correlation_id=new_id(),
                )
                proto_ok = True
            except ProtocolError:
                proto_ok = False
            try:
                conn.execute("SAVEPOINT s")
                add_exec(
                    conn,
                    o,
                    p,
                    t,
                    job,
                    status=status,
                    exit_code=code,
                    started_at=started,
                    finished_at=finished,
                )
                conn.execute("RELEASE s")
                sql_ok = True
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK TO s")
                conn.execute("RELEASE s")
                sql_ok = False
            with self.subTest(
                status=status, code=code, started=bool(started), finished=bool(finished)
            ):
                self.assertEqual((py_ok, proto_ok, sql_ok), (py_ok, py_ok, py_ok))
            accepted += py_ok
        self.assertGreater(accepted, 5)
        self.assertLess(accepted, len(grid))

    def test_validated_envelope_persists_and_payload_hash_survives(self):
        conn = fresh_db()
        o, p, t, s = world(conn)
        env = Envelope.create(
            task_id=t,
            project_id=p,
            session_id=s,
            message_type=MessageType.SHELL_COMMAND,
            source="orchestrator",
            destination="device:d1",
            payload={
                "command_id": new_id(),
                "command": "ls",
                "cwd": ".",
                "target": "local",
                "timeout_seconds": 30,
                "idempotency_key": "idem-key-abcd",
                "purpose": "list",
                "network": "none",
            },
        )
        add_message(
            conn,
            o,
            p,
            t,
            s,
            id=env.message_id,
            message_type=env.message_type.value,
            source=env.source,
            destination=env.destination,
            payload=env.to_json(),
            payload_sha256=env.payload_sha256(),
            created_at=env.timestamp,
        )
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (env.message_id,)).fetchone()
        again = Envelope.from_json(row["payload"])
        self.assertEqual(again.payload_sha256(), row["payload_sha256"])
        self.assertEqual(again, env)

    def test_secret_in_command_output_is_redacted_before_it_could_be_stored_or_sent(self):
        leaked = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
        clean = Redactor().redact(f"+ curl -H 'Authorization: token {leaked}' ...\n")
        self.assertNotIn(leaked, clean)
        env = Envelope.create(
            task_id=new_id(),
            project_id=new_id(),
            session_id=new_id(),
            message_type=MessageType.TERMINAL_STDOUT,
            source="device:d1",
            destination="orchestrator",
            correlation_id=new_id(),
            payload={"execution_id": new_id(), "command_id": new_id(), "seq": 0, "data": clean},
        )
        self.assertNotIn(leaked, env.to_json())


if __name__ == "__main__":
    unittest.main()
