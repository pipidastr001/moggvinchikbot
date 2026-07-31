import os
import json
import time
import random
import threading
from datetime import datetime
from flask import Flask

import telebot
from telebot import custom_filters
from telebot.storage import StateMemoryStorage

import database
from keyboards import *
from states import RegistrationStates
from ratings import get_queue_for_user, reset_queue_for_user

# ==========================================
# FLASK
# ==========================================
app = Flask(__name__)

@app.route('/')
def health_check():
    return "OK", 200

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
TOKEN = os.getenv("BOT_TOKEN", "8969142782:AAEBPU3N3wgxO4OIYNYEfS7r36gBMXjVStg")
OWNER_ID = 8055769849
MODERATORS = [8055769849, 942032958]

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)
last_rating_time = {}
rating_targets = {}
pending_reports = {}
user_rated_list = {}  # {user_id: {target_id: timestamp}}
RATING_COOLDOWN = 600  # 10 минут

MALE_RATINGS = ["Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam"]
FEMALE_RATINGS = ["Sub 3", "Sub 5", "LTB", "MTB", "HTB", "Stacy", "True Eve"]
ALL_RATINGS = MALE_RATINGS + FEMALE_RATINGS

def get_user_data(u):
    if not u: return None
    return {
        'user_id': u[0], 'username': u[1], 'first_name': u[2], 'gender': u[3],
        'photos': json.loads(u[4]) if u[4] else [],
        'description': u[5] if len(u) > 5 else '',
        'ratings': json.loads(u[6]) if len(u) > 6 and u[6] else [],
        'avg_rating': u[7] if len(u) > 7 else 'Нет оценок',
        'is_active': u[8] if len(u) > 8 else 1
    }

def send_album(chat_id, photos, caption):
    if not photos: return False
    media = []
    for i, p in enumerate(photos):
        try:
            media.append(telebot.types.InputMediaPhoto(p, caption=caption, parse_mode="Markdown") if i == 0 else telebot.types.InputMediaPhoto(p))
        except:
            try:
                media.append(telebot.types.InputMediaVideo(p, caption=caption, parse_mode="Markdown") if i == 0 else telebot.types.InputMediaVideo(p))
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

def get_ban_time_left(user_id):
    ban = database.db.get_ban(user_id)
    if not ban:
        return None
    banned_until = datetime.strptime(ban[1], "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    if now >= banned_until:
        database.db.unban_user(user_id)
        return None
    diff = banned_until - now
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    if days > 0:
        return f"{days} дн. {hours} ч."
    elif hours > 0:
        return f"{hours} ч. {minutes} мин."
    else:
        return f"{minutes} мин."

def can_rate_user(rater_id, target_id):
    """Проверяет можно ли рейтить цель (раз в 10 минут)"""
    now = time.time()
    if rater_id not in user_rated_list:
        user_rated_list[rater_id] = {}
    if target_id in user_rated_list[rater_id]:
        if now - user_rated_list[rater_id][target_id] < RATING_COOLDOWN:
            return False
    user_rated_list[rater_id][target_id] = now
    return True

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
        target_id = nxt[0]
        if can_rate_user(uid, target_id):
            show_user_for_rating(uid, nxt)
        else:
            show_next_rating(uid)
    else:
        bot.send_message(uid, "Все анкеты закончились, попробуйте позже", reply_markup=main_menu_keyboard())

def show_user_for_rating(rater_id, target):
    ud = get_user_data(target)
    if not ud: return
    rating_targets[rater_id] = ud['user_id']
    send_album(rater_id, ud['photos'], build_profile_text(ud))
    
    # Выбираем клавиатуру в зависимости от роли
    if rater_id in MODERATORS:
        bot.send_message(rater_id, "Выберите оценку:", reply_markup=moderator_rating_keyboard(ud['gender']))
    else:
        bot.send_message(rater_id, "Выберите оценку:", reply_markup=rating_keyboard(ud['gender']))

def notify_moderators(reporter_ud, target_ud):
    for mod_id in MODERATORS:
        try:
            bot.send_message(mod_id, f"⚠️ {reporter_ud['first_name']} пожаловался на {target_ud['first_name']}")
            send_album(mod_id, target_ud['photos'], build_profile_text(target_ud))
            pending_reports[mod_id] = {
                'target_id': target_ud['user_id'],
                'target_name': target_ud['first_name']
            }
            bot.send_message(mod_id, "Выберите действие:", reply_markup=ban_keyboard())
        except:
            pass

# ==========================================
# ОБРАБОТЧИКИ
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
    
    ban_time = get_ban_time_left(uid)
    if ban_time:
        bot.send_message(uid, f"Вы сможете создать анкету только через {ban_time}")
        return
    
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
    
    # Сбрасываем очередь чтобы получить свежие анкеты
    reset_queue_for_user(uid)
    
    if random.random() < 0.05:
        bot.send_message(uid, "Заходите в ТГК - @moggvinchiktgk", reply_markup=ad_keyboard())
        return
    
    show_next_rating(uid)

@bot.message_handler(func=lambda m: m.text == "Дальше")
def ad_next(message):
    uid = message.from_user.id
    show_next_rating(uid)

@bot.message_handler(func=lambda m: m.text == "Пожаловаться")
def report_user(message):
    uid = message.from_user.id
    target_id = rating_targets.get(uid)
    
    if not target_id:
        bot.send_message(uid, "Ошибка. Начните рейт заново", reply_markup=main_menu_keyboard())
        return
    
    reporter_ud = get_user_data(database.db.get_user(uid))
    target_ud = get_user_data(database.db.get_user(target_id))
    
    if not reporter_ud or not target_ud:
        bot.send_message(uid, "Ошибка")
        return
    
    notify_moderators(reporter_ud, target_ud)
    bot.send_message(uid, "Жалоба отправлена модератору")
    show_next_rating(uid)

@bot.message_handler(func=lambda m: m.text == "Бан")
def ban_user_handler(message):
    uid = message.from_user.id
    
    # Проверяем: модер жмёт Бан в рейте или через жалобу
    target_id = None
    
    # Сначала проверяем pending_reports
    report = pending_reports.get(uid)
    if report:
        target_id = report['target_id']
    
    # Если нет репорта, может модер банит из рейта
    if not target_id:
        target_id = rating_targets.get(uid)
    
    if not target_id:
        bot.send_message(uid, "Нет цели для бана")
        return
    
    if uid not in MODERATORS:
        bot.send_message(uid, "У вас нет прав для этого действия")
        return
    
    if target_id == OWNER_ID:
        bot.send_message(uid, "Ошибка: нельзя забанить владельца")
        return
    
    if target_id in MODERATORS and uid != OWNER_ID:
        bot.send_message(uid, "Ошибка: нельзя забанить модератора")
        return
    
    database.db.ban_user(target_id, 3, uid)
    pending_reports.pop(uid, None)
    rating_targets.pop(uid, None)
    
    try:
        bot.send_message(target_id, "Ваша анкета была удалена модератором")
    except:
        pass
    
    bot.send_message(uid, "Пользователь забанен на 3 дня", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "Пропустить")
def skip_report(message):
    uid = message.from_user.id
    if uid in MODERATORS:
        pending_reports.pop(uid, None)
        bot.send_message(uid, "Жалоба пропущена", reply_markup=main_menu_keyboard())

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
# ЗАПУСК
# ==========================================
def run_bot():
    bot.add_custom_filter(custom_filters.StateFilter(bot))
    print("Инициализация бота...")
    while True:
        try:
            bot.remove_webhook()
            print("Бот Моггвинчик запущен!")
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
