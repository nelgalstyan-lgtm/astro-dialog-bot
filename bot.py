# -*- coding: utf-8 -*-
"""
Astro Dialog Bot — основной файл.

Запуск:  python bot.py
Требует BOT_TOKEN в .env (см. .env.example).
"""
import asyncio
import logging
import signal

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import database as db
import keyboards as kb
from content import ZODIAC, get_zodiac_by_date, get_profile_type
from image_generator import get_profile_card

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("astro_dialog_bot")

PICK_YEAR, PICK_MONTH, PICK_DAY, PICK_HOUR, PICK_MINUTE, BIRTH_CITY = range(6)


async def is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(config.CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except (BadRequest, Forbidden) as e:
        logger.error(
            "ПРОВЕРКА ПОДПИСКИ ПРОПУЩЕНА для user_id=%s: не удалось обратиться к каналу %r (%s). "
            "Скорее всего CHANNEL_USERNAME в переменных окружения не совпадает с реальным username "
            "канала, либо бот не добавлен туда администратором. Пока это не исправлено, все "
            "пользователи проходят дальше без проверки.",
            user_id, config.CHANNEL_USERNAME, e,
        )
        return True


def styled(title: str, body: str, emoji: str = "") -> str:
    """Единый визуальный стиль для сообщений бота: заголовок + разделитель + текст."""
    header = f"{emoji} *{title.upper()}*".strip()
    return f"{header}\n✧┄┄┄┄┄┄┄┄┄┄┄┄✧\n\n{body}"


def welcome_text() -> str:
    return styled(
        "Astro Dialog",
        "Здесь вы получите персональный психологический профиль по дате рождения.\n\n"
        "Это займёт меньше минуты.",
        "🌙",
    )


def subscribe_text() -> str:
    return styled(
        "Профиль почти готов",
        "Остался один шаг — подпишитесь на канал «Астрологический Диалог», "
        "где ежедневно выходят новые психологические разборы знаков, "
        "интервью с персонажами и короткие видео.\n\n"
        "После подписки нажмите кнопку ниже.",
        "✨",
    )


def gender_text() -> str:
    return styled("Выберите пол", "Это нужно, чтобы подобрать вашего персонажа для карточки.", "👤")


def date_step_text(title: str, body: str) -> str:
    return styled(title, body, "📅")


def time_step_text(title: str, body: str) -> str:
    return styled(title, body, "🕐")


def city_text() -> str:
    return styled(
        "Город рождения",
        "Введите город, в котором вы родились, или нажмите кнопку ниже, если пропускаете.",
        "📍",
    )


def profile_ready_caption(type_data: dict) -> str:
    quote = f"«{type_data['quote']}»" if type_data.get("quote") else "Ваш психологический профиль готов."
    return styled("Ваш профиль готов", quote, "✨")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, username=user.username)

    await update.message.reply_text(
        welcome_text(), reply_markup=kb.kb_start(), parse_mode=ParseMode.MARKDOWN
    )


