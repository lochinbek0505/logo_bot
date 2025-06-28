from aiogram import Router, F, types

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.input_file import FSInputFile 

from utils.mohir import stt

from utils.check_audio import check_audio
from aiogram.utils.media_group import MediaGroupBuilder

from aiogram.types import FSInputFile
from aiogram.enums.parse_mode import ParseMode
from .inllines import hayvon_inline_buttons, hayvonlar_ichidan_top_inline

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMG_DIR = BASE_DIR / "bot" / "assets" / "hayvon_imgs"
AUD_DIR = BASE_DIR / "bot" / "assets" / "hayvon_audio"

hayvonlar_dict = {
"ayiq" :("ayiq.png", "ayiq.mp3", "Ayiq"),
"bori" : ("bori.png", "bori.mp3", "Bo'ri"),
"echki": ("echki.png", "echki.mp3", "Echki"), 
"eshak": ("eshak.png", "eshak.mp3", "Eshak"), 
"goz": ("goz.png", "goz.mp3", "G'oz"),
"ilon": ("ilon.png", "ilon.mp3", "Ilon"),
"kuchuk": ("kuchuk.png", "kuchuk.mp3", "Kuchuk"),
"maymun": ("maymun.png", "maymun.mp3", "Maymun"),
"mushuk": ("mushuk.png", "mushuk.mp3", "Mushuk"),
"ot": ("ot.png", "ot.mp3", "Ot"),
"sher": ("sher.png", "sher.mp3", "Sher"),
"sigir": ("sigir.png", "sigir.mp3", "Sigir"),
"tovuq": ("tovuq.png", "tovuq.mp3", "Tovuq"),
"tulki": ("tulki.png", "tulki.mp3", "Tulki"),
"xoroz": ("xoroz.png", "xoroz.mp3", "Xo'roz"),
"yolbars": ("yolbars.png", "yolbars.mp3", "Yo'lbars"),
}

hayvonlar_dict = [
    {
        "ayiq": ("ayiq.png", "ayiq.mp3", "Ayiq"),
        "bori": ("bori.png", "bori.mp3", "Bo'ri"),
        "echki": ("echki.png", "echki.mp3", "Echki"),
        "eshak": ("eshak.png", "eshak.mp3", "Eshak"),
        "goz": ("goz.png", "goz.mp3", "G'oz"),
        "ilon": ("ilon.png", "ilon.mp3", "Ilon"),
        "kuchuk": ("kuchuk.png", "kuchuk.mp3", "Kuchuk"),
        "maymun": ("maymun.png", "maymun.mp3", "Maymun"),
        "mushuk": ("mushuk.png", "mushuk.mp3", "Mushuk"),
        "ot": ("ot.png", "ot.mp3", "Ot"),
        "sher": ("sher.png", "sher.mp3", "Sher"),
        "sigir": ("sigir.png", "sigir.mp3", "Sigir"),
        "tovuq": ("tovuq.png", "tovuq.mp3", "Tovuq"),
        "tulki": ("tulki.png", "tulki.mp3", "Tulki"),
        "xoroz": ("xoroz.png", "xoroz.mp3", "Xo'roz"),
        "yolbars": ("yolbars.png", "yolbars.mp3", "Yo'lbars"),
        "ari": ("ari.png", "ari.mp3", "Ari"),
        "chigirtka": ("chigirtka.png", "chigirtka.mp3", "Chigirtka")
    },
    {
        "basketbol": ("basketbol.png", "basketbol.mp3", "Basketbol"),
        "kulish": ("kulish.png", "kulish.mp3", "Kulish"),
        "kuylash": ("kuylash.png", "kuylash.mp3", "Kuylash"),
        "opish": ("opish.png", "opish.mp3", "Opish"),
        "tish_yuvish": ("tish_yuvish.png", "tish_yuvish.mp3", "Tish Yuvish"),
        "yugurish": ("yugurish.png", "yugurish.mp3", "Yugurish"),
        "yurmoq": ("yurmoq.png", "yurmoq.mp3", "Yurish")
    },
    {
        "mashina": ("mashina.png", "mashina.mp3", "Mashina"),
        "metro": ("metro.png", "metro.mp3", "Metro"),
        "poyezd": ("poyezd.png", "poyezd.mp3", "Poyezd"),
        "vertalyot": ("vertalyot.png", "vertalyot.mp3", "Vertolyot")
    },
    {
        "chaqmoq": ("chaqmoq.png", "chaqmoq.mp3", "Chaqmoq"),
        "shamol": ("shamol.png", "shamol.mp3", "Shamol"),
        "yomgir": ("yomgir.png", "yomgir.mp3", "Yomgʻir")
    },
    {
        'aksirish': ('aksirish.png', 'aksirish.mp3', 'Aksiruv'),
        'chivin': ('chivin.png', 'chivin.mp3', 'Chivin'),
        'hurrak': ('hurrak.png', 'hurrak.mp3', 'Hurrak'),
        'kema': ('kema.png', 'kema.mp3', 'Kema'),
        'ninachi': ('ninachi.png', 'ninachi.mp3', 'Ninachish'),
        'pasha': ('pasha.png', 'pasha.mp3', 'Pashash'),
        'qarsak': ('qarsak.png', 'qarsak.mp3', 'Qarsak'),
        'sharshara': ('sharshara.png', 'sharshara.mp3', 'Sharshara'),
        'shuttak': ('shuttak.png', 'shuttak.mp3', 'Shuttak'),
        'suv_oynash': ('suv_oynash.png', 'suv_oynash.mp3', 'Suv Oʻynash'),
        'tishlash': ('tishlash.png', 'tishlash.mp3', 'Tishlash'),
        'tolqin': ('tolqin.png', 'tolqin.mp3', 'Tolqin'),
        'yiglamoq': ('yiglamoq.png', 'yiglamoq.mp3', 'Yigʻlash'),
        'yotalmoq': ('yotalmoq.png', 'yotalmoq.mp3', "Yo'talish")
    }
]

