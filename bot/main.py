from aiogram import types, Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

from buttons import markups  # sizdagi menyu (reply_markup=markups.markup())

bot = Bot(os.getenv("botToken"))
dp = Dispatcher()

# ===================== Majburiy obuna sozlamalari =====================
# ⚠️ Bot kanal(lar)da admin bo‘lishi shart (kamida "Add Members"/"See Members")
# Username'lar oldidan kodingizga @ bilan berishingiz mumkin, lekin LINKDA @ bo'lmaydi.
FALLBACK_ASSUME_JOINED = False  # Test uchun True qilishingiz mumkin, prod uchun False qoldiring.

CHANNELS = [
    {
        "title": "Asosiy kanal",
        "username": "@boqiy_qahramonlar",              # yoki "id": -100xxxxxxxxxx
        "invite":  "https://t.me/boqiy_qahramonlar",    # ✅ @ belgisiz link
    },
    # Bir nechta kanal bo‘lsa shu yerga qo‘shing
]


def _normalize_chat_ref(ch: dict) -> str | int:
    """
    chat_id uchun mos ko‘rinishni qaytaradi:
    - agar 'id' bo‘lsa: o‘sha int qaytadi
    - aks holda 'username' bo‘lsa: boshidagi '@' olib tashlanadi (username string)
    """
    if ch.get("id") is not None:
        return ch["id"]
    uname = ch.get("username", "")
    if isinstance(uname, str) and uname.startswith("@"):
        uname = uname[1:]
    return uname  # '' bo‘lsa xato deb qaraladi


async def is_user_subscribed(user_id: int) -> tuple[bool, list[str], list[str]]:
    """
    Barcha kanal(lar)ga a'zolikni tekshiradi.
    return: (ok, missing_titles, errors)
    """
    not_joined = []
    errors = []
    for ch in CHANNELS:
        chat_ref = _normalize_chat_ref(ch)
        if not chat_ref:  # bo‘sh bo‘lsa, missing
            not_joined.append(ch["title"])
            errors.append(f"{ch['title']}: chat_ref bo'sh")
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat_ref, user_id=user_id)
            status = member.status
            if status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            ):
                not_joined.append(ch["title"])
        except Exception as e:
            # Eng ko‘p sabab: bot kanalga admin emas => tekshira olmaydi
            errors.append(f"{ch['title']}: get_chat_member xatosi: {e!s}")
            if not FALLBACK_ASSUME_JOINED:
                not_joined.append(ch["title"])
            # Aks holda (fallback) a’zo deb o‘tkazib yuboramiz

    ok = (len(not_joined) == 0)
    return ok, not_joined, errors


def build_subscribe_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in CHANNELS:
        title = ch["title"]
        invite = ch.get("invite") or ch.get("username") or ""
        # Agar invite '@username' bo‘lsa, linkga aylantiramiz
        if invite.startswith("@"):
            invite = f"https://t.me/{invite[1:]}"
        kb.button(text=f"➕ {title} ga obuna bo‘lish", url=invite)
    kb.button(text="✅ Tekshirildi", callback_data="check_subs")
    kb.adjust(1)
    return kb.as_markup()


def _format_missing_text(missing: list[str]) -> str:
    return "\n".join([f"• {m}" for m in missing]) if missing else "—"


def _clean_text(s: str | None) -> str:
    return (s or "").strip()


async def safe_edit_text(msg: types.Message, text: str, **kwargs):
    """
    msg.edit_text chaqiruvini xavfsiz qiladi:
    - Agar yangi matn hozirgisi bilan bir xil bo‘lsa, edit qilmaydi (xatoni oldini oladi).
    - Agar baribir Telegram "message is not modified" desa, yangi xabar yuborishga fallback qiladi.
    """
    current = _clean_text(msg.text) if msg.text else _clean_text(msg.caption)
    newtxt = _clean_text(text)
    if current == newtxt:
        # Matn o‘zgarmagan — edit_textga hojat yo‘q
        return
    try:
        return await msg.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            # O‘rniga yangi xabar yuboramiz (reply_markup'ni qo‘ymaslik mumkin yoki qo‘yish ham mumkin)
            return await msg.answer(text, **{k: v for k, v in kwargs.items() if k != "reply_markup"})
        raise


