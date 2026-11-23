from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from nexus_core.messages import Envelope, MessageType
from nexus_core.patch_apply import PatchApplyError, apply_patch, rollback_patch
from nexus_core.ids import new_id


class TestPatchApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "workspace"
        self.backups = self.base / "backups"
        self.workspace.mkdir()
        self.backups.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def envelope(self, operation, **fields):
        return Envelope.create(
            task_id=new_id(),
            project_id=new_id(),
            session_id=new_id(),
            message_type=MessageType.FILE_PATCH,
            source="orchestrator",
            destination="worker",
            payload={
                "patch_id": new_id(),
                "path": "sample.txt",
                "operation": operation,
                **fields,
            },
        )

    def test_create_requires_approval_and_creates_backup_record(self):
        message = self.envelope("create", content="hello")

        with self.assertRaises(PatchApplyError):
            apply_patch(
                message,
                workspace=self.workspace,
                backup_root=self.backups,
            )

        result = apply_patch(
            message,
            workspace=self.workspace,
            backup_root=self.backups,
            approved=True,
        )

        self.assertEqual((self.workspace / "sample.txt").read_text(), "hello")
        self.assertEqual(result.operation, "create")
        self.assertIsNone(result.before_sha256)
        self.assertEqual(
            result.after_sha256,
            hashlib.sha256(b"hello").hexdigest(),
        )

    def test_create_refuses_existing_file(self):
        (self.workspace / "sample.txt").write_text("existing")
        message = self.envelope("create", content="replacement")

        with self.assertRaises(PatchApplyError):
            apply_patch(
                message,
                workspace=self.workspace,
                backup_root=self.backups,
                approved=True,
            )

        self.assertEqual((self.workspace / "sample.txt").read_text(), "existing")

    def test_delete_checks_base_hash_and_creates_backup(self):
        target = self.workspace / "sample.txt"
        target.write_text("original")
        digest = hashlib.sha256(b"original").hexdigest()
        message = self.envelope("delete", base_sha256=digest)

        result = apply_patch(
            message,
            workspace=self.workspace,
            backup_root=self.backups,
            approved=True,
        )

        self.assertFalse(target.exists())
        self.assertEqual(result.before_sha256, digest)
        self.assertTrue(Path(result.backup_path).is_file())
        self.assertEqual(Path(result.backup_path).read_bytes(), b"original")

    def test_delete_rejects_hash_mismatch(self):
        target = self.workspace / "sample.txt"
        target.write_text("changed")
        message = self.envelope("delete", base_sha256="0" * 64)

        with self.assertRaises(PatchApplyError):
            apply_patch(
                message,
                workspace=self.workspace,
                backup_root=self.backups,
                approved=True,
            )

        self.assertEqual(target.read_text(), "changed")

    def test_modify_applies_diff_and_creates_backup(self):
        target = self.workspace / "sample.txt"
        original = b"before\n"
        target.write_bytes(original)
        digest = hashlib.sha256(original).hexdigest()

        message = self.envelope(
            "modify",
            diff="--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-before\n+after\n",
            base_sha256=digest,
        )

        result = apply_patch(
            message,
            workspace=self.workspace,
            backup_root=self.backups,
            approved=True,
        )

        updated = b"after\n"
        self.assertEqual(target.read_bytes(), updated)
        self.assertEqual(result.before_sha256, digest)
        self.assertEqual(result.after_sha256, hashlib.sha256(updated).hexdigest())
        self.assertEqual(Path(result.backup_path).read_bytes(), original)


    def test_rollback_create_removes_created_file(self):
        message = self.envelope("create", content="hello")
        result = apply_patch(
            message, workspace=self.workspace,
            backup_root=self.backups, approved=True,
        )
        rollback_patch(
            result.patch_id, workspace=self.workspace,
            backup_root=self.backups, approved=True,
        )
        self.assertFalse((self.workspace / "sample.txt").exists())

    def test_rollback_modify_restores_original_file(self):
        target = self.workspace / "sample.txt"
        target.write_bytes(b"before\n")
        digest = hashlib.sha256(b"before\n").hexdigest()
        message = self.envelope(
            "modify",
            diff="--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-before\n+after\n",
            base_sha256=digest,
        )
        result = apply_patch(
            message, workspace=self.workspace,
            backup_root=self.backups, approved=True,
        )
        rollback_patch(
            result.patch_id, workspace=self.workspace,
            backup_root=self.backups, approved=True,
        )
        self.assertEqual(target.read_bytes(), b"before\n")

    def test_rollback_delete_restores_deleted_file(self):
        target = self.workspace / "sample.txt"
        target.write_bytes(b"original")
        digest = hashlib.sha256(b"original").hexdigest()
        message = self.envelope("delete", base_sha256=digest)
        result = apply_patch(
            message, workspace=self.workspace,
            backup_root=self.backups, approved=True,
        )
        rollback_patch(
            result.patch_id, workspace=self.workspace,
            backup_root=self.backups, approved=True,
        )
        self.assertEqual(target.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
