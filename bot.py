import os
import time
import requests
import traceback
from datetime import datetime


# =========================
# НАСТРОЙКИ ИЗ RENDER
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SHEET_WEBAPP_URL = os.getenv("SHEET_WEBAPP_URL", "").strip()
APPS_SCRIPT_SECRET = os.getenv("APPS_SCRIPT_SECRET", "").strip()
TABLE_URL = os.getenv("TABLE_URL", "").strip()

if not BOT_TOKEN:
    raise Exception("Не найден BOT_TOKEN в Render Environment Variables")

if not SHEET_WEBAPP_URL:
    raise Exception("Не найден SHEET_WEBAPP_URL в Render Environment Variables")

if not APPS_SCRIPT_SECRET:
    raise Exception("Не найден APPS_SCRIPT_SECRET в Render Environment Variables")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
if OWNER_CHAT_ID:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)

USER_STATES = {}


# =========================
# ЗАПИСЬ В GOOGLE ТАБЛИЦУ ЧЕРЕЗ APPS SCRIPT
# =========================

def send_to_sheet(data):
    payload = dict(data)
    payload["secret"] = APPS_SCRIPT_SECRET

    response = requests.post(
        SHEET_WEBAPP_URL,
        json=payload,
        timeout=30
    )

    text = response.text
    print("Ответ Apps Script:", text)

    try:
        result = response.json()
    except Exception:
        raise Exception("Apps Script вернул не JSON: " + text)

    if not result.get("ok"):
        raise Exception("Apps Script error: " + str(result))

    return result


def add_manual_test_row(chat_id=None):
    data = {
        "type": "MANUAL TEST",
        "chat_id": str(chat_id or "TEST"),
        "username": "",
        "name": "Тестовая строка",
        "phone": "89999999999",
        "service": "Проверка таблицы",
        "day": "Понедельник",
        "time": "10:00",
        "status": "Тест",
        "comment": "Если эта строка появилась — Render пишет в таблицу"
    }

    send_to_sheet(data)


def add_lead_to_sheet(chat_id, username, state):
    data = {
        "type": "ЗАЯВКА",
        "chat_id": str(chat_id),
        "username": username or "",
        "name": state.get("name", ""),
        "phone": state.get("phone", ""),
        "service": state.get("service", ""),
        "day": state.get("day", ""),
        "time": state.get("time", ""),
        "status": "Новая",
        "comment": ""
    }

    send_to_sheet(data)


# =========================
# TELEGRAM API
# =========================

def tg(method, payload=None):
    try:
        response = requests.post(
            f"{TG_API}/{method}",
            json=payload or {},
            timeout=30
        )

        try:
            data = response.json()
        except Exception:
            print("Telegram вернул не JSON:")
            print(response.text)
            return {"ok": False, "description": response.text}

        if not data.get("ok"):
            print("Telegram API error:", method)
            print(data)

        return data

    except Exception as e:
        print("Ошибка Telegram API:", e)
        return {"ok": False, "description": str(e)}


def delete_webhook():
    print("Удаляю webhook и старую очередь Telegram...")
    result = tg("deleteWebhook", {"drop_pending_updates": True})
    print(result)


def send_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    return tg("sendMessage", payload)


def get_updates(offset=None):
    payload = {
        "timeout": 25,
        "limit": 20,
        "allowed_updates": ["message"]
    }

    if offset is not None:
        payload["offset"] = offset

    try:
        response = requests.post(
            f"{TG_API}/getUpdates",
            json=payload,
            timeout=35
        )

        data = response.json()

        if not data.get("ok"):
            print("getUpdates ошибка:")
            print(data)

        return data

    except Exception as e:
        print("Ошибка getUpdates:", e)
        return {"ok": False, "result": []}


# =========================
# КЛАВИАТУРЫ
# =========================

