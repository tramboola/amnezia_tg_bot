from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

CREATE = "➕ Создать конфиг"
PROFILES = "📋 Конфиги"
STATUS = "📊 Статус"
SETTINGS = "⚙️ Настройки"


def main_menu():
    return ReplyKeyboardMarkup([[CREATE], [PROFILES, STATUS], [SETTINGS]], resize_keyboard=True)


def inline(rows):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )
