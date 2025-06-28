from aiogram import types, Bot, Dispatcher, F
from aiogram.filters import CommandStart
from dotenv import load_dotenv
import asyncio

import os

load_dotenv()

from buttons import markups

bot = Bot(os.getenv("botToken"))

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):

    await message.reply(
        f"salom {message.from_user.username}", reply_markup=markups.markup()
    )


from utils.mohir import stt


async def main():
    from handlers.ovoz import audio_handlers
    from handlers.diagnostika import diagnostika
    from handlers.hayvon_top import hayvontop

    dp.include_routers(hayvontop, diagnostika, audio_handlers)
    await dp.start_polling(bot)


asyncio.run(main())
