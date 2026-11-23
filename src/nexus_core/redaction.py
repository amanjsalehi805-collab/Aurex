"""Secret detection and redaction.

Applied before ANY text leaves the trust boundary: AI prompts, logs, audit details, UI payloads.
Detection is pattern based plus exact-match for secrets the system itself knows (API keys loaded
from the environment). It errs toward over-redaction. Findings never contain the secret text.

Known limit: a secret split across two streamed chunks is only caught after reassembly; callers
must redact complete lines/buffers, not raw fragments (enforced in Phase 5 output pipeline).
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import Any, Iterable

# (kind, regex, group index of the secret portion). Specific patterns come before generic ones.
_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("private_key", re.compile(
        r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----[\s\S]*?"
        r"(?:-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|\Z)"), 0),
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"), 0),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), 0),
    ("openai_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}"), 0),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), 0),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"), 0),
    ("stripe_key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}"), 0),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), 0),
    ("url_credentials", re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"), 0),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{16,})"), 1),
    ("assignment", re.compile(
        r"(?i)\b[A-Za-z0-9_.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
        r"private[_-]?key|credentials?|authorization)[A-Za-z0-9_.-]*[\"']?\s*[:=]\s*[\"']?"
        r"([^\s\"',;]{8,})"), 1),
]

_SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"credentials?|authorization)"
)

_SENSITIVE_FILE_PATTERNS = (
    ".env", ".env.*", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "*.pem", "*.key", "*.p12",
    "*.pfx", "*.jks", "*.keystore", ".netrc", ".npmrc", ".pypirc", ".git-credentials",
    ".htpasswd", "*.tfstate", "credentials", "credentials.json", "secrets.json", "secrets.yml",
    "secrets.yaml",
)
_SENSITIVE_FILE_ALLOW = (".env.example", ".env.sample", ".env.template")
_SENSITIVE_DIRS = frozenset({".ssh", ".aws", ".gnupg", ".kube", ".docker"})


@dataclass(frozen=True)
class Finding:
    kind: str
    start: int
    end: int


class Redactor:
    def __init__(self, known_secrets: Iterable[str] = ()) -> None:
        self._known = tuple(sorted({s for s in known_secrets if isinstance(s, str) and len(s) >= 8},
                                   key=len, reverse=True))

    def scan(self, text: str) -> list[Finding]:
        raw: list[Finding] = []
        for secret in self._known:
            for match in re.finditer(re.escape(secret), text):
                raw.append(Finding("known_secret", match.start(), match.end()))
        for kind, pattern, group in _PATTERNS:
            for match in pattern.finditer(text):
                start, end = match.span(group)
                if end > start:
                    raw.append(Finding(kind, start, end))
        # Resolve overlaps: earliest start first, longest first; stable so specific kinds win ties.
        raw.sort(key=lambda f: (f.start, -(f.end - f.start)))
        result: list[Finding] = []
        last_end = -1
        for finding in raw:
            if finding.start >= last_end:
                result.append(finding)
                last_end = finding.end
        return result

    def contains_secret(self, text: str) -> bool:
        return bool(self.scan(text))

    def redact(self, text: str) -> str:
        findings = self.scan(text)
        if not findings:
            return text
        out: list[str] = []
        cursor = 0
        for finding in findings:
            out.append(text[cursor:finding.start])
            out.append(f"[REDACTED:{finding.kind}]")
            cursor = finding.end
        out.append(text[cursor:])
        return "".join(out)

    def redact_obj(self, obj: Any) -> Any:
        """Recursively redact strings; values under secret-looking keys are replaced wholesale."""
        if isinstance(obj, str):
            return self.redact(obj)
        if isinstance(obj, list):
            return [self.redact_obj(item) for item in obj]
        if isinstance(obj, tuple):
            return tuple(self.redact_obj(item) for item in obj)
        if isinstance(obj, dict):
            cleaned: dict[Any, Any] = {}
            for key, value in obj.items():
                if isinstance(key, str) and _SENSITIVE_KEY.search(key) and isinstance(value, str) and value:
                    cleaned[key] = "[REDACTED:sensitive_key]"
                else:
                    cleaned[key] = self.redact_obj(value)
            return cleaned
        return obj


def is_sensitive_path(relative_path: str) -> bool:
    """True if a file should never be read into an AI prompt (credentials, keys, env files)."""
    parts = [p for p in relative_path.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts:
        return False
    if any(part.lower() in _SENSITIVE_DIRS for part in parts[:-1]):
        return True
    name = parts[-1].lower()
    if name in _SENSITIVE_FILE_ALLOW:
        return False
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in _SENSITIVE_FILE_PATTERNS)
