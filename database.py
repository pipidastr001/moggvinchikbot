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
                description TEXT DEFAULT '',
                ratings TEXT,
                avg_rating TEXT DEFAULT 'Нет оценок',
                is_active INTEGER DEFAULT 1
            )
        ''')
        self.conn.commit()
    
    def create_user(self, user_id, username, first_name):
        user = self.get_user(user_id)
        if user:
            self.cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
        else:
            self.cursor.execute('INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)', (user_id, username, first_name))
        self.conn.commit()
    
    def update_gender(self, user_id, gender):
        self.cursor.execute('UPDATE users SET gender = ? WHERE user_id = ?', (gender, user_id))
        self.conn.commit()
    
    def update_photos(self, user_id, photos):
        self.cursor.execute('UPDATE users SET photos = ?, is_active = 1 WHERE user_id = ?', (json.dumps(photos), user_id))
        self.conn.commit()
    
    def update_name(self, user_id, name):
        self.cursor.execute('UPDATE users SET first_name = ? WHERE user_id = ?', (name, user_id))
        self.conn.commit()
    
    def update_description(self, user_id, description):
        self.cursor.execute('UPDATE users SET description = ? WHERE user_id = ?', (description, user_id))
        self.conn.commit()
    
    def add_rating(self, user_id, rating):
        user = self.get_user(user_id)
        if not user:
            return False
        ratings = json.loads(user[6]) if user[6] else []
        ratings.append(rating)
        avg = Counter(ratings).most_common(1)[0][0] if ratings else "Нет оценок"
        self.cursor.execute('UPDATE users SET ratings = ?, avg_rating = ? WHERE user_id = ?', (json.dumps(ratings), avg, user_id))
        self.conn.commit()
        return True
    
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def get_all_active_users(self, exclude_user_id=None):
        if exclude_user_id:
            self.cursor.execute("SELECT * FROM users WHERE is_active = 1 AND photos IS NOT NULL AND photos != '' AND user_id != ?", (exclude_user_id,))
        else:
            self.cursor.execute("SELECT * FROM users WHERE is_active = 1 AND photos IS NOT NULL AND photos != ''")
        return self.cursor.fetchall()
    
    def delete_user(self, user_id):
        self.cursor.execute('UPDATE users SET is_active = 0, photos = NULL, ratings = NULL, avg_rating = "Нет оценок", gender = NULL, description = "" WHERE user_id = ?', (user_id,))
        self.conn.commit()

db = Database()
