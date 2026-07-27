from telebot.handler_backends import State, StatesGroup

class RegistrationStates(StatesGroup):
    waiting_for_gender = State()
    waiting_for_photos = State()