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
ADMIN_BASE = os.getenv("ADMIN_BASE", "http://localhost:8098")

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
# ===================== Admin API helpers (NEW for questions) =====================
async def fetch_hayvon_questions() -> list[dict]:
    # /export/hayvonq dan olamiz
    url = f"{ADMIN_BASE}/export/hayvonq"
    data = await _http_json(url)
    items = []
    for d in data:
        key = (d.get("key") or "").strip()
        title = (d.get("title") or "").strip()
        group = (d.get("group") or "").strip()
        audio_rel = (d.get("audio_url") or "").strip()
        options = d.get("options") or []
        correct = (d.get("correct_opt_key") or "").strip()
        if not (key and title and group and audio_rel and options and correct):
            continue
        items.append({
            "key": key,
            "title": title,
            "group": group,
            "audio_url": urljoin(ADMIN_BASE, audio_rel),
            "options": [
                {"opt_key": o.get("opt_key"), "image_url": urljoin(ADMIN_BASE, (o.get("image_url") or ""))}
                for o in options if (o.get("opt_key") and o.get("image_url"))
            ],
            "correct_opt_key": correct,
        })
    return items



# ===================== Round builder =====================
def group_items(items: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = {}
    for it in items:
        g.setdefault(it["group"], []).append(it)
    return g


def pick_question(qs: list[dict]) -> tuple[dict, list[dict], str]:
    """
    Bir tasodifiy savolni tanlaydi:
      returns: (question, choices[3], correct_opt_key)
    """
    q = random.choice(qs)
    opts = q["options"][:]
    random.shuffle(opts)

    # 3 dan ko'p bo'lsa — to'g'ri javob ichida bo'lishi shart
    correct = q["correct_opt_key"]
    if len(opts) > 3:
        # avval to'g'ri variantni olamiz
        right = next(o for o in opts if o["opt_key"] == correct)
        # qolganlardan 2 tasini tanlaymiz
        others = [o for o in opts if o["opt_key"] != correct]
        random.shuffle(others)
        choices = [right] + others[:2]
        random.shuffle(choices)
    else:
        choices = opts  # odatda aynan 3 ta bo'ladi

    return q, choices, correct



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

async def _build_media_group_from_options(option_list: list[dict]) -> MediaGroupBuilder:
    """
    3 ta rasm variantini media group sifatida yuboramiz.
    O'rtadagi (index 1) ga caption qo'yamiz.
    """
    mg = MediaGroupBuilder()
    for i, opt in enumerate(option_list):
        img_bytes, ct = await _download_bytes(opt["image_url"])
        ext = _infer_ext_from_ct(ct, ".jpg")
        photo = BufferedInputFile(img_bytes, filename=f"{opt['opt_key']}{ext}")
        mg.add(
            type="photo",
            media=photo,
            caption="<blockquote>Shu rasmlardan audio mosini tanlang</blockquote>" if i == 1 else None,
            parse_mode=ParseMode.HTML if i == 1 else None
        )
    return mg


@hayvontop.message(F.text.in_({"🎧 Eshituv idrokini rivojlantirish", "🎧 Eshituv idrokini rivojlantirish"}))
async def hayvonartop(message: types.Message, state: FSMContext):
    await state.clear()

    # 1) Admin'dan savollar
    try:
        questions = await fetch_hayvon_questions()
    except Exception as e:
        await message.answer(f"Ma'lumotlarni olishda xatolik: {e}")
        return

    if not questions:
        await message.answer("Materiallar yetarli emas. Admin panel orqali savollar qo‘shing.")
        return

    # 2) Bitta savol va 3 ta variant tanlaymiz
    q, choices, correct = pick_question(questions)

    # 3) 3 ta rasmni media-group qilib yuboramiz
    media = await _build_media_group_from_options(choices)
    await message.answer_media_group(media.build())

    # 4) Audio yuboramiz (savol audiosi)
    aud_bytes, act = await _download_bytes(q["audio_url"])
    aext = _infer_ext_from_ct(act, ".mp3")
    voice = BufferedInputFile(aud_bytes, filename=f"{q['key']}{aext}")

    # 5) Inline tugmalar (opt_key'lar)
    option_keys = [o["opt_key"] for o in choices]
    buttons = hayvonlar_ichidan_top_inline(option_keys, right=correct)

    await message.answer_voice(voice, caption="Bu audio qaysi rasmga mos?", reply_markup=buttons)

    # 6) Callback uchun soddalashtirilgan mapping: opt_key -> question.title
    key_title = {o["opt_key"]: q["title"] for o in q["options"]}
    await state.update_data(
        _key_title=key_title,
        _last_correct=correct
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
