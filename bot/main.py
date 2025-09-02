import os
import asyncio
from typing import Callable, Dict, Any, Awaitable, List

from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# ===================== ENV =====================
load_dotenv()
BOT_TOKEN = os.getenv("botToken")
REQUIRED_CHANNELS = [c.strip() for c in os.getenv("REQUIRED_CHANNELS", "").split(",") if c.strip()]

if not BOT_TOKEN:
    raise RuntimeError("botToken .env faylida topilmadi")

# ===================== UI (fallback) =====================
# Agar sizda buttons.markups bo'lsa ishlatadi, bo'lmasa fallback menyu
def fallback_markup():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Boshlash")]],
        resize_keyboard=True
    )

try:
    from buttons import markups  # sizdagi menyu (reply_markup=markups.markup())
    DEFAULT_MARKUP = markups.markup()
except Exception:
    DEFAULT_MARKUP = fallback_markup()

# ===================== Force Subscribe Helpers =====================
CHECK_CB_DATA = "fs_check"

def _channel_url(ch: str) -> str:
    # @username bo'lsa to'g'ridan-to'g'ri havola beramiz
    if ch.startswith("@"):
        return f"https://t.me/{ch[1:]}"
    # ID bo'lsa universal link yo'q, shunchaki fallback beramiz
    return ""

def build_sub_keyboard(channels: List[str]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        url = _channel_url(ch)
        if url:
            rows.append([InlineKeyboardButton(text=f"🔗 {ch}", url=url)])
        else:
            # Fallback (ID bo'lsa) — foydalanuvchi kanalni o'zi topsin
            rows.append([InlineKeyboardButton(text=f"📢 {ch}", url="https://t.me/")])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data=CHECK_CB_DATA)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def is_user_subscribed(bot: Bot, user_id: int, channels: List[str]) -> bool:
    # AND mantiq: barcha kanallarga obuna bo'lgan bo'lishi shart
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            status = getattr(member, "status", "left")
            if status in ("left", "kicked"):
                return False
        except Exception:
            # Kanalga kira olmasa/ bot admin bo'lmasa — obuna yo'q deb hisoblaymiz
            return False
    return True

# ===================== Middleware =====================
class ForceSubscribeMiddleware(BaseMiddleware):
    """
    Private chatda barcha xabarlar/callbacklardan oldin obunani tekshiradi.
    CHECK_CB_DATA ("✅ Tekshirish") callbackiga ruxsat beradi.
    """
    def __init__(self, channels: List[str], prompt_text: str | None = None):
        super().__init__()
        self.channels = [c.strip() for c in channels if c.strip()]
        self.prompt_text = prompt_text or (
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling.\n"
            "Obuna bo‘lgach, pastdagi **✅ Tekshirish** tugmasini bosing."
        )

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Kanallar sozlanmagan bo'lsa, tekshiruv o'tkazmaymiz
        if not self.channels:
            return await handler(event, data)

        bot: Bot = data["bot"]
        from_user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)

        # Faqat private chatda tekshiramiz
        if not from_user or not chat or getattr(chat, "type", "") != "private":
            return await handler(event, data)

        # "✅ Tekshirish" callbackini tekshiruvsiz o'tkazamiz, u o'zi ichida tekshiradi
        if isinstance(event, CallbackQuery) and event.data == CHECK_CB_DATA:
            return await handler(event, data)

        ok = await is_user_subscribed(bot, from_user.id, self.channels)
        if ok:
            return await handler(event, data)

        kb = build_sub_keyboard(self.channels)
        try:
            # Message bo'lsa chatga yuboramiz
            if isinstance(event, Message):
                await bot.send_message(chat_id=from_user.id, text=self.prompt_text, reply_markup=kb)
            # Callback bo'lsa ham foydalanuvchiga xabar ko'rsatamiz
            elif isinstance(event, CallbackQuery):
                await bot.send_message(chat_id=from_user.id, text=self.prompt_text, reply_markup=kb)
        except Exception:
            pass
        return  # handlerlarga o'tkazmaymiz

# ===================== Router: Re-Check Callback =====================
fs_router = Router()

@fs_router.callback_query(F.data == CHECK_CB_DATA)
async def recheck_subscription(cb: CallbackQuery):
    if not REQUIRED_CHANNELS:
        await cb.answer("Kanal sozlanmagan.", show_alert=True)
        return

    ok = await is_user_subscribed(cb.message.bot, cb.from_user.id, REQUIRED_CHANNELS)
    if ok:
        await cb.message.edit_text("✅ Obuna tasdiqlandi. Endi botdan foydalanishingiz mumkin.")
    else:
        await cb.answer("Hali obuna topilmadi. Iltimos, avval obuna bo‘ling.", show_alert=True)
        kb = build_sub_keyboard(REQUIRED_CHANNELS)
        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

# ===================== Bot & Dispatcher =====================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===================== Handlers =====================
@dp.message(CommandStart())
async def start(message: Message):
    username = message.from_user.username or message.from_user.full_name
    await message.reply(f"Salom, {username}!", reply_markup=DEFAULT_MARKUP)

# ===================== Main =====================
async def main():
    # Majburiy obuna middleware
    if REQUIRED_CHANNELS:
        fs_mw = ForceSubscribeMiddleware(REQUIRED_CHANNELS)
        dp.message.middleware(fs_mw)
        dp.callback_query.middleware(fs_mw)

    # Avval re-check router
    dp.include_router(fs_router)

    # Sizning boshqa routerlaringiz (agar mavjud bo'lsa)
    try:
        from handlers.ovoz import audio_handlers
        from handlers.diagnostika import diagnostika
        from handlers.hayvon_top import hayvontop
        dp.include_routers(hayvontop, diagnostika, audio_handlers)
    except Exception:
        # Routerlar yo'q bo'lsa ham bot ishlashda davom etadi
        pass

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
