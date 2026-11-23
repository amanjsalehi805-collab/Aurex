import unittest

from nexus_core.states import (
    ACTIVE,
    SUSPENDED,
    TERMINAL,
    InvalidTransition,
    TaskState as S,
    allowed_transitions,
    check_transition,
)

HAPPY = [
    S.RECEIVE_TASK,
    S.IDENTIFY_PROJECT,
    S.LOAD_CONTEXT,
    S.ANALYZE_REQUIREMENTS,
    S.CREATE_PLAN,
    S.REQUEST_APPROVAL_IF_NEEDED,
    S.GENERATE_CHANGES,
    S.VALIDATE_CHANGES,
    S.APPLY_CHANGES,
    S.EXECUTE_COMMANDS,
    S.COLLECT_OUTPUT,
    S.ANALYZE_RESULTS,
    S.RETURN_RESULTS_TO_AI,
    S.CONTINUE_OR_RETRY,
    S.RUN_FINAL_TESTS,
    S.GENERATE_COMPLETION_REPORT,
    S.COMPLETED,
]


class TestStates(unittest.TestCase):
    def test_spec_cycle_is_walkable(self):
        for a, b in zip(HAPPY, HAPPY[1:]):
            check_transition(a, b)

    def test_cannot_skip_steps(self):
        for a, b in (
            (S.RECEIVE_TASK, S.APPLY_CHANGES),
            (S.CREATE_PLAN, S.EXECUTE_COMMANDS),
            (S.GENERATE_CHANGES, S.APPLY_CHANGES),
            (S.RUN_FINAL_TESTS, S.COMPLETED),
        ):
            with self.subTest(a=a, b=b), self.assertRaises(InvalidTransition):
                check_transition(a, b)

    def test_retry_loops_exist_but_are_bounded_by_db_iteration_check(self):
        check_transition(S.CONTINUE_OR_RETRY, S.GENERATE_CHANGES)
        check_transition(S.CONTINUE_OR_RETRY, S.EXECUTE_COMMANDS)
        check_transition(S.VALIDATE_CHANGES, S.GENERATE_CHANGES)
        check_transition(S.RUN_FINAL_TESTS, S.CONTINUE_OR_RETRY)

    def test_terminal_states_have_no_exits(self):
        for t in TERMINAL:
            self.assertEqual(allowed_transitions(t), frozenset())
            with self.assertRaises(InvalidTransition):
                check_transition(t, S.RECEIVE_TASK)

    def test_every_active_state_can_pause_wait_cancel_fail(self):
        for s in ACTIVE:
            allowed = allowed_transitions(s)
            self.assertTrue({S.PAUSED, S.WAITING_APPROVAL, S.CANCELLED, S.FAILED} <= allowed, s)

    def test_suspended_resumes_only_to_saved_state(self):
        for s in SUSPENDED:
            check_transition(s, S.EXECUTE_COMMANDS, resume_state=S.EXECUTE_COMMANDS)
            check_transition(s, S.CANCELLED, resume_state=S.EXECUTE_COMMANDS)
            with self.assertRaises(InvalidTransition):
                check_transition(s, S.APPLY_CHANGES, resume_state=S.EXECUTE_COMMANDS)
            with self.assertRaises(InvalidTransition):
                allowed_transitions(s)
            with self.assertRaises(InvalidTransition):
                allowed_transitions(s, resume_state=S.PAUSED)

    def test_no_self_transitions(self):
        for s in S:
            self.assertNotIn(
                s,
                allowed_transitions(s, resume_state=S.CREATE_PLAN)
                if s in SUSPENDED
                else allowed_transitions(s),
            )

    def test_partition(self):
        self.assertEqual(ACTIVE | SUSPENDED | TERMINAL, set(S))
        self.assertEqual(len(S), 21)


if __name__ == "__main__":
    unittest.main()
