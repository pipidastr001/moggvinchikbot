import sqlite3
import json
from collections import Counter
import os

class Database:
    def __init__(self):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mogvinchik.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                gender TEXT,
                photos TEXT,
                ratings TEXT,
                avg_rating TEXT DEFAULT 'Нет оценок',
                is_active INTEGER DEFAULT 1
            )
        ''')
        self.conn.commit()
    
    def create_user(self, user_id, username, first_name):
        self.cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
            (user_id, username, first_name)
        )
        self.conn.commit()
    
    def update_gender(self, user_id, gender):
        self.cursor.execute(
            'UPDATE users SET gender = ? WHERE user_id = ?',
            (gender, user_id)
        )
        self.conn.commit()
    
    def update_photos(self, user_id, photos):
        photos_json = json.dumps(photos)
        self.cursor.execute(
            'UPDATE users SET photos = ?, is_active = 1 WHERE user_id = ?',
            (photos_json, user_id)
        )
        self.conn.commit()
    
    def add_rating(self, user_id, rating):
        user = self.get_user(user_id)
        if user:
            ratings = json.loads(user[5]) if user[5] else []
            ratings.append(rating)
            ratings_json = json.dumps(ratings)
            
            # Считаем самую частую оценку
            if ratings:
                most_common = Counter(ratings).most_common(1)[0][0]
                avg_rating = most_common
            else:
                avg_rating = "Нет оценок"
            
            self.cursor.execute(
                'UPDATE users SET ratings = ?, avg_rating = ? WHERE user_id = ?',
                (ratings_json, avg_rating, user_id)
            )
            self.conn.commit()
            print(f"DEBUG: Added rating {rating} for user {user_id}. Total ratings: {ratings}, Avg: {avg_rating}")
            return True
        print(f"DEBUG: User {user_id} not found in database")
        return False
    
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def get_all_active_users(self, exclude_user_id=None):
        if exclude_user_id:
            self.cursor.execute(
                'SELECT * FROM users WHERE is_active = 1 AND user_id != ? AND photos IS NOT NULL',
                (exclude_user_id,)
            )
        else:
            self.cursor.execute('SELECT * FROM users WHERE is_active = 1 AND photos IS NOT NULL')
        return self.cursor.fetchall()
    
    def delete_user(self, user_id):
        self.cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()

db = Database()
