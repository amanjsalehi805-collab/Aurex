import hashlib
import json
import unittest

from nexus_core.clock import format_ts, utc_now
from nexus_core.ids import new_id
from nexus_core.messages import (
    ALLOWED_SOURCES,
    MAX_ENVELOPE_BYTES,
    PAYLOAD_SPECS,
    Envelope,
    MessageType as MT,
    ProtocolError,
)

T, P, S = new_id(), new_id(), new_id()
NOW = format_ts(utc_now())
SHA = hashlib.sha256(b"x").hexdigest()


def env(mt, source, destination, payload, correlation=None):
    return Envelope.create(
        task_id=T,
        project_id=P,
        session_id=S,
        message_type=mt,
        source=source,
        destination=destination,
        payload=payload,
        correlation_id=correlation,
    )


def shell(**over):
    p = {
        "command_id": new_id(),
        "command": "ls -la",
        "cwd": ".",
        "target": "cloud",
        "timeout_seconds": 60,
        "idempotency_key": "key-0001-abcd",
        "purpose": "list",
        "network": "none",
    }
    p.update(over)
    return p


def result(**over):
    p = {
        "execution_id": new_id(),
        "command_id": new_id(),
        "status": "succeeded",
        "exit_code": 0,
        "started_at": NOW,
        "finished_at": NOW,
        "duration_ms": 5,
        "cwd": ".",
        "target": "cloud",
        "stdout_chunks": 1,
        "stderr_chunks": 0,
        "output_truncated": False,
    }
    p.update(over)
    return p


VALID = {
    MT.AI_REQUEST: (
        "orchestrator",
        "ai:anthropic",
        {
            "provider": "anthropic",
            "model": "m",
            "purpose": "plan",
            "context_message_ids": [],
            "redacted": True,
        },
        None,
    ),
    MT.AI_RESPONSE: (
        "ai:anthropic",
        "orchestrator",
        {"provider": "anthropic", "model": "m", "text": "hi"},
        None,
    ),
    MT.CODE_BLOCK: (
        "ai:anthropic",
        "orchestrator",
        {
            "block_id": new_id(),
            "language": "python",
            "purpose": "source_file",
            "destination_path": "src/a.py",
            "content": "print(1)\n",
        },
        None,
    ),
    MT.SHELL_COMMAND: ("orchestrator", "worker:w1", shell(), None),
    MT.FILE_PATCH: (
        "orchestrator",
        "device:d1",
        {"patch_id": new_id(), "path": "a.txt", "operation": "create", "content": "x"},
        None,
    ),
    MT.TERMINAL_STDOUT: (
        "worker:w1",
        "orchestrator",
        {"execution_id": new_id(), "command_id": new_id(), "seq": 0, "data": "out"},
        new_id(),
    ),
    MT.TERMINAL_STDERR: (
        "device:d1",
        "orchestrator",
        {"execution_id": new_id(), "command_id": new_id(), "seq": 0, "data": "err"},
        new_id(),
    ),
    MT.EXECUTION_RESULT: ("worker:w1", "orchestrator", result(), new_id()),
    MT.TEST_RESULT: (
        "worker:w1",
        "orchestrator",
        {
            "execution_id": new_id(),
            "runner": "unittest",
            "status": "passed",
            "exit_code": 0,
            "passed": 3,
            "failed": 0,
            "skipped": 0,
        },
        new_id(),
    ),
    MT.APPROVAL_REQUEST: (
        "orchestrator",
        "user:u1",
        {
            "approval_id": new_id(),
            "risk_category": "git_push",
            "action": "git push",
            "affected": ["origin/main"],
            "reason": "r",
            "consequences": "c",
            "action_sha256": SHA,
        },
        None,
    ),
    MT.APPROVAL_RESPONSE: (
        "user:u1",
        "orchestrator",
        {"approval_id": new_id(), "decision": "approved", "decided_by": "u1"},
        new_id(),
    ),
    MT.ERROR_REPORT: (
        "worker:w1",
        "orchestrator",
        {"code": "E1", "message": "boom", "retryable": False},
        None,
    ),
    MT.TASK_STATUS: ("orchestrator", "user:u1", {"state": "CREATE_PLAN"}, None),
}


