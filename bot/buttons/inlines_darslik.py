from __future__ import annotations

from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Callback formatlar:
#   lesson:view:<code>         — bitta darslikni ko'rish
#   lesson:page:<page>         — ro'yxatda sahifa
#   lesson:openbycode          — "Kod orqali ochish" modaliga o'tish (handlerga matn yuborish)


def lessons_list_markup(items: List[Dict], page: int, per_page: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for d in items:
        code = d.get("code", "")
        title = d.get("title", code)
        rows.append([InlineKeyboardButton(text=f"📘 {title}  ({code})", callback_data=f"lesson:view:{code}")])

    # pastki boshqaruvlar
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"lesson:page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page}", callback_data="lesson:page:-"))
    # nechta sahifa borligini oldindan hisoblab keladi handler
    nav.append(InlineKeyboardButton(text="➡️", callback_data=f"lesson:page:{page+1}"))
    rows.append(nav)

    rows.append([
        InlineKeyboardButton(text="🔎 Kod orqali ochish", callback_data="lesson:openbycode")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_view_back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data="lesson:page:1")]
    ])
