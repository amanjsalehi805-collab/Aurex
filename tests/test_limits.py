import unittest

from nexus_core.ids import new_id
from nexus_core.limits import (
    ExecutionLimits,
    LimitsError,
    NetworkPolicy,
    UnsupportedInThisPhase,
    docker_run_args,
)

KW = dict(
    image="python:3.12-slim",
    workspace_host_path="/srv/ws/p1",
    container_name="nexus-job1",
    cwd=".",
    command=["sh", "-c", "pytest"],
)


class TestLimits(unittest.TestCase):
    def test_defaults_are_safe(self):
        lim = ExecutionLimits()
        self.assertEqual(lim.network.mode, "none")
        self.assertEqual(lim.filesystem, "workspace_rw")
        self.assertLessEqual(lim.timeout_seconds, 600)

    def test_ceilings_and_types(self):
        for bad in (
            {"timeout_seconds": 0},
            {"timeout_seconds": 10**6},
            {"memory_mb": 10**6},
            {"cpus": 64},
            {"pids": 10**6},
            {"max_output_bytes": 10**12},
            {"timeout_seconds": True},
            {"memory_mb": "1g"},
            {"filesystem": "host_rw"},
        ):
            with self.subTest(bad=bad), self.assertRaises(LimitsError):
                ExecutionLimits(**bad)

    def test_network_policy_rules(self):
        a = new_id()
        ExecutionLimits(network=NetworkPolicy("scoped", ("pypi.org", "files.pythonhosted.org"), a))
        for net in (
            NetworkPolicy("scoped"),
            NetworkPolicy("scoped", ("pypi.org",)),
            NetworkPolicy("scoped", (), a),
            NetworkPolicy("scoped", ("*",), a),
            NetworkPolicy("scoped", ("bad host",), a),
            NetworkPolicy("scoped", ("pypi.org",), "not-an-id"),
            NetworkPolicy("none", ("x.org",)),
            NetworkPolicy("none", (), a),
            NetworkPolicy("open"),
        ):
            with self.subTest(net=net), self.assertRaises(LimitsError):
                ExecutionLimits(network=net)

    def test_dict_round_trip_and_unknown_fields(self):
        lim = ExecutionLimits(
            timeout_seconds=42, network=NetworkPolicy("scoped", ("pypi.org",), new_id())
        )
        self.assertEqual(ExecutionLimits.from_dict(lim.to_dict()), lim)
        with self.assertRaises(LimitsError):
            ExecutionLimits.from_dict({"privileged": True})
        with self.assertRaises(LimitsError):
            ExecutionLimits.from_dict({"network": {"mode": "none", "extra": 1}})

    def test_docker_args_contain_every_isolation_flag(self):
        args = docker_run_args(ExecutionLimits(memory_mb=512, cpus=2, pids=100), **KW)
        joined = " ".join(args)
        for needle in (
            "--network none",
            "--memory 512m",
            "--memory-swap 512m",
            "--cpus 2",
            "--pids-limit 100",
            "--read-only",
            "--cap-drop ALL",
            "--security-opt no-new-privileges",
            "--user 10001:10001",
        ):
            self.assertIn(needle, joined)
        self.assertNotIn("--privileged", args)
        self.assertNotIn(
            "host", " ".join(args[args.index("--network") : args.index("--network") + 2])
        )
        self.assertEqual(args[-3:], ["sh", "-c", "pytest"])
        self.assertIn("type=bind,source=/srv/ws/p1,target=/workspace", joined)
        self.assertNotIn("readonly", joined)

    def test_read_only_workspace_and_subdir_cwd(self):
        args = docker_run_args(
            ExecutionLimits(filesystem="workspace_ro"), **{**KW, "cwd": "sub/dir"}
        )
        self.assertIn("type=bind,source=/srv/ws/p1,target=/workspace,readonly", " ".join(args))
        self.assertEqual(args[args.index("--workdir") + 1], "/workspace/sub/dir")

    def test_injection_attempts_rejected(self):
        for over in (
            {"image": "--privileged"},
            {"image": "-v /:/host alpine"},
            {"image": "UPPER"},
            {"container_name": "a b"},
            {"container_name": "--rm"},
            {"workspace_host_path": "/srv/ws,target=/etc"},
            {"workspace_host_path": "/srv/ws\n"},
            {"workspace_host_path": "relative"},
            {"cwd": "../.."},
            {"cwd": "/etc"},
            {"command": []},
            {"command": ["a\x00b"]},
        ):
            with self.subTest(over=over), self.assertRaises(LimitsError):
                docker_run_args(ExecutionLimits(), **{**KW, **over})

    def test_scoped_network_is_refused_until_proxy_exists(self):
        lim = ExecutionLimits(network=NetworkPolicy("scoped", ("pypi.org",), new_id()))
        with self.assertRaises(UnsupportedInThisPhase):
            docker_run_args(lim, **KW)


if __name__ == "__main__":
    unittest.main()
