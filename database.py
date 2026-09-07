# -*- coding: utf-8 -*-
"""
Хранилище пользователей — полностью в оперативной памяти процесса.
При перезапуске процесса счетчики и профили обнуляются — это ожидаемое
поведение (см. README, раздел про хранение).
"""
import threading
from datetime import datetime, timezone
from typing import Optional

_lock = threading.Lock()
_users: dict[int, dict] = {}
_referrals: dict[int, set[int]] = {}


def init_db():
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_user(user_id: int, username: Optional[str] = None, **fields):
    with _lock:
        user = _users.get(user_id)
        if user is None:
            user = {
                "id": user_id,
                "username": username,
                "gender": None,
                "birth_date": None,
                "birth_day": None,
                "birth_month": None,
                "birth_time": None,
                "birth_city": None,
                "zodiac": None,
                "type_id": None,
                "referred_by": None,
                "profiles_created": 0,
                "created_at": _now(),
                "updated_at": _now(),
            }
            _users[user_id] = user
        if username is not None:
            user["username"] = username
        user.update(fields)
        user["updated_at"] = _now()


def get_user(user_id: int) -> Optional[dict]:
    with _lock:
        user = _users.get(user_id)
        return dict(user) if user else None


def increment_profiles_created(user_id: int):
    with _lock:
        if user_id in _users:
            _users[user_id]["profiles_created"] += 1


def add_referral(inviter_id: int, invited_id: int):
    if inviter_id == invited_id:
        return
    with _lock:
        invited = _referrals.setdefault(inviter_id, set())
        invited.add(invited_id)
        user = _users.get(invited_id)
        if user is not None and user.get("referred_by") is None:
            user["referred_by"] = inviter_id


def count_referrals(inviter_id: int) -> int:
    with _lock:
        return len(_referrals.get(inviter_id, ()))
