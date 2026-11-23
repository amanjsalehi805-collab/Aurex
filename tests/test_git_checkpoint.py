import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from nexus_core.git_checkpoint import (
    GitError,
    NotARepository,
    create_checkpoint,
    drop_checkpoint,
    plan_rollback,
    rollback,
)


def git(cwd, *args):
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout


def tree_state(root: Path) -> dict:
    state = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if rel.parts[0] == ".git":
            continue
        state[str(rel)] = p.read_bytes() if p.is_file() else None
    return state


class GitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(os.path.realpath(self._tmp.name)) / "repo"
        self.ws.mkdir()
        git(self.ws, "init", "-q", "-b", "main")
        git(self.ws, "config", "user.email", "t@example.invalid")
        git(self.ws, "config", "user.name", "T")
        (self.ws / ".gitignore").write_text("ignored.log\nbuild/\n")
        (self.ws / "keep.txt").write_text("keep v1\n")
        (self.ws / "edit.txt").write_text("edit v1\n")
        (self.ws / "gone.txt").write_text("gone v1\n")
        git(self.ws, "add", "-A")
        git(self.ws, "commit", "-q", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()


class TestCheckpoint(GitCase):
    def test_checkpoint_leaves_head_branch_index_and_worktree_untouched(self):
        (self.ws / "edit.txt").write_text("edit staged\n")
        git(self.ws, "add", "edit.txt")
        (self.ws / "edit.txt").write_text("edit staged then modified\n")
        (self.ws / "untracked.txt").write_text("u\n")
        before = (
            git(self.ws, "rev-parse", "HEAD"),
            git(self.ws, "status", "--porcelain=v1"),
            git(self.ws, "diff", "--cached"),
            git(self.ws, "branch", "--show-current"),
            tree_state(self.ws),
        )
        cp = create_checkpoint(self.ws, "before risky edit")
        after = (
            git(self.ws, "rev-parse", "HEAD"),
            git(self.ws, "status", "--porcelain=v1"),
            git(self.ws, "diff", "--cached"),
            git(self.ws, "branch", "--show-current"),
            tree_state(self.ws),
        )
        self.assertEqual(before, after)
        self.assertTrue(cp.ref.startswith("refs/nexus/checkpoints/"))
        self.assertEqual(git(self.ws, "rev-parse", cp.ref).strip(), cp.commit_sha)
        self.assertEqual(git(self.ws, "show", f"{cp.commit_sha}:untracked.txt"), "u\n")
        self.assertEqual(
            git(self.ws, "show", f"{cp.commit_sha}:edit.txt"), "edit staged then modified\n"
        )

    def test_ignored_files_not_captured(self):
        (self.ws / "ignored.log").write_text("secret-ish\n")
        cp = create_checkpoint(self.ws, "x")
        names = git(self.ws, "ls-tree", "-r", "--name-only", cp.commit_sha).split()
        self.assertNotIn("ignored.log", names)

    def test_label_is_sanitised(self):
        cp = create_checkpoint(self.ws, "line1\nline2\x00; rm -rf /")
        self.assertNotIn("\n", cp.label)
        self.assertNotIn("\x00", cp.label)

    def test_repo_without_commits(self):
        fresh = self.ws.parent / "fresh"
        fresh.mkdir()
        git(fresh, "init", "-q")
        (fresh / "a.txt").write_text("a\n")
        cp = create_checkpoint(fresh, "first")
        (fresh / "a.txt").write_text("changed\n")
        (fresh / "b.txt").write_text("new\n")
        rollback(fresh, plan_rollback(fresh, cp), confirm=True)
        self.assertEqual(tree_state(fresh), {"a.txt": b"a\n"})

    def test_not_a_repository_or_subdirectory(self):
        plain = self.ws.parent / "plain"
        plain.mkdir()
        with self.assertRaises(NotARepository):
            create_checkpoint(plain, "x")
        (self.ws / "sub").mkdir()
        with self.assertRaises(NotARepository):
            create_checkpoint(self.ws / "sub", "x")
        with self.assertRaises(NotARepository):
            create_checkpoint(self.ws / "missing", "x")


class TestRollback(GitCase):
    def mutate(self):
        (self.ws / "edit.txt").write_text("edit v2 BAD\n")
        (self.ws / "gone.txt").unlink()
        (self.ws / "new_dir" / "deep").mkdir(parents=True)
        (self.ws / "new_dir" / "deep" / "new.py").write_text("print('x')\n")
        (self.ws / "top_new.txt").write_text("n\n")

    def test_full_rollback_restores_exact_state(self):
        (self.ws / "untracked_before.txt").write_text("was here\n")
        snapshot = tree_state(self.ws)
        cp = create_checkpoint(self.ws, "pre")
        self.mutate()
        plan = plan_rollback(self.ws, cp)
        self.assertEqual(plan.restore, ("edit.txt", "gone.txt"))
        self.assertEqual(plan.delete, ("new_dir/deep/new.py", "top_new.txt"))
        rollback(self.ws, plan, confirm=True)
        self.assertEqual(tree_state(self.ws), snapshot)
        self.assertFalse((self.ws / "new_dir").exists())  # emptied directories pruned
        self.assertTrue(plan_rollback(self.ws, cp).is_empty)

    def test_rollback_requires_explicit_confirmation(self):
        cp = create_checkpoint(self.ws, "pre")
        self.mutate()
        plan = plan_rollback(self.ws, cp)
        for bad in (False, None, 1, "yes"):
            with self.subTest(confirm=bad), self.assertRaises(GitError):
                rollback(self.ws, plan, confirm=bad)  # type: ignore[arg-type]
        self.assertEqual((self.ws / "edit.txt").read_text(), "edit v2 BAD\n")

    def test_ignored_files_survive_rollback(self):
        cp = create_checkpoint(self.ws, "pre")
        (self.ws / "ignored.log").write_text("keep me\n")
        (self.ws / "build").mkdir()
        (self.ws / "build" / "out.bin").write_text("artifact\n")
        (self.ws / "edit.txt").write_text("x\n")
        rollback(self.ws, plan_rollback(self.ws, cp), confirm=True)
        self.assertEqual((self.ws / "ignored.log").read_text(), "keep me\n")
        self.assertTrue((self.ws / "build" / "out.bin").exists())

    def test_rollback_does_not_move_head_or_branch_or_user_commits(self):
        cp = create_checkpoint(self.ws, "pre")
        (self.ws / "edit.txt").write_text("committed later\n")
        git(self.ws, "commit", "-q", "-am", "later")
        head = git(self.ws, "rev-parse", "HEAD")
        rollback(self.ws, plan_rollback(self.ws, cp), confirm=True)
        self.assertEqual(git(self.ws, "rev-parse", "HEAD"), head)
        self.assertEqual((self.ws / "edit.txt").read_text(), "edit v1\n")

    def test_rollback_never_follows_symlinks_out_of_workspace(self):
        outside = self.ws.parent / "outside"
        outside.mkdir()
        (outside / "victim.txt").write_text("precious\n")
        cp = create_checkpoint(self.ws, "pre")
        os.symlink(outside, self.ws / "escape")  # created after the checkpoint
        rollback(self.ws, plan_rollback(self.ws, cp), confirm=True)
        self.assertFalse(os.path.lexists(self.ws / "escape"))  # link itself removed
        self.assertEqual((outside / "victim.txt").read_text(), "precious\n")

    def test_files_with_awkward_names(self):
        cp = create_checkpoint(self.ws, "pre")
        for name in ("sp ace.txt", "uni-ç-é.txt", "[glob]*.txt", "-dash.txt"):
            (self.ws / name).write_text("x\n")
        (self.ws / "edit.txt").write_text("changed\n")
        rollback(self.ws, plan_rollback(self.ws, cp), confirm=True)
        for name in ("sp ace.txt", "uni-ç-é.txt", "[glob]*.txt", "-dash.txt"):
            self.assertFalse((self.ws / name).exists(), name)
        self.assertEqual((self.ws / "edit.txt").read_text(), "edit v1\n")

    def test_tampered_checkpoint_rejected(self):
        cp = create_checkpoint(self.ws, "pre")
        forged = type(cp)(cp.checkpoint_id, cp.ref, "0" * 40, cp.label)
        with self.assertRaises(GitError):
            plan_rollback(self.ws, forged)
        bad_ref = type(cp)(cp.checkpoint_id, "refs/heads/main", cp.commit_sha, cp.label)
        with self.assertRaises(GitError):
            plan_rollback(self.ws, bad_ref)

    def test_drop_checkpoint(self):
        cp = create_checkpoint(self.ws, "pre")
        drop_checkpoint(self.ws, cp)
        with self.assertRaises(GitError):
            plan_rollback(self.ws, cp)


if __name__ == "__main__":
    unittest.main()
