# -*- coding: utf-8 -*-
"""Инлайн-клавиатуры для всех экранов бота."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import CHANNEL_URL


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


def kb_skip_time():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⏭ Не знаю время", callback_data="skip_time")]]
    )


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
