from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_manager import MemoryVpn

from amnezia_bot.manager import Manager
from amnezia_bot.telegram_bot import TelegramBot


class Client:
    def __init__(self):
        self.calls = []

    async def call(self, operation, **args):
        self.calls.append((operation, args))
        if operation == "status":
            return {
                "configured": True,
                "running": True,
                "desired_running": True,
                "host": "203.0.113.5",
                "port": 51820,
                "devices": 1,
            }
        return []


def update(user=42, chat="private", text="/status", callback=None):
    message = SimpleNamespace(text=text, reply_text=AsyncMock(), reply_document=AsyncMock())
    query = SimpleNamespace(data=callback, answer=AsyncMock()) if callback else None
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user),
        effective_chat=SimpleNamespace(type=chat),
        effective_message=message,
        callback_query=query,
    )


@pytest.mark.parametrize("user,chat", [(7, "private"), (42, "group"), (42, "supergroup")])
async def test_unapproved_users_and_group_chats_never_reach_manager(tmp_path, user, chat):
    client = Client()
    bot = TelegramBot({42}, client, tmp_path / "preferences.json")
    context = SimpleNamespace(user_data={})
    await bot.message(update(user, chat), context)
    await bot.callback(update(user, chat, callback="download:" + "a" * 32), context)
    assert client.calls == []


async def test_admin_status_command_uses_the_same_status_flow(tmp_path):
    client = Client()
    bot = TelegramBot({42}, client, tmp_path / "preferences.json")
    event = update()
    await bot.message(event, SimpleNamespace(user_data={}))
    assert client.calls == [("status", {})]
    event.effective_message.reply_text.assert_awaited_once()


async def test_stale_delete_confirmation_cannot_delete_the_server(tmp_path):
    client = Client()
    bot = TelegramBot({42}, client, tmp_path / "preferences.json")
    await bot.callback(update(callback="delete:old-confirmation"), SimpleNamespace(user_data={}))
    assert client.calls == []


async def test_admin_creates_downloads_and_revokes_real_persistent_profile(tmp_path):
    manager = Manager(tmp_path / "vpn", MemoryVpn())
    manager.start("203.0.113.5", 51820)

    class LocalClient:
        async def call(self, operation, **args):
            return getattr(manager, operation)(**args)

    bot = TelegramBot({42}, LocalClient(), tmp_path / "preferences.json")
    context = SimpleNamespace(user_data={})
    await bot.message(update(text="➕ Создать конфиг"), context)
    event = update(text="alice-phone")
    await bot.message(event, context)
    event.effective_message.reply_document.assert_awaited_once()
    assert event.effective_message.reply_document.call_args.args[0].filename == "alice-phone.conf"
    device_id = manager.list()[0]["id"]
    await bot.callback(update(callback=f"download:{device_id}"), context)
    await bot.callback(update(callback=f"revoke:{device_id}"), context)
    assert len(manager.list()) == 1
    nonce = context.user_data["revoke"][0]
    await bot.callback(update(callback=f"confirm_revoke:{nonce}"), context)
    assert manager.list() == []
    assert "[Peer]" not in manager.backend.config
