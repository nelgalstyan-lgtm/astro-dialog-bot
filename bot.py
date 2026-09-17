# -*- coding: utf-8 -*-
"""
Astro Dialog Bot — основной файл.

Запуск:  python bot.py
Требует BOT_TOKEN в .env (см. .env.example).
"""
import asyncio
import logging
import re
import signal
from datetime import datetime

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

BIRTH_DATE, BIRTH_TIME, BIRTH_CITY = range(3)

DATE_RE = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


async def is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(config.CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except (BadRequest, Forbidden) as e:
        logger.warning("Не удалось проверить подписку: %s", e)
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


def date_text() -> str:
    return styled("Дата рождения", "Укажите дату рождения — например `24.09.1997`", "📅")


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
        date_text(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return BIRTH_DATE


async def on_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = DATE_RE.match(text)
    if not match:
        await update.message.reply_text(
            styled("Не расслышал дату", "Введите в формате `ДД.ММ.ГГГГ` — например `24.09.1997`.", "🙈"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return BIRTH_DATE

    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if year < 100:
        year += 1900 if year > 25 else 2000

    try:
        birth_dt = datetime(year, month, day)
    except ValueError:
        await update.message.reply_text(
            styled("Такой даты нет", "Проверьте число и месяц и введите ещё раз.", "⚠️"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return BIRTH_DATE

    if birth_dt > datetime.now():
        await update.message.reply_text(
            styled("Ещё не наступило", "Дата рождения не может быть в будущем — введите ещё раз.", "⏳"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return BIRTH_DATE

    zodiac_key = get_zodiac_by_date(day, month)
    if zodiac_key is None:
        await update.message.reply_text(
            styled("Не определили знак", "Проверьте дату и введите ещё раз.", "⚠️"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return BIRTH_DATE

    context.user_data["birth_date"] = f"{day:02d}.{month:02d}.{year}"
    context.user_data["birth_day"] = day
    context.user_data["birth_month"] = month
    context.user_data["zodiac"] = zodiac_key
    db.upsert_user(
        update.effective_user.id,
        birth_date=context.user_data["birth_date"],
        birth_day=day,
        birth_month=month,
        zodiac=zodiac_key,
    )

    sign = ZODIAC[zodiac_key]
    await update.message.reply_text(
        f"{sign['emoji']} *ВЫ — {sign['name'].upper()}*\n"
        "✧┄┄┄┄┄┄┄┄┄┄┄┄✧\n\n"
        "Хотите сделать профиль точнее?\n\n"
        "🕐 Введите время рождения — например `14:30`\n"
        "или нажмите кнопку ниже, если не знаете.",
        reply_markup=kb.kb_skip_time(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return BIRTH_TIME


async def on_birth_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = TIME_RE.match(text)
    if not match or not (0 <= int(match.group(1)) <= 23) or not (0 <= int(match.group(2)) <= 59):
        await update.message.reply_text(
            styled(
                "Не расслышал время",
                "Введите в формате `ЧЧ:ММ` — например `14:30`, или нажмите «Не знаю время».",
                "🙈",
            ),
            reply_markup=kb.kb_skip_time(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return BIRTH_TIME

    context.user_data["birth_time"] = text
    db.upsert_user(update.effective_user.id, birth_time=text)
    await update.message.reply_text(
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
        time_match = TIME_RE.match(birth_time)
        if time_match:
            hour, minute = int(time_match.group(1)), int(time_match.group(2))

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


def build_application() -> Application:
    db.init_db()
    application = ApplicationBuilder().token(config.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_gender_chosen, pattern="^gender_(male|female)$")],
        states={
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_birth_date)],
            BIRTH_TIME: [
                CallbackQueryHandler(on_skip_time, pattern="^skip_time$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_birth_time_text),
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
    await application.bot.delete_webhook()
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
