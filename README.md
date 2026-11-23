# NEXUS AI - Phase 1 (foundation)

Reusable autonomous coding agent. **Phase 1 delivers only the verified foundation** - no orchestrator
service, Android agent, AI calls or UI yet (Phases 2-7).

What exists and is tested: structured message protocol, task state machine, database schema with
isolation + tamper-resistance constraints, workspace/path confinement, secret redaction, execution
limits + sandbox command builder, git checkpoints/rollback, execution journal (idempotency),
hash-chained audit log, device-pairing primitives.

    PYTHONPATH=src python3 -m unittest discover -s tests -t . -v     # run all tests
    python3 tools/mutation_check.py                                  # deliberate-fault gate

Runtime dependencies: none (Python >= 3.11 standard library, git >= 2.23 on PATH).
Docs: docs/ARCHITECTURE.md, PROTOCOL.md, TRUST_MODEL.md, TESTING.md, ACCEPTANCE_PHASE1.md,
PHASE1_TEST_REPORT.txt (raw output of the verification run).
