from aiogram.utils.keyboard import ReplyKeyboardBuilder


def markup():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📋 Diagnostika qilish")
    kb.button(text="🎧 Eshituv idrokini rivojlantirish")
    kb.button(text="📚 Darsliklar")

    # Tugmalarni 2+1 joylashtiramiz
    kb.adjust(2, 1)

    return kb.as_markup(resize_keyboard=True, one_time_keyboard=False)
