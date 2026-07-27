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
            
            avg_rating = self.calculate_avg_rating(ratings, user[3])
            
            self.cursor.execute(
                'UPDATE users SET ratings = ?, avg_rating = ? WHERE user_id = ?',
                (ratings_json, avg_rating, user_id)
            )
            self.conn.commit()
    
    def calculate_avg_rating(self, ratings, gender):
        if not ratings:
            return "Нет оценок"
        
        most_common = Counter(ratings).most_common(1)[0][0]
        
        male_ratings = ["Sub 3", "Sub 5", "LTN", "MTN", "HTN", "Chad", "True Adam"]
        female_ratings = ["Sub 3", "Sub 5", "LTB", "MTB", "HTB", "Stacy", "True Eve"]
        
        if gender == 'M':
            if most_common in female_ratings:
                idx = female_ratings.index(most_common)
                return male_ratings[idx]
        elif gender == 'Ж':
            if most_common in male_ratings:
                idx = male_ratings.index(most_common)
                return female_ratings[idx]
        
        return most_common
    
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def get_all_active_users(self, exclude_user_id=None):
        if exclude_user_id:
            self.cursor.execute(
                'SELECT * FROM users WHERE is_active = 1 AND user_id != ?',
                (exclude_user_id,)
            )
        else:
            self.cursor.execute('SELECT * FROM users WHERE is_active = 1')
        return self.cursor.fetchall()
    
    def delete_user(self, user_id):
        self.cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()

db = Database()
