import sqlite3
from datetime import datetime, timedelta
import os
from tools.config import Config
class DatabaseManager:
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Create tables from schema.sql
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), "r", encoding="utf-8") as f:
            cursor.executescript(f.read())
            
        conn.commit()
        conn.close()
    
    def add_user(self, telegram_id: int, email: str, password: str, 
                 email_server: str, email_port: int, smtp_server: str, smtp_port: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (telegram_id, email_address, email_password, email_server, email_port, smtp_server, smtp_port)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (telegram_id, email, password, email_server, email_port, smtp_server, smtp_port))
        conn.commit()
        conn.close()
    
    def get_user(self, telegram_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def verify_user(self, telegram_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_verified = TRUE WHERE telegram_id = ?', (telegram_id,))
        conn.commit()
        conn.close()
    
    def store_verification_code(self, telegram_id: int, code: str):
        expiry = datetime.now() + timedelta(seconds=Config.VERIFICATION_CODE_EXPIRY)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET verification_code = ?, verification_expiry = ? 
            WHERE telegram_id = ?
        ''', (code, expiry, telegram_id))
        conn.commit()
        conn.close()
    
    def verify_code(self, telegram_id: int, code: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT verification_code, verification_expiry FROM users 
            WHERE telegram_id = ? AND verification_code = ?
        ''', (telegram_id, code))
        result = cursor.fetchone()
        conn.close()
        
        if result and datetime.now() < datetime.fromisoformat(result[1]):
            self.verify_user(telegram_id)
            return True
        return False
    
    def add_processed_email(self, user_id: int, email_id: str, sender: str, 
                          subject: str, summary: str, original_body: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO processed_emails 
            (user_id, email_id, sender, subject, summary, original_body)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email_id, sender, subject, summary, original_body))
        conn.commit()
        conn.close()
    
    def is_email_processed(self, user_id: int, email_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM processed_emails WHERE user_id = ? AND email_id = ?
        ''', (user_id, email_id))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_all_verified_users(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE is_verified = TRUE')
        users = cursor.fetchall()
        conn.close()
        return users
    
# Example test usage:
# db_manager = DatabaseManager('test.db')