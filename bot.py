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
    if user_data['display_name']:
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
    
    bot.send_message(
        user_id, 
        "Отлично! Отправьте ваши реальные фото (1-3). Когда закончите, нажмите кнопку Готово",
        reply_markup=photos_keyboard()
    )

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
    except KeyError:
        bot.send_message(user_id, "Произошла ошибка. Нажмите Создать анкету чтобы начать заново.", reply_markup=start_keyboard())
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
            
            # Сохраняем фото во временные данные
            data['photos'] = photos
    except KeyError:
        bot.send_message(user_id, "Ошибка. Начните создание анкеты заново.", reply_markup=start_keyboard())
        bot.delete_state(user_id)
        return
    
    # Переходим к выбору ника
    bot.set_state(user_id, RegistrationStates.waiting_for_name)
    bot.send_message(
        user_id, 
        "Как вас зовут?",
        reply_markup=name_keyboard()
    )

@bot.message_handler(state=RegistrationStates.waiting_for_name, func=lambda message: message.text == "Взять из Telegram")
def take_name_from_telegram(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    finish_registration(user_id, first_name)

@bot.message_handler(state=RegistrationStates.waiting_for_name)
def process_name(message):
    user_id = message.from_user.id
    name = message.text
    
    if name == "Готово":
        # Если пустое имя, берём из Telegram
        name = message.from_user.first_name
    
    finish_registration(user_id, name)

def finish_registration(user_id, display_name):
    try:
        with bot.retrieve_data(user_id) as data:
            photos = data.get('photos', [])
            
            if not photos:
                bot.send_message(user_id, "Ошибка. Фото не найдены. Начните заново.", reply_markup=start_keyboard())
                bot.delete_state(user_id)
                return
            
            database.db.update_photos(user_id, photos)
            database.db.update_display_name(user_id, display_name)
    except KeyError:
        bot.send_message(user_id, "Ошибка. Начните создание анкеты заново.", reply_markup=start_keyboard())
        bot.delete_state(user_id)
        return
    
    bot.delete_state(user_id)
    bot.send_message(user_id, "Отлично! Ваши фото загружены. Идём моггать!", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text == "Моя анкета")
def show_profile(message):
    user_id = message.from_user.id
    user = database.db.get_user(user_id)
    user_data = get_user_data(user)
    
    if not user_data or not user_data['photos']:
        bot.send_message(user_id, "У вас ещё нет анкеты. Создайте её!", reply_markup=start_keyboard())
        return
    
    display_name = get_display_name(user_data)
    profile_text = f"{display_name}\nСредний рейт: {user_data['avg_rating']}"
    
    if len(user_data['photos']) == 1:
        media = user_data['photos'][0]
        try:
            bot.send_photo(user_id, media, caption=profile_text)
        except:
            try:
                bot.send_video(user_id, media, caption=profile_text)
            except:
                bot.send_message(user_id, "Не удалось загрузить медиа")
    else:
        media_group = []
        for i, media in enumerate(user_data['photos']):
            if i == 0:
                if media.startswith('video'):
                    media_group.append(telebot.types.InputMediaVideo(media, caption=profile_text))
                else:
                    media_group.append(telebot.types.InputMediaPhoto(media, caption=profile_text))
            else:
                if media.startswith('video'):
                    media_group.append(telebot.types.InputMediaVideo(media))
                else:
                    media_group.append(telebot.types.InputMediaPhoto(media))
        
        try:
            bot.send_media_group(user_id, media_group)
        except:
            bot.send_message(user_id, "Не удалось загрузить медиа")
    
    bot.send_message(user_id, "Выберите действие:", reply_markup=my_profile_keyboard())

@bot.message_handler(func=lambda message: message.text == "Назад")
def go_back(message):
    user_id = message.from_user.id
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
    user = database.db.get_user(user_id)
    user_data = get_user_data(user)
    
    if not user_data or not user_data['photos'] or len(user_data['photos']) == 0:
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
    
    display_name = get_display_name(user_data)
    profile_text = f"{display_name}\nСредний рейт: {user_data['avg_rating']}"
    
    bot.send_message(rater_id, "Выберите оценку:", reply_markup=rating_keyboard(user_data['gender']))
    
    if len(user_data['photos']) == 1:
        media = user_data['photos'][0]
        try:
            bot.send_photo(rater_id, media, caption=profile_text)
        except:
            try:
                bot.send_video(rater_id, media, caption=profile_text)
            except:
                pass
    else:
        media_group = []
        for i, media in enumerate(user_data['photos']):
            if i == 0:
                if media.startswith('video'):
                    media_group.append(telebot.types.InputMediaVideo(media, caption=profile_text))
                else:
                    media_group.append(telebot.types.InputMediaPhoto(media, caption=profile_text))
            else:
                if media.startswith('video'):
                    media_group.append(telebot.types.InputMediaVideo(media))
                else:
                    media_group.append(telebot.types.InputMediaPhoto(media))
        
        try:
            bot.send_media_group(rater_id, media_group)
        except:
            pass
    
    try:
        with bot.retrieve_data(rater_id) as data:
            data['rating_target'] = user_data['user_id']
    except:
        pass

@bot.message_handler(func=lambda message: message.text in [
    "Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam",
    "LTB", "MTB", "HTB", "Stacy", "True Eve"
])
def process_rating(message):
    rater_id = message.from_user.id
    rating = message.text
    
    try:
        with bot.retrieve_data(rater_id) as data:
            target_id = data.get('rating_target')
    except:
        bot.send_message(rater_id, "Ошибка. Начните рейт заново", reply_markup=main_menu_keyboard())
        return
    
    if not target_id:
        bot.send_message(rater_id, "Ошибка. Начните рейт заново", reply_markup=main_menu_keyboard())
        return
    
    database.db.add_rating(target_id, rating)
    
    rater = database.db.get_user(rater_id)
    rater_data = get_user_data(rater)
    
    if target_id not in rating_notifications:
        rating_notifications[target_id] = deque()
    
    rating_notifications[target_id].appendleft({
        'rater_id': rater_id,
        'rating': rating,
        'rater_gender': rater_data['gender'],
        'rater_first_name': rater_data['first_name']
    })
    
    send_next_notification(target_id)
    
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
    rating = notification['rating']
    rater_name = notification['rater_first_name']
    
    message_text = f"{rater_name} {gender_text} вас на {rating}"
    
    try:
        with bot.retrieve_data(user_id) as data:
            data['current_notification'] = notification
    except:
        pass
    
    rater = database.db.get_user(notification['rater_id'])
    rater_data = get_user_data(rater)
    
    if rater_data and rater_data['photos']:
        rater_display_name = get_display_name(rater_data)
        rater_profile = f"{rater_display_name}\nСредний рейт: {rater_data['avg_rating']}"
        
        if len(rater_data['photos']) == 1:
            media = rater_data['photos'][0]
            try:
                bot.send_photo(user_id, media, caption=rater_profile)
            except:
                try:
                    bot.send_video(user_id, media, caption=rater_profile)
                except:
                    pass
        else:
            media_group = []
            for i, media in enumerate(rater_data['photos']):
                if i == 0:
                    if media.startswith('video'):
                        media_group.append(telebot.types.InputMediaVideo(media, caption=rater_profile))
                    else:
                        media_group.append(telebot.types.InputMediaPhoto(media, caption=rater_profile))
                else:
                    if media.startswith('video'):
                        media_group.append(telebot.types.InputMediaVideo(media))
                    else:
                        media_group.append(telebot.types.InputMediaPhoto(media))
            try:
                bot.send_media_group(user_id, media_group)
            except:
                pass
    
    bot.send_message(user_id, message_text, reply_markup=notification_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "request_chat")
def request_chat(call):
    user_id = call.from_user.id
    
    try:
        with bot.retrieve_data(user_id) as data:
            notification = data.get('current_notification')
    except:
        bot.answer_callback_query(call.id, "Ошибка.")
        return
    
    if not notification:
        bot.answer_callback_query(call.id, "Ошибка.")
        return
    
    rater_id = notification['rater_id']
    user = database.db.get_user(user_id)
    user_data = get_user_data(user)
    
    if user_data and user_data['photos']:
        display_name = get_display_name(user_data)
        contact_text = f"{display_name} хочет пообщаться!"
        if user_data['username']:
            contact_text += f" - @{user_data['username']}"
        else:
            contact_text += " -"
        
        if len(user_data['photos']) == 1:
            media = user_data['photos'][0]
            try:
                bot.send_photo(rater_id, media, caption=contact_text)
            except:
                try:
                    bot.send_video(rater_id, media, caption=contact_text)
                except:
                    pass
        else:
            media_group = []
            for i, media in enumerate(user_data['photos']):
                if i == 0:
                    if media.startswith('video'):
                        media_group.append(telebot.types.InputMediaVideo(media, caption=contact_text))
                    else:
                        media_group.append(telebot.types.InputMediaPhoto(media, caption=contact_text))
                else:
                    if media.startswith('video'):
                        media_group.append(telebot.types.InputMediaVideo(media))
                    else:
                        media_group.append(telebot.types.InputMediaPhoto(media))
            try:
                bot.send_media_group(rater_id, media_group)
            except:
                pass
    
    bot.answer_callback_query(call.id, "Запрос отправлен!")
    
    if user_id in rating_notifications and rating_notifications[user_id]:
        send_next_notification(user_id)
    else:
        bot.send_message(user_id, "Все рейты просмотрены", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "next_rating")
def next_rating(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id, "Дальше")
    
    if user_id in rating_notifications and rating_notifications[user_id]:
        send_next_notification(user_id)
    else:
        bot.send_message(user_id, "Все рейты просмотрены", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "skip_all")
def skip_all(call):
    user_id = call.from_user.id
    if user_id in rating_notifications:
        rating_notifications[user_id].clear()
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