class TestEnvelope(unittest.TestCase):
    def test_every_type_has_valid_example_spec_and_source_rule(self):
        self.assertEqual(set(VALID), set(MT))
        self.assertEqual(set(PAYLOAD_SPECS), set(MT))
        self.assertEqual(set(ALLOWED_SOURCES), set(MT))

    def test_valid_envelopes_round_trip(self):
        for mt, (src, dst, payload, corr) in VALID.items():
            with self.subTest(mt=mt):
                e = env(mt, src, dst, payload, corr)
                again = Envelope.from_json(e.to_json())
                self.assertEqual(again, e)
                self.assertEqual(again.to_json(), e.to_json())

    def test_payload_hash_is_deterministic_and_key_order_independent(self):
        a = env(
            MT.ERROR_REPORT,
            "worker",
            "orchestrator",
            {"code": "c", "message": "m", "retryable": True},
        )
        b = env(
            MT.ERROR_REPORT,
            "worker",
            "orchestrator",
            {"retryable": True, "message": "m", "code": "c"},
        )
        self.assertEqual(a.payload_sha256(), b.payload_sha256())

    def test_unknown_top_level_and_payload_fields_rejected(self):
        d = env(
            MT.ERROR_REPORT,
            "worker",
            "orchestrator",
            {"code": "c", "message": "m", "retryable": True},
        ).to_dict()
        with self.assertRaises(ProtocolError):
            Envelope.from_dict({**d, "extra": 1})
        d2 = json.loads(json.dumps(d))
        d2["payload"]["surprise"] = 1
        with self.assertRaises(ProtocolError):
            Envelope.from_dict(d2)
        d3 = dict(d)
        del d3["status"]
        with self.assertRaises(ProtocolError):
            Envelope.from_dict(d3)

    def test_strict_json(self):
        good = env(MT.TASK_STATUS, "orchestrator", "user", {"state": "CREATE_PLAN"}).to_json()
        dup = good.replace('"status":"pending"', '"status":"pending","status":"processed"')
        with self.assertRaises(ProtocolError):
            Envelope.from_json(dup)
        with self.assertRaises(ProtocolError):
            Envelope.from_json(good.replace('"iteration"', '"x"').replace("CREATE_PLAN", "NaN"))
        with self.assertRaises(ProtocolError):
            Envelope.from_json("not json")
        with self.assertRaises(ProtocolError):
            Envelope.from_json("[1]")
        with self.assertRaises(ProtocolError):
            Envelope.from_json(b"x" * (MAX_ENVELOPE_BYTES + 1))
        with self.assertRaises(ProtocolError):
            Envelope.from_json('{"protocol_version": NaN}')

    def test_wrong_types_and_bool_is_not_int(self):
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(timeout_seconds=True))
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(timeout_seconds="60"))
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(command=""))
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(command="a\x00b"))

    def test_bad_ids_timestamps_endpoints_versions(self):
        base = dict(
            task_id=T,
            project_id=P,
            session_id=S,
            message_type=MT.TASK_STATUS,
            source="orchestrator",
            destination="user",
            payload={"state": "CREATE_PLAN"},
            timestamp=NOW,
            message_id=new_id(),
        )
        for bad in (
            {"task_id": "nope"},
            {"source": "root"},
            {"destination": "user:../x"},
            {"timestamp": "2026-01-01 00:00:00"},
            {"protocol_version": 2},
            {"correlation_id": "nope"},
            {"message_type": "RUN_THIS"},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ProtocolError):
                    Envelope(**{**base, **bad})


