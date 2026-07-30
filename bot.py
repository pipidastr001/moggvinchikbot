import os
import json
import time
import random
import threading
from flask import Flask

import telebot
from telebot import custom_filters
from telebot.storage import StateMemoryStorage

# Импорт ваших локальных модулей (раскомментируйте при необходимости)
import database
from keyboards import *
from states import RegistrationStates
from ratings import get_queue_for_user

# ==========================================
# 1. FLASK ВЕБ-СЕРВЕР ДЛЯ RENDER (HEALTH CHECK)
# ==========================================
app = Flask(__name__)

@app.route('/')
def health_check():
    # Render отправляет GET запрос сюда. Возвращаем 200 OK.
    return "OK", 200


# ==========================================
# 2. ИНИЦИАЛИЗАЦИЯ И КОНФИГУРАЦИЯ БОТА
# ==========================================
# Получаем токен из переменных окружения (Environment Variables в Render)
TOKEN = os.getenv("BOT_TOKEN", "8969142782:AAEBPU3N3wgxO4OIYNYEfS7r36gBMXjVStg")

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

last_rating_time = {}
rating_targets = {}

MALE_RATINGS = ["Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam"]
FEMALE_RATINGS = ["Sub 3", "Sub 5", "LTB", "MTB", "HTB", "Stacy", "True Eve"]
ALL_RATINGS = MALE_RATINGS + FEMALE_RATINGS


# ==========================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def get_user_data(u):
    if not u:
        return None
    return {
        'user_id': u[0],
        'username': u[1],
        'first_name': u[2],
        'gender': u[3],
        'photos': json.loads(u[4]) if u[4] else [],
        'description': u[5] if len(u) > 5 else '',
        'ratings': json.loads(u[6]) if len(u) > 6 and u[6] else [],
        'avg_rating': u[7] if len(u) > 7 else 'Нет оценок',
        'is_active': u[8] if len(u) > 8 else 1
    }

def send_album(chat_id, photos, caption):
    if not photos:
        return False
    media = []
    for i, p in enumerate(photos):
        try:
            media.append(
                telebot.types.InputMediaPhoto(p, caption=caption, parse_mode="Markdown")
                if i == 0 else telebot.types.InputMediaPhoto(p)
            )
        except:
            try:
                media.append(
                    telebot.types.InputMediaVideo(p, caption=caption, parse_mode="Markdown")
                    if i == 0 else telebot.types.InputMediaVideo(p)
                )
            except:
                pass
    if media:
        try:
            bot.send_media_group(chat_id, media)
            return True
        except:
            pass
    return False

def build_profile_text(ud):
    txt = f"{ud['first_name']}\nСредний рейт: **{ud['avg_rating']}**"
    if ud.get('description'):
        txt += f"\n{ud['description']}"
    return txt

def finish_photos_upload(uid):
    with bot.retrieve_data(uid) as d:
        photos = d.get('photos', [])
        if not photos:
            bot.send_message(uid, "Вы не отправили фото, отправьте **хотя бы одно**", parse_mode="Markdown", reply_markup=done_keyboard())
            return
        database.db.update_photos(uid, photos)
    
    bot.set_state(uid, RegistrationStates.waiting_for_name)
    u = database.db.get_user(uid)
    ud = get_user_data(u)
    
    if not ud:
        bot.send_message(uid, "Ошибка. Попробуйте создать анкету заново", reply_markup=start_keyboard())
        bot.delete_state(uid)
        return
    
    tg_name = ud['first_name'] if ud['first_name'] else "Пользователь"
    bot.send_message(uid, f"Как вас отображать в анкете?\n\nВаше имя в Telegram: {tg_name}", reply_markup=name_keyboard())

def show_next_rating(uid):
    q = get_queue_for_user(uid)
    nxt = q.get_next_user(uid)
    if nxt:
        show_user_for_rating(uid, nxt)
    else:
        bot.send_message(uid, "Пока нет доступных анкет для рейта. Попробуйте позже", reply_markup=main_menu_keyboard())

def show_user_for_rating(rater_id, target):
    ud = get_user_data(target)
    if not ud:
        return
    rating_targets[rater_id] = ud['user_id']
    send_album(rater_id, ud['photos'], build_profile_text(ud))
    bot.send_message(rater_id, "Выберите оценку:", reply_markup=rating_keyboard(ud['gender']))


# ==========================================
# 4. ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    database.db.create_user(uid, message.from_user.username, message.from_user.first_name)
    txt = "Привет! Я **Моггвинчик** - бот для рейта внешности\n\nСоздай **анкету**, чтобы тебя могли рейтить\n\nТГК - @moggvinchiktgk"
    bot.send_message(uid, txt, reply_markup=start_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "Создать анкету")
