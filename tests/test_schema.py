import re
import sqlite3
import unittest

from nexus_core import db
from nexus_core.ids import new_id
from nexus_core.messages import MessageType, RISK_CATEGORIES
from nexus_core.outcomes import ExecutionStatus
from nexus_core.states import ACTIVE, TaskState

from .helpers import add_project, add_task, add_user, fresh_db, ts, world

SHA = "a" * 64


def add_job(conn, o, p, t, **over):
    row = dict(id=new_id(), owner_id=o, project_id=p, task_id=t, kind="shell_command", target="cloud",
               device_id=None, worker_id=None, status="queued", idempotency_key=f"key-{new_id()[:12]}",
               limits="{}", created_at=ts())
    row.update(over)
    cols = ", ".join(row)
    conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    return row["id"]


def add_message(conn, o, p, t, s, **over):
    row = dict(id=new_id(), owner_id=o, project_id=p, task_id=t, session_id=s, message_type="TASK_STATUS",
               source="orchestrator", destination="user", correlation_id=None, status="pending",
               protocol_version=1, payload="{}", payload_sha256=SHA, created_at=ts(), received_at=ts())
    row.update(over)
    conn.execute(f"INSERT INTO messages ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    return row["id"]


def add_exec(conn, o, p, t, job, **over):
    row = dict(id=new_id(), owner_id=o, project_id=p, task_id=t, job_id=job, command_id=new_id(), target="cloud",
               command="ls", cwd=".", status="succeeded", exit_code=0, started_at=ts(), finished_at=ts())
    row.update(over)
    conn.execute(f"INSERT INTO executions ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    return row["id"]


class TestMigrations(unittest.TestCase):
    def test_fresh_apply_and_idempotent_rerun(self):
        conn = db.connect()
        self.assertEqual(db.migrate(conn), ["0001", "0002"])
        self.assertEqual(db.migrate(conn), [])
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("users", "projects", "devices", "pairing_tokens", "workers", "tasks", "task_events",
                      "sessions", "messages", "jobs", "executions", "output_chunks", "file_changes",
                      "checkpoints", "approvals", "audit_log", "memory_items", "provider_configs"):
            self.assertIn(table, names)

    def test_modified_migration_detected(self):
        conn = fresh_db()
        conn.execute("UPDATE schema_migrations SET checksum = ? WHERE version = '0001'", ("0" * 64,))
        with self.assertRaises(db.MigrationError):
            db.migrate(conn)

    def test_unknown_applied_migration_detected(self):
        conn = fresh_db()
        conn.execute("INSERT INTO schema_migrations VALUES ('9999', 'future', ?, ?)", ("0" * 64, ts()))
        with self.assertRaises(db.MigrationError):
            db.migrate(conn)

    def test_foreign_keys_are_enforced(self):
        conn = fresh_db()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO projects (id, owner_id, name, created_at, updated_at) VALUES (?,?,?,?,?)",
                         (new_id(), new_id(), "x", ts(), ts()))

    def test_drift_task_states_match_enum(self):
        sql = (db.MIGRATIONS_DIR / "0001_core.sql").read_text()
        block = re.search(r"CREATE TABLE tasks \((.*?)\n\);", sql, re.S).group(1)
        lists = re.findall(r"IN \(((?:\s*'[A-Z_]+',?)+)\)", block)
        state_list = set(re.findall(r"'([A-Z_]+)'", lists[0]))
        resume_list = set(re.findall(r"'([A-Z_]+)'", lists[1]))
        self.assertEqual(state_list, {s.value for s in TaskState})
        self.assertEqual(resume_list, {s.value for s in ACTIVE})

    def test_drift_message_types_exec_status_and_risk_categories(self):
        sql = (db.MIGRATIONS_DIR / "0001_core.sql").read_text()
        def sql_set(table, column):
            block = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", sql, re.S).group(1)
            m = re.search(rf"{column} TEXT NOT NULL CHECK \({column} IN \((.*?)\)\)", block, re.S)
            return set(re.findall(r"'([^']+)'", m.group(1)))
        self.assertEqual(sql_set("messages", "message_type"), {m.value for m in MessageType})
        self.assertEqual(sql_set("executions", "status"), {s.value for s in ExecutionStatus})
        self.assertEqual(sql_set("approvals", "risk_category"), set(RISK_CATEGORIES))


class TestIsolation(unittest.TestCase):
    def test_every_task_state_is_storable_and_bogus_is_not(self):
        conn = fresh_db()
        o = add_user(conn); p = add_project(conn, o)
        for st in TaskState:
            if st in (TaskState.PAUSED, TaskState.WAITING_APPROVAL):
                conn.execute("INSERT INTO tasks (id, owner_id, project_id, title, state, resume_state, created_at,"
                             " updated_at, last_activity_at) VALUES (?,?,?,?,?,?,?,?,?)",
                             (new_id(), o, p, "t", st.value, "CREATE_PLAN", ts(), ts(), ts()))
            else:
                add_task(conn, o, p, st.value)
        with self.assertRaises(sqlite3.IntegrityError):
            add_task(conn, o, p, "HACKED")

    def test_resume_state_only_with_suspended_states(self):
        conn = fresh_db()
        o = add_user(conn); p = add_project(conn, o)
        def insert(state, resume):
            conn.execute("INSERT INTO tasks (id, owner_id, project_id, title, state, resume_state, created_at,"
                         " updated_at, last_activity_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (new_id(), o, p, "t", state, resume, ts(), ts(), ts()))
        for state, resume in (("PAUSED", None), ("CREATE_PLAN", "CREATE_PLAN"), ("PAUSED", "PAUSED"),
                              ("WAITING_APPROVAL", "COMPLETED")):
            with self.subTest(state=state, resume=resume), self.assertRaises(sqlite3.IntegrityError):
                insert(state, resume)

    def test_iteration_limit_is_a_database_invariant(self):
        conn = fresh_db()
        o = add_user(conn); p = add_project(conn, o)
        t = add_task(conn, o, p)
        conn.execute("UPDATE tasks SET max_iterations = 3, iteration_count = 3 WHERE id = ?", (t,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE tasks SET iteration_count = 4 WHERE id = ?", (t,))

    def test_task_cannot_attach_to_another_owners_project(self):
        conn = fresh_db()
        alice, bob = add_user(conn), add_user(conn)
        p_alice = add_project(conn, alice)
        with self.assertRaises(sqlite3.IntegrityError):
            add_task(conn, bob, p_alice)

    def test_message_cannot_cross_projects_or_owners_or_tasks(self):
        conn = fresh_db()
        o, p, t, s = world(conn)
        p2 = add_project(conn, o)
        o2 = add_user(conn)
        add_message(conn, o, p, t, s)  # control: valid
        with self.assertRaises(sqlite3.IntegrityError):
            add_message(conn, o, p2, t, s)           # right task, wrong project
        with self.assertRaises(sqlite3.IntegrityError):
            add_message(conn, o2, p, t, s)           # right task, wrong owner
        t2 = add_task(conn, o, p)
        with self.assertRaises(sqlite3.IntegrityError):
            add_message(conn, o, p, t2, s)           # session belongs to a different task

    def test_message_type_and_status_constrained(self):
        conn = fresh_db()
        o, p, t, s = world(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            add_message(conn, o, p, t, s, message_type="RUN_ANYTHING")
        with self.assertRaises(sqlite3.IntegrityError):
            add_message(conn, o, p, t, s, status="maybe")

    def test_project_unique_names_and_workspaces(self):
        conn = fresh_db()
        o = add_user(conn)
        add_project(conn, o, name="same")
        with self.assertRaises(sqlite3.IntegrityError):
            add_project(conn, o, name="same")
        o2 = add_user(conn)
        add_project(conn, o2, name="same")  # another owner may reuse the name
        conn.execute("UPDATE projects SET cloud_workspace_path = '/ws/a' WHERE owner_id = ? AND name = 'same'", (o,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE projects SET cloud_workspace_path = '/ws/a' WHERE owner_id = ?", (o2,))

    def test_memory_scopes_do_not_mix(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        p2 = add_project(conn, o)
        def mem(scope, project=None, task=None, key="k"):
            conn.execute("INSERT INTO memory_items (id, owner_id, scope, project_id, task_id, key, content,"
                         " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (new_id(), o, scope, project, task, key, "c", ts(), ts()))
        mem("global"); mem("user"); mem("project", p); mem("project", p2); mem("task", p, t)
        for args in (("project", None), ("global", p), ("task", p, None), ("project", p, t)):
            with self.subTest(args=args), self.assertRaises(sqlite3.IntegrityError):
                mem(*args, key="other")
        with self.assertRaises(sqlite3.IntegrityError):
            mem("project", p)                       # duplicate key in same project/scope
        with self.assertRaises(sqlite3.IntegrityError):
            mem("task", p2, t, key="z")             # task belongs to p, not p2
        with self.assertRaises(sqlite3.IntegrityError):
            mem("global")                           # duplicate global key (COALESCE unique index)


class TestExecutionInvariants(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_db()
        self.o, self.p, self.t, self.s = world(self.conn)
        self.job = add_job(self.conn, self.o, self.p, self.t)

    def run_exec(self, **over):
        return add_exec(self.conn, self.o, self.p, self.t, self.job, **over)

    def test_success_needs_exit_zero(self):
        self.run_exec()
        for code in (None, 1):
            with self.subTest(code=code), self.assertRaises(sqlite3.IntegrityError):
                self.run_exec(status="succeeded", exit_code=code)

    def test_failed_needs_nonzero(self):
        self.run_exec(status="failed", exit_code=3)
        for code in (None, 0):
            with self.subTest(code=code), self.assertRaises(sqlite3.IntegrityError):
                self.run_exec(status="failed", exit_code=code)

    def test_unknown_and_not_executed_cannot_claim_exit_codes(self):
        self.run_exec(status="unknown", exit_code=None, finished_at=None)
        self.run_exec(status="not_executed", exit_code=None, started_at=None, finished_at=None)
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_exec(status="unknown", exit_code=0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_exec(status="not_executed", exit_code=None, started_at=ts(), finished_at=None)

    def test_timed_out_needs_start_and_finished_states_need_both_times(self):
        self.run_exec(status="timed_out", exit_code=None, finished_at=None)
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_exec(status="timed_out", exit_code=None, started_at=None, finished_at=None)
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_exec(finished_at=None)

    def test_execution_cannot_attach_to_job_of_other_project(self):
        p2 = add_project(self.conn, self.o)
        with self.assertRaises(sqlite3.IntegrityError):
            add_exec(self.conn, self.o, p2, self.t, self.job)

    def test_unknown_status_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_exec(status="great_success")


class TestJobs(unittest.TestCase):
    def test_target_never_silently_switches(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        dev = new_id()
        conn.execute("INSERT INTO devices (id, owner_id, name, platform, public_key, status, paired_at)"
                     " VALUES (?,?,?,?,?,?,?)", (dev, o, "phone", "android", "k1", "active", ts()))
        wid = new_id()
        conn.execute("INSERT INTO workers (id, kind, status, created_at) VALUES (?,?,?,?)",
                     (wid, "cloud_container", "idle", ts()))
        add_job(conn, o, p, t, target="local", device_id=dev, status="claimed")
        add_job(conn, o, p, t, target="cloud", worker_id=wid, status="claimed")
        add_job(conn, o, p, t, target="local")      # queued, unassigned is fine
        for over in ({"target": "cloud", "device_id": dev, "worker_id": wid, "status": "claimed"},
                     {"target": "local", "worker_id": wid, "device_id": dev, "status": "claimed"},
                     {"target": "local", "status": "claimed"},
                     {"target": "cloud", "status": "running"},
                     {"target": "cloud", "device_id": dev}):
            with self.subTest(over=over), self.assertRaises(sqlite3.IntegrityError):
                add_job(conn, o, p, t, **over)

    def test_idempotency_key_unique_per_owner(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        add_job(conn, o, p, t, idempotency_key="same-key-123")
        with self.assertRaises(sqlite3.IntegrityError):
            add_job(conn, o, p, t, idempotency_key="same-key-123")
        o2 = add_user(conn); p2 = add_project(conn, o2); t2 = add_task(conn, o2, p2)
        add_job(conn, o2, p2, t2, idempotency_key="same-key-123")

    def test_job_device_must_belong_to_same_owner(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        other = add_user(conn)
        dev = new_id()
        conn.execute("INSERT INTO devices (id, owner_id, name, platform, public_key, status, paired_at)"
                     " VALUES (?,?,?,?,?,?,?)", (dev, other, "phone", "android", "k2", "active", ts()))
        with self.assertRaises(sqlite3.IntegrityError):
            add_job(conn, o, p, t, target="local", device_id=dev, status="claimed")

    def test_attempts_bounded(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            add_job(conn, o, p, t, attempts=4, max_attempts=3)


class TestTamperResistance(unittest.TestCase):
    def test_append_only_tables(self):
        conn = fresh_db()
        o, p, t, s = world(conn)
        conn.execute("INSERT INTO task_events (id, owner_id, project_id, task_id, seq, to_state, actor, created_at)"
                     " VALUES (?,?,?,?,?,?,?,?)", (new_id(), o, p, t, 1, "RECEIVE_TASK", "system", ts()))
        conn.execute("INSERT INTO audit_log (id, owner_id, seq, created_at, actor_type, action, subject_type,"
                     " details, prev_hash, entry_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (new_id(), o, 1, ts(), "system", "x", "task", "{}", "0" * 64, "1" * 64))
        for sql in ("UPDATE task_events SET reason = 'edited'", "DELETE FROM task_events",
                    "UPDATE audit_log SET action = 'edited'", "DELETE FROM audit_log"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                conn.execute(sql)

    def test_messages_immutable_except_status(self):
        conn = fresh_db()
        o, p, t, s = world(conn)
        m = add_message(conn, o, p, t, s)
        conn.execute("UPDATE messages SET status = 'delivered' WHERE id = ?", (m,))
        for col, val in (("payload", "{\"x\":1}"), ("source", "worker"), ("destination", "ai"),
                         ("message_type", "AI_RESPONSE"), ("payload_sha256", "b" * 64),
                         ("correlation_id", new_id())):
            with self.subTest(col=col), self.assertRaises(sqlite3.IntegrityError):
                conn.execute(f"UPDATE messages SET {col} = ? WHERE id = ?", (val, m))

    def test_file_change_and_output_rows_are_append_only_and_consistent(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        def change(op, before, after):
            conn.execute("INSERT INTO file_changes (id, owner_id, project_id, task_id, path, operation, before_sha256,"
                         " after_sha256, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (new_id(), o, p, t, "a.txt", op, before, after, ts()))
        change("create", None, SHA); change("modify", SHA, "b" * 64); change("delete", SHA, None)
        for args in (("create", SHA, SHA), ("create", None, None), ("modify", None, SHA), ("delete", SHA, SHA),
                     ("rename", SHA, SHA)):
            with self.subTest(args=args), self.assertRaises(sqlite3.IntegrityError):
                change(*args)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE file_changes SET path = 'evil'")


class TestMisc(unittest.TestCase):
    def test_approval_constraints(self):
        conn = fresh_db()
        o, p, t, _ = world(conn)
        def approval(status, decided_at, decided_by, category="git_push"):
            conn.execute("INSERT INTO approvals (id, owner_id, project_id, task_id, risk_category, action,"
                         " action_sha256, reason, consequences, status, requested_at, decided_at, decided_by)"
                         " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (new_id(), o, p, t, category, "a", SHA, "r", "c", status, ts(), decided_at, decided_by))
        approval("pending", None, None)
        approval("approved", ts(), o)
        approval("expired", ts(), None)
        for args in (("pending", ts(), None), ("approved", None, o), ("approved", ts(), None),
                     ("rejected", ts(), None), ("maybe", ts(), o), ("pending", None, None, "do_anything")):
            with self.subTest(args=args), self.assertRaises(sqlite3.IntegrityError):
                approval(*args)

    def test_provider_secret_must_be_a_reference_never_a_raw_key(self):
        conn = fresh_db()
        o = add_user(conn)
        def cfg(ref, model="m"):
            conn.execute("INSERT INTO provider_configs (id, owner_id, provider, model, secret_ref, created_at)"
                         " VALUES (?,?,?,?,?,?)", (new_id(), o, "anthropic", model, ref, ts()))
        cfg("env:ANTHROPIC_API_KEY", "a"); cfg("file:/etc/nexus/key", "b"); cfg("vault:kv/nexus", "c")
        for raw in ("sk-ant-api03-abcdefghijklmnop", "AKIAIOSFODNN7EXAMPLE", ""):
            with self.subTest(raw=raw), self.assertRaises(sqlite3.IntegrityError):
                cfg(raw, "d")

    def test_device_and_pairing_token_constraints(self):
        conn = fresh_db()
        o = add_user(conn)
        def device(status, revoked_at, key):
            conn.execute("INSERT INTO devices (id, owner_id, name, platform, public_key, status, paired_at, revoked_at)"
                         " VALUES (?,?,?,?,?,?,?,?)", (new_id(), o, "d", "android", key, status, ts(), revoked_at))
        device("active", None, "k1"); device("revoked", ts(), "k2")
        with self.assertRaises(sqlite3.IntegrityError):
            device("revoked", None, "k3")
        with self.assertRaises(sqlite3.IntegrityError):
            device("active", ts(), "k4")
        with self.assertRaises(sqlite3.IntegrityError):
            device("active", None, "k1")   # same public key cannot be registered twice


if __name__ == "__main__":
    unittest.main()
