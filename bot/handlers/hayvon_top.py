from __future__ import annotations

import os
from typing import List, Dict, Tuple, Optional
from urllib.parse import urljoin

import aiohttp
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode
from aiogram.types.input_file import BufferedInputFile
from aiogram.utils.media_group import MediaGroupBuilder

from .inllines import hayvonlar_ichidan_top_inline  # sizdagi inline tugmalar yordamchisi

# ===================== Config =====================
# Admin API: /export/hayvonq quyidagilarni qaytaradi:
# [
#   {
#     "key": "q1",
#     "title": "Itning ovozi qaysi?",
#     "group": "animal",
#     "audio_url": "/media/audios/dog.mp3",
#     "options": [
#       {"opt_key": "dog", "image_url": "/media/images/dog.jpg"},
#       {"opt_key": "cat", "image_url": "/media/images/cat.jpg"},
#       {"opt_key": "cow", "image_url": "/media/images/cow.jpg"}
#     ],
#     "correct_opt_key": "dog"
#   }, ...
# ]
ADMIN_BASE = os.getenv("ADMIN_BASE", "http://185.217.131.39")
# Admin'ning group enumlari: animal, action, transport, nature, misc
MIN_CHOICES = 3  # bitta raundda nechta surat ko'rsatiladi (biz 3 tadan ishlatyapmiz)

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
    """
    Savollarni admin’ning /export/hayvonq endpointidan oladi va
    URL’larni to‘liq URL’ga aylantirib, invalid yozuvlarni filtrlaydi.
    """
    url = f"{ADMIN_BASE}/export/hayvonq"
    data = await _http_json(url)
    items: list[dict] = []

    for d in data:
        key = (d.get("key") or "").strip()
        title = (d.get("title") or "").strip()
        group = (d.get("group") or "").strip()
        audio_rel = (d.get("audio_url") or "").strip()
        options = d.get("options") or []
        correct = (d.get("correct_opt_key") or "").strip()

        if not (key and title and group and audio_rel and options and correct):
            continue

        normalized_opts = []
        for o in options:
            opt_key = (o.get("opt_key") or "").strip()
            img_rel = (o.get("image_url") or "").strip()
            if opt_key and img_rel:
                normalized_opts.append({
                    "opt_key": opt_key,
                    "image_url": urljoin(ADMIN_BASE, img_rel),
                })

        if not normalized_opts:
            continue

        items.append({
            "key": key,
            "title": title,
            "group": group,
            "audio_url": urljoin(ADMIN_BASE, audio_rel),
            "options": normalized_opts,
            "correct_opt_key": correct,
        })

    return items


# ===================== UI helpers =====================
def _infer_ext_from_ct(ct: Optional[str], fallback: str) -> str:
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
    3 ta rasm variantini media group sifatida yuboradi.
    O'rtadagi (index 1) ga caption qo'yiladi.
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


# ===================== Round helpers =====================
def _pick_choices(q: dict) -> list[dict]:
    """
    Berilgan savol uchun 3 ta variant qaytaradi.
    To‘g‘ri javob albatta ichida bo‘ladi.
    """
    opts = q["options"]
    correct = q["correct_opt_key"]
    if len(opts) <= MIN_CHOICES:
        return opts

    # to‘g‘ri javobni oldik, qolganlardan dastlabki ikkitasi bilan 3 tlik qilamiz (tartibli, randomsiz)
    right = next(o for o in opts if o["opt_key"] == correct)
    others = [o for o in opts if o["opt_key"] != correct]
    return [right] + others[:2]


async def _send_round(message_or_query_msg: types.Message, state: FSMContext) -> None:
    """
    Joriy `_idx` bo‘yicha bitta raundni yuboradi.
    Savollar tugasa, yakuniy xabarni chiqarib, state’ni tozalaydi.
    """
    data = await state.get_data()
    questions: list[dict] = data.get("_questions", [])
    idx: int = data.get("_idx", 0)

    if idx >= len(questions):
        await message_or_query_msg.answer("Savollar tugadi! 👏")
        await state.clear()
        return

    q = questions[idx]
    choices = _pick_choices(q)
    correct = q["correct_opt_key"]

    # 1) 3 ta rasmni media-group qilib yuborish
    media = await _build_media_group_from_options(choices)
    await message_or_query_msg.answer_media_group(media.build())

    # 2) Audio yuborish
    aud_bytes, act = await _download_bytes(q["audio_url"])
    aext = _infer_ext_from_ct(act, ".mp3")
    voice = BufferedInputFile(aud_bytes, filename=f"{q['key']}{aext}")

    # 3) Inline tugmalar
    option_keys = [o["opt_key"] for o in choices]
    buttons = hayvonlar_ichidan_top_inline(option_keys, right=correct)

    await message_or_query_msg.answer_voice(
        voice,
        caption=f"({idx+1}/{len(questions)}) Bu audio qaysi rasmga mos?",
        reply_markup=buttons
    )

    # 4) Callback uchun mapping va state yangilash
    key_title = {o["opt_key"]: q["title"] for o in q["options"]}
    await state.update_data(
        _key_title=key_title,
        _last_correct=correct,
        _idx=idx  # shu raund indeksi
    )


# ===================== Start handler =====================
@hayvontop.message(F.text == "🎧 Eshituv idrokini tekshirish va rivojlantirish")
async def hayvonartop(message: types.Message, state: FSMContext):
    """
    O‘yin starti: savollarni olib keladi, FSM’ga joylaydi va birinchi raundni yuboradi.
    """
    await state.clear()

    try:
        questions = await fetch_hayvon_questions()
    except Exception as e:
        await message.answer(f"Ma'lumotlarni olishda xatolik: {e}")
        return

    # Eng kamida 1 ta savol va unda kamida 1 ta rasm bo‘lsin
    questions = [q for q in questions if q.get("options")]
    if not questions:
        await message.answer("Materiallar yetarli emas. Admin panel orqali savollar qo‘shing.")
        return

    # (ixtiyoriy) — guruhlash yoki tartiblashni xohlasangiz shu yerda qiling
    # example: questions.sort(key=lambda x: x["group"])

    await state.update_data(_questions=questions, _idx=0)
    await _send_round(message, state)


# ===================== Callback natija =====================
@hayvontop.callback_query(F.data.startswith("hayvonlartop"))
async def natija(query: types.CallbackQuery, state: FSMContext):
    """
    Callback: "hayvonlartop:<selected_key>:<correct_key>"
    Natijani ko‘rsatadi va navbatdagi savolga o‘tadi (yoki yakunlaydi).
    """
    await query.answer()

    # kutilgan format: "hayvonlartop:<selected_key>:<correct_key>"
    try:
        _, selected, correct = query.data.split(":")
    except ValueError:
        await query.message.answer("Noto‘g‘ri format.")
        return

    data = await state.get_data()
    key_title: Dict[str, str] = data.get("_key_title", {})
    idx: int = data.get("_idx", 0)
    questions: list[dict] = data.get("_questions", [])

    sel_title = key_title.get(selected, selected)
    cor_title = key_title.get(correct, correct)

    # Joriy raund natijasi
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

    # Navbatdagi savolga o‘tish
    next_idx = idx + 1
    await state.update_data(_idx=next_idx)

    # (ixtiyoriy) Eski xabarlarni o‘chirmoqchi bo‘lsangiz:
    # try:
    #     await query.message.delete()
    # except Exception:
    #     pass

    if next_idx < len(questions):
        await _send_round(query.message, state)
    else:
        await query.message.answer("👏 Tabriklayman! Barcha savollar yakunlandi.")
        await state.clear()
