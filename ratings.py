from database import db
import random

def get_all_users_for_rating(current_user_id):
    users = db.get_all_active_users(exclude_user_id=current_user_id)
    random.shuffle(users)
    return users

user_queues = {}

def get_queue_for_user(user_id):
    # Всегда создаём новую очередь чтобы видеть все анкеты
    queue = RatingQueue()
    queue.users_pool = get_all_users_for_rating(user_id)
    queue.current_index = 0
    return queue

class RatingQueue:
    def __init__(self):
        self.current_index = 0
        self.users_pool = []
    
    def get_next_user(self, current_user_id):
        if not self.users_pool or self.current_index >= len(self.users_pool):
            self.users_pool = get_all_users_for_rating(current_user_id)
            self.current_index = 0
        
        if self.users_pool:
            user = self.users_pool[self.current_index]
            self.current_index += 1
            return user
        return None
