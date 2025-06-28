from aiogram.utils.keyboard import ReplyKeyboardBuilder



def markup():
    button = ReplyKeyboardBuilder()
    button.button(text="Diagnostika qilish")
    button.button(text="Eshituv idrokini rivojlanitrish")
    return button.as_markup()


