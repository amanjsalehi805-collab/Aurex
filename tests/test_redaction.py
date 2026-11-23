import unittest

from nexus_core.redaction import Redactor, is_sensitive_path

# Fake credentials assembled at runtime so this file never contains a scannable literal.
AWS = "AKIA" + "IOSFODNN7EXAMPLE"
GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
ANTH = "sk-ant-" + "api03-abcdefghijklmnopqrstuvwxyz0123456789"
OAI = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz0123456789"
SLACK = "xoxb-" + "1234567890-abcdefghij"
GOOG = "AIza" + "SyA1234567890abcdefghijklmnopqrstuv"
STRIPE = "sk_live_" + "abcdefghijklmnop1234"
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"
PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\nabcdef\n-----END RSA PRIVATE KEY-----"
R = Redactor()


class TestRedaction(unittest.TestCase):
    def test_each_secret_kind_is_redacted(self):
        cases = {AWS: "aws_access_key_id", GH: "github_token", ANTH: "anthropic_key", OAI: "openai_key",
                 SLACK: "slack_token", GOOG: "google_api_key", STRIPE: "stripe_key", JWT: "jwt"}
        for secret, kind in cases.items():
            with self.subTest(kind=kind):
                text = f"value is {secret} end"
                self.assertNotIn(secret, R.redact(text))
                self.assertIn(f"[REDACTED:{kind}]", R.redact(text))

    def test_private_key_block_and_truncated_block(self):
        out = R.redact(f"before\n{PEM}\nafter")
        self.assertNotIn("MIIEow", out)
        self.assertTrue(out.startswith("before") and out.endswith("after"))
        truncated = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqh"
        self.assertNotIn("MIIEvQ", R.redact(truncated))

    def test_url_credentials_and_bearer(self):
        out = R.redact("git clone https://alice:hunter2pass@github.com/x/y.git")
        self.assertNotIn("hunter2pass", out)
        self.assertIn("github.com/x/y.git", out)
        out = R.redact("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456")
        self.assertNotIn("abcdefghijklmnop", out)

    def test_assignments(self):
        for line in ("DB_PASSWORD=supersecret123", 'api_key: "abcd1234efgh5678"', "export AUTH_TOKEN='tok_abcdefgh12'",
                     "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"):
            with self.subTest(line=line):
                out = R.redact(line)
                self.assertIn("[REDACTED:", out)
                self.assertNotIn("supersecret123", out)
                self.assertNotIn("abcd1234efgh5678", out)

    def test_no_false_positives_on_ordinary_code(self):
        for line in ('author = "Jonathan Smith"', "max_tokens = 1000", "token_count: 12", "x = password_field",
                     "def get_token(self): return self._value", "total = a + b", "Run `pytest -q` now",
                     "https://example.com/path?q=1", "sha = 'deadbeef'"):
            with self.subTest(line=line):
                self.assertEqual(R.redact(line), line)

    def test_known_secrets_exact_match_even_without_pattern(self):
        custom = "correct-horse-battery-staple"
        r = Redactor(known_secrets=[custom, "short"])
        self.assertEqual(r.redact(f"pw={custom}!"), "pw=[REDACTED:known_secret]!")
        self.assertEqual(r.redact("short"), "short")  # < 8 chars ignored (would shred normal text)

    def test_idempotent_and_findings_hold_no_secret_text(self):
        text = f"a {GH} b {AWS} c password=hunter2hunter2"
        once = R.redact(text)
        self.assertEqual(R.redact(once), once)
        for f in R.scan(text):
            self.assertEqual(set(vars(f)), {"kind", "start", "end"})

    def test_overlapping_matches_collapse_to_one_marker_with_exact_output(self):
        self.assertEqual(R.redact(ANTH), "[REDACTED:anthropic_key]")
        self.assertEqual(R.redact("api_key=" + GH), "api_key=[REDACTED:github_token]")
        self.assertEqual(R.redact("x " + OAI + " y"), "x [REDACTED:openai_key] y")

    def test_bearer_keeps_scheme_word_and_masks_only_the_token(self):
        self.assertEqual(R.redact("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"),
                         "Authorization: Bearer [REDACTED:bearer_token]")

    def test_overlap_resolution_prefers_specific_kind(self):
        self.assertIn("[REDACTED:anthropic_key]", R.redact(ANTH))

    def test_redact_obj(self):
        obj = {"password": "x", "note": f"key {GH}", "nested": [{"api_key": "abc"}, f"{AWS}"], "n": 5,
               "ok": "hello"}
        out = R.redact_obj(obj)
        self.assertEqual(out["password"], "[REDACTED:sensitive_key]")
        self.assertEqual(out["nested"][0]["api_key"], "[REDACTED:sensitive_key]")
        self.assertNotIn(GH, str(out))
        self.assertNotIn(AWS, str(out))
        self.assertEqual((out["n"], out["ok"]), (5, "hello"))

    def test_sensitive_paths(self):
        for p in (".env", "app/.env.production", "id_rsa", "keys/server.pem", ".ssh/config", "x/.aws/credentials",
                  ".npmrc", "terraform.tfstate", "ID_ED25519", "a/b/secrets.json"):
            with self.subTest(p=p):
                self.assertTrue(is_sensitive_path(p))
        for p in (".env.example", "src/main.py", "README.md", "environment.py", "docs/keys.md", ""):
            with self.subTest(p=p):
                self.assertFalse(is_sensitive_path(p))


if __name__ == "__main__":
    unittest.main()
