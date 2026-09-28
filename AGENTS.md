# amnezia_tg_bot

Telegram admin bot for one self-hosted AmneziaWG 3.1 server. Work in this checkout; no local sibling-project dependencies.

Read `.docs/agents/index.md`, README and the relevant source/tests. Use `.docs/` for project memory. Do not read secrets, `.env`, generated state or profile files.

Python 3.12+, python-telegram-bot, cryptography. Run `python -m pytest` and `ruff check .`; Linux Docker and a real client are required for VPN integration verification.

Keep Telegram unprivileged. Only the manager accesses Docker. Its Unix-socket protocol exposes fixed operations, never arbitrary commands, paths, images or container names. Never log private keys, profiles or tokens.

Persist desired state before peer changes; reconcile it before returning a profile. Revocation must survive failures and restarts. Keep server and client AWG parameters in one renderer.

Branches: feature/* -> dev -> main. Do not deploy, push or merge without user authorization. Do not create CodeGraph or extra worktrees automatically.
