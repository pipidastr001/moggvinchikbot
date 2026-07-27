from database import db

class RatingQueue:
    def __init__(self):
        self.current_index = 0
        self.users_pool = []
    
    def get_next_user(self, current_user_id):
        if not self.users_pool or self.current_index >= len(self.users_pool):
            self.users_pool = db.get_all_active_users(exclude_user_id=current_user_id)
            self.current_index = 0
        
        if self.users_pool:
            user = self.users_pool[self.current_index]
            self.current_index += 1
            return user
        return None

user_queues = {}

def get_queue_for_user(user_id):
    if user_id not in user_queues:
        user_queues[user_id] = RatingQueue()
    return user_queues[user_id]
