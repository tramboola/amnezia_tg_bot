import logging

from .config import Settings
from .rpc import ManagerClient
from .telegram_bot import TelegramBot


def main():
    logging.basicConfig(level=logging.WARNING)
    # HTTP request URLs contain the bot token. Keep HTTP transport logging disabled.
    logging.getLogger("httpx").disabled = True
    logging.getLogger("httpcore").disabled = True
    settings = Settings.load()
    bot = TelegramBot(
        settings.admin_ids, ManagerClient(settings.socket_path), settings.preferences_path
    )
    bot.build_application(settings.bot_token).run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