class TestSeparation(unittest.TestCase):
    """Code, commands, output and explanations can never be confused."""

    def test_code_block_cannot_carry_a_command_or_be_a_shell_payload(self):
        p = dict(VALID[MT.CODE_BLOCK][2], command="rm -rf /")
        with self.assertRaises(ProtocolError):
            env(MT.CODE_BLOCK, "ai", "orchestrator", p)
        with self.assertRaises(ProtocolError):  # code payload under a shell type
            env(MT.SHELL_COMMAND, "orchestrator", "worker", VALID[MT.CODE_BLOCK][2])
        with self.assertRaises(ProtocolError):  # shell payload under a code type
            env(MT.CODE_BLOCK, "ai", "orchestrator", shell())

    def test_code_block_destination_rules(self):
        base = VALID[MT.CODE_BLOCK][2]
        with self.assertRaises(ProtocolError):
            env(MT.CODE_BLOCK, "ai", "orchestrator", {**base, "destination_path": None})
        env(
            MT.CODE_BLOCK,
            "ai",
            "orchestrator",
            {**base, "purpose": "snippet_only", "destination_path": None},
        )
        with self.assertRaises(ProtocolError):
            env(MT.CODE_BLOCK, "ai", "orchestrator", {**base, "purpose": "snippet_only"})
        with self.assertRaises(ProtocolError):
            env(
                MT.CODE_BLOCK,
                "ai",
                "orchestrator",
                {k: v for k, v in base.items() if k != "destination_path"},
            )
        with self.assertRaises(ProtocolError):
            env(MT.CODE_BLOCK, "ai", "orchestrator", {**base, "content_sha256": SHA})
        ok = {**base, "content_sha256": hashlib.sha256(base["content"].encode()).hexdigest()}
        env(MT.CODE_BLOCK, "ai", "orchestrator", ok)

    def test_terminal_output_cannot_be_a_file_write(self):
        out = VALID[MT.TERMINAL_STDOUT][2]
        with self.assertRaises(ProtocolError):
            env(MT.FILE_PATCH, "orchestrator", "device", out)
        with self.assertRaises(ProtocolError):
            env(MT.CODE_BLOCK, "ai", "orchestrator", out)

    def test_explicit_target_required_and_validated(self):
        p = shell()
        del p["target"]
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", p)
        for bad in ("auto", "", "CLOUD", None):
            with self.assertRaises(ProtocolError):
                env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(target=bad))

    def test_every_command_has_a_bounded_timeout(self):
        for bad in (0, -1, 3601, 10**9):
            with self.subTest(timeout=bad), self.assertRaises(ProtocolError):
                env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(timeout_seconds=bad))
        for ok in (1, 3600):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(timeout_seconds=ok))

    def test_cwd_traversal_rejected(self):
        for bad in ("..", "../x", "/etc", "a/../..", "~", "C:\\x"):
            with self.subTest(cwd=bad), self.assertRaises(ProtocolError):
                env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(cwd=bad))
        env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(cwd="sub/dir"))

    def test_scoped_network_requires_approval_and_none_forbids_it(self):
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(network="scoped"))
        env(
            MT.SHELL_COMMAND,
            "orchestrator",
            "worker",
            shell(network="scoped", approval_id=new_id()),
        )
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "worker", shell(approval_id=new_id()))

    def test_ai_request_must_attest_redaction(self):
        p = dict(VALID[MT.AI_REQUEST][2], redacted=False)
        with self.assertRaises(ProtocolError):
            env(MT.AI_REQUEST, "orchestrator", "ai", p)


class TestProvenanceAndRouting(unittest.TestCase):
    def test_ai_can_only_propose_never_report_or_approve(self):
        for mt in (
            MT.EXECUTION_RESULT,
            MT.TERMINAL_STDOUT,
            MT.TERMINAL_STDERR,
            MT.TEST_RESULT,
            MT.APPROVAL_RESPONSE,
            MT.APPROVAL_REQUEST,
            MT.TASK_STATUS,
            MT.ERROR_REPORT,
        ):
            _, dst, payload, corr = VALID[mt]
            with self.subTest(mt=mt), self.assertRaises(ProtocolError):
                env(mt, "ai:anthropic", dst, payload, corr)

    def test_only_a_user_can_approve(self):
        _, dst, payload, corr = VALID[MT.APPROVAL_RESPONSE]
        for src in ("worker", "device", "orchestrator", "system", "ai"):
            with self.subTest(src=src), self.assertRaises(ProtocolError):
                env(MT.APPROVAL_RESPONSE, src, dst, payload, corr)

    def test_ai_output_cannot_reach_an_executor_directly(self):
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "ai:anthropic", "device:d1", shell())
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "ai:anthropic", "worker:w1", shell())
        env(MT.SHELL_COMMAND, "ai:anthropic", "orchestrator", shell())  # proposal is fine

    def test_orchestrator_dispatch_must_target_executor(self):
        with self.assertRaises(ProtocolError):
            env(MT.SHELL_COMMAND, "orchestrator", "user:u1", shell())

    def test_results_must_go_to_orchestrator_and_be_correlated(self):
        _, _, payload, corr = VALID[MT.EXECUTION_RESULT]
        with self.assertRaises(ProtocolError):
            env(MT.EXECUTION_RESULT, "worker", "user", payload, corr)
        with self.assertRaises(ProtocolError):
            env(MT.EXECUTION_RESULT, "worker", "orchestrator", payload, None)


