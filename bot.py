import telebot
from telebot import custom_filters
from telebot.storage import StateMemoryStorage
from collections import deque
import json
import database
from keyboards import *
from states import RegistrationStates
from ratings import get_queue_for_user
from flask import Flask, request
import threading
import time
import os

TOKEN = "8969142782:AAEBPU3N3wgxO4OIYNYEfS7r36gBMXjVStg"

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage, threaded=False)

rating_notifications = {}
rating_targets = {}

def get_user_data(user):
    if not user:
        return None
    return {
        'user_id': user[0],
        'username': user[1],
        'first_name': user[2],
        'gender': user[3],
        'photos': json.loads(user[4]) if user[4] else [],
        'ratings': json.loads(user[5]) if user[5] else [],
        'avg_rating': user[6],
        'is_active': user[7],
        'display_name': user[8] if len(user) > 8 else None
    }

def get_display_name(user_data):
    if user_data.get('display_name'):
        return user_data['display_name']
    return user_data['first_name']

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    database.db.create_user(user_id, username, first_name)
    bot.send_message(user_id, "Привет! Я Моггвинчик - бот для рейта внешности\n\nСоздай анкету, чтобы тебя могли рейтить", reply_markup=start_keyboard())

@bot.message_handler(func=lambda message: message.text == "Создать анкету")
def create_profile(message):
    user_id = message.from_user.id
    bot.set_state(user_id, RegistrationStates.waiting_for_gender)
    bot.send_message(user_id, "Выберите ваш пол", reply_markup=gender_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_gender)
def process_gender(message):
    user_id = message.from_user.id
    gender = message.text
    if gender not in ["М", "Ж"]:
        bot.send_message(user_id, "Пожалуйста, выберите пол используя кнопки М или Ж")
        return
    database.db.update_gender(user_id, gender)
    bot.set_state(user_id, RegistrationStates.waiting_for_photos)
    with bot.retrieve_data(user_id) as data:
        data['photos'] = []
    bot.send_message(user_id, "Отлично! Отправьте ваши реальные фото (1-3). Когда закончите, нажмите кнопку Готово", reply_markup=photos_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_photos, content_types=['photo', 'video'])
def process_photos(message):
    user_id = message.from_user.id
    try:
        with bot.retrieve_data(user_id) as data:
            if 'photos' not in data:
                data['photos'] = []
            if len(data['photos']) >= 3:
                bot.send_message(user_id, "Нельзя отправлять более 3 фото. Нажмите Готово для завершения.")
                return
            if message.content_type == 'photo':
                data['photos'].append(message.photo[-1].file_id)
            elif message.content_type == 'video':
                data['photos'].append(message.video.file_id)
            count = len(data['photos'])
            bot.send_message(user_id, f"Фото получено ({count}/3). Отправьте ещё или нажмите Готово.")
    except:
        bot.send_message(user_id, "Ошибка. Нажмите Создать анкету заново.", reply_markup=start_keyboard())
        bot.delete_state(user_id)

@bot.message_handler(state=RegistrationStates.waiting_for_photos, func=lambda message: message.text == "Готово")
def finish_photos_button(message):
    user_id = message.from_user.id
    try:
        with bot.retrieve_data(user_id) as data:
            photos = data.get('photos', [])
            if not photos:
                bot.send_message(user_id, "Вы не отправили фото, отправьте хотя бы одно")
                return
    except:
        bot.send_message(user_id, "Ошибка. Начните заново.", reply_markup=start_keyboard())
        bot.delete_state(user_id)
        return
    bot.set_state(user_id, RegistrationStates.waiting_for_name)
    bot.send_message(user_id, "Как вас зовут?", reply_markup=name_keyboard())

@bot.message_handler(state=RegistrationStates.waiting_for_name, func=lambda message: message.text == "Взять из Telegram")
def take_name_from_telegram(message):
    finish_registration(message.from_user.id, message.from_user.first_name)

@bot.message_handler(state=RegistrationStates.waiting_for_name)
def process_name(message):
    name = message.text.strip()
    if not name:
        name = message.from_user.first_name
    finish_registration(message.from_user.id, name)

def finish_registration(user_id, display_name):
    try:
        with bot.retrieve_data(user_id) as data:
            photos = data.get('photos', [])
            if not photos:
                bot.send_message(user_id, "Ошибка. Начните заново.", reply_markup=start_keyboard())
                bot.delete_state(user_id)
                return
            database.db.update_photos(user_id, photos)
            database.db.update_display_name(user_id, display_name)
    except:
        bot.send_message(user_id, "Ошибка. Начните заново.", reply_markup=start_keyboard())
        bot.delete_state(user_id)
        return
    bot.delete_state(user_id)
    bot.send_message(user_id, "Отлично! Ваши фото загружены. Идём моггать!", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text == "Моя анкета")
