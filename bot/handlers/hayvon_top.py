from __future__ import annotations

import os
import random
from typing import List, Dict, Tuple
from urllib.parse import urljoin

import aiohttp
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode
from aiogram.types.input_file import BufferedInputFile
from aiogram.utils.media_group import MediaGroupBuilder

from .inllines import hayvonlar_ichidan_top_inline  # sizdagi inline tugmalar yordamchisi

# ===================== Config =====================
# Admin API: /export/hayvon quyidagilarni qaytaradi:
# [{"key","title","group","image_url","audio_url"}, ...]
ADMIN_BASE = os.getenv("ADMIN_BASE", "http://185.217.131.39")

# Admin'ning group enumlari: animal, action, transport, nature, misc
MIN_CHOICES = 3  # bitta raundda nechta surat ko'rsatiladi

hayvontop = Router(name="hayvontop")


# ===================== Admin API helpers =====================
async def _http_json(url: str) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.get(url) as r:
            r.raise_for_status()
            return await r.json()

async def _download_bytes(url: str) -> tuple[bytes, str]:
    timeout = aiohttp.ClientTimeout(total=25)
    headers = {"User-Agent": "hayvontop-bot/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
        async with s.get(url) as r:
            r.raise_for_status()
            return await r.read(), r.headers.get("Content-Type", "")

async def fetch_hayvon_items() -> list[dict]:
    url = f"{ADMIN_BASE}/export/hayvon"
    data = await _http_json(url)
    # to'liq URL'ga aylantirib beramiz
    items = []
    for d in data:
        key = (d.get("key") or "").strip()
        title = (d.get("title") or "").strip()
        group = (d.get("group") or "").strip()
        img_rel = (d.get("image_url") or "").strip()
        aud_rel = (d.get("audio_url") or "").strip()
        if not (key and title and group and img_rel and aud_rel):
            continue
        items.append({
            "key": key,
            "title": title,
            "group": group,
            "image_url": urljoin(ADMIN_BASE, img_rel),
            "audio_url": urljoin(ADMIN_BASE, aud_rel),
        })
    return items


# ===================== Round builder =====================
def group_items(items: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = {}
    for it in items:
        g.setdefault(it["group"], []).append(it)
    return g

def pick_round(grouped: dict[str, list[dict]], k: int = MIN_CHOICES) -> tuple[list[dict], dict]:
    """
    Tasodifiy guruhdan kamida k ta element tanlaydi.
    Natija:
      choices: uzunligi k bo'lgan itemlar ro'yxati
      answer: to'g'ri item (choices ichidan)
    """
    # guruhlar ichidan kamida k ta bo'lganlarni tanlaymiz
    candidates = [g for g in grouped.values() if len(g) >= k]
    if not candidates:
        raise RuntimeError("Yetarli material yo'q (kamida 1 guruhda 3+ element bo‘lishi kerak).")
    bunch = random.choice(candidates).copy()
    random.shuffle(bunch)
    choices = bunch[:k]
    answer = random.choice(choices)
    random.shuffle(choices)
    return choices, answer


# ===================== UI helpers =====================
def _infer_ext_from_ct(ct: str | None, fallback: str) -> str:
    ct_l = (ct or "").lower()
    if "png" in ct_l:   return ".png"
    if "webp" in ct_l:  return ".webp"
    if "gif" in ct_l:   return ".gif"
    if "mp3" in ct_l:   return ".mp3"
    if "ogg" in ct_l:   return ".ogg"
    if "mpeg" in ct_l:  return ".mp3"
    return fallback

async def _build_media_group(choices: list[dict]) -> MediaGroupBuilder:
    """
    3 ta rasmni bytes qilib olib, media group qaytaradi.
    O'rtadagi (index 1) ga caption qo'yamiz.
    """
    mg = MediaGroupBuilder()
    for i, it in enumerate(choices):
        img_bytes, ct = await _download_bytes(it["image_url"])
        ext = _infer_ext_from_ct(ct, ".jpg")
        photo = BufferedInputFile(img_bytes, filename=f"{it['key']}{ext}")
        mg.add(
            type="photo",
            media=photo,
            caption="<blockquote>Shu rasmlardan audio mosini tanlang</blockquote>" if i == 1 else None,
            parse_mode=ParseMode.HTML if i == 1 else None
        )
    return mg


# ===================== Game handler =====================
@hayvontop.message(F.text.in_({"🎧 Eshituv idrokini rivojlantirish", "🎧 Eshituv idrokini rivojlantirish"}))
async def hayvonartop(message: types.Message, state: FSMContext):
    """
    1 raund: 3 ta rasm (bir guruh), 1 ta audio (o'sha guruhdan to'g'ri javob).
    Inline tugmalarda item.key'lar bo'ladi.
    """
    await state.clear()

    # 1) Admin'dan materiallar
    try:
        items = await fetch_hayvon_items()
    except Exception as e:
        await message.answer(f"Ma'lumotlarni olishda xatolik: {e}")
        return

    if len(items) < MIN_CHOICES:
        await message.answer("Materiallar yetarli emas. Admin panel orqali qo‘shing (kamida 3 ta).")
        return

    grouped = group_items(items)

    try:
        choices, answer = pick_round(grouped, k=MIN_CHOICES)
    except Exception as e:
        await message.answer(str(e))
        return

    # 2) 3 ta rasm (media group)
    media = await _build_media_group(choices)
    await message.answer_media_group(media.build())

    # 3) Audio (to'g'ri javobning audio' si)
    aud_bytes, act = await _download_bytes(answer["audio_url"])
    aext = _infer_ext_from_ct(act, ".mp3")
    voice = BufferedInputFile(aud_bytes, filename=f"{answer['key']}{aext}")

    # 4) Inline tugmalar
    option_keys = [it["key"] for it in choices]
    buttons = hayvonlar_ichidan_top_inline(option_keys, right=answer["key"])

    # 5) Voice yuborish
    await message.answer_voice(voice, caption="Bu audio qaysi rasmga mos?", reply_markup=buttons)

    # 6) Callback'da ishlatish uchun mapping/state saqlab qo'yamiz
    #    (key -> title) va javob kaliti
    key_title = {it["key"]: it["title"] for it in items}
    await state.update_data(
        _key_title=key_title,
        _last_correct=answer["key"]
    )


# ===================== Callback natija =====================
@hayvontop.callback_query(F.data.startswith("hayvonlartop"))
async def natija(query: types.CallbackQuery, state: FSMContext):
    await query.answer()

    # kutilgan format: "hayvonlartop:<selected_key>:<correct_key>"
    try:
        _, selected, correct = query.data.split(":")
    except ValueError:
        await query.message.answer("Noto‘g‘ri format.")
        return

    data = await state.get_data()
    key_title: Dict[str, str] = data.get("_key_title", {})

    sel_title = key_title.get(selected, selected)
    cor_title = key_title.get(correct, correct)

    await query.message.delete()

    if selected == correct:
        await query.message.answer(
            f"Sizning javobingiz to‘g‘ri — tabriklayman 😃\n"
            f"Bu rostan ham <b>{cor_title}</b> edi.",
            parse_mode=ParseMode.HTML
        )
    else:
        await query.message.answer(
            f"Sizning javobingiz afsuski noto‘g‘ri ☹️\n"
            f"To‘g‘ri javob: <b>{cor_title}</b>.",
            parse_mode=ParseMode.HTML
        )
