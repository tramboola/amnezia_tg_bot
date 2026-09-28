---
type: verification
status: current
scope: amnezia_tg_bot
updated: 2026-09-28
---
# Local verification

Owning checkout: `feature/amneziawg-bot`, based on `dev`; code implemented and locally committed. This record covers the local implementation phase; subsequent authorized deployment is recorded in [VPS verification](vps-verification.md). No merge or push. The workspace project inventory was updated; no local dependencies identified.

## Evidence

- `python -m pytest -q --basetemp=work/pytest-review-green`: 36 passed.
- `ruff check .` and `ruff format --check src tests`: pass.
- `python -m compileall -q src`: pass.
- `uv pip check --python .venv/Scripts/python.exe`: 20 installed packages compatible.
- `uv build --out-dir work/dist`: wheel and source distribution build.
- Git Bash `bash -n install.sh`, separately `bash -n vpn/entrypoint.sh`: exit 0.
- Docker Compose `--env-file .env.example config --quiet`: exit 0.
- `.docs/agents/tools/plan_state_check.py . --portfolio`: pass. The copied checker had over-escaped regexes and did not accept bullet lifecycle fields; fixed with four RED→GREEN tests.

Tests exercise real crypto, file persistence and restart recovery; Docker is replaced by a contract adapter. A real local stream test covers RPC framing, without exposing a production TCP listener.

## Fresh review

Read-only reviewer inspected `20f9165..77094de`. No critical or minor findings. One important finding: deletion removed the container before persisting stopped intent; failed state erasure could trigger automatic resurrection. Fixed by saving `started=False` with retained keys before removing the container, then erasing identity. Two regression tests failed before the fix and passed afterward; full suite 36/36.

## Decisions made during execution

- Execute skill bookkeeping through PowerShell on Windows instead of POSIX helper scripts. Cost if wrong: manual progress bookkeeping can omit a step; concrete test/check outputs and this record provide closure evidence.
- Keep local feature branch and remaining integration stage for the user to continue. Merge/push were outside the authorized file organisation and implementation scope.
- Reviewer set aside Linux image builds, actual cross-container Unix socket access, TUN/NAT, client import/handshake, IPv6 protection, and live restart/revocation. These are not established by static review; stage 02 must verify all of them. Cost if wrong: installation or traffic forwarding may fail despite passing local tests.

## Remaining work

Continue stage 02 from [VPS verification](vps-verification.md). Follow the README acceptance procedure before colleague rollout. Preserve state backups carefully: old backups can restore revoked keys. No claim of production readiness or guaranteed bypass of blocking.

## Small-VPS preparation

The inspected VPS has 961 MiB RAM, no swap and ~3.7 GiB free disk. Switched only the Go build stage to `golang:1.25.12-alpine3.24`, pinned by the official Docker Hub tag digest. The registry reports amd64 compressed downloads of ~61.4 MiB vs ~291.2 MiB for the previous Debian tag; these are not installed disk sizes. Added Git/CA certificates, `go build -p 1`, `GOMAXPROCS=1` and a soft `GOMEMLIMIT=384MiB`; runtime settings are unchanged. Compose builds use `--parallel 1`.

Added `install.sh --prepare-only`: Docker installation and builds complete before token/admin prompts, without starting project services. Checks at that point: both shell syntax checks pass; unsupported option and extra argument exit 1 before root/OS/installation checks; Compose config with `--parallel 1` passes; Git whitespace check passes. Linux builds were still pending then and the Python suite had not been rerun for that packaging-only change.

Subsequent Linux validation reproduced a traffic interruption after manager restart caused by `setconf` replacing all peers. Switched live updates to `syncconf`; updated Docker contract test failed before the fix and passed after it. Fresh full suite: 36 passed (`work/pytest-syncconf-green`); ruff and formatting checks pass. Two-client live verification is recorded separately. Compose Bake built both targets concurrently despite `--parallel 1`, so the installer now builds `manager` and `bot` with separate commands. Runtime test directory is excluded from Docker build contexts.
