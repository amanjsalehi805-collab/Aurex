"""Device pairing primitives: one-time, expiring, hashed tokens; revocable device identities.

Flow (completed in Phase 3): user issues a token in the Control Center -> types it into Termux ->
agent redeems it together with its Ed25519 PUBLIC key -> the device is 'active'. Afterwards every
agent connection must prove possession of the private key (challenge-response, Phase 3).
Only the SHA-256 of a token is stored. All redeem failures return the same message.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
import sqlite3
from datetime import timedelta

from .audit import AuditLog
from .clock import Clock, format_ts, utc_now
from .db import transaction
from .ids import new_id

TOKEN_PREFIX = "nxp_"
MIN_TTL, MAX_TTL = 30, 3600
GENERIC_FAILURE = "invalid or expired pairing token"


class PairingError(Exception):
    pass


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _valid_public_key(value: str) -> bool:
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (binascii.Error, ValueError, TypeError):
        return False


class PairingStore:
    def __init__(self, conn: sqlite3.Connection, clock: Clock = utc_now,
                 audit: AuditLog | None = None) -> None:
        self._conn, self._clock, self._audit = conn, clock, audit

    def _log(self, owner_id: str, action: str, subject_id: str, actor_type: str, actor_id: str | None) -> None:
        if self._audit:
            self._audit.append(owner_id=owner_id, actor_type=actor_type, actor_id=actor_id,
                               action=action, subject_type="device", subject_id=subject_id)

    def issue(self, owner_id: str, ttl_seconds: int = 600) -> tuple[str, str]:
        if not (MIN_TTL <= ttl_seconds <= MAX_TTL):
            raise PairingError(f"ttl must be between {MIN_TTL} and {MAX_TTL} seconds")
        token, token_id, now = generate_token(), new_id(), self._clock()
        self._conn.execute(
            "INSERT INTO pairing_tokens (id, owner_id, token_hash, created_at, expires_at) VALUES (?,?,?,?,?)",
            (token_id, owner_id, hash_token(token), format_ts(now), format_ts(now + timedelta(seconds=ttl_seconds))),
        )
        return token_id, token

    def redeem(self, token: str, *, device_name: str, platform: str, public_key: str) -> str:
        if not isinstance(token, str) or not _valid_public_key(public_key):
            raise PairingError(GENERIC_FAILURE)
        now = format_ts(self._clock())
        device_id = new_id()
        with transaction(self._conn):
            row = self._conn.execute(
                "SELECT id, owner_id, expires_at, used_at, revoked_at FROM pairing_tokens WHERE token_hash = ?",
                (hash_token(token),),
            ).fetchone()
            if row is None or row["used_at"] or row["revoked_at"] or row["expires_at"] <= now:
                raise PairingError(GENERIC_FAILURE)
            try:
                self._conn.execute(
                    "INSERT INTO devices (id, owner_id, name, platform, public_key, status, paired_at)"
                    " VALUES (?,?,?,?,?, 'active', ?)",
                    (device_id, row["owner_id"], device_name, platform, public_key, now),
                )
            except sqlite3.IntegrityError as exc:
                raise PairingError(GENERIC_FAILURE) from exc
            changed = self._conn.execute(
                "UPDATE pairing_tokens SET used_at = ?, device_id = ? WHERE id = ? AND used_at IS NULL AND revoked_at IS NULL",
                (now, device_id, row["id"]),
            ).rowcount
            if changed != 1:
                raise PairingError(GENERIC_FAILURE)
            owner = row["owner_id"]
        self._log(owner, "device.paired", device_id, "device", device_id)
        return device_id

    def revoke_device(self, device_id: str, owner_id: str) -> bool:
        changed = self._conn.execute(
            "UPDATE devices SET status='revoked', revoked_at=? WHERE id=? AND owner_id=? AND status='active'",
            (format_ts(self._clock()), device_id, owner_id),
        ).rowcount
        if changed:
            self._log(owner_id, "device.revoked", device_id, "user", owner_id)
        return bool(changed)

    def is_device_active(self, device_id: str) -> bool:
        row = self._conn.execute("SELECT status FROM devices WHERE id = ?", (device_id,)).fetchone()
        return bool(row and row["status"] == "active")
