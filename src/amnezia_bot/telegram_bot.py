import json
import logging
import secrets
from io import BytesIO
from pathlib import Path

from telegram import BotCommand, InputFile
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from .manager import ManagerError, validate_endpoint, validate_name
from .public_ip import detect_public_ipv4
from .storage import save_json
from .telegram_ui import CREATE, PROFILES, SETTINGS, STATUS, inline, main_menu

LOG = logging.getLogger(__name__)
PAGE_SIZE = 15


class TelegramBot:
    def __init__(self, admin_ids, client, preferences_path, ip_detector=detect_public_ipv4):
        self.admin_ids = frozenset(admin_ids)
        self.client = client
        self.preferences_path = Path(preferences_path)
        self.ip_detector = ip_detector
        self.suffix = ""
        if self.preferences_path.exists():
            self.suffix = json.loads(self.preferences_path.read_text(encoding="utf-8"))["suffix"]
            if self.suffix:
                validate_name(self.suffix)

    def build_application(self, token):
        application = Application.builder().token(token).post_init(self.post_init).build()
        application.add_handler(MessageHandler(filters.TEXT, self.message))
        application.add_handler(CallbackQueryHandler(self.callback))
        application.add_error_handler(self.on_error)
        return application

    async def post_init(self, application):
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Главное меню"),
                BotCommand("init", "Запустить VPN"),
                BotCommand("generate", "Создать конфиг"),
                BotCommand("users", "Конфиги"),
                BotCommand("status", "Статус VPN"),
                BotCommand("settings", "Настройки"),
                BotCommand("stop", "Остановить VPN"),
                BotCommand("shutdown", "Удалить VPN"),
                BotCommand("cancel", "Отменить ввод"),
                BotCommand("help", "Справка"),
            ]
        )

    def allowed(self, update):
        return bool(
            update.effective_user
            and update.effective_chat
            and update.effective_user.id in self.admin_ids
            and update.effective_chat.type == "private"
        )

    async def message(self, update, context):
        if not self.allowed(update):
            return
        message = update.effective_message
        text = message.text.strip()
        command = text.split()[0].split("@")[0] if text else ""
        try:
            if command in ("/start", "/cancel", "/help"):
                context.user_data.clear()
                await message.reply_text(
                    "AmneziaWG 3.1. Для каждого устройства создавайте отдельный конфиг.\n"
                    "/init — запуск, /stop — остановка с сохранением конфигов.\n"
                    "Файл содержит ключ доступа; передавайте его только владельцу устройства.",
                    reply_markup=main_menu(),
                )
                if command == "/start":
                    status = await self.client.call("status")
                    if not status["configured"]:
                        await self.setup(message, context)
            elif command == "/init":
                context.user_data.clear()
                status = await self.client.call("status")
                if status["configured"]:
                    await self.client.call("start")
                    await message.reply_text("VPN запущен.", reply_markup=main_menu())
                else:
                    await self.setup(message, context)
            elif text == CREATE or command == "/generate":
                context.user_data.clear()
                context.user_data["awaiting"] = "name"
                await message.reply_text(
                    "Введите имя устройства: например, alice-phone. "
                    "До 32 латинских букв, цифр, _ или -."
                )
            elif text == PROFILES or command == "/users":
                context.user_data.clear()
                await self.profiles(message)
            elif text == STATUS or command == "/status":
                context.user_data.clear()
                await self.status(message)
            elif text == SETTINGS or command == "/settings":
                context.user_data.clear()
                await self.settings(message)
            elif command == "/stop":
                context.user_data.clear()
                await self.client.call("stop")
                await message.reply_text("VPN остановлен. Ключи и конфиги сохранены.")
            elif command == "/shutdown":
                await self.ask_delete(message, context)
            elif context.user_data.get("awaiting") == "name":
                result = await self.client.call("create", name=text)
                context.user_data.pop("awaiting", None)
                await self.send_profile(message, result)
            elif context.user_data.get("awaiting") == "endpoint":
                host, separator, port = text.partition(":")
                try:
                    port = int(port) if separator else 51820
                except ValueError:
                    raise ManagerError("invalid_port", "Введите IPv4:порт, например 1.2.3.4:51820.")
                host = validate_endpoint(host, port)
                context.user_data.pop("awaiting", None)
                nonce = secrets.token_hex(6)
                context.user_data["setup"] = (nonce, host, port)
                await message.reply_text(
                    f"Сервер: {host}:{port}/UDP. Откройте этот UDP-порт "
                    "в firewall VPS и панели провайдера.",
                    reply_markup=inline(
                        [
                            [("🚀 Запустить VPN", f"launch:{nonce}")],
                            [("Отмена", "cancel")],
                        ]
                    ),
                )
            elif context.user_data.get("awaiting") == "suffix":
                validate_name(text)
                self.set_suffix(text)
                context.user_data.pop("awaiting", None)
                await self.settings(message)
            else:
                await message.reply_text(
                    "Выберите действие в меню или используйте /help.", reply_markup=main_menu()
                )
        except ManagerError as error:
            await self.report_error(message, error)

    async def setup(self, message, context):
        detected = await self.ip_detector()
        context.user_data["awaiting"] = "endpoint"
        hint = f" Определённый внешний адрес: {detected}." if detected else ""
        await message.reply_text("Введите публичный IPv4 VPS и UDP-порт: IPv4:51820." + hint)

    async def status(self, message):
        status = await self.client.call("status")
        if not status["configured"]:
            await message.reply_text("Сервер ещё не настроен. Используйте /init.")
            return
        running = "работает" if status["running"] else "остановлен"
        pending = (
            "\nЕсть неприменённые изменения. Менеджер повторяет их применение. "
            "До успешного применения отзыв доступа не гарантирован."
            if status.get("pending_changes")
            else ""
        )
        await message.reply_text(
            f"VPN {running}. AmneziaWG 3.1\n"
            f"{status['host']}:{status['port']}/UDP\n"
            f"Устройств: {status['devices']}{pending}"
        )

    async def profiles(self, message, page=0):
        devices = await self.client.call("list")
        page = min(max(page, 0), max((len(devices) - 1) // PAGE_SIZE, 0))
        rows = [
            [
                (f"⬇️ {device['name']}", f"download:{device['id']}"),
                ("🗑 Отозвать", f"revoke:{device['id']}"),
            ]
            for device in devices[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        ]
        navigation = []
        if page:
            navigation.append(("←", f"profiles:{page - 1}"))
        if (page + 1) * PAGE_SIZE < len(devices):
            navigation.append(("→", f"profiles:{page + 1}"))
        if navigation:
            rows.append(navigation)
        rows.append([("🔄 Обновить", f"profiles:{page}")])
        await message.reply_text(
            f"Конфиги: {len(devices)}. Страница {page + 1}." if devices else "Конфигов пока нет.",
            reply_markup=inline(rows),
        )

    async def send_profile(self, message, profile):
        suffix = f"_{self.suffix}" if self.suffix else ""
        filename = f"{profile['name']}{suffix}.conf"
        await message.reply_document(
            InputFile(BytesIO(profile["config"].encode()), filename=filename),
            caption="Импортируйте файл в клиент с поддержкой AmneziaWG 3.1. "
            "Один конфиг — одно устройство.",
        )

    def set_suffix(self, suffix):
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(self.preferences_path, {"suffix": suffix})
        self.suffix = suffix

    async def settings(self, message):
        await message.reply_text(
            f"Суффикс файлов: {self.suffix or 'не задан'}",
            reply_markup=inline(
                [
                    [("✏️ Изменить суффикс", "suffix")],
                    [("Очистить суффикс", "suffix_clear")],
                    [("🚀 Запустить VPN", "resume")],
                    [("⏸ Остановить VPN", "stop")],
                    [("⚠️ Удалить VPN и все конфиги", "delete_request")],
                ]
            ),
        )

    async def ask_delete(self, message, context):
        context.user_data.clear()
        nonce = secrets.token_hex(6)
        context.user_data["delete_nonce"] = nonce
        await message.reply_text(
            "Удалить VPN и все ключи? Все выданные конфиги перестанут работать. "
            "Отменить удаление можно только восстановлением резервной копии.",
            reply_markup=inline([[("Да, удалить всё", f"delete:{nonce}")], [("Отмена", "cancel")]]),
        )

    async def callback(self, update, context):
        if not self.allowed(update):
            if update.callback_query:
                await update.callback_query.answer("Доступ закрыт.", show_alert=True)
            return
        query = update.callback_query
        await query.answer()
        message = update.effective_message
        action, _, argument = (query.data or "").partition(":")
        try:
            if action == "cancel":
                context.user_data.clear()
                await message.reply_text("Отменено.", reply_markup=main_menu())
            elif action == "profiles" and argument.isdecimal():
                await self.profiles(message, min(int(argument), 1000))
            elif action == "download":
                await self.send_profile(
                    message, await self.client.call("download", device_id=argument)
                )
            elif action == "revoke":
                devices = await self.client.call("list")
                device = next((d for d in devices if d["id"] == argument), None)
                if not device:
                    raise ManagerError("not_found", "Устройство уже удалено или отозвано.")
                nonce = secrets.token_hex(6)
                context.user_data["revoke"] = (nonce, argument)
                await message.reply_text(
                    f"Отозвать доступ {device['name']}?",
                    reply_markup=inline(
                        [
                            [("Да, отозвать доступ", f"confirm_revoke:{nonce}")],
                            [("Отмена", "cancel")],
                        ]
                    ),
                )
            elif action == "confirm_revoke":
                pending = context.user_data.pop("revoke", None)
                if not pending or pending[0] != argument:
                    await message.reply_text("Подтверждение устарело. Откройте список конфигов.")
                    return
                await self.client.call("revoke", device_id=pending[1])
                await message.reply_text("Доступ отозван.")
            elif action == "launch":
                pending = context.user_data.pop("setup", None)
                if not pending or pending[0] != argument:
                    await message.reply_text("Подтверждение устарело. Используйте /init.")
                    return
                await self.client.call("start", host=pending[1], port=pending[2])
                await message.reply_text("VPN запущен.", reply_markup=main_menu())
            elif action in ("stop", "resume"):
                await self.client.call("stop" if action == "stop" else "start")
                await self.status(message)
            elif action == "suffix":
                context.user_data.clear()
                context.user_data["awaiting"] = "suffix"
                await message.reply_text("Введите суффикс: до 32 латинских букв, цифр, _ или -.")
            elif action == "suffix_clear":
                self.set_suffix("")
                await self.settings(message)
            elif action == "delete_request":
                await self.ask_delete(message, context)
            elif action == "delete":
                nonce = context.user_data.pop("delete_nonce", None)
                if not nonce or nonce != argument:
                    await message.reply_text("Подтверждение устарело. Откройте настройки.")
                    return
                await self.client.call("delete")
                await message.reply_text("VPN и ключи удалены. /init — настроить заново.")
        except ManagerError as error:
            await self.report_error(message, error)

    async def report_error(self, message, error):
        text = str(error)
        if error.code in ("docker_failed", "docker_unavailable", "vpn_not_ready"):
            text += (
                "\nИзменение могло сохраниться. Менеджер повторяет применение каждые 10 секунд. "
            )
            text += "До успешного применения отзыв доступа не гарантирован."
        await message.reply_text(text)

    async def on_error(self, update, context):
        # Never log update/context/exception: any may contain tokens or config bytes.
        LOG.error("Telegram operation failed; details suppressed")
        if update and self.allowed(update) and update.effective_message:
            await update.effective_message.reply_text(
                "Операция не завершена. Проверьте статус и повторите запрос."
            )
