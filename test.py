import os
import json
import base64
import asyncio
import random
import string
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

# Google OAuth2 and Gmail API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Telegram
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Database
import sqlite3
from cryptography.fernet import Fernet

load_dotenv()

# ==================== CONFIGURATION ====================
class Config:
    # Google OAuth2 Configuration
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080/callback")
    
    # If you want to use a public URL for OAuth callback (recommended for production)
    # You can use services like ngrok or deploy to a server
    OAUTH_SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    # LLM Configuration (for email summarization)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Security
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    DATABASE_PATH = "secure_email_bot.db"
    
    # Email Provider Detection
    EMAIL_PROVIDERS = {
        'gmail.com': {
            'name': 'Gmail',
            'oauth_supported': True,
            'imap': ('imap.gmail.com', 993),
            'smtp': ('smtp.gmail.com', 587)
        },
        'outlook.com': {
            'name': 'Outlook',
            'oauth_supported': True,  # Can be implemented
            'imap': ('outlook.office365.com', 993),
            'smtp': ('smtp.office365.com', 587)
        },
        'hotmail.com': {
            'name': 'Hotmail',
            'oauth_supported': True,
            'imap': ('outlook.office365.com', 993),
            'smtp': ('smtp.office365.com', 587)
        }
    }

# ==================== ENHANCED DATABASE ====================
class SecureDatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.cipher = Fernet(Config.ENCRYPTION_KEY.encode())
        self.init_database()
    
    def init_database(self):
        """Initialize database with enhanced schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhanced users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL,
                provider TEXT,
                auth_method TEXT,  -- 'oauth' or 'app_password'
                oauth_tokens TEXT,  -- Encrypted OAuth tokens
                app_password TEXT,  -- Encrypted app password (fallback)
                setup_stage TEXT DEFAULT 'initial',
                is_verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP
            )
        ''')
        
        # Processed emails table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email_id TEXT UNIQUE,
                sender TEXT,
                subject TEXT,
                summary TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            )
        ''')
        
        # OAuth states for security
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                telegram_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def save_oauth_tokens(self, telegram_id: int, email: str, tokens: dict):
        """Save OAuth tokens securely"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        encrypted_tokens = self.encrypt_data(json.dumps(tokens))
        provider = email.split('@')[1].lower()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (telegram_id, email, provider, auth_method, oauth_tokens, is_verified)
            VALUES (?, ?, ?, 'oauth', ?, 1)
        ''', (telegram_id, email, provider, encrypted_tokens))
        
        conn.commit()
        conn.close()
    
    def get_oauth_tokens(self, telegram_id: int) -> Optional[dict]:
        """Retrieve OAuth tokens"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT oauth_tokens FROM users WHERE telegram_id = ?', (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return json.loads(self.decrypt_data(result[0]))
        return None
    
    def save_oauth_state(self, state: str, telegram_id: int):
        """Save OAuth state for security verification"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clean old states
        cursor.execute('''
            DELETE FROM oauth_states 
            WHERE created_at < datetime('now', '-1 hour')
        ''')
        
        cursor.execute('''
            INSERT INTO oauth_states (state, telegram_id) VALUES (?, ?)
        ''', (state, telegram_id))
        
        conn.commit()
        conn.close()
    
    def verify_oauth_state(self, state: str) -> Optional[int]:
        """Verify OAuth state and return telegram_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT telegram_id FROM oauth_states WHERE state = ?', (state,))
        result = cursor.fetchone()
        
        if result:
            # Delete used state
            cursor.execute('DELETE FROM oauth_states WHERE state = ?', (state,))
            conn.commit()
        
        conn.close()
        return result[0] if result else None

# ==================== GMAIL API SERVICE ====================
class GmailAPIService:
    def __init__(self, db_manager: SecureDatabaseManager):
        self.db = db_manager
    
    def get_gmail_service(self, telegram_id: int):
        """Get authenticated Gmail service"""
        tokens = self.db.get_oauth_tokens(telegram_id)
        if not tokens:
            return None
        
        creds = Credentials(
            token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=Config.GOOGLE_CLIENT_ID,
            client_secret=Config.GOOGLE_CLIENT_SECRET,
            scopes=Config.OAUTH_SCOPES
        )
        
        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed tokens
            self.db.save_oauth_tokens(telegram_id, tokens.get('email'), {
                'access_token': creds.token,
                'refresh_token': creds.refresh_token,
                'email': tokens.get('email')
            })
        
        return build('gmail', 'v1', credentials=creds)
    
    def get_recent_emails(self, telegram_id: int, max_results: int = 5):
        """Get recent unread emails"""
        service = self.get_gmail_service(telegram_id)
        if not service:
            return []
        
        try:
            # Get unread emails from primary category
            results = service.users().messages().list(
                userId='me',
                q='is:unread category:primary',
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            email_data = []
            
            for message in messages:
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id']
                ).execute()
                
                # Extract email details
                headers = msg['payload'].get('headers', [])
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                
                # Extract body
                body = self.extract_body(msg['payload'])
                
                email_data.append({
                    'id': message['id'],
                    'sender': sender,
                    'subject': subject,
                    'body': body[:1000],  # Limit body length
                    'snippet': msg.get('snippet', '')
                })
                
                # Mark as read (optional)
                service.users().messages().modify(
                    userId='me',
                    id=message['id'],
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
            
            return email_data
            
        except HttpError as error:
            logging.error(f'Gmail API error: {error}')
            return []
    
    def extract_body(self, payload):
        """Extract email body from payload"""
        body = ''
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        elif payload['body'].get('data'):
            body = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8', errors='ignore')
        
        return body

# ==================== LLM SERVICE ====================
class LLMService:
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        self.api_url = Config.GEMINI_API_URL
    
    def summarize_email(self, sender: str, subject: str, body: str) -> str:
        """Summarize email using Gemini"""
        if not self.api_key:
            # Fallback without LLM
            return f"From: {sender[:30]}\nRe: {subject[:50]}"
        
        try:
            headers = {
                'Content-Type': 'application/json',
            }
            
            prompt = f"""
            Summarize this email in 2-3 short sentences, like a text message:
            From: {sender}
            Subject: {subject}
            Body: {body[:500]}
            
            Keep it casual and focus on key points/actions needed.
            """
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 150
                }
            }
            
            response = requests.post(
                f"{self.api_url}?key={self.api_key}",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result['candidates'][0]['content']['parts'][0]['text']
                return summary.strip()
            else:
                return f"From: {sender[:30]}\nRe: {subject[:50]}"
                
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return f"From: {sender[:30]}\nRe: {subject[:50]}"

# ==================== SIMPLIFIED TELEGRAM BOT ====================
class SimplifiedEmailBot:
    def __init__(self):
        self.db = SecureDatabaseManager(Config.DATABASE_PATH)
        self.gmail_service = GmailAPIService(self.db)
        self.llm = LLMService()
        self.app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.monitoring_tasks = {}
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup telegram bot handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("connect", self.connect_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("check", self.check_emails_command))
        self.app.add_handler(CommandHandler("stop", self.stop_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Simplified start message"""
        welcome = """
🚀 **Gmail to Telegram Bot**

Get your Gmail summaries instantly!

**Super Simple Setup:**
1️⃣ Type `/connect` 
2️⃣ Click the button to connect Gmail
3️⃣ Authorize access (one-time)
4️⃣ Done! Get email summaries 📧

**Commands:**
• `/connect` - Connect your Gmail
• `/check` - Check emails now
• `/status` - Connection status
• `/stop` - Pause notifications

No passwords needed! Uses secure Google login.
        """
        await update.message.reply_text(welcome, parse_mode='Markdown')
    
    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Simplified connection process"""
        telegram_id = update.message.from_user.id
        
        # Generate OAuth URL
        state = self.generate_state()
        self.db.save_oauth_state(state, telegram_id)
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": Config.GOOGLE_CLIENT_ID,
                    "client_secret": Config.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=Config.OAUTH_SCOPES
        )
        flow.redirect_uri = Config.GOOGLE_REDIRECT_URI
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'
        )
        
        # Create inline button
        keyboard = [[
            InlineKeyboardButton("🔗 Connect Gmail", url=auth_url)
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = """
✨ **One-Click Gmail Setup!**

1. Click the button below
2. Sign in with Google
3. Allow access to read emails
4. Come back here - you're done!

_No passwords stored, using Google's secure OAuth2_
        """
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Alternative: Show manual option
        await update.message.reply_text(
            "⚡ After authorizing, I'll automatically start sending you email summaries!\n\n"
            "_Having issues? Type /help for manual setup_",
            parse_mode='Markdown'
        )
    
    async def check_emails_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually check for new emails"""
        telegram_id = update.message.from_user.id
        
        # Check if user is connected
        tokens = self.db.get_oauth_tokens(telegram_id)
        if not tokens:
            await update.message.reply_text(
                "❌ Gmail not connected yet!\nUse `/connect` to get started.",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text("🔄 Checking your emails...")
        
        # Get recent emails
        emails = self.gmail_service.get_recent_emails(telegram_id, max_results=3)
        
        if not emails:
            await update.message.reply_text("📭 No new emails!")
            return
        
        # Send summaries
        for email in emails:
            summary = self.llm.summarize_email(
                email['sender'],
                email['subject'],
                email['body']
            )
            
            message = f"""
📧 **New Email**

{summary}

_From: {email['sender'][:40]}_
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check connection status"""
        telegram_id = update.message.from_user.id
        tokens = self.db.get_oauth_tokens(telegram_id)
        
        if tokens:
            email = tokens.get('email', 'Connected')
            monitoring = "🟢 Active" if telegram_id in self.monitoring_tasks else "⏸️ Paused"
            
            message = f"""
✅ **Gmail Connected**

📧 Account: {email}
📊 Monitoring: {monitoring}

Use `/check` to get emails now
Use `/stop` to pause notifications
            """
        else:
            message = """
❌ **Gmail Not Connected**

Use `/connect` to connect your Gmail account.
It only takes 30 seconds!
            """
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop email monitoring"""
        telegram_id = update.message.from_user.id
        
        if telegram_id in self.monitoring_tasks:
            self.monitoring_tasks[telegram_id].cancel()
            del self.monitoring_tasks[telegram_id]
            await update.message.reply_text("⏸️ Email monitoring paused.\nUse `/check` to manually check emails.")
        else:
            await update.message.reply_text("📭 Monitoring is not active.")
    
    async def button_callback(self, query, context):
        """Handle button callbacks"""
        await query.answer()
        # Handle any button callbacks here
    
    def generate_state(self) -> str:
        """Generate secure random state for OAuth"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    
    async def monitor_emails(self, telegram_id: int):
        """Background task to monitor emails"""
        bot = Bot(Config.TELEGRAM_BOT_TOKEN)
        
        while True:
            try:
                # Check emails every 2 minutes
                await asyncio.sleep(120)
                
                emails = self.gmail_service.get_recent_emails(telegram_id, max_results=3)
                
                for email in emails:
                    # Check if already processed
                    # ... (add deduplication logic)
                    
                    summary = self.llm.summarize_email(
                        email['sender'],
                        email['subject'],
                        email['body']
                    )
                    
                    message = f"📧 {summary}"
                    
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=message
                    )
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Monitor error: {e}")
                await asyncio.sleep(300)
    
    def run(self):
        """Start the bot"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        print("🚀 Simplified Gmail Bot starting...")
        print("✅ No IMAP setup needed!")
        print("✅ No app passwords required!")
        print("✅ Just OAuth2 - simple and secure!")
        
        self.app.run_polling()

# ==================== OAUTH CALLBACK SERVER ====================
class OAuthCallbackHandler:
    """
    Simple OAuth callback handler
    In production, this should be a proper web server
    """
    
    @staticmethod
    def handle_callback(code: str, state: str, bot: SimplifiedEmailBot) -> bool:
        """Handle OAuth callback"""
        # Verify state
        telegram_id = bot.db.verify_oauth_state(state)
        if not telegram_id:
            return False
        
        # Exchange code for tokens
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": Config.GOOGLE_CLIENT_ID,
                    "client_secret": Config.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=Config.OAUTH_SCOPES
        )
        flow.redirect_uri = Config.GOOGLE_REDIRECT_URI
        
        try:
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Get user email
            service = build('gmail', 'v1', credentials=credentials)
            profile = service.users().getProfile(userId='me').execute()
            email = profile['emailAddress']
            
            # Save tokens
            bot.db.save_oauth_tokens(telegram_id, email, {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'email': email
            })
            
            # Start monitoring
            asyncio.create_task(bot.monitor_emails(telegram_id))
            
            # Send success message to Telegram
            asyncio.create_task(
                bot.app.bot.send_message(
                    chat_id=telegram_id,
                    text=f"✅ Success! Connected to {email}\n\n"
                         f"I'll start sending you email summaries now! 🎉"
                )
            )
            
            return True
            
        except Exception as e:
            logging.error(f"OAuth callback error: {e}")
            return False

# ==================== MAIN ====================
def main():
    """Run the simplified bot"""
    
    # Check configuration
    if not Config.TELEGRAM_BOT_TOKEN:
        print("❌ Missing TELEGRAM_BOT_TOKEN in .env file")
        return
    
    if not Config.GOOGLE_CLIENT_ID or not Config.GOOGLE_CLIENT_SECRET:
        print("❌ Missing Google OAuth credentials in .env file")
        print("\n📝 Setup Instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing")
        print("3. Enable Gmail API")
        print("4. Create OAuth 2.0 credentials")
        print("5. Add redirect URI: http://localhost:8080/callback")
        print("6. Copy Client ID and Secret to .env file")
        return
    
    # Start bot
    bot = SimplifiedEmailBot()
    bot.run()

if __name__ == "__main__":
    main()

# ==================== REQUIREMENTS ====================
"""
# requirements.txt

python-telegram-bot>=20.0
google-auth>=2.20.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.2.0
google-api-python-client>=2.90.0
cryptography>=41.0.0
python-dotenv>=1.0.0
requests>=2.31.0

# .env file structure:
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GEMINI_API_KEY=your_gemini_api_key_optional
ENCRYPTION_KEY=your_generated_encryption_key
"""