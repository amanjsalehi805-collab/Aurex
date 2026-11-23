import tempfile
import unittest
from pathlib import Path

from nexus_core.ids import new_id
from nexus_core.journal import Decision, ExecutionJournal, JournalConflict

K, C = "idem-key-0001", new_id()
ARGS = (K, C, "rm -rf build", ".", "local")


class TestJournal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "journal.db"
        self.j = ExecutionJournal(self.path)

    def tearDown(self):
        self.j.close()
        self._tmp.cleanup()

    def test_first_begin_executes_and_finish_is_recorded(self):
        self.assertEqual(self.j.begin(*ARGS).decision, Decision.EXECUTE)
        rec = self.j.finish(K, "succeeded", 0, duration_ms=12)
        self.assertEqual((rec.status, rec.exit_code, rec.duration_ms), ("succeeded", 0, 12))

    def test_replay_after_finish_returns_stored_result_without_executing(self):
        self.j.begin(*ARGS)
        self.j.finish(K, "failed", 2)
        again = self.j.begin(*ARGS)
        self.assertEqual(again.decision, Decision.ALREADY_FINISHED)
        self.assertEqual((again.record.status, again.record.exit_code), ("failed", 2))

    def test_duplicate_while_running_is_not_executed_twice(self):
        self.j.begin(*ARGS)
        self.assertEqual(self.j.begin(*ARGS).decision, Decision.IN_PROGRESS)

    def test_crash_mid_run_becomes_unknown_and_is_never_auto_rerun(self):
        self.j.begin(*ARGS)  # command started, process dies before finish()
        self.j.close()
        reopened = ExecutionJournal(self.path)
        recovered = reopened.recover_interrupted()
        self.assertEqual([r.status for r in recovered], ["unknown"])
        self.assertIsNone(recovered[0].exit_code)
        self.assertEqual(reopened.begin(*ARGS).decision, Decision.NEEDS_REVIEW)
        with self.assertRaises(
            JournalConflict
        ):  # an unknown run can't be retroactively declared a success
            reopened.finish(K, "succeeded", 0)
        reopened.close()
        self.j = ExecutionJournal(self.path)

    def test_lost_response_is_resendable_not_rerunnable(self):
        self.j.begin(*ARGS)
        self.j.finish(K, "succeeded", 0)
        self.assertEqual([r.idempotency_key for r in self.j.unreported()], [K])
        self.j.mark_reported(K)
        self.assertEqual(self.j.unreported(), [])
        self.assertEqual(self.j.begin(*ARGS).decision, Decision.ALREADY_FINISHED)

    def test_unknown_records_are_reported_to_cloud_too(self):
        self.j.begin(*ARGS)
        self.j.recover_interrupted()
        self.assertEqual([r.status for r in self.j.unreported()], ["unknown"])

    def test_key_reuse_for_different_command_is_a_conflict(self):
        self.j.begin(*ARGS)
        with self.assertRaises(JournalConflict):
            self.j.begin(K, C, "echo hi", ".", "local")
        with self.assertRaises(JournalConflict):
            self.j.begin(K, C, "rm -rf build", ".", "cloud")
        with self.assertRaises(JournalConflict):
            self.j.begin("another-key-0002", C, "x", ".", "local")  # command_id reuse

    def test_invalid_outcomes_rejected(self):
        self.j.begin(*ARGS)
        for status, code in (
            ("succeeded", 1),
            ("succeeded", None),
            ("failed", 0),
            ("failed", None),
            ("unknown", 0),
            ("bogus", 0),
            ("started", None),
        ):
            with self.subTest(status=status, code=code), self.assertRaises(JournalConflict):
                self.j.finish(K, status, code)
        self.assertEqual(self.j.begin(*ARGS).decision, Decision.IN_PROGRESS)  # still 'started'

    def test_cannot_finish_twice_or_unknown_key(self):
        self.j.begin(*ARGS)
        self.j.finish(K, "succeeded", 0)
        with self.assertRaises(JournalConflict):
            self.j.finish(K, "failed", 1)
        with self.assertRaises(JournalConflict):
            self.j.finish("missing-key-0000", "succeeded", 0)

    def test_state_is_durable_across_reopen(self):
        self.j.begin(*ARGS)
        self.j.finish(K, "succeeded", 0)
        self.j.close()
        self.j = ExecutionJournal(self.path)
        self.assertEqual(self.j.begin(*ARGS).decision, Decision.ALREADY_FINISHED)


if __name__ == "__main__":
    unittest.main()