def get_third_element_by_key(key, data_list):
    for dictionary in data_list:
        if key in dictionary:
            return dictionary[key][2]
    return None



hayvontop = Router(name="hayvontop")

import random

# @hayvontop.message(F.text == "hayvontop")
# async def diagnostika_start(message: types.Message, state: FSMContext):
#     images = [i[0] for i in sozlar]
#     audios = [i[1] for i in sozlar]
#     random.shuffle(images)
#     random.shuffle(audios)
    
#     image = images[0]
#     audio = audios[0]
    
#     await message.answer_photo(FSInputFile("bot/assets/hayvon_imgs/" + image),
#                                caption= "<blockquote>shu rasmdagi hayvon audio ga to'g'ri keladimi? \n" \
#                            "3 martadan takrorlang bitta audioda</blockquote>", parse_mode=ParseMode.HTML)
    
#     await message.answer_audio(FSInputFile("bot/assets/hayvon_audio/" + audio), caption="Bu rasm audio bilan mos tushadimi? ", reply_markup=hayvon_inline_buttons(image=image, audio=audio))



# @hayvontop.callback_query(F.data.startswith("hayvontop"))
# async def tekshir(query: types.CallbackQuery):
#     data = query.data.split(":")
#     print(data[1].strip(".png"),data[2].strip(".mp3"), data[3])
#     if ((data[1].strip(".png") == data[2].strip(".mp3")) and data[3] == "1") or \
#         ((data[1].strip(".png") != data[2].strip(".mp3")) and data[3] == "0"):
#         await query.message.delete()
#         await query.message.answer(text="Sizning javobingiz to'g'ri tabriklayman 😃")
#     else:
#         await query.message.delete()
#         await query.message.answer(text="Sizning javobingiz afsuski noto'g'ri ☹️")
        


@hayvontop.message(F.text=="Eshituv idrokini rivojlanitrish")
async def hayvonartop(message: types.Message, state: FSMContext):
    await state.clear()
    global hayvonlar_dict
    
    sozlar = hayvonlar_dict
    
    
    random.shuffle(sozlar)
    sozlar = list(sozlar[0].items())
    random.shuffle(sozlar)
    
    hayvonlar = sozlar[:3]
    right_index = random.randint(0, 2)
    buttons = hayvonlar_ichidan_top_inline([i[0] for i in hayvonlar], right=hayvonlar[right_index][0])
    
    
    media = MediaGroupBuilder()
    files = [FSInputFile(IMG_DIR / image[1][0])
            for image in hayvonlar
    ]
    
    for n, i in enumerate(files):
        
        media.add(type="photo", media = i, caption= "<blockquote>shu rasmlardan audio mosini tanlang </blockquote>" if n == 1 else None, parse_mode=ParseMode.HTML)
    
    await message.answer_media_group(media.build())
    await message.answer_voice(FSInputFile(AUD_DIR / sozlar[right_index][1][1], filename=sozlar[right_index][1][1]), reply_markup=buttons)
    
    
    
@hayvontop.callback_query(F.data.startswith("hayvonlartop"))
async def natija(query: types.CallbackQuery):
    await query.answer()
    data= query.data.split(":")
    
    if data[1] == data[2]:
        await query.message.delete()
        await query.message.answer(f"Sizning javobingiz to'g'ri tabriklayman 😃 \nbu rostanham {get_third_element_by_key(data[2], hayvonlar_dict)} edi")
    else:
        await query.message.delete()
        await query.message.answer(f"Sizning javobingiz afsuski noto'g'ri ☹️ \nbu bu {get_third_element_by_key(data[2], hayvonlar_dict)} edi")