def show_profile(message):
    user_id = message.from_user.id
    user_data = get_user_data(database.db.get_user(user_id))
    if not user_data or not user_data['photos']:
        bot.send_message(user_id, "У вас ещё нет анкеты. Создайте её!", reply_markup=start_keyboard())
        return
    display_name = get_display_name(user_data)
    profile_text = f"{display_name}\nСредний рейт: {user_data['avg_rating']}"
    send_media_with_caption(user_id, user_data['photos'], profile_text)
    bot.send_message(user_id, "Выберите действие:", reply_markup=my_profile_keyboard())

def send_media_with_caption(chat_id, photos, caption):
    if not photos:
        return
    if len(photos) == 1:
        media = photos[0]
        try:
            bot.send_photo(chat_id, media, caption=caption)
        except:
            try:
                bot.send_video(chat_id, media, caption=caption)
            except:
                pass
    else:
        media_group = []
        for i, media in enumerate(photos):
            is_video = str(media).startswith('video') or str(media).startswith('BAAC')
            if i == 0:
                if is_video:
                    media_group.append(telebot.types.InputMediaVideo(media, caption=caption))
                else:
                    media_group.append(telebot.types.InputMediaPhoto(media, caption=caption))
            else:
                if is_video:
                    media_group.append(telebot.types.InputMediaVideo(media))
                else:
                    media_group.append(telebot.types.InputMediaPhoto(media))
        try:
            bot.send_media_group(chat_id, media_group)
        except:
            pass

@bot.message_handler(func=lambda message: message.text == "Назад")
def go_back(message):
    user_id = message.from_user.id
    bot.delete_state(user_id)
    rating_targets.pop(user_id, None)
    bot.send_message(user_id, "Главное меню", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text == "Изменить анкету")
def edit_profile(message):
    user_id = message.from_user.id
    bot.send_message(user_id, "Давайте обновим вашу анкету!")
    bot.set_state(user_id, RegistrationStates.waiting_for_gender)
    bot.send_message(user_id, "Выберите ваш пол", reply_markup=gender_keyboard())

@bot.message_handler(func=lambda message: message.text == "Удалить анкету")
def delete_profile(message):
    user_id = message.from_user.id
    database.db.delete_user(user_id)
    database.db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    bot.send_message(user_id, "Анкета удалена. Для создания новой нажмите кнопку ниже", reply_markup=start_keyboard())

@bot.message_handler(func=lambda message: message.text == "Рейтить")
def start_rating(message):
    user_id = message.from_user.id
    user_data = get_user_data(database.db.get_user(user_id))
    if not user_data or not user_data['photos']:
        bot.send_message(user_id, "Сначала создайте анкету!", reply_markup=start_keyboard())
        return
    queue = get_queue_for_user(user_id)
    next_user = queue.get_next_user(user_id)
    if next_user:
        show_user_for_rating(user_id, next_user)
    else:
        bot.send_message(user_id, "Пока нет доступных анкет для рейта. Попробуйте позже", reply_markup=main_menu_keyboard())

def show_user_for_rating(rater_id, target_user):
    user_data = get_user_data(target_user)
    if not user_data:
        return
    target_gender = user_data['gender']
    rating_targets[rater_id] = target_gender
    display_name = get_display_name(user_data)
    profile_text = f"{display_name}\nСредний рейт: {user_data['avg_rating']}"
    # Отправляем кнопки СТРОГО по полу цели
    bot.send_message(rater_id, "Выберите оценку:", reply_markup=rating_keyboard(target_gender))
    send_media_with_caption(rater_id, user_data['photos'], profile_text)

