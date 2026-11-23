import base64
import unittest
from datetime import datetime, timedelta, timezone

from nexus_core.audit import AuditLog
from nexus_core.pairing import GENERIC_FAILURE, PairingError, PairingStore, hash_token

from .helpers import add_user, fresh_db

KEY1 = base64.b64encode(b"\x01" * 32).decode()
KEY2 = base64.b64encode(b"\x02" * 32).decode()


class Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class TestPairing(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_db()
        self.owner = add_user(self.conn)
        self.clock = Clock()
        self.audit = AuditLog(self.conn, clock=self.clock)
        self.store = PairingStore(self.conn, self.clock, self.audit)

    def redeem(self, token, key=KEY1, name="phone"):
        return self.store.redeem(token, device_name=name, platform="android", public_key=key)

    def test_issue_redeem_creates_active_device_for_token_owner(self):
        _, token = self.store.issue(self.owner)
        device = self.redeem(token)
        row = self.conn.execute("SELECT * FROM devices WHERE id = ?", (device,)).fetchone()
        self.assertEqual((row["owner_id"], row["status"], row["public_key"]), (self.owner, "active", KEY1))
        self.assertTrue(self.store.is_device_active(device))

    def test_token_is_single_use(self):
        _, token = self.store.issue(self.owner)
        self.redeem(token)
        with self.assertRaises(PairingError) as ctx:
            self.redeem(token, key=KEY2)
        self.assertEqual(str(ctx.exception), GENERIC_FAILURE)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0], 1)

    def test_expired_token_rejected_but_valid_just_before_expiry(self):
        _, t1 = self.store.issue(self.owner, ttl_seconds=60)
        self.clock.now += timedelta(seconds=59)
        self.redeem(t1)
        _, t2 = self.store.issue(self.owner, ttl_seconds=60)
        self.clock.now += timedelta(seconds=60)
        with self.assertRaises(PairingError):
            self.redeem(t2, key=KEY2)

    def test_revoked_token_rejected(self):
        tid, token = self.store.issue(self.owner)
        self.conn.execute("UPDATE pairing_tokens SET revoked_at = '2026-01-01T00:00:00.000000Z' WHERE id = ?", (tid,))
        with self.assertRaises(PairingError):
            self.redeem(token)

    def test_all_failures_look_identical(self):
        _, token = self.store.issue(self.owner)
        messages = set()
        for t, k in (("nxp_wrong", KEY1), (token, "not-base64!!"), (token, base64.b64encode(b"short").decode()),
                     ("", KEY1)):
            with self.assertRaises(PairingError) as ctx:
                self.redeem(t, key=k)
            messages.add(str(ctx.exception))
        self.assertEqual(messages, {GENERIC_FAILURE})

    def test_same_public_key_cannot_pair_twice(self):
        _, t1 = self.store.issue(self.owner); _, t2 = self.store.issue(self.owner)
        self.redeem(t1)
        with self.assertRaises(PairingError):
            self.redeem(t2)
        # the failed redeem must not burn the second token
        self.assertIsNone(self.conn.execute("SELECT used_at FROM pairing_tokens WHERE token_hash = ?",
                                            (hash_token(t2),)).fetchone()["used_at"])
        self.redeem(t2, key=KEY2)

    def test_plaintext_token_is_never_stored(self):
        _, token = self.store.issue(self.owner)
        dump = " ".join(str(tuple(r)) for r in self.conn.execute("SELECT * FROM pairing_tokens"))
        self.assertNotIn(token, dump)
        self.assertIn(hash_token(token), dump)

    def test_ttl_bounds(self):
        for ttl in (0, 29, 3601, -5):
            with self.subTest(ttl=ttl), self.assertRaises(PairingError):
                self.store.issue(self.owner, ttl_seconds=ttl)

    def test_revocation_is_immediate_and_owner_scoped(self):
        _, token = self.store.issue(self.owner)
        device = self.redeem(token)
        stranger = add_user(self.conn)
        self.assertFalse(self.store.revoke_device(device, stranger))
        self.assertTrue(self.store.is_device_active(device))
        self.assertTrue(self.store.revoke_device(device, self.owner))
        self.assertFalse(self.store.is_device_active(device))
        self.assertFalse(self.store.revoke_device(device, self.owner))   # already revoked
        self.assertFalse(self.store.is_device_active("00000000-0000-4000-8000-000000000000"))

    def test_pairing_and_revocation_are_audited(self):
        _, token = self.store.issue(self.owner)
        device = self.redeem(token)
        self.store.revoke_device(device, self.owner)
        actions = [r["action"] for r in self.conn.execute("SELECT action FROM audit_log ORDER BY seq")]
        self.assertEqual(actions, ["device.paired", "device.revoked"])
        self.assertIsNone(self.audit.verify(self.owner))


if __name__ == "__main__":
    unittest.main()
