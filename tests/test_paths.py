import os
import tempfile
import unittest
from pathlib import Path

from nexus_core.paths import (PathSecurityError, assert_workspaces_disjoint, resolve_in_workspace,
                              validate_relative_path, validate_workspace_root)


class TestLexical(unittest.TestCase):
    def test_accepts_normal_paths_and_normalises(self):
        self.assertEqual(validate_relative_path("a/b.txt"), "a/b.txt")
        self.assertEqual(validate_relative_path("./a//b"), "a/b")
        self.assertEqual(validate_relative_path(".", allow_root=True), ".")

    def test_rejects_attacks(self):
        bad = ["", "..", "../x", "a/../../x", "a/..", "/etc/passwd", "~", "~root/x", "C:\\Windows",
               "c:/x", "a\\..\\b", "a\x00b", "a\nb", "a\x7fb", "x" * 5000, ".", "./", "//"]
        for p in bad:
            with self.subTest(p=p), self.assertRaises(PathSecurityError):
                validate_relative_path(p)

    def test_non_string(self):
        for p in (None, 5, b"a", ["a"]):
            with self.assertRaises(PathSecurityError):
                validate_relative_path(p)  # type: ignore[arg-type]


class TestResolve(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(os.path.realpath(self._tmp.name))
        self.ws = base / "ws"
        self.outside = base / "outside"
        self.ws.mkdir(); self.outside.mkdir()
        (self.outside / "secret.txt").write_text("s")
        (self.ws / "src").mkdir()
        (self.ws / "src" / "a.py").write_text("x")
        os.symlink(self.outside, self.ws / "linkdir")
        os.symlink(self.outside / "secret.txt", self.ws / "linkfile")
        os.symlink("src", self.ws / "inner_link")
        self.base = base

    def tearDown(self):
        self._tmp.cleanup()

    def test_existing_and_new_files_resolve_inside(self):
        self.assertEqual(resolve_in_workspace(self.ws, "src/a.py"), self.ws / "src" / "a.py")
        self.assertEqual(resolve_in_workspace(self.ws, "src/new/deep.py", for_write=True),
                         self.ws / "src" / "new" / "deep.py")
        self.assertEqual(resolve_in_workspace(self.ws, ".", allow_root=True), self.ws)

    def test_symlink_escapes_are_blocked(self):
        for rel in ("linkdir", "linkdir/secret.txt", "linkdir/new.txt", "linkfile", "linkdir/../x"):
            with self.subTest(rel=rel), self.assertRaises(PathSecurityError):
                resolve_in_workspace(self.ws, rel)

    def test_symlink_staying_inside_is_allowed(self):
        self.assertEqual(resolve_in_workspace(self.ws, "inner_link/a.py"), self.ws / "src" / "a.py")

    def test_sibling_prefix_directory_is_not_inside(self):
        evil = self.base / "ws-evil"
        evil.mkdir()
        os.symlink(evil, self.ws / "evil")
        with self.assertRaises(PathSecurityError):
            resolve_in_workspace(self.ws, "evil/x")

    def test_protected_git_paths_not_writable(self):
        (self.ws / ".git").mkdir()
        for rel in (".git/config", ".git/hooks/pre-commit", ".GIT/config", "src/.git/hooks/x", ".Git"):
            with self.subTest(rel=rel), self.assertRaises(PathSecurityError):
                resolve_in_workspace(self.ws, rel, for_write=True)
        resolve_in_workspace(self.ws, ".git/config")  # reading is a separate policy decision
        resolve_in_workspace(self.ws, ".gitignore", for_write=True)
        resolve_in_workspace(self.ws, ".github/workflows/ci.yml", for_write=True)

    def test_symlink_into_git_dir_not_writable(self):
        (self.ws / ".git").mkdir()
        os.symlink(self.ws / ".git", self.ws / "sneaky")
        with self.assertRaises(PathSecurityError):
            resolve_in_workspace(self.ws, "sneaky/hooks/x", for_write=True)

    def test_dot_git_symlink_alias_is_blocked_by_its_lexical_name(self):
        (self.ws / "realgit" / "hooks").mkdir(parents=True)
        os.symlink("realgit", self.ws / ".git")
        with self.assertRaises(PathSecurityError):
            resolve_in_workspace(self.ws, ".git/hooks/pre-commit", for_write=True)

    def test_relative_workspace_root_rejected_even_when_directory_exists(self):
        old_cwd = os.getcwd()
        try:
            os.chdir(self.ws.parent)
            with self.assertRaises(PathSecurityError):
                validate_workspace_root("ws")
            with self.assertRaises(PathSecurityError):
                resolve_in_workspace("ws", "src/a.py")
        finally:
            os.chdir(old_cwd)

    def test_bad_roots(self):
        for root in ("/", "relative/dir", str(self.ws / "missing")):
            with self.subTest(root=root), self.assertRaises(PathSecurityError):
                validate_workspace_root(root)

    def test_workspaces_must_be_disjoint(self):
        a, b, nested = self.base / "a", self.base / "b", self.base / "a" / "inner"
        for d in (a, b, nested):
            d.mkdir(parents=True, exist_ok=True)
        assert_workspaces_disjoint({"p1": a, "p2": b})
        with self.assertRaises(PathSecurityError):
            assert_workspaces_disjoint({"p1": a, "p2": nested})
        with self.assertRaises(PathSecurityError):
            assert_workspaces_disjoint({"p1": a, "p2": a})
        os.symlink(a, self.base / "alias")
        with self.assertRaises(PathSecurityError):
            assert_workspaces_disjoint({"p1": a, "p2": self.base / "alias"})


if __name__ == "__main__":
    unittest.main()
