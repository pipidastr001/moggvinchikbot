from telebot import types

# Чётко: только мужские оценки
MALE_RATINGS = ["Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam"]

# Чётко: только женские оценки
FEMALE_RATINGS = ["Sub 3", "Sub 5", "LTB", "MTB", "HTB", "Stacy", "True Eve"]

def start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Создать анкету"))
    return keyboard

def gender_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("М"), types.KeyboardButton("Ж"))
    return keyboard

def photos_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Готово"))
    return keyboard

def name_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Взять из Telegram"))
    return keyboard

def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Рейтить"), types.KeyboardButton("Моя анкета"))
    return keyboard

def my_profile_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Назад"))
    keyboard.add(types.KeyboardButton("Изменить анкету"), types.KeyboardButton("Удалить анкету"))
    return keyboard

def rating_keyboard(gender):
    """Возвращает клавиатуру ТОЛЬКО с оценками для указанного пола"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Жёсткая проверка пола
    if gender == "M" or gender == "М":
        ratings = MALE_RATINGS
    elif gender == "Ж":
        ratings = FEMALE_RATINGS
    else:
        # На всякий случай — мужские по умолчанию
        ratings = MALE_RATINGS
    
    for rating in ratings:
        keyboard.add(types.KeyboardButton(rating))
    
    keyboard.add(types.KeyboardButton("Назад"))
    return keyboard

def notification_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Запросить общение", callback_data="request_chat")
    )
    keyboard.add(
        types.InlineKeyboardButton("Дальше", callback_data="next_rating")
    )
    keyboard.add(
        types.InlineKeyboardButton("Пропустить всех", callback_data="skip_all")
    )
    return keyboard