@bot.message_handler(func=lambda message: message.text in [
    "Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam",
    "LTB", "MTB", "HTB", "Stacy", "True Eve"
])
def process_rating(message):
    rater_id = message.from_user.id
    rating = message.text
    target_gender = rating_targets.get(rater_id)
    
    if not target_gender:
        bot.send_message(rater_id, "Ошибка. Начните рейт заново", reply_markup=main_menu_keyboard())
        return
    
    # ЖЁСТКАЯ проверка соответствия оценки полу
    if target_gender == "M" or target_gender == "М":
        if rating not in ["Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam"]:
            bot.send_message(rater_id, "Ошибка! Используйте мужские оценки.", reply_markup=main_menu_keyboard())
            rating_targets.pop(rater_id, None)
            return
    elif target_gender == "Ж":
        if rating not in ["Sub 3", "Sub 5", "LTB", "MTB", "HTB", "Stacy", "True Eve"]:
            bot.send_message(rater_id, "Ошибка! Используйте женские оценки.", reply_markup=main_menu_keyboard())
            rating_targets.pop(rater_id, None)
            return
    
    rating_targets.pop(rater_id, None)
    
    # Ищем user_id цели по gender (костыль, но рабочий)
    target_user = None
    all_users = database.db.get_all_active_users()
    for u in all_users:
        ud = get_user_data(u)
        if ud and ud['gender'] == target_gender and ud['user_id'] != rater_id:
            target_user = ud
            break
    
    if target_user:
        database.db.add_rating(target_user['user_id'], rating)
        
        rater_data = get_user_data(database.db.get_user(rater_id))
        if rater_data:
            if target_user['user_id'] not in rating_notifications:
                rating_notifications[target_user['user_id']] = deque()
            rating_notifications[target_user['user_id']].appendleft({
                'rater_id': rater_id,
                'rating': rating,
                'rater_gender': rater_data.get('gender', 'М'),
                'rater_first_name': get_display_name(rater_data)
            })
            send_next_notification(target_user['user_id'])
    
    queue = get_queue_for_user(rater_id)
    next_user = queue.get_next_user(rater_id)
    if next_user:
        show_user_for_rating(rater_id, next_user)
    else:
        bot.send_message(rater_id, "Пока нет доступных анкет для рейта. Попробуйте позже", reply_markup=main_menu_keyboard())

def send_next_notification(user_id):
    if user_id not in rating_notifications or not rating_notifications[user_id]:
        return
    notification = rating_notifications[user_id].popleft()
    gender_text = "Оценила" if notification['rater_gender'] == 'Ж' else "Оценил"
    message_text = f"{notification['rater_first_name']} {gender_text} вас на {notification['rating']}"
    rating_targets[user_id] = notification
    rater_data = get_user_data(database.db.get_user(notification['rater_id']))
    if rater_data and rater_data.get('photos'):
        rater_name = get_display_name(rater_data)
        rater_profile = f"{rater_name}\nСредний рейт: {rater_data['avg_rating']}"
        send_media_with_caption(user_id, rater_data['photos'], rater_profile)
    bot.send_message(user_id, message_text, reply_markup=notification_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "request_chat")
def request_chat(call):
    user_id = call.from_user.id
    notification = rating_targets.get(user_id)
    if not notification or not isinstance(notification, dict) or 'rater_id' not in notification:
        bot.answer_callback_query(call.id, "Ошибка.")
        return
    rater_id = notification['rater_id']
    user_data = get_user_data(database.db.get_user(user_id))
    if user_data and user_data.get('photos'):
        display_name = get_display_name(user_data)
        contact_text = f"{display_name} хочет пообщаться!"
        if user_data.get('username'):
            contact_text += f" - @{user_data['username']}"
        else:
            contact_text += " -"
        send_media_with_caption(rater_id, user_data['photos'], contact_text)
    bot.answer_callback_query(call.id, "Запрос отправлен!")
    rating_targets.pop(user_id, None)
    if user_id in rating_notifications and rating_notifications[user_id]:
        send_next_notification(user_id)
    else:
        bot.send_message(user_id, "Все рейты просмотрены", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "next_rating")
def next_rating(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id, "Дальше")
    rating_targets.pop(user_id, None)
    if user_id in rating_notifications and rating_notifications[user_id]:
        send_next_notification(user_id)
    else:
        bot.send_message(user_id, "Все рейты просмотрены", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "skip_all")
def skip_all(call):
    user_id = call.from_user.id
    if user_id in rating_notifications:
        rating_notifications[user_id].clear()
    rating_targets.pop(user_id, None)
    bot.send_message(user_id, "Все рейты пропущены", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id, "Пропущено")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route(f'/bot{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    return 'Bad request'

def set_webhook():
    time.sleep(2)
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url='https://moggvinchikbot.onrender.com/bot' + TOKEN)

def start_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    print("Бот Моггвинчик запущен!")
    bot.add_custom_filter(custom_filters.StateFilter(bot))
    threading.Thread(target=set_webhook).start()
    start_flask()
