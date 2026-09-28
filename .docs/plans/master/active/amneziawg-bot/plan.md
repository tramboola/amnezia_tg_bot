---
type: plan
status: active
scope: amnezia_tg_bot
updated: 2026-09-28
---
# AmneziaWG bot

Current stage: 02
Current checkpoint: 02-01

## Lifecycle

- Owner: Codex, inline execution explicitly authorized by user.
- Next action: confirm internet and IPv6 behaviour on the colleague's external AWG 3.1 client; finish pending acceptance checks without disturbing real profiles.
- Handoff: [handoff.md](handoff.md)
- Intended integration branch: `dev`
- Primary plan: none

## Spec

[Approved design](../../../../knowledge/decisions/2026-09-28-amneziawg.md)

## Goal

A reviewable local implementation, deployment script and verification instructions for an admin Telegram bot managing AmneziaWG.

## Definition Of Done

- Unique device profiles; restart-stable keys and addresses; durable revocation.
- Admin-only private-chat menus, downloads and destructive confirmations.
- Restricted manager RPC; Docker mutations limited to owned resources.
- Unit/contract tests pass. Build and live VPN checks explicitly tracked separately until Linux Docker and VPS are available.

## Stage Map

- [x] [01. Implementation](stages/01.md)
- [ ] [02. VPS validation](stages/02.md)

## Checkpoint Map

- [x] [01-01. Local implementation](checkpoints/01-01.md)
- [ ] [02-01. Live validation](checkpoints/02-01.md)

## Tasks

1. Profiles and manager: write failing persistence/revocation tests, implement keys, rendering, atomic state, reconcile and owned Docker adapter. Verify pytest. Commit.
2. RPC and Telegram: write failing whitelist/auth tests; implement Unix socket client/server, menu flow and confirmations. Verify pytest. Commit.
3. Deployment: create Docker images, Compose, Ubuntu installer, README; verify static contracts and full tests. Commit. Fresh review and fix important findings with regression tests.

## Interfaces

Manager exposes status/start/stop/create/list/download/revoke/delete; device UUID is public identity. Config bodies only returned by create/download. Docker backend takes a rendered server file and fixed endpoint port. Telegram consumes only JSON data from the local manager.

## Global Constraints

Do not log secrets. User explicitly authorized deployment/testing on `108.174.78.189`; token entry stays in their SSH terminal. No arbitrary command RPC. One owning checkout on feature branch. Install test dependencies only into project `.venv`. No merge/push authorized.

## Review Focus

Check crash windows, revocation of the last peer, container restart behaviour, foreign-container ownership, Unix socket permissions, private-chat/admin checks, Docker build commands and AWG 3.1 parameter compatibility. Tests with a fake Docker adapter do not prove real Docker/awg behaviour.

## Completion Evidence

Local implementation completed on `feature/amneziawg-bot`; no merge/push. 36 pytest tests pass; ruff, compileall, package build, bash syntax and Compose validation pass. Fresh read-only review: one important deletion-intent finding fixed with two RED→GREEN regression tests; no critical/minor findings. [Local verification record](../../../../knowledge/local-verification.md).

Subsequently deployment was explicitly authorized and completed through the Linux integration checks: all three images built, manager/socket access, two concurrent clients, NAT/DNS, restart recovery and selective/last-peer revocation pass. Live interruption fixed with `syncconf`; fresh 36-test suite passes. Telegram bot now runs without restarts and the colleague creates configs; latest status shows one real device/handshake and no pending changes. [VPS verification](../../../../knowledge/vps-verification.md). Actual client internet/IPv6 and remaining acceptance checks are pending.