class TestResultConsistency(unittest.TestCase):
    def mk(self, **over):
        return env(MT.EXECUTION_RESULT, "worker", "orchestrator", result(**over), new_id())

    def test_success_requires_exit_zero(self):
        self.mk()
        for code in (1, -1, None):
            with self.subTest(code=code), self.assertRaises(ProtocolError):
                self.mk(exit_code=code)

    def test_failed_requires_nonzero(self):
        self.mk(status="failed", exit_code=2)
        for code in (0, None):
            with self.subTest(code=code), self.assertRaises(ProtocolError):
                self.mk(status="failed", exit_code=code)

    def test_other_statuses(self):
        self.mk(status="timed_out", exit_code=-9)
        self.mk(status="timed_out", exit_code=None)
        self.mk(status="cancelled", exit_code=None, finished_at=None)
        self.mk(
            status="not_executed",
            exit_code=None,
            started_at=None,
            finished_at=None,
            duration_ms=None,
        )
        self.mk(status="unknown", exit_code=None, finished_at=None)
        with self.assertRaises(ProtocolError):
            self.mk(status="not_executed", exit_code=0, started_at=None)
        with self.assertRaises(ProtocolError):
            self.mk(status="unknown", exit_code=0)
        with self.assertRaises(ProtocolError):
            self.mk(status="timed_out", exit_code=None, started_at=None)
        with self.assertRaises(ProtocolError):
            self.mk(status="finished-ish")

    def test_output_truncation_must_be_declared(self):
        p = result()
        del p["output_truncated"]
        with self.assertRaises(ProtocolError):
            env(MT.EXECUTION_RESULT, "worker", "orchestrator", p, new_id())

    def test_finish_not_before_start(self):
        with self.assertRaises(ProtocolError):
            self.mk(
                started_at="2026-01-02T00:00:00.000000Z", finished_at="2026-01-01T00:00:00.000000Z"
            )

    def test_test_result_cannot_claim_pass_with_failures(self):
        base = VALID[MT.TEST_RESULT][2]
        for bad in ({"failed": 1}, {"exit_code": 1}, {"exit_code": None}):
            with self.subTest(bad=bad), self.assertRaises(ProtocolError):
                env(MT.TEST_RESULT, "worker", "orchestrator", {**base, **bad}, new_id())


class TestFilePatch(unittest.TestCase):
    def mk(self, **p):
        return env(MT.FILE_PATCH, "orchestrator", "worker", {"patch_id": new_id(), **p})

    def test_operation_field_rules(self):
        self.mk(path="a", operation="modify", diff="@@", base_sha256=SHA)
        self.mk(path="a", operation="create", content="x")
        self.mk(path="a", operation="delete", base_sha256=SHA)
        for bad in (
            {"operation": "modify", "diff": "@@"},
            {"operation": "modify", "diff": "@@", "base_sha256": SHA, "content": "x"},
            {"operation": "create", "content": "x", "diff": "@@"},
            {"operation": "delete"},
            {"operation": "delete", "base_sha256": SHA, "content": "x"},
            {"operation": "rename", "content": "x"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ProtocolError):
                self.mk(path="a", **bad)

    def test_patch_path_traversal(self):
        for bad in ("../a", "/etc/passwd", "a/../../b", ""):
            with self.subTest(p=bad), self.assertRaises(ProtocolError):
                self.mk(path=bad, operation="create", content="x")


if __name__ == "__main__":
    unittest.main()