async def on_start_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await is_subscribed(context.bot, user_id):
        await query.edit_message_text(
            gender_text(), reply_markup=kb.kb_gender(), parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(
            subscribe_text(), reply_markup=kb.kb_subscribe(), parse_mode=ParseMode.MARKDOWN
        )


async def on_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if await is_subscribed(context.bot, user_id):
        await query.answer("Подписка подтверждена ✅")
        await query.edit_message_text(
            gender_text(), reply_markup=kb.kb_gender(), parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.answer(
            "Пока не вижу подписку. Подпишитесь и попробуйте снова.", show_alert=True
        )


async def on_gender_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gender = "female" if query.data == "gender_female" else "male"
    context.user_data["gender"] = gender
    db.upsert_user(query.from_user.id, gender=gender)

    await query.edit_message_text(
        date_step_text("Год рождения", "Выберите год рождения."),
        reply_markup=kb.kb_year_picker(0),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_YEAR


async def on_year_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    context.user_data["year_page"] = page
    await query.edit_message_text(
        date_step_text("Год рождения", "Выберите год рождения."),
        reply_markup=kb.kb_year_picker(page),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_YEAR


async def on_year_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    year = int(query.data.split(":")[1])
    context.user_data["picker_year"] = year
    await query.edit_message_text(
        date_step_text("Месяц рождения", f"Год: {year}. Теперь выберите месяц."),
        reply_markup=kb.kb_month_picker(year),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_MONTH


async def on_back_to_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = context.user_data.get("year_page", 0)
    await query.edit_message_text(
        date_step_text("Год рождения", "Выберите год рождения."),
        reply_markup=kb.kb_year_picker(page),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_YEAR


async def on_month_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month = int(query.data.split(":")[1])
    year = context.user_data["picker_year"]
    context.user_data["picker_month"] = month
    await query.edit_message_text(
        date_step_text("День рождения", f"{kb.MONTHS_RU[month - 1]} {year}. Теперь выберите день."),
        reply_markup=kb.kb_day_picker(year, month),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_DAY


async def on_back_to_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    year = context.user_data["picker_year"]
    await query.edit_message_text(
        date_step_text("Месяц рождения", f"Год: {year}. Теперь выберите месяц."),
        reply_markup=kb.kb_month_picker(year),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_MONTH


async def on_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Клетки-заглушки в календаре (шапка дней недели, пустые ячейки, недоступные месяцы)."""
    await update.callback_query.answer()


async def on_future_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Эта дата ещё не наступила 🙂", show_alert=True)


async def on_day_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day = int(query.data.split(":")[1])
    year = context.user_data["picker_year"]
    month = context.user_data["picker_month"]

    zodiac_key = get_zodiac_by_date(day, month)
    if zodiac_key is None:
        await query.answer("Не получилось определить знак. Попробуйте другую дату.", show_alert=True)
        return PICK_DAY

    context.user_data["birth_date"] = f"{day:02d}.{month:02d}.{year}"
    context.user_data["birth_day"] = day
    context.user_data["birth_month"] = month
    context.user_data["zodiac"] = zodiac_key
    db.upsert_user(
        query.from_user.id,
        birth_date=context.user_data["birth_date"],
        birth_day=day,
        birth_month=month,
        zodiac=zodiac_key,
    )

    sign = ZODIAC[zodiac_key]
    await query.edit_message_text(
        f"{sign['emoji']} *ВЫ — {sign['name'].upper()}*\n"
        "✧┄┄┄┄┄┄┄┄┄┄┄┄✧\n\n"
        "Хотите сделать профиль точнее?\n\n"
        "🕐 Выберите час рождения\n"
        "или нажмите «Не знаю время» ниже.",
        reply_markup=kb.kb_hour_picker(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_HOUR


async def on_hour_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hour = int(query.data.split(":")[1])
    context.user_data["picker_hour"] = hour
    await query.edit_message_text(
        time_step_text("Минуты рождения", f"Час: {hour:02d}. Теперь выберите минуты."),
        reply_markup=kb.kb_minute_picker(hour),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_MINUTE


async def on_back_to_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        time_step_text("Час рождения", "Выберите час рождения."),
        reply_markup=kb.kb_hour_picker(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PICK_HOUR


async def on_minute_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    minute = int(query.data.split(":")[1])
    hour = context.user_data["picker_hour"]
    text = f"{hour:02d}:{minute:02d}"
    context.user_data["birth_time"] = text
    db.upsert_user(query.from_user.id, birth_time=text)
    await query.edit_message_text(
        city_text(), reply_markup=kb.kb_skip_city(), parse_mode=ParseMode.MARKDOWN
    )
    return BIRTH_CITY


async def on_skip_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["birth_time"] = None
    await query.edit_message_text(
        city_text(), reply_markup=kb.kb_skip_city(), parse_mode=ParseMode.MARKDOWN
    )
    return BIRTH_CITY


async def on_birth_city_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    context.user_data["birth_city"] = city
    db.upsert_user(update.effective_user.id, birth_city=city)
    await run_analysis_and_send_card(update.message, context, update.effective_user.id)
    return ConversationHandler.END


async def on_skip_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["birth_city"] = None
    await run_analysis_and_send_card(query.message, context, query.from_user.id, edit=True)
    return ConversationHandler.END


async def run_analysis_and_send_card(message, context, user_id: int, edit: bool = False):
    """Показывает экран анализа и присылает карточку профиля."""
    steps = [
        "Определяем знак...\n▓▓▓░░░░░░░",
        "Анализируем данные...\n▓▓▓▓▓▓▓░░░",
        "Создаем профиль...\n▓▓▓▓▓▓▓▓▓▓",
    ]
    if edit:
        msg = await message.edit_text(styled("Анализ", steps[0], "🔮"), parse_mode=ParseMode.MARKDOWN)
    else:
        msg = await message.reply_text(styled("Анализ", steps[0], "🔮"), parse_mode=ParseMode.MARKDOWN)

    for step_text in steps[1:]:
        await asyncio.sleep(0.9)
        try:
            await msg.edit_text(styled("Анализ", step_text, "🔮"), parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            pass

    await asyncio.sleep(0.6)
    user = db.get_user(user_id) or {}
    zodiac_key = context.user_data.get("zodiac") or user.get("zodiac")
    gender = context.user_data.get("gender") or user.get("gender")
    birth_day = context.user_data.get("birth_day") or user.get("birth_day")
    birth_month = context.user_data.get("birth_month") or user.get("birth_month")
    birth_time = context.user_data.get("birth_time")
    if birth_time is None:
        birth_time = user.get("birth_time")

    hour = minute = None
    if birth_time:
        try:
            h_str, m_str = birth_time.split(":")
            hour, minute = int(h_str), int(m_str)
        except (ValueError, AttributeError):
            pass

    type_data = get_profile_type(zodiac_key, month=birth_month, day=birth_day, hour=hour, minute=minute)
    db.upsert_user(user_id, zodiac=zodiac_key, gender=gender, type_id=type_data["id"])

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_PHOTO)
    card_buf = get_profile_card(zodiac_key, type_data, gender)
    db.increment_profiles_created(user_id)

    await context.bot.send_photo(
        chat_id=message.chat_id,
        photo=card_buf,
        filename=card_buf.name,
        caption=profile_ready_caption(type_data),
        reply_markup=kb.kb_profile_menu(zodiac_key),
    )

    try:
        await msg.delete()
    except BadRequest:
        pass


async def on_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_username = config.BOT_USERNAME or (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}"

    text = (
        "📤 *ПОДЕЛИТЬСЯ*\n"
        "✧┄┄┄┄┄┄┄┄┄┄┄┄✧\n\n"
        "Понравился профиль? Отправьте бота другу — пусть сравнит результат со своим 🌙\n\n"
        f"{link}"
    )
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def on_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        gender_text(), reply_markup=kb.kb_gender(), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        styled("Остановлено", "Когда будете готовы — нажмите /start.", "🌙"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ошибка при обработке апдейта %s: %s", update, context.error, exc_info=context.error)


async def _post_init(application: Application) -> None:
    """Проверяет при старте, что канал для подписки вообще найден — чтобы
    ошибка конфигурации (неверный CHANNEL_USERNAME, бот не админ канала)
    была сразу видна в логах, а не терялась среди сообщений пользователей."""
    try:
        chat = await application.bot.get_chat(config.CHANNEL_USERNAME)
        logger.info("✅ Канал для проверки подписки найден: %s (%s)", chat.title, config.CHANNEL_USERNAME)
    except Exception as e:
        logger.error(
            "❌ КАНАЛ %r НЕ НАЙДЕН — проверка подписки будет пропускаться для ВСЕХ пользователей, "
            "пока это не исправлено. Проверьте: 1) переменная CHANNEL_USERNAME в настройках хостинга "
            "точно совпадает с username канала (с собакой @); 2) бот добавлен в канал администратором. "
            "Ошибка: %s",
            config.CHANNEL_USERNAME, e,
        )


def build_application() -> Application:
    db.init_db()
    application = ApplicationBuilder().token(config.BOT_TOKEN).post_init(_post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_gender_chosen, pattern="^gender_(male|female)$")],
        states={
            PICK_YEAR: [
                CallbackQueryHandler(on_year_page, pattern="^yrpage:"),
                CallbackQueryHandler(on_year_picked, pattern="^yr:"),
            ],
            PICK_MONTH: [
                CallbackQueryHandler(on_back_to_year, pattern="^back_yr$"),
                CallbackQueryHandler(on_noop, pattern="^noop$"),
                CallbackQueryHandler(on_month_picked, pattern="^mo:"),
            ],
            PICK_DAY: [
                CallbackQueryHandler(on_back_to_month, pattern="^back_mo$"),
                CallbackQueryHandler(on_noop, pattern="^noop$"),
                CallbackQueryHandler(on_future_day, pattern="^future$"),
                CallbackQueryHandler(on_day_picked, pattern="^dy:"),
            ],
            PICK_HOUR: [
                CallbackQueryHandler(on_skip_time, pattern="^skip_time$"),
                CallbackQueryHandler(on_hour_picked, pattern="^hr:"),
            ],
            PICK_MINUTE: [
                CallbackQueryHandler(on_back_to_hour, pattern="^back_hr$"),
                CallbackQueryHandler(on_minute_picked, pattern="^mi:"),
            ],
            BIRTH_CITY: [
                CallbackQueryHandler(on_skip_city, pattern="^skip_city$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_birth_city_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        name="profile_conversation",
        persistent=False,
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(conv_handler)

    application.add_handler(CallbackQueryHandler(on_start_flow, pattern="^start_flow$"))
    application.add_handler(CallbackQueryHandler(on_check_sub, pattern="^check_sub$"))
    application.add_handler(CallbackQueryHandler(on_restart, pattern="^restart$"))
    application.add_handler(CallbackQueryHandler(on_share, pattern="^share$"))

    application.add_error_handler(error_handler)
    return application


async def _run_webhook_server():
    from aiohttp import web

    application = build_application()
    await application.initialize()
    await _post_init(application)  # initialize() не вызывает post_init сам — это делают только
                                    # встроенные run_polling/run_webhook, которыми мы тут не пользуемся.
    await application.start()

    webhook_url = f"{config.WEBHOOK_URL.rstrip('/')}/{config.WEBHOOK_PATH}"
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=config.WEBHOOK_SECRET or None,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    logger.info("Webhook зарегистрирован в Telegram: %s", webhook_url)

    async def handle_webhook(request: "web.Request") -> "web.Response":
        if config.WEBHOOK_SECRET:
            token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if token != config.WEBHOOK_SECRET:
                return web.Response(status=401, text="unauthorized")
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="bad request")
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(status=200, text="ok")

    async def handle_health(request: "web.Request") -> "web.Response":
        return web.Response(status=200, text="Astro Dialog Bot is alive")

    web_app = web.Application()
    web_app.router.add_post(f"/{config.WEBHOOK_PATH}", handle_webhook)
    web_app.router.add_get("/", handle_health)
    web_app.router.add_get("/healthz", handle_health)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info("Astro Dialog Bot запущен в режиме webhook, слушает порт %s", config.PORT)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                pass

    await stop_event.wait()

    logger.info("Останавливаю бота...")
    # Важно: НЕ вызываем delete_webhook() здесь. Если это происходит во время
    # передеплоя/пробуждения на Render, новый процесс может успеть заново
    # зарегистрировать вебхук чуть раньше, чем старый процесс досюда дойдет —
    # тогда этот вызов удалит уже актуальный, только что поставленный вебхук,
    # и бот перестанет получать обновления до следующего ручного вмешательства.
    # Telegram сам спокойно ждет, пока адрес снова станет доступен, отписка
    # от вебхука при обычной остановке не нужна.
    await application.stop()
    await application.shutdown()
    await runner.cleanup()


def main():
    if not config.BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN не найден. Создайте файл .env на основе .env.example и укажите токен."
        )

    if config.RUN_MODE == "webhook":
        if not config.WEBHOOK_URL:
            raise SystemExit(
                "RUN_MODE=webhook, но WEBHOOK_URL не задан и RENDER_EXTERNAL_URL не найден. "
                "Укажите WEBHOOK_URL вручную (полный https-адрес сервиса без пути)."
            )
        asyncio.run(_run_webhook_server())
    else:
        application = build_application()
        logger.info("Astro Dialog Bot запущен в режиме polling (локальная разработка).")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
