import telebot
from telebot import custom_filters
from telebot.storage import StateMemoryStorage
import json
import database
from keyboards import *
from states import RegistrationStates
from ratings import get_queue_for_user
import time
import random

TOKEN = "8969142782:AAEBPU3N3wgxO4OIYNYEfS7r36gBMXjVStg"
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)
last_rating_time = {}

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
    database.db.update_gender(uid, g)
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
    bot.send_message(uid, f"Как вас отображать в анкете?\n\nВаше имя в Telegram: {ud['first_name']}", reply_markup=name_keyboard())

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

def build_profile_text(ud):
    txt = f"{ud['first_name']}\nПол: **{ud['gender']}**\nСредний рейт: **{ud['avg_rating']}**"
    if ud.get('description'):
        txt += f"\n{ud['description']}"
    return txt

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
    bot.send_message(message.from_user.id, "Главное меню", reply_markup=main_menu_keyboard())

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
    
    # 30% шанс показать рекламу ТГК
    if random.random() < 0.3:
        bot.send_message(uid, "Заходите в ТГК - @moggvinchiktgk", reply_markup=ad_keyboard())
        with bot.retrieve_data(uid) as d:
            d['ad_mode'] = True
        return
    
    show_next_rating(uid)

def show_next_rating(uid):
    q = get_queue_for_user(uid)
    nxt = q.get_next_user(uid)
    if nxt:
        show_user_for_rating(uid, nxt)
    else:
        bot.send_message(uid, "Пока нет доступных анкет для рейта. Попробуйте позже", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "Дальше")
def ad_next(message):
    uid = message.from_user.id
    with bot.retrieve_data(uid) as d:
        if d.get('ad_mode'):
            d['ad_mode'] = False
            show_next_rating(uid)
            return
    # Если не в рекламном режиме, игнорируем

def show_user_for_rating(rater_id, target):
    ud = get_user_data(target)
    if not ud: return
    send_album(rater_id, ud['photos'], build_profile_text(ud))
    bot.send_message(rater_id, "Выберите оценку:", reply_markup=rating_keyboard(ud['gender']))
    with bot.retrieve_data(rater_id) as d:
        d['rating_target'] = ud['user_id']

MALE_RATINGS = ["Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam"]
FEMALE_RATINGS = ["Sub 3", "Sub 5", "LTB", "MTB", "HTB", "Stacy", "True Eve"]
ALL_RATINGS = MALE_RATINGS + FEMALE_RATINGS

@bot.message_handler(func=lambda m: m.text in ALL_RATINGS)
def process_rating(message):
    rater_id = message.from_user.id
    rating = message.text
    now = time.time()
    if rater_id in last_rating_time and now - last_rating_time[rater_id] < 1:
        return
    last_rating_time[rater_id] = now
    
    with bot.retrieve_data(rater_id) as d:
        target_id = d.get('rating_target')
    if not target_id:
        bot.send_message(rater_id, "**Ошибка.** Начните рейт заново", reply_markup=main_menu_keyboard(), parse_mode="Markdown")
        return
    
    database.db.add_rating(target_id, rating)
    rater_ud = get_user_data(database.db.get_user(rater_id))
    gender_text = "Оценила" if rater_ud['gender'] == 'Ж' else "Оценил"
    
    if rater_ud['photos']:
        rp = f"{rater_ud['first_name']}\nПол: **{rater_ud['gender']}**\nСредний рейт: **{rater_ud['avg_rating']}**\n\n{rater_ud['first_name']} {gender_text} вас на **{rating}**"
        with bot.retrieve_data(target_id) as td:
            td['current_notification'] = {'rater_id': rater_id, 'rating': rating, 'rater_gender': rater_ud['gender'], 'rater_first_name': rater_ud['first_name']}
        if not send_album(target_id, rater_ud['photos'], rp):
            bot.send_message(target_id, f"{rater_ud['first_name']} {gender_text} вас на **{rating}**", reply_markup=notification_keyboard(), parse_mode="Markdown")
        else:
            bot.send_message(target_id, "Что дальше?", reply_markup=notification_keyboard())
    
    # 30% шанс показать рекламу перед следующей анкетой
    if random.random() < 0.3:
        bot.send_message(rater_id, "Заходите в ТГК - @moggvinchiktgk", reply_markup=ad_keyboard())
        with bot.retrieve_data(rater_id) as d:
            d['ad_mode'] = True
        return
    
    show_next_rating(rater_id)

@bot.callback_query_handler(func=lambda c: c.data == "request_chat")
def request_chat(call):
    uid = call.from_user.id
    with bot.retrieve_data(uid) as d:
        notif = d.get('current_notification')
    if not notif:
        bot.answer_callback_query(call.id, "Ошибка"); return
    ud = get_user_data(database.db.get_user(uid))
    if ud and ud['photos']:
        txt = f"{ud['first_name']} хочет пообщаться!"
        txt += f" - @{ud['username']}" if ud['username'] else " -"
        send_album(notif['rater_id'], ud['photos'], txt)
    bot.answer_callback_query(call.id, "Запрос отправлен!")
    bot.send_message(uid, "Все рейты просмотрены", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "next_rating")
def next_rating(call):
    bot.answer_callback_query(call.id, "Дальше")
    bot.send_message(call.from_user.id, "Все рейты просмотрены", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "skip_all")
def skip_all(call):
    bot.send_message(call.from_user.id, "Все рейты пропущены", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id, "Пропущено")

if __name__ == "__main__":
    print("Бот Моггвинчик запущен!")
    bot.add_custom_filter(custom_filters.StateFilter(bot))
    bot.remove_webhook()
    bot.infinity_polling()
