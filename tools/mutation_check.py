"""Deliberate-fault harness: breaks one safety rule at a time and requires the test-suite to fail.

Run: python tools/mutation_check.py   (restores every file after each mutation)
"""
import subprocess, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, R, L = "src/nexus_core/paths.py", "src/nexus_core/redaction.py", "src/nexus_core/limits.py"
M = [
 # ---- paths
 ("paths", "'..' segments allowed", [(P, 'if any(part == ".." for part in parts):', 'if False:')]),
 ("paths", "absolute '/' paths allowed", [(P, 'if path.startswith("/") or path.startswith("~") or _DRIVE_RE.match(path):', 'if path.startswith("~") or _DRIVE_RE.match(path):')]),
 ("paths", "home '~' / drive-letter paths allowed", [(P, 'if path.startswith("/") or path.startswith("~") or _DRIVE_RE.match(path):', 'if path.startswith("/"):')]),
 ("paths", "backslashes allowed", [(P, r'if "\\" in path:', 'if False:')]),
 ("paths", "control chars / NUL allowed", [(P, 'if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in path):', 'if False:')]),
 ("paths", "over-long paths allowed", [(P, 'if len(path) > MAX_PATH_LEN:', 'if False:')]),
 ("paths", "symlinks not resolved", [(P, 'candidate = Path(os.path.realpath(root_real / normalised))', 'candidate = root_real / normalised')]),
 ("paths", "containment check disabled", [(P, 'if not _within(candidate, root_real):', 'if False:')]),
 ("paths", "containment uses string-prefix (sibling-dir bug)", [(P, 'return child == parent or parent in child.parents', 'return str(child).startswith(str(parent))')]),
 ("paths", ".git protection ignores resolved (symlink) path", [(P, 'for p in lexical_parts + resolved_parts', 'for p in lexical_parts')]),
 ("paths", ".git protection ignores lexical path", [(P, 'for p in lexical_parts + resolved_parts', 'for p in resolved_parts')]),
 ("paths", ".git protection case-sensitive", [(P, '[p.lower() for p in normalised.split("/")]', '[p for p in normalised.split("/")]'), (P, '[p.lower() for p in candidate.relative_to(root_real).parts]', '[p for p in candidate.relative_to(root_real).parts]')]),
 ("paths", ".git protection disabled for_write", [(P, 'if for_write:\n        lexical_parts', 'if False:\n        lexical_parts')]),
 ("paths", "overlap check one-directional", [(P, 'if _within(path_a, path_b) or _within(path_b, path_a):', 'if _within(path_a, path_b):')]),
 ("paths", "overlap check disabled", [(P, 'if _within(path_a, path_b) or _within(path_b, path_a):', 'if False:')]),
 ("paths", "filesystem root allowed as workspace", [(P, 'if real == Path(real.anchor):', 'if False:')]),
 ("paths", "relative workspace root allowed", [(P, 'if not Path(root).is_absolute():', 'if False:')]),
 ("paths", "missing workspace dir allowed", [(P, 'if not real.is_dir():', 'if False:')]),
 # ---- redaction
 ("redaction", "AWS key pattern disabled", [(R, '(?:AKIA|ASIA)', '(?:NEVERMATCHXYZ)')]),
 ("redaction", "Anthropic key pattern disabled", [(R, r'\bsk-ant-', r'\bNEVERMATCHXYZ-')]),
 ("redaction", "OpenAI key pattern disabled", [(R, r'\bsk-(?:proj-|svcacct-)?', r'\bNEVERMATCHXYZ-(?:proj-|svcacct-)?')]),
 ("redaction", "Slack token pattern disabled", [(R, r'\bxox[abprs]-', r'\bNEVERMATCHXYZ-')]),
 ("redaction", "JWT pattern disabled", [(R, r'\beyJ', r'\bNEVERMATCHXYZ')]),
 ("redaction", "PEM truncated-block handling removed", [(R, r'(?:-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|\Z)', r'(?:-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----)')]),
 ("redaction", "URL-credential pattern disabled", [(R, '(?<=://)', '(?<=NEVERMATCHXYZ://)')]),
 ("redaction", "bearer redacts whole match instead of token", [(R, '{16,})"), 1),\n    ("assignment"', '{16,})"), 0),\n    ("assignment"')]),
 ("redaction", "assignment pattern ignores 'password'", [(R, '(?:password|passwd|pwd|secret|', '(?:secret|')]),
 ("redaction", "assignment min value length raised to 40", [(R, '([^\\s\\"\',;]{8,})"), 1),', '([^\\s\\"\',;]{40,})"), 1),')]),
 ("redaction", "known secrets ignored", [(R, 'for secret in self._known:', 'for secret in ():')]),
 ("redaction", "known-secret min length lowered to 1", [(R, 'len(s) >= 8', 'len(s) >= 1')]),
 ("redaction", "overlapping findings not resolved", [(R, 'if finding.start >= last_end:', 'if True:')]),
 ("redaction", "redact() returns text unchanged", [(R, '        findings = self.scan(text)\n        if not findings:\n            return text', '        return text')]),
 ("redaction", "redact_obj ignores secret-looking keys", [(R, 'if isinstance(key, str) and _SENSITIVE_KEY.search(key)', 'if False and _SENSITIVE_KEY.search(key)')]),
 ("redaction", "redact_obj skips nested lists", [(R, 'return [self.redact_obj(item) for item in obj]', 'return obj')]),
 ("redaction", "sensitive-file allow-list removed (.env.example flagged)", [(R, 'if name in _SENSITIVE_FILE_ALLOW:', 'if False:')]),
 ("redaction", "sensitive dirs (.ssh/.aws) ignored", [(R, 'if any(part.lower() in _SENSITIVE_DIRS for part in parts[:-1]):', 'if False:')]),
 ("redaction", "'.env.*' pattern removed", [(R, '".env", ".env.*",', '".env",')]),
 # ---- limits
 ("limits", "docker: --network none -> bridge", [(L, '"--network", "none",', '"--network", "bridge",')]),
 ("limits", "docker: --cap-drop ALL removed", [(L, '"--cap-drop", "ALL",', '')]),
 ("limits", "docker: --read-only removed", [(L, '"--read-only",', '')]),
 ("limits", "docker: --security-opt no-new-privileges removed", [(L, '"--security-opt", "no-new-privileges",', '')]),
 ("limits", "docker: runs as root", [(L, '"--user", "10001:10001",', '"--user", "0:0",')]),
 ("limits", "docker: --pids-limit removed", [(L, '"--pids-limit", str(limits.pids),', '')]),
 ("limits", "docker: --memory-swap removed", [(L, '"--memory", mem, "--memory-swap", mem,', '"--memory", mem,')]),
 ("limits", "docker: --cpus removed", [(L, '"--cpus", str(limits.cpus),', '')]),
 ("limits", "docker: readonly mount flag dropped", [(L, 'if limits.filesystem == "workspace_ro":', 'if False:')]),
 ("limits", "docker: mount-option injection (comma) allowed", [(L, '_BAD_MOUNT_CHARS = re.compile(r"[,\\n\\r\\x00=]")', '_BAD_MOUNT_CHARS = re.compile(r"[\\n\\r\\x00]")')]),
 ("limits", "docker: option-injection via image name allowed", [(L, '_IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/:@-]{0,254}$")', '_IMAGE_RE = re.compile(r"^[a-z0-9-][a-z0-9._/:@ -]{0,254}$")')]),
 ("limits", "docker: cwd traversal allowed", [(L, 'rel = validate_relative_path(cwd, allow_root=True)', 'rel = cwd')]),
 ("limits", "docker: scoped network silently accepted", [(L, 'if limits.network.mode != "none":\n        raise UnsupportedInThisPhase(', 'if False:\n        raise UnsupportedInThisPhase(')]),
 ("limits", "timeout ceiling removed", [(L, 'MAX_TIMEOUT_SECONDS = 3600', 'MAX_TIMEOUT_SECONDS = 10**12')]),
 ("limits", "memory ceiling removed", [(L, 'MAX_MEMORY_MB = 8192', 'MAX_MEMORY_MB = 10**12')]),
 ("limits", "bool accepted as number", [(L, 'if isinstance(value, bool) or not isinstance(value, (int, float)):', 'if not isinstance(value, (int, float)):')]),
 ("limits", "filesystem mode unchecked", [(L, 'if self.filesystem not in ("workspace_rw", "workspace_ro"):', 'if False:')]),
 ("limits", "network policy not validated by limits", [(L, '        self.network.validate()\n\n    def to_dict', '        pass\n\n    def to_dict')]),
 ("limits", "scoped network without approval id allowed", [(L, 'if not is_valid_id(self.approval_id):', 'if False:')]),
 ("limits", "scoped network without hosts allowed", [(L, 'if not self.allowed_hosts:\n                raise LimitsError("scoped network requires', 'if False:\n                raise LimitsError("scoped network requires')]),
 ("limits", "wildcard host allowed (explicit check only)", [(L, 'if host in ("*", "") or not _HOST_RE.match(host):', 'if not _HOST_RE.match(host):')]),
 ("limits", "host name syntax unchecked", [(L, 'if host in ("*", "") or not _HOST_RE.match(host):', 'if host in ("*", ""):')]),
 ("limits", "mode 'none' may carry hosts/approval", [(L, 'if self.allowed_hosts or self.approval_id is not None:', 'if False:')]),
 ("limits", "unknown limit fields accepted by from_dict", [(L, 'if extra:\n            raise LimitsError(f"unknown limit fields', 'if False:\n            raise LimitsError(f"unknown limit fields')]),
]
M += [
    ('other', 'success no longer requires exit 0', [('src/nexus_core/outcomes.py', 'if exit_code != 0:\n            raise OutcomeError("succeeded requires exit_code == 0")', "if False:\n            raise OutcomeError('x')")]),
    ('other', 'AI allowed to approve', [('src/nexus_core/messages.py', 'MessageType.APPROVAL_RESPONSE: frozenset({"user"})', 'MessageType.APPROVAL_RESPONSE: frozenset({"user", "ai"})')]),
    ('other', 'AI may dispatch straight to executors', [('src/nexus_core/messages.py', 'elif dst != "orchestrator":\n            _fail("destination", f"{mt.value} from {src!r} may only', 'elif False:\n            _fail("destination", f"{mt.value} from {src!r} may only')]),
    ('other', 'unknown journal state re-executes', [('src/nexus_core/journal.py', 'return BeginResult(Decision.NEEDS_REVIEW, existing)', 'return BeginResult(Decision.EXECUTE, existing)')]),
    ('other', 'rollback ignores confirm', [('src/nexus_core/git_checkpoint.py', 'if confirm is not True:', 'if False:')]),
    ('other', 'SQL: failed may have exit 0', [('src/nexus_core/migrations/0001_core.sql', "CHECK (status <> 'failed' OR (exit_code IS NOT NULL AND exit_code <> 0)),", '')]),
    ('other', 'audit hash ignores previous hash', [('src/nexus_core/audit.py', 'hashlib.sha256((prev_hash + "\\n" + canonical_json(fields))', 'hashlib.sha256(("" + "\\n" + canonical_json(fields))')]),
    ('other', 'composite FK on messages dropped', [('src/nexus_core/migrations/0001_core.sql', '  FOREIGN KEY (task_id, project_id, owner_id) REFERENCES tasks (id, project_id, owner_id),\n  FOREIGN KEY (session_id, task_id) REFERENCES sessions (id, task_id)', '  FOREIGN KEY (task_id) REFERENCES tasks (id),\n  FOREIGN KEY (session_id) REFERENCES sessions (id)')]),
    ('other', 'unknown payload fields ignored', [('src/nexus_core/messages.py', '_fail(f"payload.{key}", "unknown field")', 'pass')]),
    ('other', 'pairing: both single-use layers removed', [('src/nexus_core/pairing.py', 'row["used_at"] or row["revoked_at"] or ', 'row["revoked_at"] or '), ('src/nexus_core/pairing.py', ' AND used_at IS NULL AND revoked_at IS NULL",\n                (now, device_id, row["id"]),', ' ",\n                (now, device_id, row["id"]),')]),
    ('other', 'shell timeout ceiling not enforced in protocol', [('src/nexus_core/messages.py', 'if not 1 <= p["timeout_seconds"] <= MAX_TIMEOUT_SECONDS:', 'if False:')]),
]
results = []
for module, name, edits in M:
    saved = {}
    try:
        for rel, old, new in edits:
            path = os.path.join(ROOT, rel)
            saved.setdefault(path, open(path).read())
            cur = open(path).read()
            if old not in cur:
                raise AssertionError(f"pattern not found: {old[:60]!r}")
            open(path, "w").write(cur.replace(old, new, 1))
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT,
                           env={**os.environ, "PYTHONPATH": "src"}, capture_output=True, text=True)
        verdict = "CAUGHT" if r.returncode != 0 else "SURVIVED"
    except AssertionError as e:
        verdict = "BADPATTERN " + str(e)
    finally:
        for path, orig in saved.items():
            open(path, "w").write(orig)
    results.append((module, name, verdict))
    print(f"{verdict:9} [{module}] {name}", flush=True)
from collections import Counter
print()
for mod in ("paths", "redaction", "limits", "other"):
    c = Counter(v.split()[0] for m, n, v in results if m == mod)
    print(mod, dict(c))
not_caught = [(m, n, v) for m, n, v in results if not v.startswith("CAUGHT")]
print("NOT CAUGHT:", not_caught)
# Known EQUIVALENT mutant (explicit check is redundant with _HOST_RE, behaviour identical):
ALLOWED = {"wildcard host allowed (explicit check only)"}
sys.exit(1 if [x for x in not_caught if x[1] not in ALLOWED] else 0)
