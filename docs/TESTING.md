# Testing and CI strategy

Layers: (1) unit tests per module, (2) cross-layer agreement tests (protocol vs outcome rules vs SQL
on a 96-case grid), (3) real-dependency tests (real `git`, real SQLite, real filesystem symlinks),
(4) **mutation gate** - `tools/mutation_check.py` breaks 72 safety rules one at a time and requires
the suite to fail; the only permitted survivor is a documented equivalent mutant,
(5) drift tests - SQL CHECK lists must equal the Python enums.

Rules: no network in tests; deterministic clocks injected; fake credentials assembled at runtime;
tests never claim what they do not execute (Docker, Android, Postgres are NOT exercised in Phase 1).

CI (`.github/workflows/ci.yml`, **not yet run**): tests on Python 3.11 + 3.12, ruff + mypy lint,
mutation gate. Phase 2 adds a Postgres service job; Phase 3 adds an emulated-Termux job; Phase 5 adds
Docker-in-CI sandbox tests (escape attempts, network denial, OOM, fork bomb, timeout kill).
