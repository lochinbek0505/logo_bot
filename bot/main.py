import os
import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable, List
from user_service import upsert_user

from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("bot")

# ===================== ENV =====================
load_dotenv()
BOT_TOKEN = os.getenv("botToken")
REQUIRED_CHANNELS = [c.strip() for c in os.getenv("REQUIRED_CHANNELS", "").split(",") if c.strip()]

if not BOT_TOKEN:
    log.error("botToken .env faylida topilmadi")
    raise RuntimeError("botToken .env faylida topilmadi")

# ===================== UI (fallback) =====================
def fallback_markup():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Boshlash")]],
        resize_keyboard=True
    )

try:
    from buttons import markups  # sizdagi menyu (reply_markup=markups.markup())
    DEFAULT_MARKUP = markups.markup()
    log.info("Custom markups yuklandi: buttons.markups")
except Exception:
    DEFAULT_MARKUP = fallback_markup()
    log.warning("Custom markups topilmadi, fallback markup ishlatiladi")

# ===================== Force Subscribe Helpers =====================
CHECK_CB_DATA = "fs_check"

def _channel_url(ch: str) -> str:
    ch = ch.strip()
    if ch.startswith("https://t.me/"):
        return ch
    if ch.startswith("@"):
        return f"https://t.me/{ch[1:]}"
    return ""  # -100... bo‘lsa universal link yo‘q

