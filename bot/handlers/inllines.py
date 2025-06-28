from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.media_group import MediaGroupBuilder

class HayvonTop(CallbackData, prefix="hayvontop"):
    image: str
    audio: str
    right: bool

class HayvonTopKop(CallbackData, prefix="hayvonlartop"):
    ism: str
    right: str
    
    
    
def hayvon_inline_buttons(image, audio):
    button = InlineKeyboardBuilder()
    button.button(text="✅", callback_data=HayvonTop(image=image, audio=audio, right=True))
    button.button(text="❌", callback_data=HayvonTop(image=image, audio=audio, right=False))
    return button.as_markup() 


def hayvonlar_ichidan_top_inline(hayvonlar, right):
    
    button = InlineKeyboardBuilder()
    
    for number, hayvon in enumerate(hayvonlar, 1):
        button.button(text=str(number), callback_data=HayvonTopKop(ism=hayvon, right=right))
        
    return button.as_markup()