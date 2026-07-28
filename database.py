import sqlite3
import json
from collections import Counter
import os

class Database:
    def __init__(self):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mogvinchik.db')
        self.db_path = db_path
        self.create_tables()
    
    def get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def create_tables(self):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('''
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
        conn.commit()
        conn.close()
    
    def create_user(self, user_id, username, first_name):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        if user:
            c.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
        else:
            c.execute('INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)', (user_id, username, first_name))
        conn.commit()
        conn.close()
    
    def update_gender(self, user_id, gender):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE users SET gender = ? WHERE user_id = ?', (gender, user_id))
        conn.commit()
        conn.close()
    
    def update_photos(self, user_id, photos):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE users SET photos = ?, is_active = 1 WHERE user_id = ?', (json.dumps(photos), user_id))
        conn.commit()
        conn.close()
    
    def update_name(self, user_id, name):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE users SET first_name = ? WHERE user_id = ?', (name, user_id))
        conn.commit()
        conn.close()
    
    def update_description(self, user_id, description):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE users SET description = ? WHERE user_id = ?', (description, user_id))
        conn.commit()
        conn.close()
    
    def add_rating(self, user_id, rating):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        if not user:
            conn.close()
            return False
        ratings = json.loads(user[6]) if user[6] else []
        ratings.append(rating)
        avg = Counter(ratings).most_common(1)[0][0] if ratings else "Нет оценок"
        c.execute('UPDATE users SET ratings = ?, avg_rating = ? WHERE user_id = ?', (json.dumps(ratings), avg, user_id))
        conn.commit()
        conn.close()
        return True
    
    def get_user(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    
    def get_all_active_users(self, exclude_user_id=None):
        conn = self.get_conn()
        c = conn.cursor()
        if exclude_user_id:
            c.execute("SELECT * FROM users WHERE is_active = 1 AND photos IS NOT NULL AND photos != '' AND user_id != ?", (exclude_user_id,))
        else:
            c.execute("SELECT * FROM users WHERE is_active = 1 AND photos IS NOT NULL AND photos != ''")
        users = c.fetchall()
        conn.close()
        return users
    
    def delete_user(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE users SET is_active = 0, photos = NULL, ratings = NULL, avg_rating = "Нет оценок", gender = NULL, description = "" WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

db = Database()
