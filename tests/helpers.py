from __future__ import annotations

import sqlite3

from nexus_core import db
from nexus_core.clock import format_ts, utc_now
from nexus_core.ids import new_id


def ts() -> str:
    return format_ts(utc_now())


def fresh_db() -> sqlite3.Connection:
    conn = db.connect()
    db.migrate(conn)
    return conn


def add_user(conn, email=None) -> str:
    uid = new_id()
    conn.execute(
        "INSERT INTO users (id, email, display_name, created_at) VALUES (?,?,?,?)",
        (uid, email or f"{uid}@example.invalid", "User", ts()),
    )
    return uid


def add_project(conn, owner_id, name=None, **extra) -> str:
    pid = new_id()
    conn.execute(
        "INSERT INTO projects (id, owner_id, name, created_at, updated_at) VALUES (?,?,?,?,?)",
        (pid, owner_id, name or f"p-{pid[:8]}", ts(), ts()),
    )
    return pid


def add_task(conn, owner_id, project_id, state="RECEIVE_TASK") -> str:
    tid = new_id()
    conn.execute(
        "INSERT INTO tasks (id, owner_id, project_id, title, state, created_at, updated_at, last_activity_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (tid, owner_id, project_id, "t", state, ts(), ts(), ts()),
    )
    return tid


def add_session(conn, owner_id, project_id, task_id) -> str:
    sid = new_id()
    conn.execute(
        "INSERT INTO sessions (id, owner_id, project_id, task_id, created_at) VALUES (?,?,?,?,?)",
        (sid, owner_id, project_id, task_id, ts()),
    )
    return sid


def world(conn):
    """owner -> project -> task -> session"""
    o = add_user(conn)
    p = add_project(conn, o)
    t = add_task(conn, o, p)
    s = add_session(conn, o, p, t)
    return o, p, t, s
