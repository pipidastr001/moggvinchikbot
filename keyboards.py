from telebot import types

def start_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("Создать анкету"))
    return k

def gender_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("М"), types.KeyboardButton("Ж"))
    return k

def main_menu_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("Рейтить"), types.KeyboardButton("Моя анкета"))
    return k

def my_profile_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("Назад"))
    k.add(types.KeyboardButton("Изменить анкету"), types.KeyboardButton("Удалить анкету"))
    return k

def rating_keyboard(gender):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if str(gender) == "M":
        for r in ["Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam"]:
            k.add(types.KeyboardButton(r))
    else:
        for r in ["Sub 3", "Sub 5", "LTB", "MTB", "HTB", "Stacy", "True Eve"]:
            k.add(types.KeyboardButton(r))
    k.add(types.KeyboardButton("Назад"))
    return k

def name_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("Взять из Telegram"))
    return k

def done_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("Готово"))
    return k

def desc_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("Готово"), types.KeyboardButton("Пропустить"))
    return k

def ad_keyboard():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.add(types.KeyboardButton("Дальше"), types.KeyboardButton("Назад"))
    return k

def notification_keyboard():
    k = types.InlineKeyboardMarkup()
    k.add(types.InlineKeyboardButton("Запросить общение", callback_data="request_chat"))
    k.add(types.InlineKeyboardButton("Дальше", callback_data="next_rating"))
    k.add(types.InlineKeyboardButton("Пропустить всех", callback_data="skip_all"))
    return k