# ===================== /start handler =====================
@dp.message(CommandStart())
async def start(message: types.Message):
    ok, missing, errors = await is_user_subscribed(message.from_user.id)
    if not ok:
        txt = (
            "👋 Salom! Botdan foydalanishdan oldin quyidagi kanal(lar)ga obuna bo‘ling:\n"
            f"{_format_missing_text(missing)}\n\n"
            "Obuna bo‘lgach, pastdagi <b>✅ Tekshirildi</b> tugmasini bosing."
        )
        # (ixtiyoriy) Diagnostika uchun xabar
        if errors:
            txt += "\n\n<i>Diagnoz (admin kerak bo‘lishi mumkin):</i>\n" + "\n".join([f"∙ {e}" for e in errors])
        await message.reply(txt, reply_markup=build_subscribe_keyboard(), parse_mode="HTML")
        return

    # A’zo bo‘lsa -> menyu
    await message.reply(
        f"salom {message.from_user.username}", reply_markup=markups.markup()
    )


# ===================== Callback: "✅ Tekshirildi" =====================
@dp.callback_query(F.data == "check_subs")
async def cb_check_subs(call: CallbackQuery):
    ok, missing, errors = await is_user_subscribed(call.from_user.id)
    if not ok:
        txt = (
            "❗️ Hali ham barcha kanal(lar)ga obuna bo‘lmadingiz:\n"
            f"{_format_missing_text(missing)}\n\n"
            "Obuna bo‘lgach, yana <b>✅ Tekshirildi</b> tugmasini bosing."
        )
        if errors:
            txt += "\n\n<i>Diagnoz (admin kerak bo‘lishi mumkin):</i>\n" + "\n".join([f"∙ {e}" for e in errors])

        # Edit qilishdan oldin xavfsiz tekshiruvchi helper
        await safe_edit_text(
            call.message,
            txt,
            reply_markup=build_subscribe_keyboard(),
            parse_mode="HTML",
        )
        await call.answer("Avval obuna bo‘ling!", show_alert=False)
        return

    # Obuna tasdiqlandi — menyu ko‘rsatamiz
    await safe_edit_text(call.message, "✅ Obuna tasdiqlandi! Asosiy menyu:", parse_mode="HTML")
    await call.message.answer("Menyuni tanlang:", reply_markup=markups.markup())
    await call.answer("Tasdiqlandi!")


# ========== (Ixtiyoriy) Global middleware: boshqa xabarlar uchun ham tekshiradi ==========
from aiogram.dispatcher.middlewares.base import BaseMiddleware

class ForceSubscribeMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # /start va callback `check_subs` ni chetlab o‘tamiz, boshqa holatda tekshiramiz
        if isinstance(event, types.Message):
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
            ok, _, _ = await is_user_subscribed(event.from_user.id)
            if not ok:
                await event.answer(
                    "⚠️ Avval kanal(lar)ga obuna bo‘ling va /start ni qayta yuboring.",
                    reply_markup=build_subscribe_keyboard()
                )
                return
        if isinstance(event, types.CallbackQuery):
            if event.data == "check_subs":
                return await handler(event, data)
            ok, _, _ = await is_user_subscribed(event.from_user.id)
            if not ok:
                await event.message.answer(
                    "⚠️ Avval kanal(lar)ga obuna bo‘ling.",
                    reply_markup=build_subscribe_keyboard()
                )
                await event.answer()
                return
        return await handler(event, data)

# Middleware'ni ulash (xohlasangiz izohlab qo‘ying)
dp.message.middleware(ForceSubscribeMiddleware())
dp.callback_query.middleware(ForceSubscribeMiddleware())


# ===================== Boshqa routerlar va polling =====================
async def main():
    from handlers.ovoz import audio_handlers
    from handlers.diagnostika import diagnostika
    from handlers.hayvon_top import hayvontop

    dp.include_routers(hayvontop, diagnostika, audio_handlers)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
