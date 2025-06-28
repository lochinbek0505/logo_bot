from aiogram import Router, F, types

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.input_file import FSInputFile

from utils.mohir import stt

from utils.check_audio import check_audio

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMG_DIR = BASE_DIR / "bot" / "assets" / "img"

from aiogram.enums.parse_mode import ParseMode

sozlar = [
    ("Savat Asal Gilos", "savat.png"),
    ("Zina Uzum Xo'roz", "zina.png"),
    ("Shaftoli Qoshiq Quyosh", "shaftoli.png"),
    ("Choynak Arg'imchoq uch", "choynak.png"),
    ("Jo'ja Zanjir Toj", "joja.png"),
    ("Likopcha Bulut Stol", "likopcha.png"),
    ("Ruchka Arra Bir", "ruchka.png"),
    ("Kitob Ukki Chelak", "kitob.png"),
    ("Gilos Sigir Yaproq", "gilos.png"),
    ("Qovun Baqlajon Tovuq", "qovun.png"),
]


class Diagnostika(StatesGroup):
    test1 = State()
    test2 = State()
    test3 = State()
    test4 = State()
    test5 = State()
    test6 = State()
    test7 = State()
    test8 = State()
    test9 = State()
    test10 = State()


diagnostika = Router(name="diagnostika")


@diagnostika.message(F.text == "Diagnostika qilish")
async def diagnostika_start(message: types.Message, state: FSMContext):
    await state.set_state(Diagnostika.test1)
    await state.update_data(test1=sozlar[0][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[0][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(Diagnostika.test1)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]

    result = check_audio(data["test1"], text)
    print(text, data["test1"], result)
    await state.update_data(test1=str(result))
    await state.set_state(Diagnostika.test2)
    await state.update_data(test2=sozlar[1][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[1][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test2)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test2"]
    result = check_audio(data["test2"], text)
    print(text, data["test2"], result)
    await state.update_data(test2=str(result))
    await state.set_state(Diagnostika.test3)
    await state.update_data(test3=sozlar[2][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[2][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test3)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test3"]
    result = check_audio(data["test3"], text)
    print(text, data["test3"], result)
    await state.update_data(test3=str(result))
    await state.set_state(Diagnostika.test4)
    await state.update_data(test4=sozlar[3][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[3][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test4)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test4"]
    result = check_audio(data["test4"], text)
    print(text, data["test4"], result)
    await state.update_data(test4=str(result))
    await state.set_state(Diagnostika.test5)
    await state.update_data(test5=sozlar[4][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[4][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test5)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = "salom salom salom salom"
    result = check_audio(data["test5"], text)
    print(text, data["test5"], result)
    await state.update_data(test5=str(result))
    await state.set_state(Diagnostika.test6)
    await state.update_data(test6=sozlar[5][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[5][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test6)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test6"]
    result = check_audio(data["test6"], text)
    print(text, data["test6"], result)
    await state.update_data(test6=str(result))
    await state.set_state(Diagnostika.test7)
    await state.update_data(test7=sozlar[6][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[6][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test7)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test7"]
    result = check_audio(data["test7"], text)
    print(text, data["test7"], result)
    await state.update_data(test6=str(result))
    await state.set_state(Diagnostika.test8)
    await state.update_data(test8=sozlar[7][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[7][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test8)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test8"]
    result = check_audio(data["test8"], text)
    print(text, data["test8"], result)
    await state.update_data(test8=str(result))
    await state.set_state(Diagnostika.test9)
    await state.update_data(test9=sozlar[8][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[8][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test9)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test9"]
    result = check_audio(data["test9"], text)
    print(text, data["test9"], result)
    await state.update_data(test9=str(result))
    await state.set_state(Diagnostika.test10)
    await state.update_data(test10=sozlar[9][0])

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[9][1]),
        caption="<blockquote>shu rasmdagi so'zlarni \n"
        "3 martadan takrorlang bitta audioda</blockquote>",
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(F.audio)
@diagnostika.message(Diagnostika.test10)
async def echo_audio(message: types.Message, state: FSMContext):

    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path

    file_bytes = await message.bot.download_file(file_path)

    data = await state.get_data()

    text = stt(file_bytes.getvalue())["result"]["text"]
    # text = data["test10"]
    result = check_audio(data["test10"], text)
    print(text, data["test10"], result)
    await state.update_data(test10=str(result))

    data = await state.get_data()
    await state.clear()
    flag = False
    text = "<blockquote>Sizda nuqson bo'lishi mumkin chunki siz"
    for key, value in data.items():
        if value != "True":
            text += f" \n{sozlar[int(key[-1])][0]}\n"
            flag = True
    text += " \n so'zlarini aytishda xatolik bilan aytdingiz</blockquote>"

    if flag:
        await message.answer(text, parse_mode=ParseMode.HTML)
    else:
        await message.answer("Tabriklaymiz sizda nuqson yo'q")
