# ==================== FILE: telegram_handlers.py ====================
"""
Telegram bot command handlers
"""
import re
import logging
from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional
from tools.database_manager import DatabaseManager 
from tools.models import User, EmailConfig
from tools.prompts import Prompts
from tools.verification_service import VerificationService

class TelegramHandlers:
    """All Telegram bot command handlers"""
    
    def __init__(self, db_manager, email_service, monitoring_manager):
        self.db: DatabaseManager = db_manager
        # self.db = db_manager
        self.email_service = email_service
        self.monitoring = monitoring_manager
        self.verification = VerificationService(db_manager)
        self.logger = logging.getLogger(__name__)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(Prompts.WELCOME_MESSAGE, parse_mode='Markdown')
    
    async def setup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setup command"""
        await update.message.reply_text(Prompts.SETUP_MESSAGE, parse_mode='Markdown')

    
    # async def handle_setup_data(self, update: Update, setup_data: str):
    #     """Process email setup data"""
    #     try:
    #         parts = setup_data.split('|')
    #         if len(parts) != 6:
    #             await update.message.reply_text(
    #                 "❌ Invalid format. Please use: email|password|imap_server|imap_port|smtp_server|smtp_port"
    #             )
    #             return
            
    #         email_addr, password, imap_server, imap_port, smtp_server, smtp_port = parts
    #         telegram_id = update.message.from_user.id
            
    #         # Create user
    #         user = User(
    #             telegram_id=telegram_id,
    #             email=email_addr,
    #             password=password,
    #             imap_server=imap_server,
    #             imap_port=int(imap_port),
    #             smtp_server=smtp_server,
    #             smtp_port=int(smtp_port)
    #         )
            
    #         # Store user data
    #         self.db.add_user(
    #             telegram_id, email_addr, password, 
    #             imap_server, int(imap_port), smtp_server, int(smtp_port)
    #         )
            
    #         # Generate and send verification code
    #         verification_code = self.verification.generate_verification_code()
    #         self.db.store_verification_code(telegram_id, verification_code)
            
    #         # Send verification email
    #         if self.verification.send_verification_email(
    #             email_addr, password, smtp_server, int(smtp_port), verification_code
    #         ):
    #             await update.message.reply_text(
    #                 f"✅ Setup saved! Check your email for verification code.\n"
    #                 f"Use `/verify {verification_code}` to complete setup."
    #             )
    #         else:
    #             await update.message.reply_text(
    #                 "❌ Failed to send verification email. Please check your email settings."
    #             )
                
    #     except Exception as e:
    #         self.logger.error(f"Setup error: {e}")
    #         await update.message.reply_text(
    #             "❌ Setup failed. Please check your email settings and try again."
    #         )
###=========================KAI setup===========================###
    '''async def handle_setup_data(self, update: Update, setup_data: str):
        """Process email setup data using regex for Gmail + app password"""
        try:
            setup_data = setup_data.strip()
            parts = setup_data.split('|')
            print(setup_data)
            print(parts)
            # Regex for Gmail + 4x4 app password
            match = re.match(r'([a-zA-Z0-9._%+-]+@gmail\.com)\s+([a-zA-Z]{4}\s?[a-zA-Z]{4}\s?[a-zA-Z]{4}\s?[a-zA-Z]{4})$', setup_data)
            if match:
                print("ur mom")
                email_addr = match.group(1)
                print(email_addr)
                password = match.group(2).replace(' ', '')  # remove spaces
                print(password)
                imap_server, imap_port = "imap.gmail.com", "993"
                smtp_server, smtp_port = "smtp.gmail.com", "587"
                parts = [email_addr, password, imap_server, imap_port, smtp_server, smtp_port]

            if len(parts) != 6:
                await update.message.reply_text("❌ Invalid format. Use either:\n"
                                                "`email|password|imap|port|smtp|port`\n"
                                                "or simply: `<gmail_username> <password>`")
                return

            email_addr, password, imap_server, imap_port, smtp_server, smtp_port = parts
            telegram_id = update.message.from_user.id

            # Store user data
            self.db.add_user(
                telegram_id, email_addr, password,
                imap_server, int(imap_port), smtp_server, int(smtp_port)
            )

            # Generate and send verification code
            verification_code = self.verification.generate_verification_code()
            self.db.store_verification_code(telegram_id, verification_code)

            # Send verification email
            if self.verification.send_verification_email(email_addr, password, smtp_server, int(smtp_port), verification_code):
                await update.message.reply_text(
                    f"✅ Setup saved! Check your email for verification code.\n"
                    f"Use `/verify code` to complete setup."
                )
            else:
                await update.message.reply_text("❌ Failed to send verification email. Please check your email settings.")

        except Exception as e:
            logging.error(f"Setup error: {e}")
            await update.message.reply_text("❌ Setup failed. Please check your email settings and try again.")
    '''
#=========================Bala setup===========================#
    async def handle_setup_data(self, update: Update, setup_data: str):
        """
        Process email setup data from user.
        Accepts:
        1. email|password|imap|port|smtp|port
        2. Gmail + 16-char app password
        """
        try:
            setup_data = setup_data.strip()
            setup_data = setup_data.strip()
            parts = setup_data.split('|')
            print(setup_data)
            print(parts)
            # Regex for Gmail + 4x4 app password
            match = re.match(r'([a-zA-Z0-9._%+-]+@gmail\.com)\s+([a-zA-Z]{4}\s?[a-zA-Z]{4}\s?[a-zA-Z]{4}\s?[a-zA-Z]{4})$', setup_data)
            if match:
                print("ur mom")
                email_addr = match.group(1)
                print(email_addr)
                password = match.group(2).replace(' ', '')  # remove spaces
                print(password)
                imap_server, imap_port = "imap.gmail.com", "993"
                smtp_server, smtp_port = "smtp.gmail.com", "587"
                parts = [email_addr, password, imap_server, imap_port, smtp_server, smtp_port]

            if len(parts) != 6:
                await update.message.reply_text("❌ Invalid format. Use either:\n"
                                                "`email|password|imap|port|smtp|port`\n"
                                                "or simply: `<gmail_username> <password>`")
                return

            email_addr, password, imap_server, imap_port, smtp_server, smtp_port = parts
            telegram_id = update.message.from_user.id

            # Store user in DB
            self.db.add_user(
                telegram_id=telegram_id,
                email=email_addr,
                password=password,
                email_server=imap_server,
                email_port=imap_port,
                smtp_server=smtp_server,
                smtp_port=smtp_port
            )

            # Generate verification code
            verification_code = self.verification.generate_verification_code()
            self.db.store_verification_code(telegram_id, verification_code)

            # Send verification email
            sent = self.verification.send_verification_email(
                email_addr, password, smtp_server, smtp_port, verification_code
            )

            if sent:
                await update.message.reply_text(
                    f"✅ Setup saved! Check your email for verification code.\n"
                    "Use `/verify code` to complete setup."
                )
            else:
                await update.message.reply_text(
                    "❌ Failed to send verification email. Please check your email settings."
            )

        except Exception as e:
            self.logger.error(f"Setup error: {e}")
            await update.message.reply_text(
            "❌ Setup failed. Please check your email settings and try again."
            )

    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command"""
        if not context.args:
            await update.message.reply_text("Please provide verification code: `/verify YOUR_CODE`")
            return
        
        code = context.args[0].upper()
        telegram_id = update.message.from_user.id
        
        if self.verification.verify_code(telegram_id, code):
            await update.message.reply_text("✅ Email verified! You'll now receive email summaries.")
            # Start monitoring emails for this user
            await self.monitoring.start_monitoring(telegram_id)
        else:
            await update.message.reply_text("❌ Invalid or expired verification code.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        telegram_id = update.message.from_user.id
        user_data = self.db.get_user(telegram_id)
        
        if not user_data:
            await update.message.reply_text("❌ No email configured. Use `/setup` first.")
            return
        
        user = User.from_db_row(user_data)
        status = "✅ Verified" if user.is_verified else "⏳ Pending verification"
        monitoring_status = "🟢 Active" if self.monitoring.is_monitoring(telegram_id) else "🔴 Stopped"
        
        await update.message.reply_text(
            f"📧 Email: {user.email}\n"
            f"🔒 Status: {status}\n"
            f"📊 Monitoring: {monitoring_status}"
        )
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        telegram_id = update.message.from_user.id
        
        if self.monitoring.stop_monitoring(telegram_id):
            await update.message.reply_text("⏹️ Email monitoring stopped.")
        else:
            await update.message.reply_text("❌ No active monitoring found.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        message_text = update.message.text
        telegram_id = update.message.from_user.id
        
        # Check if it's setup data
        if '|' in message_text or '@' in message_text:
            await self.handle_setup_data(update, message_text)
            return
        
        # Check if user is verified
        user_data = self.db.get_user(telegram_id)
        if not user_data or not user_data[8]:  # not verified
            await update.message.reply_text(
                "❌ Please complete email setup and verification first."
            )
            return
            
        # Handle email reply (placeholder for now)
        await update.message.reply_text(
            "📧 Email reply feature coming soon!\n"
            "For now, you can reply directly to emails in your email client."
        )


    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            chat_id = update.effective_chat.id
            # Number of messages to delete (including the /clear command)
            num_messages = 20

            # Fetch recent messages
            for i in range(num_messages):
                try:
                    await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id - i
            )
                except Exception as e:
                    pass # Skip if the message cannot be deleted


