import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    socket_path: Path
    preferences_path: Path

    @classmethod
    def load(cls):
        token_file = os.environ.get("BOT_TOKEN_FILE", "/run/secrets/bot_token")
        token = Path(token_file).read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError("BOT_TOKEN_FILE is empty")
        admins = frozenset(
            int(value.strip())
            for value in os.environ.get("ADMIN_IDS", "").split(",")
            if value.strip()
        )
        if not admins or any(value <= 0 for value in admins):
            raise ValueError("ADMIN_IDS must contain positive Telegram user IDs")
        return cls(
            token,
            admins,
            Path(os.environ.get("MANAGER_SOCKET", "/run/manager/manager.sock")),
            Path(os.environ.get("BOT_PREFERENCES", "/bot-data/preferences.json")),
        )
