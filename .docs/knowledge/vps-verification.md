---
type: verification
status: partial
scope: amnezia_tg_bot
updated: 2026-09-28
---
# VPS verification

User explicitly authorized upload, Docker installation, deployment and testing on `root@108.174.78.189`. They created the BotFather bot and completed token/admin setup in their SSH terminal. The token was not read or printed by Codex. Never read or print the token, generated state, full profiles or private keys.

## Deployed

- `/opt/amnezia-tg-bot`: source bundle from `6bab065`, verified by SHA256, followed by the tested `syncconf` backend, installer and Docker-context exclusion updates.
- Ubuntu 24.04.5 x86_64; Docker Engine 29.8.1, Compose 5.5.1 from the official Docker apt repository. No OS-wide upgrade, firewall change or reboot.
- All three pinned-base images built successfully on this 961 MiB/no-swap VPS: AWG ~28 MB, bot ~226 MB, manager ~291 MB (Docker-reported image sizes).
- Manager healthy; AWG running at `108.174.78.189:51820/UDP`; public IPv4 checked against ipify. After test cleanup the colleague began issuing real profiles; latest read-only status reports one active device, one handshake and no pending changes. User confirms the bot successfully creates configs. Do not revoke/delete test or real devices now without distinguishing ownership and scope.
- Bot running for >5 minutes, zero restarts, UID/GID 10001; token-file metadata `0600 10001:10001`, no contents read. Public status RPC also works from the real bot container.
- Idle snapshot after tests: ~1.7 GiB free root disk, ~514 MiB available RAM; manager ~17.5 MiB and AWG ~3.6 MiB container RSS/accounted memory. These are idle observations, not a capacity/load guarantee.
- Unix directory `0750 root:10001`, socket `0660 root:10001`; tested via a separate UID 10001 container with only the socket and verification directory mounted.

## Live checks passed

Two temporary Linux AWG clients used the same built userspace binary as the server, each in a separate Docker network namespace. They connected to the server's Docker bridge IP, not through the provider's public UDP path.

- Start/config parser/TUN, two distinct per-device profiles and stable repeated downloads.
- Both clients forward HTTPS and DNS through the tunnel/NAT; observed IPv4 exit matches the VPS. IPv6 connection attempts are blocked with the Linux tunnel routes installed.
- Manager recreation and restart retain profile hashes and both clients' traffic.
- Full VPN container restart retains profiles; automatic client recovery observed (~22 seconds from the first traffic probe, without editing its config).
- Revoke the first device: its new traffic fails, the second still succeeds; live peer count is one.
- Revoke the last device: live peer count is zero and its traffic fails.
- Stop/start and another manager restart retain both revocations; revoked downloads are rejected. Temporary client containers and private test config files removed.

Verification helpers remain under ignored local `work/deploy` and VPS `checks/`; the latter is excluded from Docker contexts. Its report contains only device UUIDs/profile digests, not configs or keys.

## Fix from live validation

`awg setconf` removes all peers, so applying the saved configuration after manager restart interrupted an existing client's traffic. The official [Go UAPI](https://github.com/amnezia-vpn/amneziawg-go/blob/b5928efb6ca19f0153958460c3d141f04abc5c2e/device/uapi.go) calls `RemoveAllPeers` for `replace_peers`. Changed live updates to `syncconf`, leaving `setconf` only for initial container setup. The pinned [tools implementation](https://github.com/amnezia-vpn/amneziawg-tools/blob/ee0f0a9aa34ff0a0da4b3433b9512781cfe02843/src/setconf.c) retains existing peers and removes absent ones; an empty desired peer list retains replace-all semantics. The last-peer case was also verified live.

Fresh local checks after the fix: Docker contract test RED→GREEN, 36 pytest tests pass, ruff and formatting checks pass; installer shell syntax passes. Installer builds Compose targets separately because the observed Bake build scheduled both targets despite `--parallel 1`.

Independent read-only review of `6bab065..521dd65` found no critical, important or minor issues; patch verdict ready. It verified the pinned syncconf semantics and surrounding source. Public-client web/DNS/IPv6, complete live Telegram menu/auth flows, VPS reboot, backup/restore, Docker-outage recovery and load capacity were explicitly set aside; they remain unverified or pending as stated here, not silently accepted.

## Pending

Telegram startup and config creation are confirmed. Actual Telegram download/revoke confirmation paths and denied access for a non-admin/group have not been exercised live; local tests cover them. Do not revoke the colleague's active profile as a verification step.

A device handshake with a public source IP is observed after all temporary client containers and peers were removed. This establishes public UDP reception for that peer, but does not identify its owner or prove web/DNS forwarding on the colleague's device. User clarified the colleague has only created a config so far. Next step: import it into a current AWG 3.1 client and verify internet, VPS IPv4 exit, DNS and IPv6 leak behaviour on the actual device. VPS reboot recovery, backup/restore and Docker-failure recovery have not been exercised. Provider firewall settings and behaviour on other colleagues' networks are unknown. Stage 02 remains active; no rollout-ready claim yet. Avoid restarts/destructive integration checks while the colleague issues real configs.
