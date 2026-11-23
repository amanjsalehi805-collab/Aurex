# Trust model and security boundaries

## Trust levels
| Actor | Trust |
|---|---|
| The human user (authenticated in Control Center) | Authority for approvals |
| Orchestrator + its DB | Trusted computing base; holds credentials and policy |
| AI model output, repository content, command output, web content | **Untrusted data** (prompt injection assumed) |
| Cloud worker container | Untrusted execution; disposable; no network, no secrets |
| Android agent / Termux | Semi-trusted: authenticated per device key, but runs on a user device without container isolation |
| Network | Hostile; all channels authenticated + encrypted (Phase 2/3) |

## Boundaries and the Phase 1 control at each
1. **AI -> orchestrator**: structured messages only; provenance + routing rules (`messages.py`).
2. **Orchestrator -> executor**: explicit target, bounded limits, workspace-relative paths only.
3. **Workspace boundary**: `paths.py` rejects `..`, absolute/home/drive paths, backslashes, control
   characters, symlink escapes, sibling-prefix tricks; `.git` is write-protected; project workspaces
   must be disjoint.
4. **Process boundary (cloud)**: `docker_run_args` = `--network none`, memory+swap, cpus, pids,
   read-only rootfs, `--cap-drop ALL`, `no-new-privileges`, UID 10001, workspace the only mount; inputs
   validated against option injection (image, name, mount path, cwd). Scoped network is refused until the
   Phase 5 egress proxy exists. Wall-clock timeout must be enforced by the runner (not a docker flag).
5. **Secret boundary**: `Redactor` before prompts, logs, audit details, UI; sensitive-file list keeps
   `.env`, keys, `.ssh` etc. out of prompts; `provider_configs` stores references only.
6. **Rollback boundary**: checkpoints never touch the user's branch/HEAD/index; rollback = plan +
   `confirm=True`; ignored files untouched.
7. **Replay boundary**: journal marks interrupted commands `unknown` and never auto-re-runs them.
8. **Evidence boundary**: audit chain + DB append-only triggers.
9. **Device identity**: one-time, expiring, hashed tokens; Ed25519 public-key registration; instant
   revocation; identical failure messages.

## Risks and mitigations (Phase 1 view)
| Risk | Mitigation | Status |
|---|---|---|
| Prompt injection makes AI run/approve things | AI cannot emit results/approvals; cannot reach executors | tested |
| Path traversal / symlink escape | `paths.py` | tested |
| Git hook planting via `.git` writes | `.git` write-protected | tested, **see residual R1** |
| Secret leakage to model/logs | `Redactor`, sensitive paths, audit redaction | tested (pattern-based; novel formats can slip through) |
| Destructive replay after lost response | journal + idempotency keys | tested |
| Runaway loops | DB invariant `iteration_count <= max_iterations`; budget columns | schema only; enforcement in Phase 6 |
| Tampered history | hash chain + triggers | tested; tail truncation undetected until Phase 8 anchoring |

## Known limitations / residual risks (honest list)
* **R1 - `.git` symlink alias.** If `.git` is a symlink to a directory *inside* the workspace, a write
  to the alias target (e.g. `realgit/hooks/pre-commit`) is NOT blocked (probe-verified). Proposed fix:
  refuse all writes when the workspace's `.git` entry is a symlink. **Not applied - awaiting owner decision.**
* R2 - Check-then-use symlink races (TOCTOU) on the host. Closed in Phase 5 by container-only mounts
  and dir-fd opens.
* R3 - Local (Termux) execution has no container isolation; it relies on workspace confinement,
  command policy/approvals, process-group timeouts. Android may kill the agent; the phone being off
  stops local jobs (the UI must say so).
* R4 - Redaction is pattern-based; secrets split across stream chunks are only caught on reassembly.
* R5 - Audit tail truncation is undetectable from the chain alone (external anchoring planned).
* R6 - PostgreSQL immutability (triggers/REVOKE) and Postgres CI arrive in Phase 2.
* R7 - `message.source` authenticity depends on the Phase 2/3 transport.