def main_keyboard():
    return {
        "keyboard": [
            [{"text": "📝 Записаться"}, {"text": "💰 Прайс"}],
            [{"text": "❓ FAQ"}, {"text": "📍 Адрес и график"}],
            [{"text": "📲 Связаться"}, {"text": "🔄 Меню"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def service_keyboard():
    return {
        "keyboard": [
            [{"text": "💅 Маникюр"}, {"text": "🦶 Педикюр"}],
            [{"text": "✨ Наращивание"}, {"text": "🎨 Дизайн ногтей"}],
            [{"text": "⬅️ В меню"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def day_keyboard():
    return {
        "keyboard": [
            [{"text": "Понедельник"}, {"text": "Вторник"}],
            [{"text": "Среда"}, {"text": "Четверг"}],
            [{"text": "Пятница"}, {"text": "Суббота"}],
            [{"text": "Воскресенье"}],
            [{"text": "⬅️ К выбору услуги"}, {"text": "⬅️ В меню"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def time_keyboard():
    return {
        "keyboard": [
            [{"text": "10:00"}, {"text": "11:00"}, {"text": "12:00"}],
            [{"text": "13:00"}, {"text": "14:00"}, {"text": "15:00"}],
            [{"text": "16:00"}, {"text": "17:00"}, {"text": "18:00"}],
            [{"text": "19:00"}, {"text": "20:00"}],
            [{"text": "⬅️ К выбору дня"}, {"text": "⬅️ В меню"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


# =========================
# ПРОВЕРКИ
# =========================

def is_valid_name(name):
    name = name.strip()

    if len(name) < 2:
        return False

    for char in name:
        if char.isdigit():
            return False

    return True


def is_valid_phone(phone):
    phone = phone.strip()

    if not phone.isdigit():
        return False

    if len(phone) < 10 or len(phone) > 15:
        return False

    return True


def is_day(text):
    return text in [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье"
    ]


def is_time(text):
    return text in [
        "10:00",
        "11:00",
        "12:00",
        "13:00",
        "14:00",
        "15:00",
        "16:00",
        "17:00",
        "18:00",
        "19:00",
        "20:00"
    ]


def is_service(text):
    return text in [
        "💅 Маникюр",
        "🦶 Педикюр",
        "✨ Наращивание",
        "🎨 Дизайн ногтей"
    ]


def clean_service(text):
    return (
        text
        .replace("💅 ", "")
        .replace("🦶 ", "")
        .replace("✨ ", "")
        .replace("🎨 ", "")
    )


# =========================
# ЭКРАНЫ
# =========================

def send_main_menu(chat_id):
    USER_STATES.pop(chat_id, None)

    send_message(
        chat_id,
        "<b>Здравствуйте! 👋</b>\n\n"
        "Я помогу записаться на услугу, посмотреть прайс или узнать FAQ.\n\n"
        "Выберите действие:",
        main_keyboard()
    )


def send_price(chat_id):
    send_message(
        chat_id,
        "<b>💰 Прайс</b>\n\n"
        "💅 Маникюр — от 1500 ₽\n"
        "🦶 Педикюр — от 1800 ₽\n"
        "✨ Наращивание — от 2500 ₽\n"
        "🎨 Дизайн — от 300 ₽",
        main_keyboard()
    )


def send_faq(chat_id):
    send_message(
        chat_id,
        "<b>❓ FAQ</b>\n\n"
        "<b>Сколько длится процедура?</b>\n"
        "Обычно от 1,5 до 2,5 часов.\n\n"
        "<b>Можно ли перенести запись?</b>\n"
        "Да, желательно предупредить заранее.\n\n"
        "<b>Нужна ли предоплата?</b>\n"
        "Иногда да, зависит от услуги.",
        main_keyboard()
    )


def send_info(chat_id):
    send_message(
        chat_id,
        "<b>📍 Адрес и график</b>\n\n"
        "Адрес: г. Сургут, ул. Примерная, 10\n"
        "График: ежедневно с 10:00 до 20:00",
        main_keyboard()
    )


def send_contact(chat_id):
    send_message(
        chat_id,
        "<b>📲 Связаться</b>\n\n"
        "Оставьте заявку через бота, мастер получит данные и свяжется с вами.",
        main_keyboard()
    )


def send_help(chat_id):
    send_message(
        chat_id,
        "<b>Команды владельца:</b>\n\n"
        "/start — открыть меню\n"
        "/setowner — получать заявки в этот чат\n"
        "/table — ссылка на таблицу\n"
        "/testsheet — тестовая строка в таблицу\n"
        "/reset — сбросить диалог",
        main_keyboard()
    )


def send_services(chat_id):
    USER_STATES.pop(chat_id, None)

    send_message(
        chat_id,
        "<b>📝 Запись</b>\n\nВыберите услугу:",
        service_keyboard()
    )


def send_days(chat_id, service):
    USER_STATES[chat_id] = {
        "step": "day",
        "service": service
    }

    send_message(
        chat_id,
        f"Вы выбрали: <b>{service}</b>\n\n"
        "Теперь выберите удобный день:",
        day_keyboard()
    )


def send_times(chat_id, state):
    USER_STATES[chat_id] = state

    send_message(
        chat_id,
        f"Вы выбрали день: <b>{state.get('day')}</b>\n\n"
        "Теперь выберите удобное время:",
        time_keyboard()
    )


# =========================
# УВЕДОМЛЕНИЕ ВЛАДЕЛЬЦУ
# =========================

def notify_owner(client_chat_id, username, state):
    if not OWNER_CHAT_ID:
        return

    text = (
        "<b>🔥 Новая заявка</b>\n\n"
        f"<b>Услуга:</b> {state.get('service', '')}\n"
        f"<b>День:</b> {state.get('day', '')}\n"
        f"<b>Время:</b> {state.get('time', '')}\n"
        f"<b>Имя:</b> {state.get('name', '')}\n"
        f"<b>Телефон:</b> {state.get('phone', '')}\n"
        f"<b>Telegram:</b> {username or 'нет username'}\n"
        f"<b>Chat ID:</b> {client_chat_id}\n\n"
        "✅ Заявка добавлена в таблицу."
    )

    if TABLE_URL:
        text += f"\n\n📄 Таблица:\n{TABLE_URL}"

    send_message(OWNER_CHAT_ID, text)


# =========================
# ОБРАБОТКА СООБЩЕНИЙ
# =========================

def handle_message(message):
    global OWNER_CHAT_ID

    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_id = chat.get("id")
    text = str(message.get("text", "")).strip()

    username = user.get("username")
    if username:
        username = "@" + username

    print("Сообщение:", chat_id, text)

    if text in ["/start", "/menu", "🔄 Меню", "⬅️ В меню"]:
        send_main_menu(chat_id)
        return

    if text == "/help":
        send_help(chat_id)
        return

    if text == "/ping":
        send_message(chat_id, "✅ Бот работает.")
        return

    if text == "/setowner":
        OWNER_CHAT_ID = chat_id
        send_message(
            chat_id,
            "✅ Готово. Теперь заявки будут приходить в этот чат."
        )
        return

    if text == "/table":
        if TABLE_URL:
            send_message(chat_id, f"📄 Таблица заявок:\n{TABLE_URL}")
        else:
            send_message(chat_id, "Таблица подключена через Apps Script. Ссылку TABLE_URL можно добавить в Render.")
        return

    if text == "/testsheet":
        try:
            add_manual_test_row(chat_id)
            send_message(
                chat_id,
                "✅ Тестовая строка добавлена в таблицу.",
                main_keyboard()
            )
        except Exception as e:
            print("Ошибка теста таблицы:")
            traceback.print_exc()

            send_message(
                chat_id,
                "❌ Не получилось добавить тестовую строку.\n\n"
                f"Ошибка:\n<code>{str(e)}</code>",
                main_keyboard()
            )
        return

    if text in ["/reset", "/cancel"]:
        USER_STATES.pop(chat_id, None)
        send_message(chat_id, "✅ Сброшено. Напишите /start.", main_keyboard())
        return

    if text == "💰 Прайс":
        send_price(chat_id)
        return

    if text == "❓ FAQ":
        send_faq(chat_id)
        return

    if text == "📍 Адрес и график":
        send_info(chat_id)
        return

    if text == "📲 Связаться":
        send_contact(chat_id)
        return

    if text == "📝 Записаться":
        send_services(chat_id)
        return

    if text == "⬅️ К выбору услуги":
        send_services(chat_id)
        return

    state = USER_STATES.get(chat_id)

    if is_service(text):
        service = clean_service(text)
        send_days(chat_id, service)
        return

    if state and text == "⬅️ К выбору дня":
        state["step"] = "day"
        state.pop("day", None)
        state.pop("time", None)
        USER_STATES[chat_id] = state

        send_message(chat_id, "Выберите удобный день:", day_keyboard())
        return

    if state and state.get("step") == "day":
        if not is_day(text):
            send_message(
                chat_id,
                "Пожалуйста, выберите день кнопкой ниже:",
                day_keyboard()
            )
            return

        state["day"] = text
        state["step"] = "time"
        send_times(chat_id, state)
        return

    if state and state.get("step") == "time":
        if not is_time(text):
            send_message(
                chat_id,
                "Пожалуйста, выберите время кнопкой ниже:",
                time_keyboard()
            )
            return

        state["time"] = text
        state["step"] = "name"
        USER_STATES[chat_id] = state

        send_message(
            chat_id,
            "Отлично. Теперь напишите ваше имя.\n\n"
            "Важно: имя не должно содержать цифры."
        )
        return

    if state and state.get("step") == "name":
        if not is_valid_name(text):
            send_message(
                chat_id,
                "❌ Имя указано неправильно.\n\n"
                "Имя не должно содержать цифры и должно быть минимум из 2 символов.\n\n"
                "Напишите имя ещё раз:"
            )
            return

        state["name"] = text
        state["step"] = "phone"
        USER_STATES[chat_id] = state

        send_message(
            chat_id,
            "Теперь напишите номер телефона.\n\n"
            "Важно: только цифры, без +, пробелов и букв.\n"
            "Пример: <code>89991234567</code>"
        )
        return

    if state and state.get("step") == "phone":
        if not is_valid_phone(text):
            send_message(
                chat_id,
                "❌ Номер указан неправильно.\n\n"
                "Телефон должен содержать только цифры.\n"
                "Длина: от 10 до 15 цифр.\n\n"
                "Пример: <code>89991234567</code>\n\n"
                "Введите номер ещё раз:"
            )
            return

        state["phone"] = text

        try:
            add_lead_to_sheet(chat_id, username, state)
            notify_owner(chat_id, username, state)

            USER_STATES.pop(chat_id, None)

            send_message(
                chat_id,
                "✅ Заявка принята!\n\n"
                f"<b>Услуга:</b> {state.get('service')}\n"
                f"<b>День:</b> {state.get('day')}\n"
                f"<b>Время:</b> {state.get('time')}\n"
                f"<b>Имя:</b> {state.get('name')}\n"
                f"<b>Телефон:</b> {state.get('phone')}\n\n"
                "Мастер скоро свяжется с вами.",
                main_keyboard()
            )

        except Exception as e:
            print("Ошибка записи заявки:")
            traceback.print_exc()

            send_message(
                chat_id,
                "⚠️ Заявку получил, но таблица не записалась.\n\n"
                f"Ошибка:\n<code>{str(e)}</code>",
                main_keyboard()
            )

        return

    send_message(chat_id, "Я вас не понял. Напишите /start.", main_keyboard())


# =========================
# ЗАПУСК
# =========================

def run_bot():
    delete_webhook()

    offset = None

    print("Бот запущен.")
    print("Напиши в Telegram /start")
    print("Потом /setowner")

    while True:
        try:
            updates = get_updates(offset)

            if not updates.get("ok"):
                print("getUpdates вернул ошибку:")
                print(updates)
                time.sleep(3)
                continue

            for update in updates.get("result", []):
                offset = update["update_id"] + 1

                if "message" in update:
                    handle_message(update["message"])

            time.sleep(0.3)

        except KeyboardInterrupt:
            print("Бот остановлен.")
            break

        except Exception:
            print("Ошибка основного цикла:")
            traceback.print_exc()
            time.sleep(3)


run_bot()
