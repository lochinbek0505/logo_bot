# user_service.py
from aiogram.types import User as TgUser
import aiohttp
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger("user_service")

# Bazani moslang: http://IP yoki https://domain
API_BASE = os.getenv("ADMIN_API_BASE", "http://185.217.131.39")
# Flutter userCreate bilan bir xil endpoint: POST /users  (trailing slashsiz)
USERS_ENDPOINT = f"{API_BASE}/users"
API_KEY = os.getenv("ADMIN_API_KEY", "changeme")  # .env dan oling

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10)


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,   # nginx/fastapi uchun aynan shu nom
    }


def _build_payload_from_tg(
    u: TgUser,
    *,
    role: str = "user",
    is_blocked: bool = False,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Flutter'dagi BotUser.create JSON bilan bir xil maydonlarni tayyorlaydi.
    NULL/bo'sh qiymatlarni yubormaslikka harakat qilamiz.
    """
    payload: Dict[str, Any] = {
        "tg_id": u.id,
        "role": role,
        "is_blocked": is_blocked,
    }

    if u.username:  # bo'sh bo'lmasa
        payload["username"] = u.username

    full_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
    if full_name:
        payload["full_name"] = full_name

    if notes:
        payload["notes"] = notes

    return payload


async def create_user_from_tg(
    u: TgUser,
    *,
    role: str = "user",
    is_blocked: bool = False,
    notes: Optional[str] = None,
) -> Any:
    """
    Flutter'dagi userCreate ga mos: POST /users  (JSON)
    Muvaffaqiyatda serverdan qaytgan JSON yoki True qaytaradi.
    Xatoda False qaytaradi.
    """
    payload = _build_payload_from_tg(u, role=role, is_blocked=is_blocked, notes=notes)
    log.info("Creating user via %s: %s", USERS_ENDPOINT, payload)

    try:
        async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as sess:
            async with sess.post(USERS_ENDPOINT, json=payload, headers=_headers()) as resp:
                text = await resp.text()
                log.info("create_user_from_tg resp: %s %s", resp.status, text)

                if resp.status in (200, 201):
                    # JSON bo'lsa uni qaytaramiz, bo'lmasa True
                    try:
                        return await resp.json()
                    except Exception:
                        return True
                else:
                    # 4xx/5xx: masalan 401 (API key yo'q yoki noto'g'ri), 409 (exists), 422 (validation)
                    log.warning("create_user_from_tg failed: %s %s", resp.status, text)
                    return False
    except Exception as e:
        log.exception("create_user_from_tg error: %s", e)
        return False


# Oldingi nomni saqlamoqchi bo'lsangiz, upsert_user ni ham userCreate kabi ishlatamiz:
async def upsert_user(u: TgUser) -> Any:
    """
    Agar siz bot tomonda hozircha faqat 'create' semantikasidan foydalansangiz,
    upsert_user ham aynan shuni chaqirsin. Keyinroq serverda haqiqiy /users/upsert
    chiqsa, shu funksiya ichidan endpointni o'zgartirasiz.
    """
    return await create_user_from_tg(u)