def create_profile(message):
    uid = message.from_user.id
    bot.set_state(uid, RegistrationStates.waiting_for_gender)
    bot.send_message(uid, "Выберите ваш пол", reply_markup=gender_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_gender)
def process_gender(message):
    uid = message.from_user.id
    g = message.text
    if g not in ["М", "Ж"]:
        bot.send_message(uid, "Пожалуйста, выберите пол используя кнопки М или Ж")
        return
    gender_code = "M" if g == "М" else "Ж"
    database.db.update_gender(uid, gender_code)
    bot.set_state(uid, RegistrationStates.waiting_for_photos)
    bot.send_message(uid, "Отлично! Отправьте ваши **реальные фото** (1-3)", parse_mode="Markdown", reply_markup=done_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_photos, content_types=['photo', 'video'])
def process_photos(message):
    uid = message.from_user.id
    with bot.retrieve_data(uid) as d:
        d.setdefault('photos', [])
        if len(d['photos']) >= 3:
            bot.send_message(uid, "Нельзя отправлять более 3 фото")
            finish_photos_upload(uid)
            return
        d['photos'].append(message.photo[-1].file_id if message.content_type == 'photo' else message.video.file_id)
        if len(d['photos']) >= 3:
            finish_photos_upload(uid)
        else:
            bot.send_message(uid, f"Фото {len(d['photos'])}/3 загружено. Отправьте ещё или напишите Готово", reply_markup=done_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_photos, func=lambda m: m.text == "Готово")
def finish_photos_text(message):
    finish_photos_upload(message.from_user.id)

@bot.message_handler(state=RegistrationStates.waiting_for_name, func=lambda m: m.text == "Взять из Telegram")
def use_tg_name(message):
    uid = message.from_user.id
    database.db.update_name(uid, message.from_user.first_name)
    bot.set_state(uid, RegistrationStates.waiting_for_description)
    bot.send_message(uid, "Добавьте описание (рост, вес, интересы — что угодно) или нажмите Пропустить", reply_markup=desc_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_name)
def set_custom_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    if len(name) > 50:
        bot.send_message(uid, "Имя слишком длинное. Напишите до 50 символов")
        return
    database.db.update_name(uid, name)
    bot.set_state(uid, RegistrationStates.waiting_for_description)
    bot.send_message(uid, "Добавьте описание (рост, вес, интересы — что угодно) или нажмите Пропустить", reply_markup=desc_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_description, func=lambda m: m.text == "Пропустить")
def skip_description(message):
    uid = message.from_user.id
    database.db.update_description(uid, "")
    bot.delete_state(uid)
    bot.send_message(uid, "Отлично! Ваша анкета создана. Идём моггать!", reply_markup=main_menu_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_description, func=lambda m: m.text == "Готово")
def done_description(message):
    uid = message.from_user.id
    with bot.retrieve_data(uid) as d:
        desc = d.get('desc', '')
    database.db.update_description(uid, desc)
    bot.delete_state(uid)
    bot.send_message(uid, "Отлично! Ваша анкета создана. Идём моггать!", reply_markup=main_menu_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_description)
def set_description(message):
    uid = message.from_user.id
    desc = message.text.strip()
    if len(desc) > 200:
        bot.send_message(uid, "Описание слишком длинное. Напишите до 200 символов")
        return
    with bot.retrieve_data(uid) as d:
        d['desc'] = desc
    bot.send_message(uid, "Описание сохранено. Нажмите Готово чтобы завершить, или Пропустить чтобы не добавлять", reply_markup=desc_keyboard())

@bot.message_handler(func=lambda m: m.text == "Моя анкета")
def show_profile(message):
    uid = message.from_user.id
    ud = get_user_data(database.db.get_user(uid))
    if not ud or not ud['photos']:
        bot.send_message(uid, "У вас ещё нет анкеты. **Создайте её!**", reply_markup=start_keyboard(), parse_mode="Markdown")
        return
    send_album(uid, ud['photos'], build_profile_text(ud))
    bot.send_message(uid, "Ваша анкета", reply_markup=my_profile_keyboard())

@bot.message_handler(func=lambda m: m.text == "Назад")
def go_back(message):
    uid = message.from_user.id
    rating_targets.pop(uid, None)
    bot.send_message(uid, "Главное меню", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "Изменить анкету")
def edit_profile(message):
    create_profile(message)

@bot.message_handler(func=lambda m: m.text == "Удалить анкету")
def delete_profile(message):
    database.db.delete_user(message.from_user.id)
    bot.send_message(message.from_user.id, "Анкета удалена. Для создания новой нажмите кнопку ниже", reply_markup=start_keyboard())

