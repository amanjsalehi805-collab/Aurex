import sqlite3
import unittest

from nexus_core.audit import GENESIS, AuditLog, _entry_hash
from nexus_core.redaction import Redactor

from .helpers import add_user, fresh_db

GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


def append(log, owner, n, **details):
    return log.append(
        owner_id=owner,
        actor_type="system",
        actor_id=None,
        action=f"act{n}",
        subject_type="task",
        subject_id=None,
        details=details,
    )


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_db()
        self.owner = add_user(self.conn)
        self.log = AuditLog(self.conn)

    def test_chain_links_and_verifies(self):
        for i in range(1, 6):
            self.assertEqual(append(self.log, self.owner, i, i=i), i)
        self.assertIsNone(self.log.verify(self.owner))
        rows = list(self.conn.execute("SELECT * FROM audit_log ORDER BY seq"))
        self.assertEqual(rows[0]["prev_hash"], GENESIS)
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(b["prev_hash"], a["entry_hash"])

    def test_empty_chain_verifies(self):
        self.assertIsNone(self.log.verify(self.owner))

    def test_chains_are_per_owner(self):
        other = add_user(self.conn)
        append(self.log, self.owner, 1)
        append(self.log, other, 1)
        append(self.log, self.owner, 2)
        self.assertEqual(append(self.log, other, 2), 2)
        self.assertIsNone(self.log.verify(self.owner))
        self.assertIsNone(self.log.verify(other))

    def _bypass_triggers(self, sql, params=()):
        self.conn.execute("DROP TRIGGER audit_log_no_update")
        self.conn.execute("DROP TRIGGER audit_log_no_delete")
        self.conn.execute(sql, params)

    def test_edit_of_a_middle_entry_is_detected(self):
        for i in range(1, 5):
            append(self.log, self.owner, i)
        self._bypass_triggers("UPDATE audit_log SET action = 'forged' WHERE seq = 2")
        self.assertEqual(self.log.verify(self.owner), 2)

    def test_deleting_a_middle_entry_is_detected(self):
        for i in range(1, 5):
            append(self.log, self.owner, i)
        self._bypass_triggers("DELETE FROM audit_log WHERE seq = 2")
        self.assertEqual(self.log.verify(self.owner), 3)

    def test_rewriting_hash_to_hide_edit_breaks_the_next_link(self):
        for i in range(1, 4):
            append(self.log, self.owner, i)
        self._bypass_triggers(
            "UPDATE audit_log SET action = 'forged', entry_hash = ? WHERE seq = 1", ("f" * 64,)
        )
        self.assertIn(self.log.verify(self.owner), (1, 2))

    def test_forged_entry_with_repaired_next_link_is_still_detected(self):
        for i in range(1, 4):
            append(self.log, self.owner, i)
        row = self.conn.execute("SELECT * FROM audit_log WHERE seq = 1").fetchone()
        fields = {
            k: row[k]
            for k in (
                "owner_id",
                "seq",
                "created_at",
                "actor_type",
                "actor_id",
                "action",
                "subject_type",
                "subject_id",
                "details",
            )
        }
        fields["action"] = "forged"
        forged_hash = _entry_hash(GENESIS, fields)
        self._bypass_triggers(
            "UPDATE audit_log SET action = 'forged', entry_hash = ? WHERE seq = 1", (forged_hash,)
        )
        self.conn.execute("UPDATE audit_log SET prev_hash = ? WHERE seq = 2", (forged_hash,))
        # entry 1 is now internally consistent and entry 2 links to it, but entry 2's own hash
        # was computed over the ORIGINAL previous hash, so the chain must still break at 2.
        self.assertEqual(self.log.verify(self.owner), 2)

    def test_database_refuses_edits_without_tampering_tools(self):
        append(self.log, self.owner, 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE audit_log SET action = 'x'")

    def test_secrets_never_reach_the_log(self):
        log = AuditLog(self.conn, Redactor(known_secrets=["correct-horse-battery-staple"]))
        log.append(
            owner_id=self.owner,
            actor_type="user",
            actor_id=None,
            action=f"used {GH}",
            subject_type="cmd",
            subject_id=None,
            details={"password": "x", "env": f"TOKEN={GH}", "note": "correct-horse-battery-staple"},
        )
        row = self.conn.execute("SELECT action, details FROM audit_log").fetchone()
        blob = row["action"] + row["details"]
        self.assertNotIn(GH, blob)
        self.assertNotIn("correct-horse", blob)
        self.assertIsNone(log.verify(self.owner))

    def test_unknown_actor_rejected(self):
        with self.assertRaises(ValueError):
            self.log.append(
                owner_id=self.owner,
                actor_type="root",
                actor_id=None,
                action="a",
                subject_type="t",
                subject_id=None,
            )


if __name__ == "__main__":
    unittest.main()
