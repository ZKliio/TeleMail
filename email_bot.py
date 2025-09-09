import os
import json
import imaplib
import email
import smtplib
import asyncio
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import sqlite3
import hashlib
from dotenv import load_dotenv

from DatabaseManager import DatabaseManager
load_dotenv()

# ==================== CONFIGURATION ====================
class Config:
    # LLM API Configuration (Initialize with your preferred LLM)
    LLM_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"  # Changed to OpenAI format
    LLM_API_KEY = os.getenv("OPENAI_API_KEY")  # Your OpenAI API key
    LLM_MODEL = "Gemini 2.5 Flash"  # Changed to OpenAI model
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Replace with your bot token
    
    # Email Configuration (will be set per user)
    DATABASE_PATH = "email_bot.db"
    
    # Security
    VERIFICATION_CODE_EXPIRY = 300  # 5 minutes

# ==================== EMAIL SUMMARIZATION PROMPT ====================
EMAIL_SUMMARY_PROMPT = """
You are an email summarization assistant. Your task is to convert emails into short, text-message-like summaries that capture the key information.

Guidelines:
- Keep it conversational and brief (like a text message)
- Extract the main action items, requests, or information
- Preserve important details like dates, times, names
- Use casual language but remain professional
- Maximum 2-3 sentences
- Focus on what the recipient needs to know or do

Email to summarize:
From: {sender}
Subject: {subject}
Body: {body}

Provide only the summary, no additional text:
"""

# ==================== LLM INTEGRATION ====================
class LLMService:
    def __init__(self):
        self.api_url = Config.LLM_API_URL
        self.api_key = Config.LLM_API_KEY
        self.model = Config.LLM_MODEL
    
    def summarize_email(self, sender: str, subject: str, body: str) -> str:
        """Summarize email using LLM API"""
        try:
            prompt = EMAIL_SUMMARY_PROMPT.format(
                sender=sender,
                subject=subject,
                body=body[:2000]  # Limit body length
            )
            
            # OpenAI API call format
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.3
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                logging.error(f"LLM API error: {response.status_code} - {response.text}")
                return f"📧 {sender}: {subject}"  # Fallback summary
                
        except Exception as e:
            logging.error(f"Error summarizing email: {e}")
            return f"📧 {sender}: {subject}"  # Fallback summary

# ==================== EMAIL SERVICE ====================
class EmailService:
    def __init__(self, db_manager: DatabaseManager, llm_service: LLMService):
        self.db = db_manager
        self.llm = llm_service
    
    def connect_to_email(self, user_data):
        """Connect to user's email account"""
        try:
            mail = imaplib.IMAP4_SSL(user_data[3], user_data[4])  # server, port
            mail.login(user_data[1], user_data[2])  # email, password
            return mail
        except Exception as e:
            logging.error(f"Email connection failed: {e}")
            return None
    
    def check_new_emails(self, user_data):
        """Check for new emails and return summaries"""
        mail = self.connect_to_email(user_data)
        if not mail:
            return []
        
        try:
            mail.select('inbox')
            
            # Search for unread emails from last 24 hours
            today = datetime.now().strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(UNSEEN SINCE "{today}")')
            
            email_summaries = []
            
            if messages[0]:
                for num in messages[0].split()[-5:]:  # Last 5 new emails
                    try:
                        status, msg_data = mail.fetch(num, '(RFC822)')
                        
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                
                                # Extract email details
                                sender = msg.get('From', 'Unknown')
                                subject = msg.get('Subject', 'No Subject')
                                email_id = msg.get('Message-ID', str(num))
                                
                                # Check if already processed
                                if self.db.is_email_processed(user_data[0], email_id):
                                    continue
                                
                                # Extract body
                                body = self.extract_email_body(msg)
                                
                                # Generate summary
                                summary = self.llm.summarize_email(sender, subject, body)
                                
                                # Store in database
                                self.db.add_processed_email(
                                    user_data[0], email_id, sender, subject, summary, body
                                )
                                
                                email_summaries.append({
                                    'sender': sender,
                                    'subject': subject,
                                    'summary': summary,
                                    'email_id': email_id
                                })
                    except Exception as e:
                        logging.error(f"Error processing email {num}: {e}")
                        continue
            
            mail.logout()
            return email_summaries
            
        except Exception as e:
            logging.error(f"Error checking emails: {e}")
            try:
                mail.logout()
            except:
                pass
            return []
    
    def extract_email_body(self, msg):
        """Extract text content from email message"""
        body = ""
        
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode('utf-8', errors='ignore')
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
        except Exception as e:
            logging.error(f"Error extracting email body: {e}")
            body = "Could not extract email content"
        
        return body.strip()
    
    def send_reply_email(self, user_data, recipient_email: str, subject: str, body: str):
        """Send reply email on behalf of user"""
        try:
            msg = MIMEMultipart()
            msg['From'] = user_data[1]  # user email
            msg['To'] = recipient_email
            msg['Subject'] = f"Re: {subject}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(user_data[5], user_data[6])  # smtp_server, smtp_port
            server.starttls()
            server.login(user_data[1], user_data[2])
            
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            logging.error(f"Error sending email: {e}")
            return False

