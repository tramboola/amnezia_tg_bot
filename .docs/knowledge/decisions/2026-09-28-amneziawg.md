---
type: decision
status: accepted
scope: amnezia_tg_bot
updated: 2026-09-28
---
# AmneziaWG bot design

User approved adapting https://github.com/tramboola/openvpn_tg_bot and explicitly authorized file organisation and immediate implementation on 2026-09-28.

Keep Python/python-telegram-bot, administrator menus, configuration downloads, revocation and deletion confirmations. Replace OpenVPN/EasyRSA with AmneziaWG 3.1 keys and peers. One IPv4 UDP server; per-device keys, preshared key and address. Export native `.conf` files. No billing, public self-service or multiple protocols.

The non-root bot talks over a local Unix socket to a manager with Docker access. The manager owns one labelled userspace AWG container, stores authoritative state on a persistent volume and reconciles it on restart. Telegram access is limited to allowed numeric user IDs in private chats. Files delivered through Telegram contain connection secrets.

Full tunnel IPv4; client IPv6 is routed into the tunnel and dropped until server IPv6 support is implemented. This policy requires verification on supported clients. VPN integration requires a Linux VPS with `/dev/net/tun`; Windows unit tests cannot prove packet forwarding or client import.

Sources frozen for adaptation:

- OpenVPN reference: `a0b5a5cec629e9a7509f5f3fa468d10ffc91efce` (Unlicense).
- amneziawg-go: `b5928efb6ca19f0153958460c3d141f04abc5c2e`.
- amneziawg-tools: `ee0f0a9aa34ff0a0da4b3433b9512781cfe02843`.

Use Go 1.25 as required by the official v3 module. AWG 3.1 uses matching HeaderProtectionKey and S1–S4 >= 12. Defaults are a starting point, not a guarantee of bypassing blocking.