def build_sub_keyboard(channels: List[str]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        url = _channel_url(ch)
        if url:
            rows.append([InlineKeyboardButton(text=f"🔗 {ch}", url=url)])
        else:
            rows.append([InlineKeyboardButton(text=f"📢 {ch}", url="https://t.me/")])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data=CHECK_CB_DATA)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def is_user_subscribed(bot: Bot, user_id: int, channels: List[str]) -> bool:
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            status = getattr(member, "status", "left")
            log.info("Sub-check: user=%s channel=%s status=%s", user_id, ch, status)
            if status in ("left", "kicked"):
                return False
        except Exception as e:
            log.warning("Sub-check exception: user=%s channel=%s err=%s", user_id, ch, e)
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
            "Obuna bo‘lgach, pastdagi <b>✅ Tekshirish</b> tugmasini bosing."
        )
        log.info("ForceSubscribeMiddleware init: channels=%s", self.channels)

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Agar kanal sozlanmagan bo‘lsa yoki private chat bo‘lmasa — o‘tkazib yuboramiz
        if not self.channels:
            return await handler(event, data)

        bot: Bot = data["bot"]
        from_user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)

        if not from_user or not chat or getattr(chat, "type", "") != "private":
            return await handler(event, data)

        # "✅ Tekshirish" callbackiga ruxsat
        if isinstance(event, CallbackQuery) and event.data == CHECK_CB_DATA:
            log.info("Skip FS check for re-check callback: user=%s", from_user.id)
            return await handler(event, data)

        ok = await is_user_subscribed(bot, from_user.id, self.channels)
        log.info("FS check result: user=%s ok=%s", from_user.id, ok)
        if ok:
            return await handler(event, data)

        kb = build_sub_keyboard(self.channels)
        try:
            # foydalanuvchiga prompt yuboramiz
            if isinstance(event, Message):
                await bot.send_message(
                    chat_id=from_user.id,
                    text=self.prompt_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await bot.send_message(
                    chat_id=from_user.id,
                    text=self.prompt_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
        except Exception as e:
            log.error("FS prompt send error: user=%s err=%s", from_user.id, e)
        return

# ===================== Router: Re-Check Callback =====================
fs_router = Router()

async def send_welcome(bot: Bot, user_id: int, user_obj=None):
    """
    Obuna tasdiqlangach darhol asosiy menyuni yuboradi.
    upsert_user() chaqiradi va salomlashadi.
    """
    try:
        if user_obj is not None:
            await upsert_user(user_obj)
        else:
            # Agar user_obj bo‘lmasa ham, getChat orqali kamida username olishga urinamiz
            pass
    except Exception as e:
        log.warning("upsert_user fail user_id=%s err=%s", user_id, e)

    # Username yoki full_name
    username = None
    try:
        if user_obj and getattr(user_obj, "username", None):
            username = user_obj.username
        elif user_obj and getattr(user_obj, "full_name", None):
            username = user_obj.full_name
    except Exception:
        pass
    if not username:
        username = "foydalanuvchi"

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"✅ Obuna tasdiqlandi.\nSalom, {username}! Asosiy menyudan foydalanishingiz mumkin.",
            reply_markup=DEFAULT_MARKUP
        )
    except Exception as e:
        log.error("send_welcome error user_id=%s err=%s", user_id, e)

@fs_router.callback_query(F.data == CHECK_CB_DATA)
async def recheck_subscription(cb: CallbackQuery):
    user_id = cb.from_user.id
    if not REQUIRED_CHANNELS:
        await cb.answer("Kanal sozlanmagan.", show_alert=True)
        log.warning("Re-check: channels not configured, user=%s", user_id)
        return

    ok = await is_user_subscribed(cb.message.bot, user_id, REQUIRED_CHANNELS)
    log.info("Re-check pressed: user=%s ok=%s", user_id, ok)

    if ok:
        # Inline klaviaturani olib tashlab, matnni yangilab qo‘yamiz (agar tahrir qilish imkoni bo‘lsa)
        try:
            await cb.message.edit_text("✅ Obuna tasdiqlandi. Asosiy menyu yuborildi.")
        except Exception as e:
            log.debug("edit_text skipped user=%s err=%s", user_id, e)
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await cb.answer()  # Loading spinner yopilsin

        # 🔹 Eng muhim qism: darhol asosiy menyuni yuboramiz ( /start bosmasdan )
        await send_welcome(cb.message.bot, user_id, user_obj=cb.from_user)
        return
    else:
        await cb.answer("Hali obuna topilmadi. Iltimos, avval obuna bo‘ling.", show_alert=True)
        kb = build_sub_keyboard(REQUIRED_CHANNELS)
        try:
            # Faqat klaviaturani yangilaymiz, matnni saqlab qolamiz
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception as e:
            log.warning("Edit reply markup failed: user=%s err=%s", user_id, e)

# ===================== Bot & Dispatcher =====================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===================== Handlers =====================

@dp.message(CommandStart())
async def start(message: Message):
    await upsert_user(message.from_user)  # 🔹 user’ni ro‘yxatga olish
    username = message.from_user.username or message.from_user.full_name or "foydalanuvchi"
    await message.reply(f"Salom, {username}!", reply_markup=DEFAULT_MARKUP)

# ixtiyoriy: foydalanuvchi "Boshlash" deb yozsa ham start menyusini yuborish
@dp.message(F.text.in_({"Boshlash", "boshlash", "Start", "start"}))
async def start_alias(message: Message):
    await start(message)

# ===================== Main =====================
async def main():
    # Bot ma'lumotini loglaymiz
    me = await bot.get_me()
    log.info("Bot starting: @%s (id=%s)", me.username, me.id)

    # Majburiy obuna middleware
    if REQUIRED_CHANNELS:
        log.info("REQUIRED_CHANNELS: %s", REQUIRED_CHANNELS)
        fs_mw = ForceSubscribeMiddleware(REQUIRED_CHANNELS)
        dp.message.middleware(fs_mw)
        dp.callback_query.middleware(fs_mw)
    else:
        log.info("REQUIRED_CHANNELS bo‘sh. Force-subscribe o‘chirilgan.")

    # Avval re-check router
    dp.include_router(fs_router)

    # === Routers: ovoz, diagnostika, hayvontop, darsliklar ===
    try:
        from handlers.ovoz import audio_handlers
        from handlers.diagnostika import diagnostika
        from handlers.hayvon_top import hayvontop
        from handlers.darsliklar import darsliklar   # <<— Qo‘shildi

        dp.include_router(hayvontop)
        dp.include_router(diagnostika)
        dp.include_router(darsliklar)                # <<— Qo‘shildi
        dp.include_router(audio_handlers)

        log.info("Routers ulandi: hayvontop, diagnostika, darsliklar, audio_handlers")
    except Exception as e:
        log.warning("Qo‘shimcha routerlar ulanmagan yoki xato: %s", e)

    try:
        log.info("Start polling…")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        log.exception("Pollingda xato: %s", e)
    finally:
        log.info("Bot to‘xtadi.")

if __name__ == "__main__":
    asyncio.run(main())
