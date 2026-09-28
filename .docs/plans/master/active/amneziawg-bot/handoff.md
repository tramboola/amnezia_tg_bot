---
type: handoff
status: active
scope: amnezia_tg_bot
updated: 2026-09-28
---
# AmneziaWG bot handoff

Current stage: 02
Current checkpoint: 02-01

## Lifecycle

- Owner: Codex
- Next action: confirm internet and IPv6 behaviour on the colleague's external AWG 3.1 client; finish pending acceptance checks without disturbing real profiles.
- Worktree disposition: commit-and-resume

## Last Completed

01-01: profiles, durable manager, local RPC, Telegram menus, Docker images/Compose, Ubuntu installer, README and fresh review fix.

## Verified

36 pytest tests, ruff, compileall, Python package build, both shell syntax checks, Compose config and plan portfolio audit pass. Fresh reviewer found deletion could resurrect keys after a write failure; corrected by saving stopped intent before container removal, covered by two failing-then-passing tests. Source/base images pinned. Full details: [verification](../../../../knowledge/local-verification.md).

## Current State

Owning checkout on `feature/amneziawg-bot`, base `dev`; no new worktree, merge/push or remote Git. User explicitly authorized VPS installation/deployment/testing. Docker installed, three images built, manager healthy and AWG running at `108.174.78.189:51820/UDP`. Two Linux clients passed real tunnel, NAT/DNS, restart and revocation tests; live updates corrected to `syncconf` to retain sessions. Fresh 36 pytest tests, ruff and format pass. User completed token/admin setup and reports colleague successfully creates configs. Bot runs >5min with zero restarts as UID10001; token-file metadata is restrictive, contents never read. One real device and handshake observed; no pending changes. Full [VPS verification](../../../../knowledge/vps-verification.md) records pending actual-device internet/IPv6 confirmation.

## Next Step

- [02-01](checkpoints/02-01.md): user clarified the colleague has only created a config. Guide import into a current AWG 3.1 client, then confirm actual-device IPv4/DNS and IPv6 protection; remaining live Telegram download/revoke/denied-access and maintenance checks are recorded in VPS verification. A public-source handshake is observed, but its owner is not established. Real profiles now exist: do not stop/restart/revoke/delete them for tests. Deployment authorization persists; never inspect token/state/profile contents. Scoped read-only review of `6bab065..521dd65` is complete with no critical/important/minor findings; pending live acceptance checks and capacity were explicitly not judged, as recorded in VPS verification.

## Access status

Target: `root@108.174.78.189`, port 22. Public-key login via the dedicated identity and strict host-key checking works. Pre-install read-only preflight: Ubuntu 24.04.5 LTS, 961 MiB RAM, no swap, 4.9 GiB root filesystem (~3.7 GiB free), `/dev/net/tun` present, no Docker/conflicting packages found. No other external app listener observed; not a full data inventory. After authorized deployment: Docker 29.8.1, Compose 5.5.1, ~1.7 GiB free disk/~514 MiB available RAM, UDP 51820 published. No OS-wide upgrade, host firewall change or reboot.

Pre-install host iptables policies ACCEPT with no filtering rules shown, eth0 MTU 1500. Provider firewall settings remain unknown. Pinned Alpine Go builder, serial compilation and separate Compose target builds fit the inspected VPS; memory limit is soft. Test config files removed and test containers stopped/removed; owned bot, manager and VPN are now running.

User explicitly requested a new RSA keypair to give its public part to the colleague. Dedicated RSA 4096 identity: `C:\Users\User\.ssh\amnezia_vps_rsa` (outside project, no passphrase); public file has `.pub` suffix. Public SHA256 fingerprint: `sd12KbGlO5kzrlm3CW3KWvUCT+ffKaexoIq0E/H2r28`. OpenSSH validated the public key; Windows private-file ACL checked/restricted to the local user and system/administrators. Colleague installation and successful login confirmed. Do not read or print private contents; use the identity through SSH.
