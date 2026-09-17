# -*- coding: utf-8 -*-
"""Инлайн-клавиатуры для всех экранов бота."""
import calendar
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import CHANNEL_URL

MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

YEARS_PER_PAGE = 12
MIN_YEAR = 1920


def kb_start():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✨ Получить профиль", callback_data="start_flow")]]
    )


def kb_subscribe():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📣 Подписаться на канал", url=CHANNEL_URL)],
            [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")],
        ]
    )


def kb_gender():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👩 Женщина", callback_data="gender_female"),
                InlineKeyboardButton("👨 Мужчина", callback_data="gender_male"),
            ]
        ]
    )


def kb_year_picker(page: int = 0):
    """Клавиатура выбора года рождения — по YEARS_PER_PAGE лет на страницу,
    начиная с самых свежих (текущий год) и уходя вглубь по кнопке "Старше"."""
    today = date.today()
    start = today.year - page * YEARS_PER_PAGE
    years = [y for y in range(start, start - YEARS_PER_PAGE, -1) if y >= MIN_YEAR]

    rows = []
    row = []
    for y in years:
        row.append(InlineKeyboardButton(str(y), callback_data=f"yr:{y}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Новее", callback_data=f"yrpage:{page - 1}"))
    if years and years[-1] > MIN_YEAR:
        nav.append(InlineKeyboardButton("Старше ▶️", callback_data=f"yrpage:{page + 1}"))
    if nav:
        rows.append(nav)

    return InlineKeyboardMarkup(rows)


def kb_month_picker(year: int):
    """Клавиатура выбора месяца; месяцы позже текущего (если год = текущий) неактивны."""
    today = date.today()
    rows = []
    row = []
    for i, name in enumerate(MONTHS_RU, start=1):
        if year == today.year and i > today.month:
            row.append(InlineKeyboardButton(f"· {name[:3]} ·", callback_data="noop"))
        else:
            row.append(InlineKeyboardButton(name[:3], callback_data=f"mo:{i}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Назад к году", callback_data="back_yr")])
    return InlineKeyboardMarkup(rows)


def kb_day_picker(year: int, month: int):
    """Настоящий календарь на месяц: дни выровнены по дням недели, дни в будущем
    (если месяц текущий) кликабельны, но сообщают, что дата ещё не наступила."""
    today = date.today()
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)

    rows = [[InlineKeyboardButton(w, callback_data="noop") for w in WEEKDAYS_RU]]
    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            elif year == today.year and month == today.month and day > today.day:
                row.append(InlineKeyboardButton(str(day), callback_data="future"))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=f"dy:{day}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Назад к месяцу", callback_data="back_mo")])
    return InlineKeyboardMarkup(rows)


def kb_hour_picker():
    rows = []
    row = []
    for h in range(24):
        row.append(InlineKeyboardButton(f"{h:02d}", callback_data=f"hr:{h}"))
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⏭ Не знаю время", callback_data="skip_time")])
    return InlineKeyboardMarkup(rows)


def kb_minute_picker(hour: int):
    rows = []
    row = []
    for m in range(0, 60, 5):
        row.append(InlineKeyboardButton(f"{hour:02d}:{m:02d}", callback_data=f"mi:{m}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Назад к часу", callback_data="back_hr")])
    return InlineKeyboardMarkup(rows)


def kb_skip_city():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_city")]]
    )


def kb_profile_menu(zodiac_key: str | None = None):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📤 Поделиться ботом", callback_data="share")],
            [InlineKeyboardButton("🔄 Новый профиль", callback_data="restart")],
        ]
    )