# ==================== TELEGRAM BOT ====================
class EmailTelegramBot:
    def __init__(self):
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.llm = LLMService()
        self.email_service = EmailService(self.db, self.llm)
        self.app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.monitoring_tasks = {}
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup telegram bot command handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("setup", self.setup_command))
        self.app.add_handler(CommandHandler("verify", self.verify_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("stop", self.stop_monitoring_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_msg = """
🤖 **Email Summary Bot**

I'll help you get short summaries of your emails via Telegram!

**Setup Steps:**
1. Use `/setup` to configure your email
2. I'll send a verification code to your email
3. Use `/verify <code>` to confirm
4. Start receiving email summaries!

**Commands:**
- `/setup` - Configure email settings
- `/verify <code>` - Verify your email
- `/status` - Check connection status
- `/stop` - Stop email monitoring

Type any message to reply to the last email.
        """
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def setup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setup command"""
        setup_msg = """
📧 **Email Setup**

Please provide your email details in this format:
`email@domain.com|password|imap_server|imap_port|smtp_server|smtp_port`

**Common configurations:**

**Gmail:**
`your@gmail.com|app_password|imap.gmail.com|993|smtp.gmail.com|587`

**Outlook:**
`your@outlook.com|password|outlook.office365.com|993|smtp.office365.com|587`

**Note:** For Gmail, use an App Password, not your regular password!
        """
        await update.message.reply_text(setup_msg, parse_mode='Markdown')
    
    async def handle_setup(self, update: Update, setup_data: str):
        """Process email setup data"""
        try:
            parts = setup_data.split('|')
            if len(parts) != 6:
                await update.message.reply_text("❌ Invalid format. Please use: email|password|imap_server|imap_port|smtp_server|smtp_port")
                return
            
            email_addr, password, imap_server, imap_port, smtp_server, smtp_port = parts
            telegram_id = update.message.from_user.id
            
            # Store user data
            self.db.add_user(
                telegram_id, email_addr, password, 
                imap_server, int(imap_port), smtp_server, int(smtp_port)
            )
            
            # Generate and send verification code
            verification_code = self.generate_verification_code()
            self.db.store_verification_code(telegram_id, verification_code)
            
            # Send verification email
            if self.send_verification_email(email_addr, password, smtp_server, int(smtp_port), verification_code):
                await update.message.reply_text(
                    f"✅ Setup saved! Check your email for verification code.\n"
                    f"Use `/verify {verification_code}` to complete setup."
                )
            else:
                await update.message.reply_text("❌ Failed to send verification email. Please check your email settings.")
                
        except Exception as e:
            logging.error(f"Setup error: {e}")
            await update.message.reply_text("❌ Setup failed. Please check your email settings and try again.")
    
    def generate_verification_code(self) -> str:
        """Generate random verification code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    def send_verification_email(self, email_addr: str, password: str, smtp_server: str, smtp_port: int, code: str) -> bool:
        """Send verification code via email"""
        try:
            msg = MIMEText(f"""
Email Summary Bot Verification

Your verification code is: {code}

Use this code in Telegram to complete your setup.
This code expires in 5 minutes.

If you didn't request this, please ignore this email.
            """)
            
            msg['From'] = email_addr
            msg['To'] = email_addr
            msg['Subject'] = "Email Bot Verification Code"
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(email_addr, password)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            logging.error(f"Verification email failed: {e}")
            return False
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command"""
        if not context.args:
            await update.message.reply_text("Please provide verification code: `/verify YOUR_CODE`")
            return
        
        code = context.args[0].upper()
        telegram_id = update.message.from_user.id
        
        if self.db.verify_code(telegram_id, code):
            await update.message.reply_text("✅ Email verified! You'll now receive email summaries.")
            # Start monitoring emails for this user
            await self.start_user_monitoring(telegram_id)
        else:
            await update.message.reply_text("❌ Invalid or expired verification code.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        telegram_id = update.message.from_user.id
        user = self.db.get_user(telegram_id)
        
        if not user:
            await update.message.reply_text("❌ No email configured. Use `/setup` first.")
            return
        
        status = "✅ Verified" if user[8] else "⏳ Pending verification"
        monitoring_status = "🟢 Active" if telegram_id in self.monitoring_tasks else "🔴 Stopped"
        await update.message.reply_text(f"📧 Email: {user[1]}\n🔒 Status: {status}\n📊 Monitoring: {monitoring_status}")
    
    async def stop_monitoring_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        telegram_id = update.message.from_user.id
        
        if telegram_id in self.monitoring_tasks:
            self.monitoring_tasks[telegram_id].cancel()
            del self.monitoring_tasks[telegram_id]
            await update.message.reply_text("⏹️ Email monitoring stopped.")
        else:
            await update.message.reply_text("❌ No active monitoring found.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (setup data or email replies)"""
        message_text = update.message.text
        telegram_id = update.message.from_user.id
        
        # Check if it's setup data
        if '|' in message_text and '@' in message_text:
            await self.handle_setup(update, message_text)
            return
        
        # Check if user is verified
        user = self.db.get_user(telegram_id)
        if not user or not user[8]:  # not verified
            await update.message.reply_text("❌ Please complete email setup and verification first.")
            return
        
        # Handle email reply
        await update.message.reply_text(
            "📧 Email reply feature coming soon!\n"
            "For now, you can reply directly to emails in your email client."
        )
    
    async def monitor_user_emails(self, telegram_id: int):
        """Monitor emails for a specific user"""
        try:
            while True:
                try:
                    user = self.db.get_user(telegram_id)
                    if not user or not user[8]:  # not verified
                        break
                    
                    # Check for new emails
                    summaries = self.email_service.check_new_emails(user)
                    
                    # Send summaries via Telegram
                    bot = Bot(Config.TELEGRAM_BOT_TOKEN)
                    for summary_data in summaries:
                        message = f"📧 **{summary_data['sender'][:50]}**\n\n{summary_data['summary']}"
                        
                        try:
                            await bot.send_message(
                                chat_id=telegram_id, 
                                text=message, 
                                parse_mode='Markdown'
                            )
                        except Exception as send_error:
                            logging.error(f"Error sending message to {telegram_id}: {send_error}")
                    
                    # Wait before checking again
                    await asyncio.sleep(60)  # Check every minute
                    
                except asyncio.CancelledError:
                    logging.info(f"Email monitoring cancelled for user {telegram_id}")
                    break
                except Exception as e:
                    logging.error(f"Email monitoring error for user {telegram_id}: {e}")
                    await asyncio.sleep(300)  # Wait 5 minutes on error
        
        finally:
            # Clean up the task reference
            if telegram_id in self.monitoring_tasks:
                del self.monitoring_tasks[telegram_id]
    
    async def start_user_monitoring(self, telegram_id: int):
        """Start monitoring emails for a specific user"""
        if telegram_id not in self.monitoring_tasks:
            task = asyncio.create_task(self.monitor_user_emails(telegram_id))
            self.monitoring_tasks[telegram_id] = task
    
    async def start_monitoring_all_users(self):
        """Start monitoring emails for all verified users"""
        verified_users = self.db.get_all_verified_users()
        
        for user in verified_users:
            telegram_id = user[0]
            await self.start_user_monitoring(telegram_id)
    
    def run(self):
        """Start the bot"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        print("🤖 Email Summary Bot starting...")
        print("📧 Configure your LLM API settings in the Config class")
        print("🔧 Set your Telegram bot token")
        
        # Use the existing event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Start monitoring existing users
            loop.run_until_complete(self.start_monitoring_all_users())
            
            # Start the bot
            self.app.run_polling()
        finally:
            # Clean up
            for task in self.monitoring_tasks.values():
                task.cancel()
            loop.close()

# ==================== MAIN EXECUTION ====================
def main():
    """Main function to run the bot"""
    
    # Configuration check
    if Config.TELEGRAM_BOT_TOKEN == "your-telegram-bot-token-here":
        print("❌ Please configure your Telegram bot token in Config class")
        return
    
    if Config.LLM_API_KEY == "your-openai-api-key-here":
        print("⚠️  Please configure your LLM API key in Config class")
        print("The bot will run but email summarization won't work properly")
    
    # Start the bot
    bot = EmailTelegramBot()
    bot.run()

if __name__ == "__main__":
    main()

# ==================== INSTALLATION REQUIREMENTS ====================
"""
Required packages (install with pip):

pip install python-telegram-bot requests

For development/testing:
pip install pytest python-dotenv

Setup Instructions:

1. Create a Telegram bot:
   - Message @BotFather on Telegram
   - Use /newbot command
   - Get your bot token

2. Configure LLM API:
   - Sign up for OpenAI API
   - Get your API key from https://platform.openai.com/api-keys
   - Replace Config.LLM_API_KEY with your actual key

3. Email Setup:
   - For Gmail: Enable 2FA and create App Password
   - For Outlook: Use regular password or App Password

4. Run the bot:
   python email_telegram_bot.py

5. In Telegram:
   - Start conversation with your bot
   - Use /setup command
   - Follow verification process
   - Enjoy email summaries!

Security Notes:
- Passwords are stored in local SQLite database
- Consider encrypting stored passwords for production
- Use environment variables for sensitive config
- Implement rate limiting for production use
"""