@bot.message_handler(func=lambda m: m.text == "Рейтить")
def start_rating(message):
    uid = message.from_user.id
    ud = get_user_data(database.db.get_user(uid))
    if not ud or not ud['photos']:
        bot.send_message(uid, "**Сначала создайте анкету!**", reply_markup=start_keyboard(), parse_mode="Markdown")
        return
    
    if random.random() < 0.05:
        bot.send_message(uid, "Заходите в ТГК - @moggvinchiktgk", reply_markup=ad_keyboard())
        return
    
    show_next_rating(uid)

@bot.message_handler(func=lambda m: m.text == "Дальше")
def ad_next(message):
    uid = message.from_user.id
    show_next_rating(uid)

@bot.message_handler(func=lambda m: m.text in ALL_RATINGS)
def process_rating(message):
    rater_id = message.from_user.id
    rating = message.text
    
    now = time.time()
    if rater_id in last_rating_time and now - last_rating_time[rater_id] < 1:
        return
    last_rating_time[rater_id] = now
    
    target_id = rating_targets.get(rater_id)
    
    if not target_id:
        bot.send_message(rater_id, "Цель не найдена. Начните рейт заново", reply_markup=main_menu_keyboard())
        return
    
    database.db.add_rating(target_id, rating)
    rater_ud = get_user_data(database.db.get_user(rater_id))
    
    if not rater_ud:
        bot.send_message(rater_id, "Ваша анкета не найдена", reply_markup=main_menu_keyboard())
        return
    
    gender_text = "Оценила" if rater_ud['gender'] == 'Ж' else "Оценил"
    
    if rater_ud['photos']:
        rp = f"{rater_ud['first_name']}\nСредний рейт: **{rater_ud['avg_rating']}**\n\n{rater_ud['first_name']} {gender_text} вас на **{rating}**"
        if rater_ud.get('description'):
            rp = f"{rater_ud['first_name']}\nСредний рейт: **{rater_ud['avg_rating']}**\n{rater_ud['description']}\n\n{rater_ud['first_name']} {gender_text} вас на **{rating}**"
        
        with bot.retrieve_data(target_id) as td:
            td['current_notification'] = {'rater_id': rater_id, 'rating': rating, 'rater_gender': rater_ud['gender'], 'rater_first_name': rater_ud['first_name']}
        
        if not send_album(target_id, rater_ud['photos'], rp):
            try:
                bot.send_message(target_id, f"{rater_ud['first_name']} {gender_text} вас на **{rating}**", reply_markup=notification_keyboard(), parse_mode="Markdown")
            except:
                pass
        else:
            try:
                bot.send_message(target_id, "Что дальше?", reply_markup=notification_keyboard())
            except:
                pass
    
    if random.random() < 0.05:
        bot.send_message(rater_id, "Заходите в ТГК - @moggvinchiktgk", reply_markup=ad_keyboard())
        return
    
    show_next_rating(rater_id)

@bot.message_handler(func=lambda m: m.text == "Запросить общение")
def request_chat_button(message):
    uid = message.from_user.id
    with bot.retrieve_data(uid) as d:
        notif = d.get('current_notification')
    if not notif:
        bot.send_message(uid, "Ошибка")
        return
    ud = get_user_data(database.db.get_user(uid))
    if ud and ud['photos']:
        txt = f"{ud['first_name']} хочет пообщаться!"
        txt += f" - @{ud['username']}" if ud['username'] else " -"
        send_album(notif['rater_id'], ud['photos'], txt)
    bot.send_message(uid, "Запрос отправлен!")
    bot.send_message(uid, "Все рейты просмотрены", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "Пропустить всех")
def skip_all_button(message):
    uid = message.from_user.id
    bot.send_message(uid, "Все рейты пропущены", reply_markup=main_menu_keyboard())


# ==========================================
# 5. ФУНКЦИЯ ФОНОВОГО ЗАПУСКА БОТА
# ==========================================
def run_bot():
    bot.add_custom_filter(custom_filters.StateFilter(bot))
    print("Инициализация телеграм бота...")
    while True:
        try:
            bot.remove_webhook()
            print("Бот Моггвинчик запущен!")
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка в infinity_polling: {e}")
            time.sleep(5)


# Запускаем бота в отдельном фоновом потоке
threading.Thread(target=run_bot, daemon=True).start()


# ==========================================
# 6. ТОЧКА ВХОДА (ДЛЯ ЛОКАЛЬНОГО ТЕСТА)
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
