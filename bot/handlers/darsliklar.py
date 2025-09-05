from __future__ import annotations

import math
from typing import List, Dict

from aiogram import Router, F, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.input_file import BufferedInputFile

from utils.admin_client import AdminClient
from buttons.inlines_darslik import lessons_list_markup, lesson_view_back_markup


darsliklar = Router(name="darsliklar")
client = AdminClient()

PER_PAGE = 6  # bitta sahifada nechta darslik ko'rsatamiz


class DarslikStates(StatesGroup):
    waiting_code = State()  # "Kod orqali ochish" uchun


# --------- Katalogga kirish: "📚 Darsliklar" tugmasi ---------
@darsliklar.message(F.text.in_({"📚 Darsliklar", "Darsliklar"}))
async def open_lessons(message: types.Message, state: FSMContext):
    await state.clear()
    await _send_lessons_page(message, page=1)


# --------- Inline: sahifalash ---------
@darsliklar.callback_query(F.data.startswith("lesson:page:"))
async def lessons_page_cb(cb: types.CallbackQuery):
    await cb.answer()
    _, _, page_s = cb.data.split(":")
    if page_s == "-":
        # sahifa raqami tugmasi: hech narsa qilmaymiz
        return
    try:
        page = int(page_s)
    except ValueError:
        page = 1
    await _send_lessons_page(cb.message, page=page, edit=True)


# --------- Inline: "Kod orqali ochish" ---------
@darsliklar.callback_query(F.data == "lesson:openbycode")
async def ask_code(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(DarslikStates.waiting_code)
    await cb.message.answer("✍️ Darslik kodini yuboring (masalan: <code>ENG-101</code> yoki <code>matn1</code>).", parse_mode=ParseMode.HTML)


# --------- Kod yuborildi ---------
@darsliklar.message(DarslikStates.waiting_code)
async def open_by_code(message: types.Message, state: FSMContext):
    code = (message.text or "").strip()
    if not code:
        await message.answer("Kod bo'sh bo'lmasligi kerak.")
        return
    await state.clear()
    await _send_single_lesson(message, code)


# --------- Inline: bitta darslikni ko'rish ---------
@darsliklar.callback_query(F.data.startswith("lesson:view:"))
async def view_lesson_cb(cb: types.CallbackQuery):
    await cb.answer()
    _, _, code = cb.data.split(":")
    await _send_single_lesson(cb.message, code, edit=False)


# ===================== Helpers =====================
async def _send_lessons_page(message: types.Message, page: int = 1, edit: bool = False):
    # 1) ro'yxatni olish
    try:
        lessons: List[Dict] = await client.list_lessons(enabled=True)
    except Exception as e:
        await message.answer(f"Xatolik: darsliklar olinmadi. {e}")
        return

    total = len(lessons)
    if total == 0:
        await message.answer("Hozircha darsliklar topilmadi. 🗂️")
        return

    # 2) sahifalash
    pages = max(1, math.ceil(total / PER_PAGE))
    page = max(1, min(page, pages))
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    chunk = lessons[start:end]

    # 3) inline markup
    kb = lessons_list_markup(chunk, page=page, per_page=PER_PAGE, total=total)

    # 4) chiqish
    text = (
        f"📚 <b>Darsliklar</b>\n"
        f"Jami: <b>{total}</b> ta.\n"
        f"Sahifa: <b>{page}/{pages}</b>\n\n"
        f"<i>Istalgan darslikni ochish uchun tugmasini bosing.\n"
        f"Yoki “Kod orqali ochish” tugmasidan foydalaning.</i>"
    )
    if edit:
        try:
            await message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception:
            # eski xabarni o'chira olmay qolsa, yangidan yuboramiz
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _send_single_lesson(message: types.Message, code: str, edit: bool = False):
    try:
        data = await client.export_lesson(code)
    except Exception as e:
        await message.answer(f"❌ Darslik topilmadi yoki o‘chirilgan. ({code})\n{e}")
        return

    title = data.get("title", code)
    text = (data.get("text") or "").strip()
    pdf_url = (data.get("pdf_url") or "").strip()

    # 1) matnni yuborish
    body = f"📘 <b>{title}</b>\n<code>{code}</code>\n\n{text or 'Matn berilmagan.'}"
    await message.answer(body, parse_mode=ParseMode.HTML, reply_markup=lesson_view_back_markup())

    # 2) PDF bo'lsa — hujjat sifatida yuboramiz
    if pdf_url:
        try:
            pdf_bytes, ct = await client.download_pdf(pdf_url)
            filename = f"{code}.pdf"
            doc = BufferedInputFile(pdf_bytes, filename=filename)
            await message.answer_document(document=doc, caption="📎 Darslik PDF")
        except Exception:
            # agar yuklab bo'lmasa, hech bo'lmasa linkni yuboramiz
            await message.answer(f"🔗 PDF: {pdf_url}")
