# Phase 1 acceptance criteria and verification status

Status legend: VERIFIED = executed locally, result recorded in PHASE1_TEST_REPORT.txt.
NOT VERIFIED = written but not executed in this environment.

| # | Criterion | Evidence (tests) | Status |
|---|---|---|---|
| 1 | Every message type has a strict schema; invalid/unknown/ambiguous input is rejected | test_messages (28 tests) | VERIFIED |
| 2 | Code, shell commands, terminal output, approvals can never be confused | TestSeparation, TestProvenanceAndRouting | VERIFIED |
| 3 | AI cannot emit results/approvals or reach executors directly | TestProvenanceAndRouting | VERIFIED |
| 4 | Success is decided by exit status only, in protocol, journal and SQL | TestResultConsistency, test_integration grid, TestExecutionInvariants | VERIFIED |
| 5 | Schema applies from clean, idempotently; tampered/unknown migrations refused | TestMigrations | VERIFIED (SQLite 3.45.1) |
| 6 | Projects/tasks/messages/jobs/executions cannot cross project or owner boundaries | TestIsolation, TestJobs | VERIFIED (SQLite) |
| 7 | Audit/event history is append-only and tamper-evident | test_audit, TestTamperResistance | VERIFIED (SQLite) |
| 8 | Path traversal, symlink escape, `.git` writes, overlapping workspaces blocked | test_paths | VERIFIED (see residual R1) |
| 9 | Secrets redacted from prompts/logs/audit; sensitive files identified | test_redaction, test_audit | VERIFIED (pattern based) |
| 10 | Every execution carries bounded limits; sandbox argv is no-network, non-root, read-only, capability-free; injection rejected | test_limits | VERIFIED (argv only; Docker not run) |
| 11 | Git checkpoint leaves branch/HEAD/index untouched; rollback is planned, confirmed, exact; ignored files safe | test_git_checkpoint | VERIFIED (git 2.43.0) |
| 12 | Interrupted commands become `unknown` and are never auto re-run; replay returns stored result | test_journal | VERIFIED |
| 13 | Pairing tokens are single-use, expiring, hashed; devices revocable; failures indistinguishable | test_pairing | VERIFIED |
| 14 | Tests detect deliberately broken safety rules | tools/mutation_check.py: 72 mutants, 71 caught, 1 documented equivalent | VERIFIED |
| 15 | CI pipeline runs tests, lint, mutation gate | .github/workflows/ci.yml | NOT VERIFIED (never run) |
| 16 | ruff / mypy clean | - | NOT VERIFIED (tools unavailable offline) |
| 17 | Works on Python 3.11 and in Termux, on PostgreSQL, with real Docker | - | NOT VERIFIED (only CPython 3.12.3 + SQLite exercised) |
